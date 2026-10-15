"""Клієнт Odoo (API-01…API-07), Pusher і StatusReporter (SPEC §8.3.5, §8.4)."""

from __future__ import annotations

import logging
import ssl
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import aiohttp

from collector import __version__
from collector.core.buffer import Buffer
from collector.core.types import Command, CommandResult, PushEvent, Reading
from collector.util.timeutil import Clock, SystemClock, parse_iso, to_iso_z

log = logging.getLogger("collector.odoo")

RETRY_STATUSES = frozenset({502, 503, 504})
RETRY_DELAYS = (1.0, 2.0)  # між 3 спробами
EVENT_BATCH = 100
RESULT_BATCH = 100


class OdooError(Exception):
    """Помилка виклику Odoo; `status=None` — мережева помилка/таймаут."""

    def __init__(self, status: int | None, message: str = "", retry_after: float | None = None) -> None:
        super().__init__(f"odoo HTTP {status}: {message}" if status else f"odoo unreachable: {message}")
        self.status = status
        self.retry_after = retry_after


class OdooClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        session: aiohttp.ClientSession | None = None,
        *,
        collector: str = "",
        clock: Clock | None = None,
        metrics: Any = None,
        skew_warn_s: float = 30,
        ca: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.collector = collector
        self.clock: Clock = clock or SystemClock()
        self.metrics = metrics
        self.skew_warn_s = skew_warn_s
        self.ca = ca
        self._session = session
        self._own_session = session is None
        self._seq = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            connector = None
            if self.ca:
                connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=self.ca))
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), connector=connector)
        return self._session

    async def close(self) -> None:
        if self._session is not None and self._own_session:
            await self._session.close()
        self._session = None

    def _check_skew(self, data: Any) -> None:
        if not isinstance(data, dict) or not data.get("server_time"):
            return
        try:
            skew = abs((parse_iso(str(data["server_time"])) - self.clock.now()).total_seconds())
        except ValueError:
            return
        if self.metrics is not None:
            self.metrics.clock_skew.set(skew)
        if skew > self.skew_warn_s:
            log.warning("clock skew with Odoo is %.0f s (limit %s s)", skew, self.skew_warn_s)

    async def request(
        self, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None
    ) -> tuple[int, Any]:
        """Запит з ретраями (мережа, 502/503/504: 3 спроби, пауза 1/2 с). Статус >= 400 -> OdooError."""
        session = await self._get_session()
        hdrs = {"Authorization": f"Bearer {self.token}", **(headers or {})}
        url = f"{self.base_url}{path}"
        last: OdooError | None = None
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                async with session.request(method, url, json=body, headers=hdrs) as resp:
                    status = resp.status
                    if status == 304:
                        self._ok()
                        return 304, None
                    try:
                        data = await resp.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError):
                        data = None
                    if status >= 400:
                        ra = resp.headers.get("Retry-After")
                        last = OdooError(status, _err_text(data), float(ra) if ra and ra.isdigit() else None)
                    else:
                        self._ok()
                        self._check_skew(data)
                        return status, data
            except (aiohttp.ClientError, TimeoutError) as exc:
                last = OdooError(None, type(exc).__name__)
            assert last is not None
            if last.status is not None and last.status not in RETRY_STATUSES:
                if last.status >= 500 and self.metrics is not None:
                    self.metrics.odoo_failed()
                raise last
            if attempt < len(RETRY_DELAYS):
                await self.clock.sleep(RETRY_DELAYS[attempt])
        assert last is not None
        if self.metrics is not None:
            self.metrics.odoo_failed()
        raise last

    def _ok(self) -> None:
        if self.metrics is not None:
            self.metrics.odoo_ok()

    # --- API ---
    async def health(self) -> dict:
        _, data = await self.request("GET", "/f3d/telemetry/health")
        return data if isinstance(data, dict) else {}

    async def config(self, etag: str | None = None) -> dict | None:
        """API-01: None при 304."""
        headers = {"If-None-Match": f'"{etag}"'} if etag else None
        status, data = await self.request("GET", "/f3d/telemetry/config", headers=headers)
        if status == 304:
            return None
        if not isinstance(data, dict):
            raise OdooError(status, "config is not an object")
        return data

    async def push(self, readings: Iterable[Reading]) -> dict:
        """API-02."""
        self._seq += 1
        items = []
        for r in readings:
            item: dict[str, Any] = {"code": r.code, "ts": to_iso_z(r.ts), "q": r.q}
            if r.text is not None:
                item["text"] = r.text
            if r.value is not None or r.text is None:
                item["value"] = r.value
            items.append(item)
        body = {"collector": self.collector, "seq": self._seq, "sent_at": to_iso_z(self.clock.now()), "readings": items}
        _, data = await self.request("POST", "/f3d/telemetry/push", body)
        return data if isinstance(data, dict) else {}

    async def status(self, payload: dict) -> dict:
        """API-03."""
        _, data = await self.request("POST", "/f3d/telemetry/status", payload)
        return data if isinstance(data, dict) else {}

    async def event(self, events: Iterable[PushEvent]) -> dict:
        """API-05."""
        items = [
            {
                "event_id": e.event_id,
                "route": e.route,
                "ts": to_iso_z(e.ts),
                "remote": e.remote,
                "headers": e.headers,
                "payload": e.payload,
            }
            for e in events
        ]
        _, data = await self.request("POST", "/f3d/telemetry/event", {"collector": self.collector, "events": items})
        return data if isinstance(data, dict) else {}

    async def commands(self, limit: int = 50) -> tuple[list[Command], bool]:
        """API-06 -> (команди, write_enabled)."""
        _, data = await self.request("GET", f"/f3d/telemetry/commands?limit={limit}")
        data = data if isinstance(data, dict) else {}
        out = []
        for c in data.get("commands") or []:
            out.append(
                Command(
                    id=int(c["id"]),
                    code=c["code"],
                    source=c.get("source", ""),
                    value=c.get("value"),
                    text=c.get("text"),
                    address=c.get("address") or {},
                    expires_at=parse_iso(c["expires_at"]),
                    payload=c.get("payload"),
                )
            )
        return out, bool(data.get("write_enabled", False))

    async def commands_result(self, results: Iterable[CommandResult]) -> dict:
        """API-07."""
        items = [
            {"id": r.id, "state": r.state, "ts": to_iso_z(r.ts), "result": r.result, "error": r.error, "data": r.data}
            for r in results
        ]
        _, data = await self.request(
            "POST", "/f3d/telemetry/commands/result", {"collector": self.collector, "results": items}
        )
        return data if isinstance(data, dict) else {}


def _err_text(data: Any) -> str:
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            return str(err.get("code") or err.get("message") or "")
        return str(err or "")
    return ""


async def flush_results(client: OdooClient, buffer: Buffer) -> int:
    """Відправляє накопичені результати команд (API-07); при помилці — лишає в буфері."""
    rows = await buffer.take_results(RESULT_BATCH)
    if not rows:
        return 0
    try:
        await client.commands_result([r for _, r in rows])
    except OdooError as exc:
        if exc.status in (400, 413):
            log.error("results rejected by Odoo (%s), dropped", exc.status)
            await buffer.ack_results([i for i, _ in rows])
        else:
            log.warning("results not delivered, kept in buffer: %s", exc)
        return 0
    await buffer.ack_results([i for i, _ in rows])
    return len(rows)


async def flush_events(client: OdooClient, buffer: Buffer) -> int:
    rows = await buffer.take_events(EVENT_BATCH)
    if not rows:
        return 0
    try:
        await client.event([e for _, e in rows])
    except OdooError as exc:
        if exc.status in (400, 413):
            log.error("events rejected by Odoo (%s), dropped", exc.status)
            await buffer.ack_events([i for i, _ in rows])
        else:
            log.warning("events not delivered, kept in buffer: %s", exc)
        return 0
    await buffer.ack_events([i for i, _ in rows])
    return len(rows)


class Pusher:
    """Буфер -> API-02 (R-19, §8.4). `push_once()` повертає: ok|empty|wait|retry|locked|rejected."""

    def __init__(
        self,
        client: OdooClient,
        buffer: Buffer,
        *,
        push_max: int = 1000,
        push_interval_s: float = 5,
        registry: Any = None,
        metrics: Any = None,
        clock: Clock | None = None,
        on_read_enabled: Callable[[bool], Awaitable[None]] | None = None,
    ) -> None:
        self.client = client
        self.buffer = buffer
        self.push_max = push_max
        self.push_interval_s = push_interval_s
        self.registry = registry
        self.metrics = metrics
        self.clock: Clock = clock or SystemClock()
        self.on_read_enabled = on_read_enabled
        self.read_enabled = True
        self.retry_at = 0.0  # monotonic: не раніше цього моменту
        self._fails = 0

    def _count(self, status: str) -> None:
        if self.metrics is not None:
            self.metrics.push.labels(status).inc()

    async def _set_read_enabled(self, value: bool) -> None:
        if value != self.read_enabled:
            self.read_enabled = value
            if self.on_read_enabled is not None:
                await self.on_read_enabled(value)

    async def push_once(self) -> str:
        now = self.clock.monotonic()
        if now < self.retry_at:
            return "wait"
        rows = await self.buffer.take(self.push_max)
        if not rows:
            await flush_events(self.client, self.buffer)
            await flush_results(self.client, self.buffer)
            return "empty"
        t0 = self.clock.monotonic()
        try:
            resp = await self.client.push([r for _, r in rows])
        except OdooError as exc:
            return await self._on_error(exc, [i for i, _ in rows])
        if self.metrics is not None:
            self.metrics.push_latency.observe(max(0.0, self.clock.monotonic() - t0))
        await self.buffer.ack([i for i, _ in rows])
        self._fails = 0
        self._count("ok")
        await self._after_ok(resp)
        await flush_events(self.client, self.buffer)
        await flush_results(self.client, self.buffer)
        return "ok"

    async def _on_error(self, exc: OdooError, ids: list[int]) -> str:
        st = exc.status
        now = self.clock.monotonic()
        if st == 423:
            self._count("locked")
            self.retry_at = now + self.push_interval_s
            await self._set_read_enabled(False)
            return "locked"
        if st == 429:
            self._count("retry")
            self.retry_at = now + (exc.retry_after or 10.0)
            return "retry"
        if st is not None and 400 <= st < 500 and st not in (401, 403, 408):
            log.error("push rejected by Odoo (HTTP %s): %d readings dropped", st, len(ids))
            await self.buffer.ack(ids)
            if self.metrics is not None:
                self.metrics.push_rejected.inc()
            self._count("rejected")
            return "rejected"
        if st in (401, 403):
            log.error("push refused by Odoo (HTTP %s): check F3D_COLLECTOR_TOKEN; readings kept", st)
        else:
            log.warning("push failed (%s), readings kept in buffer", exc)
        self._fails += 1
        self.retry_at = now + min(60.0, 2.0 ** (self._fails - 1))
        self._count("retry")
        return "retry"

    async def _after_ok(self, resp: dict) -> None:
        rejected = resp.get("rejected") or []
        if rejected:
            by_reason = Counter(str(r.get("reason", "?")) for r in rejected if isinstance(r, dict))
            for reason, n in by_reason.items():
                log.warning("Odoo rejected %d readings: %s", n, reason)
                if self.metrics is not None:
                    self.metrics.readings_rejected.labels(reason).inc(n)
        if "read_enabled" in resp:
            await self._set_read_enabled(bool(resp["read_enabled"]))
        etag = resp.get("config_etag")
        if self.registry is not None and etag and etag != self.registry.etag:
            await self.registry.refresh()

    async def run(self) -> None:
        while True:
            status = await self.push_once()
            if self.metrics is not None:
                self.metrics.buffer_rows.set(await self.buffer.count())
            if status == "ok" and await self.buffer.count() >= self.push_max:
                await self.clock.sleep(1)
            elif status in ("wait", "retry", "locked"):
                await self.clock.sleep(max(self.retry_at - self.clock.monotonic(), 0.5))
            else:
                await self.clock.sleep(self.push_interval_s)


class StatusReporter:
    """Health усіх джерел, буфер і версії -> API-03 кожні `status_interval_s`."""

    def __init__(
        self,
        client: OdooClient,
        registry: Any,
        buffer: Buffer,
        scheduler: Any = None,
        *,
        interval_s: float = 60,
        clock: Clock | None = None,
        metrics: Any = None,
        on_flags: Callable[[bool, bool], Awaitable[None]] | None = None,
    ) -> None:
        self.client = client
        self.registry = registry
        self.buffer = buffer
        self.scheduler = scheduler
        self.interval_s = interval_s
        self.clock: Clock = clock or SystemClock()
        self.metrics = metrics
        self.on_flags = on_flags
        self._started = self.clock.monotonic()

    def source_health(self, code: str) -> Any:
        from collector.core.types import Health

        reg = self.registry
        if code in reg.errors:
            return reg.errors[code]
        plugin = reg.plugins.get(code)
        if plugin is None:
            return Health(state="offline")
        h = plugin.health()
        if not plugin.push_mode and self.scheduler is not None:
            sh = self.scheduler.health(code)
            return Health(state=sh.state, error=sh.error, last_ok=sh.last_ok, stats={**h.stats, **sh.stats})
        return h

    async def build(self) -> dict:
        reg = self.registry
        sources = []
        for code in reg.sources:
            h = self.source_health(code)
            sources.append(
                {
                    "code": code,
                    "state": h.state,
                    "error": (h.error or None) and h.error[:512],
                    "last_ok": to_iso_z(h.last_ok) if h.last_ok else None,
                    "stats": h.stats,
                }
            )
        by_type: dict[str, list] = {}
        for plugin in reg.plugins.values():
            by_type.setdefault(plugin.type, []).append(plugin)
        plugins = [{"type": t, "version": ps[0].version, "sources": len(ps)} for t, ps in by_type.items()]
        return {
            "collector": self.client.collector,
            "version": __version__,
            "uptime_s": int(self.clock.monotonic() - self._started),
            "ts": to_iso_z(self.clock.now()),
            "buffer": {
                "rows": await self.buffer.count(),
                "dropped_total": self.buffer.dropped_total,
                "bytes": await self.buffer.size_bytes(),
            },
            "plugins": plugins,
            "sources": sources,
        }

    async def send_once(self) -> dict | None:
        try:
            resp = await self.client.status(await self.build())
        except OdooError as exc:
            log.warning("status not delivered: %s", exc)
            return None
        if self.on_flags is not None and "read_enabled" in resp:
            await self.on_flags(
                bool(resp["read_enabled"]), bool(resp.get("write_enabled", self.registry.write_enabled))
            )
        etag = resp.get("config_etag")
        if etag and etag != self.registry.etag:
            await self.registry.refresh()
        return resp

    async def run(self) -> None:
        while True:
            await self.send_once()
            await self.clock.sleep(self.interval_s)
