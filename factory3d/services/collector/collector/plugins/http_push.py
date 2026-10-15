"""Плагін `http_push` (SPEC §8.7, R-22): реєструє маршрути джерела в HttpPushServer; сигнали обробляє Odoo."""

from __future__ import annotations

from typing import ClassVar

from collector.core.errors import ConnectError
from collector.core.http_push import DEFAULT_MAX_BODY, HttpPushServer, RouteCfg
from collector.core.types import Health, SourceCfg
from collector.plugins._common import load_schema, validate_source
from collector.plugins.base import PluginContext, SourcePlugin


class HttpPushPlugin(SourcePlugin):
    type: ClassVar[str] = "http_push"
    push_mode: ClassVar[bool] = True
    address_schema: ClassVar[dict] = load_schema("address.http_push")
    params_schema: ClassVar[dict] = load_schema("params.http_push")

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        super().__init__(source, ctx)
        self.server: HttpPushServer | None = None
        self._routes: list[RouteCfg] = []

    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        return validate_source(source, cls.address_schema, cls.params_schema, cls._check_address)

    @staticmethod
    def _check_address(a: dict, params: dict) -> list[str]:
        routes = params.get("routes")
        if isinstance(routes, list) and a.get("route") not in routes:
            return [f"route: «{a.get('route')}» відсутній у params.routes"]
        return []

    async def connect(self) -> None:
        self.server = HttpPushServer.current()
        if self.server is None:
            raise ConnectError("http_push server is not running")

    async def subscribe(self) -> None:
        if self.server is None:
            await self.connect()
        assert self.server is not None
        p = self.source.params
        secret = self._secret(p.get("secret_ref"))
        token = self._secret(p.get("token_ref"))
        for route in p.get("routes", []):
            ts_paths = [
                s.address["ts_path"]
                for s in self.source.signals
                if s.address and s.address.get("route") == route and s.address.get("ts_path")
            ]
            cfg = RouteCfg(
                route=route,
                source=self.source.code,
                emit_event=self.ctx.emit_event,
                secret=secret,
                token=token,
                max_bytes=int(p.get("max_body_kb", 1024)) * 1024 or DEFAULT_MAX_BODY,
                ts_paths=ts_paths,
            )
            try:
                await self.server.register(cfg, list(p.get("allow_ips", [])))
            except ValueError as e:
                raise ConnectError(str(e)) from e
            self._routes.append(cfg)

    def _secret(self, ref: str | None) -> str | None:
        if not ref:
            return None
        try:
            return self.ctx.secrets(ref)
        except KeyError:
            raise ConnectError(f"secret {ref} is not set") from None

    async def disconnect(self) -> None:
        if self.server is not None:
            self.server.unregister(self.source.code)
        self._routes = []
        self.server = None

    def health(self) -> Health:
        stats = {"requests": 0, "rejected_ip": 0, "rejected_auth": 0, "events": 0}
        for r in self._routes:
            for k in stats:
                stats[k] += r.stats[k]
        if self.server is None or HttpPushServer.current() is not self.server:
            return Health(state="error", error="http_push server is not running", stats=stats)
        return Health(state="online", stats=stats)
