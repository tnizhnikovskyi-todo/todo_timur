"""Годинник сервісу (SPEC §8.2.2): ``now() = sim_t0 + (real_now - real_t0) * factor``.

Усе внутрішнє — tz-aware (``SIM_TZ``); sim-час монотонний у UTC (перехід DST не дублює хвилини,
бо хвилинні кроки шуму рахуються по UTC-епосі: ``minute_index()``).
``FakeClock`` — ручний годинник для тестів: час рухається лише через ``advance()``,
а ``World.step(dt)`` сам його просуває.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

MAX_FACTOR = 60.0
MIN_FACTOR = 0.1
MAX_SUBSTEP_S = 10.0


class FakeRealTime:
    """Підміна ``time.time`` для тестів: ``advance(s)`` рухає «реальний» час."""

    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class SimClock:
    manual = False

    def __init__(self, tz: str = "Europe/Kyiv", factor: float = 1.0,
                 sim_t0: datetime | None = None,
                 real_time: Callable[[], float] = time.time) -> None:
        self.tz = ZoneInfo(tz)
        self._real = real_time
        self.factor = float(factor)
        self.real_t0 = self._real()
        start = sim_t0 if sim_t0 is not None else datetime.fromtimestamp(self.real_t0, self.tz)
        if start.tzinfo is None:
            start = start.replace(tzinfo=self.tz)
        self.sim_t0 = start.timestamp()  # UTC-секунди епохи

    def epoch(self) -> float:
        return self.sim_t0 + (self._real() - self.real_t0) * self.factor

    def now(self) -> datetime:
        return datetime.fromtimestamp(self.epoch(), self.tz)

    def set(self, dt: datetime) -> None:
        """Переставляє ``sim_t0`` (поточний реальний час стає точкою відліку)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.tz)
        self.real_t0 = self._real()
        self.sim_t0 = dt.timestamp()

    def set_factor(self, factor: float) -> None:
        """Фіксує поточний ``now()`` як нову точку відліку (час не стрибає)."""
        if not MIN_FACTOR <= factor <= MAX_FACTOR:
            raise ValueError(f"factor має бути в [{MIN_FACTOR}; {MAX_FACTOR}]")
        cur = self.epoch()
        self.real_t0 = self._real()
        self.sim_t0 = cur
        self.factor = float(factor)

    def minute_index(self) -> int:
        """Номер sim-хвилини від епохи UTC (ключ хвилинного шуму R-00)."""
        return int(self.epoch() // 60)

    def advance(self, sim_seconds: float) -> None:  # реальний годинник сам іде
        return None


class FakeClock(SimClock):
    """Ручний sim-годинник: ``now()`` змінюється лише через ``advance()``/``set()``."""

    manual = True

    def __init__(self, start: datetime | str = "2026-10-12T10:30:00",
                 tz: str = "Europe/Kyiv", factor: float = 1.0) -> None:
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        self._fake = FakeRealTime()
        super().__init__(tz=tz, factor=factor, sim_t0=start, real_time=self._fake)

    def advance(self, sim_seconds: float) -> None:
        self._fake.advance(sim_seconds / self.factor)
