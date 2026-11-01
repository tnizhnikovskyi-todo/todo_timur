"""Клієнт Odoo (API-01…API-07), Pusher і StatusReporter (SPEC §8.3.5, §8.4)."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
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
STALE_AFTER_S = 600.0  # черга старша за це -> «спершу живі дані» (див. Pusher)
BACKLOG_GAP_S = 1.25  # пауза між пакетами при черзі: ≤ 48 пакетів/хв при ліміті Odoo 60/хв (429 + Retry-After 10 с)
POISON_AFTER = 5  # скільки поспіль HTTP 500 на єдиному показанні, щоб відкинути його як «отруєне»
BUFFER_ERRORS = (sqlite3.Error, OSError)


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
        self,
        method: str,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
        resp_headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        """Запит з ретраями (мережа, 502/503/504: 3 спроби, пауза 1/2 с). Статус >= 400 -> OdooError.

        `resp_headers` (необов'язковий) заповнюється заголовками успішної відповіді (імена — у нижньому регістрі).
        """
        session = await self._get_session()
        hdrs = {"Authorization": f"Bearer {self.token}", **(headers or {})}
        url = f"{self.base_url}{path}"
        last: OdooError | None = None
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                async with session.request(method, url, json=body, headers=hdrs) as resp:
                    status = resp.status
                    if resp_headers is not None:
                        resp_headers.clear()
                        resp_headers.update({k.lower(): v for k, v in resp.headers.items()})
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

    async def automation_config(self, etag: str | None = None) -> tuple[dict | None, int | None]:
        """API-24 `GET /td/energy/automation/config` (C-39): `(конфиг | None при 304, X-Config-Version | None)`."""
        headers = {"If-None-Match": f'"{etag}"'} if etag else None
        got: dict[str, str] = {}
        status, data = await self.request("GET", "/td/energy/automation/config", headers=headers, resp_headers=got)
        raw = got.get("x-config-version", "")
        version = int(raw) if raw.isdigit() else None
        if status == 304:
            return None, version
        if not isinstance(data, dict):
            raise OdooError(status, "automation config is not an object")
        return data, version

    async def automation_state(self, body: dict) -> dict:
        """API-25 `POST /td/energy/automation/state` (C-39)."""
        _, data = await self.request("POST", "/td/energy/automation/state", body)
        return data if isinstance(data, dict) else {}

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
    """Буфер -> API-02 (R-19, §8.4). `push_once()` повертає: ok|empty|wait|retry|locked|rejected.

    Політика черги (інцидент стенда: 3 млн рядків, відправка крутила найстаріше, нове не доходило):

    * видаляється (ack) рівно те, що Odoo прийняв (HTTP 200 -> увесь пакет; `rejected` у відповіді — це невалідні
      рядки, повторна відправка їм не допоможе). Якщо Odoo прийняв, а видалити з буфера не вдалося (locked/IO),
      id запам'ятовуються у `_pending_ack` і видаляються першими на наступному кроці — пакет НЕ шлеться вдруге;
    * помилка буфера (locked/IO) — це «retry з бекофом», а не падіння циклу;
    * звичайний режим — FIFO. Якщо найстаріше показання старше за `stale_after_s` (черга «відстає»), пакети чергуються:
      найновіші (`take(newest=True)`, живі дані доходять за ≤ 2 кроки) — найстаріші (черга розгрібається). Старе
      Odoo приймає як історію (`last_*` оновлюються лише свіжішими `ts`); те, що не встигло, викидає ліміт розміру
      буфера (найстаріше першим);
    * пакет, що не проходить (таймаут/5xx), ділиться навпіл після 2-ї поспіль невдачі (`_cap`), щоб не слати той самий
      великий пакет вічно; єдине показання з `POISON_AFTER` поспіль HTTP 500 відкидається, лише якщо інші пакети
      Odoo при цьому приймав (глобальний збій Odoo буфер не спустошує).
    """

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
        stale_after_s: float = STALE_AFTER_S,
        backlog_gap_s: float = BACKLOG_GAP_S,
    ) -> None:
        self.client = client
        self.buffer = buffer
        self.push_max = push_max
        self.push_interval_s = push_interval_s
        self.registry = registry
        self.metrics = metrics
        self.clock: Clock = clock or SystemClock()
        self.on_read_enabled = on_read_enabled
        self.stale_after_s = stale_after_s
        self.backlog_gap_s = backlog_gap_s
        self.read_enabled = True
        self.retry_at = 0.0  # monotonic: не раніше цього моменту
        self.behind = False  # черга старша за stale_after_s
        self.backlog_age_s = 0.0
        self._fails = 0
        self._buffer_fails = 0
        self._pending_ack: list[int] = []
        self._cap: int | None = None  # тимчасове зменшення пакета після невдач
        self._cap_ok = False  # поки пакет зменшено, хоч один пакет Odoo прийняв (отже, Odoo живий, а рядок «отруєний»)
        self._live_turn = False
        self._took_live = False

    def configure(self, interval_s: float | None, push_max: int | None) -> None:
        """Параметри з Odoo (`collector.push_interval_s/push_max`) мають пріоритет над F3D_PUSH_*; None — лишити."""
        if interval_s:
            self.push_interval_s = interval_s
        if push_max:
            self.push_max = push_max

    def _count(self, status: str) -> None:
        if self.metrics is not None:
            self.metrics.push.labels(status).inc()

    async def _set_read_enabled(self, value: bool) -> None:
        if value != self.read_enabled:
            self.read_enabled = value
            if self.on_read_enabled is not None:
                await self.on_read_enabled(value)

    async def _take_batch(self) -> list[tuple[int, Reading]]:
        limit = max(1, min(self.push_max, self._cap or self.push_max))
        oldest = await self.buffer.oldest_ts()
        if oldest is None:
            self.backlog_age_s = 0.0
            self.behind = False
            return []
        self.backlog_age_s = max(0.0, (self.clock.now() - oldest).total_seconds())
        behind = self.stale_after_s > 0 and self.backlog_age_s > self.stale_after_s
        if behind != self.behind:
            self.behind = behind
            if behind:
                log.warning(
                    "push backlog is %.0f s behind (%d rows): live readings first, backlog in turns",
                    self.backlog_age_s,
                    self.buffer.rows,
                )
            else:
                log.info("push backlog caught up")
        self._took_live = behind and self._live_turn
        return await self.buffer.take(limit, newest=self._took_live)

    async def push_once(self) -> str:
        now = self.clock.monotonic()
        if now < self.retry_at:
            return "wait"
        try:
            status = await self._push_once()
        except BUFFER_ERRORS as exc:
            self._buffer_fails += 1
            delay = min(30.0, 2.0 ** (self._buffer_fails - 1))
            log.warning("buffer error (%s): push postponed for %.0f s, will retry", exc, delay)
            self.retry_at = self.clock.monotonic() + delay
            self._count("retry")
            return "retry"
        self._buffer_fails = 0
        return status

    async def _push_once(self) -> str:
        if self._pending_ack:  # Odoo це вже прийняв: спершу видалити, а не слати вдруге
            await self.buffer.ack(self._pending_ack)
            self._pending_ack = []
        rows = await self._take_batch()
        if not rows:
            await flush_events(self.client, self.buffer)
            await flush_results(self.client, self.buffer)
            return "empty"
        ids = [i for i, _ in rows]
        t0 = self.clock.monotonic()
        try:
            resp = await self.client.push([r for _, r in rows])
        except OdooError as exc:
            return await self._on_error(exc, ids)
        if self.metrics is not None:
            self.metrics.push_latency.observe(max(0.0, self.clock.monotonic() - t0))
        self._pending_ack = ids
        self._fails = 0
        if self._cap is not None:
            self._cap_ok = True
            self._cap = self._cap * 2 if self._cap * 2 < self.push_max else None
            if self._cap is None:
                self._cap_ok = False
        self._live_turn = self.behind and not self._took_live
        self._count("ok")
        ack_error: Exception | None = None
        try:
            await self.buffer.ack(ids)
            self._pending_ack = []
        except BUFFER_ERRORS as exc:
            ack_error = exc  # id лишаються у _pending_ack
        await self._after_ok(resp)
        if ack_error is not None:
            raise ack_error
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
        fails = self._fails + 1
        if st in (401, 403):
            log.error("push refused by Odoo (HTTP %s): check F3D_COLLECTOR_TOKEN; readings kept", st)
        else:
            log.warning("push failed (%s), readings kept in buffer", exc)
            if len(ids) > 1 and fails >= 2:
                self._cap = max(1, len(ids) // 2)
                log.warning("push of %d readings keeps failing: batch lowered to %d", len(ids), self._cap)
            elif len(ids) == 1 and st == 500 and self._cap_ok and fails >= POISON_AFTER:
                log.error("push of reading id=%d failed %d times with HTTP 500: dropped as poisoned", ids[0], fails)
                await self.buffer.ack(ids)
                self._fails = 0
                if self.metrics is not None:
                    self.metrics.push_rejected.inc()
                self._count("rejected")
                return "rejected"
        self._fails = fails
        self.retry_at = now + min(60.0, 2.0 ** (fails - 1))
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
        """Цикл відправки; не завершується від помилок. Є черга -> наступний пакет через `backlog_gap_s`
        (кілька пакетів за інтервал, у межах ліміту Odoo), інакше — через `push_interval_s`."""
        while True:
            try:
                status = await self.push_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - цикл відправки не має вмирати
                log.exception("push loop error, retrying")
                self._fails += 1
                self.retry_at = self.clock.monotonic() + min(60.0, 2.0 ** (self._fails - 1))
                status = "retry"
            if status == "ok" and (self.buffer.rows >= self.push_max or self.behind):
                await self.clock.sleep(self.backlog_gap_s)
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
        except BUFFER_ERRORS as exc:
            log.warning("status not built (buffer error): %s", exc)
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
            try:
                await self.send_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - звіт статусу не має вмирати
                log.exception("status loop error")
            await self.clock.sleep(self.interval_s)
