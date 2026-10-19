"""Клієнт HTTP Odoo: API-01 ``GET /f3d/sim/devices`` і API-03 ``POST /f3d/sim/events`` (SPEC §7.1, §8.2.4).

Авторизація — ``Bearer SIM_ODOO_EXPORT_TOKEN``. Вихідні з'єднання — через ``OutboundGuard`` (allow-list).
``EventForwarder`` збирає події шини (``scenario/fault/alarm/error``, ``info`` лише із запуску) і пакетами
≤ 100 шлях в Odoo з ``payload.event_id`` (дедуплікація на боці Odoo); помилка — повтор пізніше.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import httpx

from iot_sim.core.events import Event
from iot_sim.core.world import World

log = logging.getLogger("iot_sim.odoo")

FORWARD_KINDS = ("scenario", "fault", "alarm", "error")
BATCH = 100
MAX_QUEUE = 5000


class DevicesClient:
    def __init__(
        self,
        url: str,
        export_token: str,
        *,
        guard: Any = None,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base = url.rstrip("/")
        self.token = export_token
        self.guard = guard
        hooks = [guard.httpx_hook] if guard is not None else []
        self._client = client or httpx.AsyncClient(timeout=timeout, event_hooks={"request": hooks})
        self.etag: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.base and self.token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def get_devices(self, protocol: str | None = None, use_etag: bool = True) -> dict[str, Any] | None:
        """API-01. ``None`` — 304 (каталог не змінився). Помилка HTTP -> ``httpx.HTTPStatusError``."""
        headers = self._headers()
        if use_etag and self.etag and protocol is None:
            headers["If-None-Match"] = self.etag
        r = await self._client.get(
            f"{self.base}/f3d/sim/devices", headers=headers, params={"protocol": protocol} if protocol else None
        )
        if r.status_code == 304:
            return None
        r.raise_for_status()
        if protocol is None:
            self.etag = r.headers.get("ETag", self.etag)
        return r.json()  # type: ignore[no-any-return]

    async def post_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        """API-03: ``{"accepted": n, "rejected": [{"index", "reason"}]}``."""
        r = await self._client.post(f"{self.base}/f3d/sim/events", headers=self._headers(), json={"events": events})
        r.raise_for_status()
        return r.json()  # type: ignore[no-any-return]

    async def aclose(self) -> None:
        await self._client.aclose()


class EventForwarder:
    def __init__(self, world: World, client: DevicesClient, *, period_s: float = 5.0) -> None:
        self.world, self.client, self.period_s = world, client, period_s
        self.queue: list[dict[str, Any]] = []
        self.sent = 0
        self.dropped = 0
        self._task: asyncio.Task[Any] | None = None

    def to_item(self, ev: Event) -> dict[str, Any]:
        run = self.world.runs.get(ev.run_id) if ev.run_id else None
        item: dict[str, Any] = {
            "kind": ev.kind,
            "message": ev.message,
            "ts": ev.ts.isoformat(),
            "device": ev.device,
            "payload": {**ev.payload, "event_id": ev.id},
        }
        if ev.run_id:
            item["sim_run_id"] = ev.run_id
            ref = getattr(run, "run_ref", None) or ev.payload.get("run_ref")
            if ref:
                item["run_ref"] = ref
        return item

    def on_event(self, ev: Event) -> None:
        if ev.kind not in FORWARD_KINDS and not (ev.kind == "info" and ev.run_id):
            return
        self.queue.append(self.to_item(ev))
        if len(self.queue) > MAX_QUEUE:
            del self.queue[0]
            self.dropped += 1

    async def flush(self) -> int:
        """Відправляє накопичене; повертає кількість прийнятих. Помилка — залишає чергу."""
        total = 0
        while self.queue and self.client.configured:
            batch = self.queue[:BATCH]
            try:
                res = await self.client.post_events(batch)
            except (httpx.HTTPError, OSError) as exc:
                log.warning("API-03 post failed: %s", exc, extra={"proto": "odoo"})
                break
            del self.queue[: len(batch)]
            total += int(res.get("accepted", 0))
            self.sent += len(batch)
        return total

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.period_s)
            with contextlib.suppress(Exception):
                await self.flush()

    async def start(self) -> None:
        self.world.events.subscribe(self.on_event)
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self.on_event in self.world.events.subscribers:
            self.world.events.subscribers.remove(self.on_event)
        with contextlib.suppress(Exception):
            await self.flush()
