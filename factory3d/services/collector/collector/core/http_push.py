"""Приймач http_push: один aiohttp-застосунок на процес (SPEC §8.7, R-22)."""
from __future__ import annotations

import asyncio
import contextlib
import email
import email.policy
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from aiohttp import web

from collector.core.types import PushEvent
from collector.plugins._common import canonical_json, parse_ts
from collector.util import jsonpath
from collector.util.timeutil import Clock, SystemClock

log = logging.getLogger("collector.http_push")

DEFAULT_MAX_BODY = 1024 * 1024
_KEEP_HEADERS = ("user-agent", "content-type")
_Net = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass
class RouteCfg:
    """Маршрут одного джерела http_push."""

    route: str
    source: str
    emit_event: Callable[[PushEvent], None]
    nets: list[_Net] = field(default_factory=list)  # порожньо = будь-який IP
    secret: str | None = None
    token: str | None = None
    max_bytes: int = DEFAULT_MAX_BODY
    ts_paths: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=lambda: {"requests": 0, "rejected_ip": 0, "rejected_auth": 0,
                                                            "events": 0})


async def resolve_allow(entries: list[str]) -> list[_Net]:
    """Хости/IP/CIDR -> мережі (імена резолвляться; нерозв'язні — WARNING і пропуск)."""
    nets: list[_Net] = []
    loop = asyncio.get_running_loop()
    for e in entries:
        try:
            nets.append(ipaddress.ip_network(e, strict=False))
            continue
        except ValueError:
            pass
        try:
            infos = await loop.getaddrinfo(e, None, type=socket.SOCK_STREAM)
        except OSError:
            log.warning("http_push allow_ips: cannot resolve %s", e)
            continue
        for info in infos:
            nets.append(ipaddress.ip_network(info[4][0], strict=False))
    return nets


class HttpPushServer:
    _instance: ClassVar[HttpPushServer | None] = None

    def __init__(self, settings: Any = None, clock: Clock | None = None, buffer: Any = None, registry: Any = None,
                 metrics: Any = None, allowlist: Any = None, emitter: Any = None) -> None:
        self.settings = settings
        self.clock: Clock = clock or SystemClock()
        self.buffer = buffer
        self.registry = registry
        self.metrics = metrics
        self.allowlist = allowlist
        self.emitter = emitter
        self.routes: dict[str, RouteCfg] = {}
        self.env_nets: list[_Net] = []
        self.port: int = getattr(settings, "http_push_port", 8080)
        self.app = web.Application()
        self.app.router.add_get("/f3d/health", self._health)
        self.app.router.add_post("/f3d/{route}", self._handle)
        self.app.router.add_post("/f3d/{route}/{secret}", self._handle)
        self._runner: web.AppRunner | None = None
        HttpPushServer._instance = self

    # --- процесний синглтон (плагін знаходить сервер, який створив app.py) ---
    @classmethod
    def current(cls) -> HttpPushServer | None:
        return cls._instance

    def reset_instance(self) -> None:
        if HttpPushServer._instance is self:
            HttpPushServer._instance = None

    # --- реєстрація маршрутів ---
    async def register(self, cfg: RouteCfg, allow_ips: list[str]) -> None:
        if cfg.route in self.routes:
            raise ValueError(f"route {cfg.route} already registered by {self.routes[cfg.route].source}")
        if not self.env_nets:
            env = list(getattr(self.settings, "http_push_allow_ips", []) or [])
            self.env_nets = await resolve_allow(env)
        src_nets = await resolve_allow(allow_ips)
        cfg.nets = [*src_nets, *self.env_nets] if (src_nets or self.env_nets) else []
        self.routes[cfg.route] = cfg

    def unregister(self, source: str) -> None:
        for r in [r for r, c in self.routes.items() if c.source == source]:
            del self.routes[r]

    # --- життєвий цикл ---
    async def start(self) -> None:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        sockets = getattr(site._server, "sockets", None) or []
        if sockets:
            self.port = int(sockets[0].getsockname()[1])
        log.info("http_push listening on :%s", self.port)

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        self.reset_instance()

    # --- обробка ---
    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "routes": sorted(self.routes)})

    def _done(self, route: str, status: int, resp: web.Response) -> web.Response:
        if self.metrics is not None:
            self.metrics.http_push_requests.labels(route, str(status)).inc()
        return resp

    @staticmethod
    def _fail(status: int, text: str) -> web.Response:
        return web.json_response({"received": False, "error": text}, status=status)

    @staticmethod
    def _ip_ok(remote: str | None, nets: list[_Net]) -> bool:
        if not nets:
            return True
        try:
            ip = ipaddress.ip_address(remote or "")
        except ValueError:
            return False
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return any(ip in n for n in nets)

    @staticmethod
    def _token_ok(request: web.Request, token: str) -> bool:
        given = request.headers.get("X-F3D-Token", "")
        auth = request.headers.get("Authorization", "")
        if not given and auth.lower().startswith("bearer "):
            given = auth[7:].strip()
        return bool(given) and hmac.compare_digest(given.encode(), token.encode())

    async def _read_body(self, request: web.Request, limit: int) -> bytes | None:
        body = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            body += chunk
            if len(body) > limit:
                return None
        return bytes(body)

    @staticmethod
    def _json_from_multipart(content_type: str, body: bytes) -> Any:
        msg = email.message_from_bytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body,
                                       policy=email.policy.HTTP)
        for part in msg.iter_parts():
            if part.get_content_type() == "application/json":
                raw = part.get_payload(decode=True)
                return json.loads(raw.decode("utf-8")) if isinstance(raw, bytes) else None
        raise ValueError("no application/json part")

    async def _handle(self, request: web.Request) -> web.Response:
        route = request.match_info["route"]
        cfg = self.routes.get(route)
        if cfg is None:
            return self._done("unknown", 404, self._fail(404, "unknown route"))
        cfg.stats["requests"] += 1
        status, resp = await self._process(request, cfg)
        return self._done(route, status, resp)

    async def _process(self, request: web.Request, cfg: RouteCfg) -> tuple[int, web.Response]:
        if request.content_length is not None and request.content_length > cfg.max_bytes:
            return 413, self._fail(413, "body too large")
        if not self._ip_ok(request.remote, cfg.nets):
            cfg.stats["rejected_ip"] += 1
            return 403, self._fail(403, "forbidden")
        secret = request.match_info.get("secret")
        if (cfg.secret is not None) != (secret is not None) or (
                cfg.secret is not None and not hmac.compare_digest(str(secret).encode(), cfg.secret.encode())):
            cfg.stats["rejected_auth"] += 1
            return 404, self._fail(404, "unknown route")
        if cfg.token is not None and not self._token_ok(request, cfg.token):
            cfg.stats["rejected_auth"] += 1
            return 401, self._fail(401, "unauthorized")
        ctype = request.content_type
        if ctype not in ("application/json", "multipart/form-data"):
            return 415, self._fail(415, "unsupported media type")
        body = await self._read_body(request, cfg.max_bytes)
        if body is None:
            return 413, self._fail(413, "body too large")
        try:
            if ctype == "application/json":
                payload = json.loads(body.decode("utf-8"))
            else:
                payload = self._json_from_multipart(request.headers.get("Content-Type", ctype), body)
        except (ValueError, UnicodeDecodeError):
            return 400, self._fail(400, "invalid json")
        if not isinstance(payload, dict):
            return 400, self._fail(400, "json object expected")
        remote = request.remote or ""
        event_id = hashlib.sha256(f"{cfg.route}\n{remote}\n{canonical_json(payload)}".encode()).hexdigest()
        headers = {k: request.headers[k] for k in _KEEP_HEADERS if k in request.headers}
        event = PushEvent(event_id=event_id, route=cfg.route, ts=self._event_ts(cfg, payload), remote=remote,
                          headers=headers, payload=payload)
        cfg.stats["events"] += 1
        try:
            cfg.emit_event(event)
        except Exception:
            log.exception("emit_event failed for route %s", cfg.route)
        return 200, web.json_response({"received": True})

    def _event_ts(self, cfg: RouteCfg, payload: dict) -> Any:
        for path in cfg.ts_paths:
            raw = jsonpath.get(path, payload, None)
            if raw is None:
                continue
            with contextlib.suppress(ValueError, OverflowError, OSError):
                return parse_ts(raw)
        return self.clock.now()
