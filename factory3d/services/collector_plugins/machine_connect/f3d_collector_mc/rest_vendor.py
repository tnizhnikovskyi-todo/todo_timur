"""Плагін `rest_vendor` (§8.4, R-23, R-24): REST-пристрої за адаптером `params.vendor`."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

import aiohttp
from collector.core.errors import ConnectError, NotSupported, PollError, WriteError
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins._common import validate_source
from collector.plugins.base import PluginContext, SourcePlugin
from collector.util.jsonpath import parse as parse_jsonpath
from collector.util.timeutil import SystemClock

from . import cmdtext
from .events import inc_metric, make_event

VENDOR_GROUP = "factory3d_collector.rest_vendors"
MAX_RESULT_BYTES = 64 * 1024
MAX_RESULT_TEXT = 256

_SCHEMA_DIR = Path(__file__).parent / "schemas"


def _ext(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / f"{name}.ext.json").read_text(encoding="utf-8"))


_BASE_ADDRESS = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["path"],
    "properties": {
        "method": {"enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
        "path": {"type": "string", "pattern": "^/", "maxLength": 512},
        "query": {"type": "object"},
        "json_path": {"type": "string", "pattern": r"^\$"},
        "map": {"type": "object", "additionalProperties": {"type": "string", "maxLength": 64}},
    },
}
_BASE_PARAMS = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["base_url"],
    "properties": {
        "base_url": {"type": "string", "pattern": "^https?://"},
        "auth": {"enum": ["none", "api_key", "bearer", "basic"]},
        "header": {"type": "string"},
        "key_ref": {"type": "string"},
        "user": {"type": "string"},
        "password_ref": {"type": "string"},
        "verify_tls": {"type": "boolean"},
        "timeout_s": {"type": "number", "minimum": 1, "maximum": 60},
    },
}


class NetError(Exception):
    """Мережева помилка або таймаут HTTP-запиту (адаптер перетворює на PollError/WriteError)."""


@dataclass
class Resp:
    status: int
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8")) if self.body else None


def _load_adapter(name: str) -> type:
    for ep in entry_points(group=VENDOR_GROUP):
        if ep.name == name:
            return ep.load()  # type: ignore[no-any-return]
    # запасний шлях, якщо пакет запущено без встановлення (entry points недоступні)
    from .cutopt import CutOptAdapter
    from .generic import GenericAdapter
    from .woodstore import WoodStoreAdapter

    builtin = {"generic": GenericAdapter, "woodstore": WoodStoreAdapter, "cutopt": CutOptAdapter}
    if name not in builtin:
        raise ConnectError(f"unknown rest vendor {name}")
    return builtin[name]


class RestVendorPlugin(SourcePlugin):
    type = "rest_vendor"
    version = "0.1.0"
    push_mode = False
    address_schema: ClassVar[dict] = {"allOf": [_BASE_ADDRESS, _ext("address.rest_vendor")]}
    params_schema: ClassVar[dict] = {"allOf": [_BASE_PARAMS, _ext("params.rest_vendor")]}

    def __init__(self, source: SourceCfg, ctx: PluginContext, clock: Any = None) -> None:
        super().__init__(source, ctx)
        self.clock = clock or getattr(ctx, "clock", None) or SystemClock()
        p = source.params
        self.base_url: str = p.get("base_url", "")
        self.vendor: str = p.get("vendor", "generic")
        self.timeout_s: float = float(p.get("timeout_s", 5))
        self.http: aiohttp.ClientSession | None = None
        self.adapter: Any = None
        self._auth_failed = False
        self._last_error: str | None = None
        self._last_ok: datetime | None = None
        self.stats = {"requests": 0, "errors": 0}

    # --- валідація ---
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        return validate_source(source, cls.address_schema, cls.params_schema, cls._check_address, cls._check_params)

    @staticmethod
    def _check_address(addr: dict, params: dict) -> list[str]:
        errs: list[str] = []
        if "json_path" in addr:
            try:
                parse_jsonpath(addr["json_path"])
            except ValueError as exc:
                errs.append(f"json_path: {exc}")
        return errs

    @staticmethod
    def _check_params(params: dict) -> list[str]:
        errs: list[str] = []
        if params.get("verify_tls") is False and str(params.get("base_url", "")).startswith("https://"):
            errs.append("verify_tls: false не дозволено для https://")
        if params.get("auth", "none") != "none" and not params.get("key_ref") and not params.get("password_ref"):
            errs.append("auth: потрібен key_ref або password_ref")
        return errs

    # --- з'єднання ---
    def _session_factory(self) -> aiohttp.ClientSession:
        """HTTP-сесія адаптерів (§13.0.2: підмінюється в тестах)."""
        p = self.source.params
        auth = p.get("auth", "none")
        headers: dict[str, str] = {}
        basic = None
        if auth == "api_key":
            headers[p.get("header") or "X-Api-Key"] = self._secret(p.get("key_ref"))
        elif auth == "bearer":
            headers["Authorization"] = f"Bearer {self._secret(p.get('key_ref'))}"
        elif auth == "basic":
            basic = aiohttp.BasicAuth(p.get("user", ""), self._secret(p.get("password_ref")))
        return aiohttp.ClientSession(
            base_url=self.base_url,
            timeout=aiohttp.ClientTimeout(total=self.timeout_s),
            headers=headers,
            auth=basic,
        )

    def _secret(self, name: str | None) -> str:
        if not name:
            raise ConnectError("secret reference is not set")
        try:
            return self.ctx.secrets(name)
        except KeyError:
            raise ConnectError(f"secret {name} not set") from None

    async def connect(self) -> None:
        p = self.source.params
        self.ctx.allowlist(urlparse(self.base_url).hostname or "")
        if p.get("verify_tls") is False and self.base_url.startswith("https://"):
            raise ConnectError("verify_tls false is not allowed for https")
        adapter_cls = _load_adapter(self.vendor)
        if self.http is None or self.http.closed:
            self.http = self._session_factory()
        self.adapter = adapter_cls(self)
        await self.adapter.start()

    async def disconnect(self) -> None:
        adapter, self.adapter = self.adapter, None
        if adapter is not None:
            await adapter.stop()
        http, self.http = self.http, None
        if http is not None:
            await http.close()

    # --- HTTP ---
    @staticmethod
    def _path_label(path: str) -> str:
        return re.sub(r"/(jobs|stacks)/[^/?]+", r"/\1/{id}", path)

    async def request(
        self, method: str, path: str, *, params: dict | None = None, json_body: Any = None, data: Any = None
    ) -> Resp:
        if self.http is None:
            raise NetError("not connected")
        try:
            async with self.http.request(method, path, params=params, json=json_body, data=data) as r:
                resp = Resp(r.status, await r.read())
        except (aiohttp.ClientError, TimeoutError, OSError) as exc:
            self.stats["errors"] += 1
            self._last_error = f"{type(exc).__name__}: {exc}"
            raise NetError(f"{method} {path}: {type(exc).__name__}: {exc}") from exc
        self.stats["requests"] += 1
        inc_metric(
            self.ctx,
            "collector_mc_rest_requests_total",
            source=self.source.code,
            path=self._path_label(path),
            code=str(resp.status),
        )
        if resp.status in (401, 403):
            self._auth_failed = True
            self._last_error = "auth"
        elif resp.status < 400:
            self._auth_failed = False
            self._last_error = None
            self._last_ok = self.clock.now()
        if 400 <= resp.status < 500:
            self.ctx.log.warning("rest %s: %s %s -> %s", self.source.code, method, path, resp.status)
        return resp

    def emit_event(self, route: str, payload: dict) -> None:
        size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if size > 256 * 1024:
            raise WriteError(f"event too large: {size} bytes")
        self.ctx.emit_event(make_event(route, self.source.code, payload, ts=self.clock.now()))

    # --- опитування ---
    async def poll(self, signals: Any) -> list[Reading]:
        if self.adapter is None:
            raise PollError("not connected")
        sigs = [s for s in signals if (s.address.get("io") or "read") != "write" and not s.address.get("cmd")]
        return await self.adapter.poll(sigs)  # type: ignore[no-any-return]

    # --- команди (R-21) ---
    def _cmd_kind(self, signal: SignalCfg) -> str:
        kind = (signal.address or {}).get("cmd")
        if not kind or self.vendor == "generic" or self.adapter is None:
            raise NotSupported("call")
        return str(kind)

    async def call(self, signal: SignalCfg, payload: dict) -> dict:
        kind = self._cmd_kind(signal)
        try:
            checked = cmdtext.check_payload(kind, payload)
        except ValueError as exc:
            self._count(kind, payload.get("op") if isinstance(payload, dict) else None, "rejected")
            raise WriteError(f"bad_command: {exc}") from exc
        return await self._run(signal, kind, checked)

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        kind = self._cmd_kind(signal)
        try:
            checked = cmdtext.parse_cmd(kind, text or "")
        except ValueError as exc:
            self._count(kind, None, "rejected")
            raise WriteError(f"bad_command: {exc}") from exc
        data = await self._run(signal, kind, checked)
        return cmdtext.result_text(kind, checked, data)[:MAX_RESULT_TEXT]

    async def _run(self, signal: SignalCfg, kind: str, checked: dict) -> dict:
        try:
            data = await self.adapter.command(signal, checked)
        except WriteError:
            self._count(kind, checked.get("op"), "error")
            raise
        except NetError as exc:
            self._count(kind, checked.get("op"), "error")
            raise WriteError(f"network error: {exc}") from exc
        if len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > MAX_RESULT_BYTES:
            raise WriteError("result too large")
        self._count(kind, checked.get("op"), "ok")
        self.ctx.log.info("rest %s: command %s %s ok", self.source.code, kind, checked.get("op"))
        return data  # type: ignore[no-any-return]

    def _count(self, kind: str, op: Any, result: str) -> None:
        inc_metric(self.ctx, "collector_mc_commands_total", source=self.source.code, cmd=f"{kind}.{op}", result=result)

    def health(self) -> Health:
        stats = dict(self.stats)
        if self._auth_failed:
            return Health(state="error", error="auth", last_ok=self._last_ok, stats=stats)
        if self.http is None:
            return Health(state="offline", stats=stats)
        if self._last_error:
            return Health(state="error", error=self._last_error, last_ok=self._last_ok, stats=stats)
        return Health(state="online", last_ok=self._last_ok, stats=stats)


async def gather_quiet(tasks: list[asyncio.Task]) -> None:
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
