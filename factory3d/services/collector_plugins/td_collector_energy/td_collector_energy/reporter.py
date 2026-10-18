"""Reporter: POST API-25 раз у 10 с або негайно при зміні дії, буфер при збої, throttle подій (R-53 №1)."""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict, deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

from collector.core.odoo_client import OdooError
from collector.util.timeutil import Clock, to_iso_z

MAX_ACTIONS, MAX_EVENTS = 200, 1000  # буфер при недоступному Odoo
BATCH_ACTIONS, BATCH_EVENTS = 100, 200  # ліміти одного запиту (API-25)
EVENT_THROTTLE_S = 60.0
BACKOFF_MAX_S = 60.0
FINAL = ("done", "failed", "blocked")
ORDER = {"executing": 0, "done": 1, "failed": 1, "blocked": 1}


class Reporter:
    def __init__(
        self,
        odoo: Any,
        collector: str,
        clock: Clock,
        snapshot: Callable[[], dict[str, Any]],
        log: logging.Logger | None = None,
        on_config: Callable[[str | None, int | None], None] | None = None,
    ) -> None:
        self.odoo, self.collector, self.clock, self.snapshot = odoo, collector, clock, snapshot
        self.log = log or logging.getLogger("collector.plugin.energy_ctl")
        self.on_config = on_config
        self.actions: OrderedDict[int, dict[str, Any]] = OrderedDict()
        self.events: deque[dict[str, Any]] = deque()
        self.dropped_actions = self.dropped_events = self.throttled = self.sent_batches = 0
        self.wake = asyncio.Event()
        self.last_error: str | None = None
        self._last_event: dict[tuple[str, str, str], float] = {}
        self._next_try = float("-inf")
        self._backoff = 1.0
        self._last_flush = float("-inf")

    # --- постановка в чергу -------------------------------------------------------------------------
    def add_action(self, item: dict[str, Any], *, now_flush: bool = True) -> None:
        """Стан дії лише «вперед» (executing < done|failed|blocked); повтор того самого стану не дублюється."""
        key = int(item["id"])
        cur = self.actions.get(key)
        if cur is not None and ORDER.get(item["state"], 0) < ORDER.get(cur["state"], 0):
            return
        self.actions[key] = dict(item)
        self.actions.move_to_end(key)
        while len(self.actions) > MAX_ACTIONS:
            self.actions.popitem(last=False)
            self.dropped_actions += 1
        if now_flush:
            self.wake.set()

    def add_event(self, ev: dict[str, Any]) -> bool:
        """Однакові події (вид, сценарій, текст) не частіше разу на 60 с; `False` — відкинуто throttle-ом."""
        key = (ev.get("kind", ""), ev.get("scenario", ""), ev.get("text", ""))
        t = self.clock.monotonic()
        if t - self._last_event.get(key, float("-inf")) < EVENT_THROTTLE_S:
            self.throttled += 1
            return False
        self._last_event[key] = t
        if len(self._last_event) > 2000:
            self._last_event = {k: v for k, v in self._last_event.items() if t - v < EVENT_THROTTLE_S}
        self.events.append(ev)
        while len(self.events) > MAX_EVENTS:
            self.events.popleft()
            self.dropped_events += 1
        return True

    def pending(self) -> tuple[int, int]:
        return len(self.actions), len(self.events)

    # --- відправка --------------------------------------------------------------------------------
    def due(self, period_s: float = 10.0) -> bool:
        return self.wake.is_set() or self.clock.monotonic() - self._last_flush >= period_s

    async def flush(self, now: datetime | None = None) -> bool:
        """Один (або кілька, якщо черга довга) запит(и); `False` — Odoo недоступний, буфер лишається."""
        if self.odoo is None:
            return False
        if self.clock.monotonic() < self._next_try:
            return False
        self.wake.clear()
        now = now or self.clock.now()
        for _ in range(10):
            acts = list(self.actions.values())[:BATCH_ACTIONS]
            evs = list(self.events)[:BATCH_EVENTS]
            body = {
                "collector": self.collector,
                "sent_at": to_iso_z(now),
                **self.snapshot(),
                "actions": acts,
                "events": evs,
            }
            try:
                resp = await self.odoo.automation_state(body)
            except OdooError as exc:
                self._on_error(exc, len(acts), len(evs))
                return False
            self._ok(acts, evs, resp)
            if len(self.actions) <= 0 and len(self.events) <= 0:
                break
        self._last_flush = self.clock.monotonic()
        return True

    def _ok(self, acts: list[dict[str, Any]], evs: list[dict[str, Any]], resp: dict[str, Any]) -> None:
        for a in acts:
            cur = self.actions.get(int(a["id"]))
            if cur is not None and cur["state"] == a["state"]:  # зміни під час запиту не губимо
                del self.actions[int(a["id"])]
        for _ in evs:
            self.events.popleft()
        self.sent_batches += 1
        self.last_error = None
        self._backoff = 1.0
        self._next_try = float("-inf")
        for rej in resp.get("rejected") or []:
            self.log.debug("Odoo відхилив елемент звіту: %s", rej)
        if self.on_config is not None:
            self.on_config(resp.get("config_etag"), resp.get("config_version"))

    def _on_error(self, exc: OdooError, n_acts: int, n_evs: int) -> None:
        self.last_error = str(exc)
        if exc.status == 400:  # структура відхилена — «отруєну» пачку не повторюємо вічно
            for key in list(self.actions)[:n_acts]:
                del self.actions[key]
            for _ in range(min(n_evs, len(self.events))):
                self.events.popleft()
            self.log.warning("API-25 відхилив звіт (400): пачку скинуто")
            return
        delay = float(exc.retry_after) if exc.status == 429 and exc.retry_after else self._backoff
        self._backoff = min(BACKOFF_MAX_S, self._backoff * 2)
        self._next_try = self.clock.monotonic() + delay
        self.log.warning("API-25 недоступний: %s (повтор через %.0f с)", exc, delay)
