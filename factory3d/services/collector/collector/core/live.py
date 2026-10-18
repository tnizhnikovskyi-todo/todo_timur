"""LiveCache: останні показання сигналів у пам'яті (C-40, W2 SPEC §8.1.2).

Один рядок на код, без історії. Один event loop — потокобезпечність не потрібна. Плагін `energy_ctl` читає звідси
входи рушія та свіжість (`age_s`); показання пишуть `Scheduler` і `Emitter` після `apply_signal_scale`.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from collector.core.types import Reading
from collector.util.timeutil import Clock, SystemClock


class LiveCache:
    def __init__(self, clock: Clock | None = None) -> None:
        self.clock: Clock = clock or SystemClock()
        self._last: dict[str, Reading] = {}
        self._writes: dict[str, tuple[float | str | None, datetime]] = {}

    def update(self, readings: Iterable[Reading]) -> None:
        for r in readings:
            self._last[r.code] = r

    def get(self, code: str) -> Reading | None:
        return self._last.get(code)

    def age_s(self, code: str, now: datetime | None = None) -> float | None:
        """Вік показання в секундах за `Reading.ts`; `None`, якщо показань немає."""
        r = self._last.get(code)
        if r is None:
            return None
        return (now or self.clock.now()).timestamp() - r.ts.timestamp()

    def snapshot(self, codes: Iterable[str]) -> dict[str, Reading | None]:
        return {c: self._last.get(c) for c in codes}

    def note_write(self, code: str, value: float | str | None, ts: datetime | None = None) -> None:
        """Запам'ятати останній запис у пристрій (значення й час) — для політики «пишемо лише за зміни»."""
        self._writes[code] = (value, ts or self.clock.now())

    def last_write(self, code: str) -> tuple[float | str | None, datetime] | None:
        return self._writes.get(code)
