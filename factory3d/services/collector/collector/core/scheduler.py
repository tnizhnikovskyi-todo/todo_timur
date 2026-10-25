"""Планувальник опитування (R-19), apply_signal_scale (R-02, X-63) і приймач emit() від push-плагінів."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import random
import sqlite3
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from collector.core.buffer import Buffer
from collector.core.live import LiveCache
from collector.core.types import Health, PushEvent, Reading, SignalCfg, SourceCfg
from collector.plugins.base import SourcePlugin
from collector.util.timeutil import Clock, SystemClock

log = logging.getLogger("collector.scheduler")

POLL_BACKOFF_MAX = 30.0
CONNECT_BACKOFF_MAX = 60.0
ERROR_AFTER = 3
OVERRUN_LOG_EVERY_S = 60.0
MAX_PENDING = 500_000  # показань у пам'яті Emitter, поки буфер недоступний
SCALED_KINDS = frozenset({"gauge", "counter"})


def apply_signal_scale(
    readings: Iterable[Reading], signals: Mapping[str, SignalCfg], warn: Callable[[str], None] | None = None
) -> list[Reading]:
    """R-02: `value = eng · signal.scale` рівно один раз, лише gauge/counter з числовим value."""
    out: list[Reading] = []
    for r in readings:
        sig = signals.get(r.code)
        if sig is None:
            (warn or log.warning)(f"reading for unknown signal {r.code}: scale not applied")
            out.append(r)
        elif sig.kind in SCALED_KINDS and r.value is not None and sig.scale != 1.0:
            out.append(dataclasses.replace(r, value=r.value * sig.scale))
        else:
            out.append(r)
    return out


class _SourceState:
    def __init__(self) -> None:
        self.fails = 0
        self.health = Health(state="online", stats={"polls": 0, "errors": 0, "readings": 0})


class Scheduler:
    def __init__(
        self,
        buffer: Buffer,
        registry: Any = None,
        metrics: Any = None,
        clock: Clock | None = None,
        rand: Callable[[], float] = random.random,
        live: LiveCache | None = None,
    ) -> None:
        self.buffer = buffer
        self.registry = registry
        self.metrics = metrics
        self.clock: Clock = clock or SystemClock()
        self.rand = rand
        self.live = live
        self._state: dict[str, _SourceState] = {}
        self._tasks: dict[str, list[asyncio.Task]] = {}
        self._plugins: dict[str, SourcePlugin] = {}
        self._last_overrun_log: dict[str, float] = {}
        if registry is not None:
            registry.listeners.append(self.sync)

    # --- групи і запуск ---
    @staticmethod
    def group_signals(source: SourceCfg) -> dict[int, list[SignalCfg]]:
        groups: dict[int, list[SignalCfg]] = {}
        for sg in source.signals:
            groups.setdefault(sg.period_s, []).append(sg)
        return groups

    def start_source(self, source: SourceCfg, plugin: SourcePlugin) -> list[asyncio.Task]:
        self._plugins[source.code] = plugin
        self._state.setdefault(source.code, _SourceState())
        tasks = [
            asyncio.create_task(self.loop_poll(source, period, sigs, plugin), name=f"poll:{source.code}:{period}")
            for period, sigs in self.group_signals(source).items()
        ]
        self._tasks[source.code] = tasks
        return tasks

    async def stop_source(self, code: str) -> None:
        tasks = self._tasks.pop(code, [])
        self._plugins.pop(code, None)
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        for code in list(self._tasks):
            await self.stop_source(code)

    async def sync(self) -> None:
        """Узгоджує таски з Registry: нові/змінені плагіни — старт, зниклі — зупинка. Push-плагіни не опитуються."""
        reg = self.registry
        desired = {c: p for c, p in reg.plugins.items() if not p.push_mode}
        for code in list(self._tasks):
            if code not in desired or self._plugins.get(code) is not desired[code]:
                await self.stop_source(code)
                if code not in desired:
                    self._state.pop(code, None)
        for code, plugin in desired.items():
            if code not in self._tasks:
                self.start_source(reg.sources[code], plugin)

    # --- здоров'я ---
    def health(self, code: str) -> Health:
        st = self._state.get(code)
        return st.health if st else Health(state="online")

    # --- цикл опитування ---
    async def _ensure_connected(self, code: str, plugin: SourcePlugin) -> None:
        reg = self.registry
        if reg is None or reg.plugins.get(code) is not plugin:
            return
        delay = 1.0
        while code not in reg.connected:
            if await reg.connect_source(code):
                return
            self._mark(code, "error", reg.errors[code].error if code in reg.errors else "connect failed")
            await self.clock.sleep(delay)
            delay = min(CONNECT_BACKOFF_MAX, delay * 2)

    def _mark(self, code: str, state: str, error: str | None) -> None:
        st = self._state.setdefault(code, _SourceState())
        st.health.state = state
        st.health.error = error
        if self.metrics is not None:
            plugin = self._plugins.get(code)
            self.metrics.set_source(code, plugin.source.type if plugin else "", state)

    async def loop_poll(
        self, source: SourceCfg, period: int, signals: list[SignalCfg], plugin: SourcePlugin | None = None
    ) -> None:
        code = source.code
        plugin = plugin or self.registry.plugins[code]
        by_code = {s.code: s for s in signals}
        st = self._state.setdefault(code, _SourceState())
        fails = 0
        await self.clock.sleep(self.rand() * period)
        while True:
            await self._ensure_connected(code, plugin)
            t0 = self.clock.monotonic()
            try:
                readings = await plugin.poll(signals)
                readings = apply_signal_scale(readings, by_code)
                if self.live is not None:
                    self.live.update(readings)
                await self.buffer.put_many(readings)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - будь-яка помилка опитування -> бекоф
                fails += 1
                st.fails += 1
                st.health.stats["errors"] = st.health.stats.get("errors", 0) + 1
                if self.metrics is not None:
                    self.metrics.poll_errors.labels(code).inc()
                msg = str(exc) or type(exc).__name__
                log.warning("poll %s failed: %s", code, msg, extra={"source": code})
                if st.fails >= ERROR_AFTER:
                    self._mark(code, "error", msg)
                await self.clock.sleep(min(POLL_BACKOFF_MAX, 2.0 ** (fails - 1)))
                continue
            fails = 0
            st.fails = 0
            elapsed = self.clock.monotonic() - t0
            st.health.last_ok = self.clock.now()
            st.health.stats["polls"] = st.health.stats.get("polls", 0) + 1
            st.health.stats["readings"] = st.health.stats.get("readings", 0) + len(readings)
            st.health.stats["latency_ms"] = int(elapsed * 1000)
            self._mark(code, "online", None)
            if self.metrics is not None:
                self.metrics.poll_seconds.labels(code).observe(elapsed)
                self.metrics.readings.labels(code).inc(len(readings))
            if elapsed > period:
                self._overrun(code, elapsed, period)
            else:
                await self.clock.sleep(period - elapsed)

    def _overrun(self, code: str, elapsed: float, period: int) -> None:
        if self.metrics is not None:
            self.metrics.poll_overrun.labels(code).inc()
        now = self.clock.monotonic()
        if now - self._last_overrun_log.get(code, float("-inf")) >= OVERRUN_LOG_EVERY_S:
            self._last_overrun_log[code] = now
            log.warning("poll %s took %.1f s > period %s s", code, elapsed, period, extra={"source": code})


class Emitter:
    """`ctx.emit`/`ctx.emit_event` для push-плагінів: масштаб ядра, черга, запис у буфер (R-02)."""

    def __init__(
        self,
        buffer: Buffer,
        signals: Callable[[], Mapping[str, SignalCfg]] | Mapping[str, SignalCfg],
        metrics: Any = None,
        live: LiveCache | None = None,
    ) -> None:
        self.buffer = buffer
        self._signals = signals
        self.metrics = metrics
        self.live = live
        self._readings: list[Reading] = []
        self._events: list[PushEvent] = []

    def _lookup(self) -> Mapping[str, SignalCfg]:
        return self._signals() if callable(self._signals) else self._signals

    def emit(self, reading: Reading) -> None:
        scaled = apply_signal_scale([reading], self._lookup())
        if self.live is not None:
            self.live.update(scaled)
        self._readings.extend(scaled)

    def emit_event(self, event: PushEvent) -> None:
        self._events.append(event)

    async def flush(self) -> int:
        """Скидає чергу в буфер. Помилка буфера (locked/IO) не губить дані: те, що не записалося, лишається в черзі
        (не більше `MAX_PENDING` показань — тоді відкидаються найстаріші) і піде на наступному виклику."""
        readings, self._readings = self._readings, []
        events, self._events = self._events, []
        done = 0
        try:
            if readings:
                await self.buffer.put_many(readings)
                done += len(readings)
                if self.metrics is not None:
                    for r in readings:
                        sig = self._lookup().get(r.code)
                        self.metrics.readings.labels(sig.source_code if sig else "unknown").inc()
                readings = []
            while events:
                await self.buffer.put_event(events[0])
                events.pop(0)
                done += 1
        except (sqlite3.Error, OSError) as exc:
            self._readings = (readings + self._readings)[-MAX_PENDING:]
            self._events = events + self._events
            log.warning(
                "buffer write failed (%s): %d readings, %d events kept in memory", exc, len(readings), len(events)
            )
        return done

    async def run(self, interval_s: float = 0.5) -> None:
        while True:
            await asyncio.sleep(interval_s)
            await self.flush()
