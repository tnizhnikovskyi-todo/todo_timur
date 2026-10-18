"""Writer і Actuator: запис «лише за зміни», інтервал, запобіжник частоти, читання назад (R-44 п.7, R-60 п.2).

`Writer` — єдина точка запису в пристрої (`ctx.write_signal`): дозволені лише коди з API-24 (`signals`, `shed[].signal`,
`bms.*`) і ніколи — префікси `DENY_PREFIXES` (`WriteRefused` + подія `interlock`). Ним користуються й `Actuator`
(автоматика), й `Executor` (інтенти оператора).
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from collector.core.errors import WriteRefused

from . import limits
from .config import Config
from .inputs import Inputs
from .model import Request

TOL = 0.006  # допуск порівняння з читанням назад (менший за 1 одиницю регістра ×0,01)
FAILS_TO_WARN = 3


def same(want: float | None, text: str | None, got_v: float | None, got_t: str | None) -> bool:
    """Чи збігається бажане значення з прочитаним назад (текст — за рівністю, число — з допуском)."""
    if text is not None:
        return got_t is not None and str(got_t) == text
    if want is None:
        return True
    return got_v is not None and abs(float(want) - float(got_v)) <= TOL


class Writer:
    def __init__(
        self,
        write: Callable[..., Any] | None,
        get_cfg: Callable[[], Config],
        live: Any,
        now: Callable[[], datetime],
        on_event: Callable[[str, str, str, str | None], None] | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self._write, self.get_cfg, self.live, self.now = write, get_cfg, live, now
        self.on_event = on_event  # (kind, text, level, signal)
        self.log = log or logging.getLogger("collector.plugin.energy_ctl")
        self.stamps: deque[float] = deque()  # записи за ковзну хвилину (R-44 п.7, R-52 п.10)

    def resolve(self, target: str) -> str:
        """Логічне ім'я → код; код поза дозволеним набором або з забороненим префіксом → `WriteRefused`."""
        cfg = self.get_cfg()
        code = cfg.signals.get(target) or target
        for prefix in limits.DENY_PREFIXES:
            if code.startswith(prefix):
                self._refuse(f"заборонено: {prefix}", code)
        if code not in cfg.writable_codes():
            self._refuse("поза конфігом", code)
        return code

    def _refuse(self, reason: str, code: str) -> None:
        if self.on_event is not None:
            self.on_event("interlock", f"Запис у {code} відхилено: {reason}", "warn", code)
        raise WriteRefused(f"{reason}: {code}")

    def writes_last_min(self, now: datetime | None = None) -> int:
        t = (now or self.now()).timestamp()
        while self.stamps and t - self.stamps[0] > 60.0:
            self.stamps.popleft()
        return len(self.stamps)

    async def write(self, target: str, value: float | None = None, text: str | None = None) -> str:
        """Запис з таймаутом `step_timeout_s`; повертає рядок результату плагіна протоколу."""
        code = self.resolve(target)
        if self._write is None:
            raise WriteRefused("запис недоступний: ядро не передало write_signal")
        cfg = self.get_cfg()
        res = await asyncio.wait_for(self._write(code, value, text), cfg.engine.step_timeout_s)
        now = self.now()
        self.stamps.append(now.timestamp())
        if self.live is not None:
            self.live.note_write(code, value if value is not None else text, now)
        return str(res)


@dataclass
class ApplyResult:
    written: int = 0
    failed: list[str] = field(default_factory=list)  # ресурси, де 3 записи підряд невдалі
    refused: str | None = None  # `WriteRefused` (запобіжник вимкнено): рушій → off
    rate_exceeded: bool = False


class Actuator:
    """Бажані стани ресурсів: запис лише при розбіжності з читанням назад і не частіше `min_write_interval_s`."""

    def __init__(
        self, writer: Writer, get_cfg: Callable[[], Config], live: Any, log: logging.Logger | None = None
    ) -> None:
        self.writer, self.get_cfg, self.live = writer, get_cfg, live
        self.log = log or logging.getLogger("collector.plugin.energy_ctl")
        self.last_try: dict[str, float] = {}
        self.fails: dict[str, int] = {}

    def reset_resource(self, resource: str) -> None:
        self.fails.pop(resource, None)

    def _due(self, code: str, now: float, interval: float) -> bool:
        return now - self.last_try.get(code, float("-inf")) >= interval

    async def apply(self, req: Request, inp: Inputs, *, auto: bool = True) -> ApplyResult:
        cfg = self.get_cfg()
        res = ApplyResult()
        now = inp.now.timestamp()
        interval = cfg.engine.min_write_interval_s
        for w in req.writes:
            code = cfg.sig(w.target) or w.target
            if w.target == req.watchdog:
                last = self.live.last_write(code) if self.live is not None else None
                refresh = req.refresh_s or interval
                same_val = last is not None and (last[0] == (w.value if w.value is not None else w.text))
                due = not same_val or now - last[1].timestamp() >= refresh  # type: ignore[index]
                if not due:
                    continue
            else:
                reading = inp.reading(w.target) if inp.code(w.target) else None
                cmp_text = (
                    w.text if w.value is None else None
                )  # текст-модифікатор («fade=2.0») у порівнянні не бере участі
                if reading is not None and same(w.value, cmp_text, reading.value, reading.text):
                    continue
                last = self.live.last_write(code) if self.live is not None else None
                wrote_same = last is not None and last[0] == (w.value if w.value is not None else w.text)
                # читання назад недоступне або старіше за наш запис: порівнюємо з останнім записом
                if wrote_same and (reading is None or reading.ts <= last[1]):  # type: ignore[index]
                    continue
            if not self._due(code, now, interval):
                break  # порядок записів зберігається (режим — останнім): не обходимо сигнал, що чекає інтервалу
            if auto and self.writer.writes_last_min(inp.now) >= cfg.engine.max_writes_per_min:
                res.rate_exceeded = True
                return res
            self.last_try[code] = now
            try:
                await self.writer.write(w.target, w.value, w.text)
            except WriteRefused as exc:
                res.refused = exc.reason
                return res
            except Exception as exc:  # noqa: BLE001 - відмова пристрою/таймаут: повтор через інтервал
                n = self.fails[req.resource] = self.fails.get(req.resource, 0) + 1
                self.log.warning("запис %s не вдався (%d): %s", code, n, exc or type(exc).__name__)
                if n >= FAILS_TO_WARN:
                    res.failed.append(req.resource)
                    self.fails[req.resource] = 0
                return res
            self.fails[req.resource] = 0
            res.written += 1
        return res
