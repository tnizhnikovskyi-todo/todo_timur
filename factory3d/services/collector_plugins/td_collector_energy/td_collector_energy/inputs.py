"""Inputs: знімок живих значень із `ctx.live` зі свіжістю (R-41 п.2, R-44 п.3).

Значення вважається відсутнім (`None`), якщо показання немає, `q != "good"` або `age > max(3·period_s, max_age_s)`.
Період сигналу плагіну недоступний (`PluginContext` не несе `SignalCfg` чужих сигналів), тому `periods` необов'язковий,
а базою служить `max_age_s` (60 с, `data_fresh.params`, межа коду 120 с).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from typing import Any

from collector.core.live import LiveCache
from collector.core.types import Reading

from .config import Config

MAX_AGE_DEFAULT = 60.0
# стани з текстом (kind=state з `map`): ядро віддає `Reading(text=…)` без `value` — зводимо до числа
TEXT_NUM: dict[str, dict[str, float]] = {
    "remote": {"local": 0.0, "remote": 1.0},
    "src1_ok": {"unavailable": 0.0, "lost": 0.0, "available": 1.0, "ok": 1.0},
    "qs_state": {"open": 0.0, "closed": 1.0},
    # kind=state з `map` у W1 (energy_signals.csv): число = індекс стану
    "bess_state": {"offline": 0.0, "standby": 1.0, "running": 2.0, "fault": 3.0, "sleep": 4.0},
    "chp_state": {"stop": 0.0, "starting": 1.0, "running": 2.0, "fault": 3.0, "cooling": 4.0},
    "ats_pos": {"unknown": 0.0, "pos_0": 1.0, "pos_i": 2.0, "pos_ii": 3.0},
}


def text_value(name: str, reading: Reading | None) -> float | None:
    """Число показання: `value`, а для станів з текстом (`Reading(text="running")`) — індекс за `TEXT_NUM`."""
    if reading is None:
        return None
    if reading.value is not None:
        return float(reading.value)
    return TEXT_NUM.get(name, {}).get(str(reading.text or "").lower())


class Inputs:
    """Свіжі значення логічних входів (`cfg.inputs`) і сигналів керування (`cfg.signals`) за іменем."""

    def __init__(
        self,
        cfg: Config,
        live: LiveCache | None,
        now: datetime,
        max_age_s: float | None = None,
        periods: Mapping[str, float] | Callable[[str], float | None] | None = None,
    ) -> None:
        self.cfg, self.live, self.now = cfg, live, now
        self.max_age_s = float(
            max_age_s if max_age_s is not None else cfg.interlock("data_fresh").params.get("max_age_s", MAX_AGE_DEFAULT)
        )
        self.periods = periods

    # --- доступ -------------------------------------------------------------------------------
    def code(self, name: str) -> str | None:
        return self.cfg.inp(name) or (name if "/" in name else None)

    def reading(self, name: str) -> Reading | None:
        """Свіже показання (`None`: немає, несвіже, погана якість)."""
        code = self.code(name)
        if code is None or self.live is None:
            return None
        r = self.live.get(code)
        if r is None or r.q == "bad":
            return None
        age = self.live.age_s(code, self.now)
        period = self.periods(code) if callable(self.periods) else (self.periods or {}).get(code)
        if age is None or age > max(3.0 * float(period or 0.0), self.max_age_s):
            return None
        return r

    def v(self, name: str) -> float | None:
        return text_value(name, self.reading(name))

    def t(self, name: str) -> str | None:
        r = self.reading(name)
        return None if r is None or r.text is None else str(r.text)

    def known(self, name: str) -> bool:
        return self.reading(name) is not None

    def absent(self, name: str) -> bool:
        """Сигналу немає взагалі (не в конфігу або ще жодного показання): «не підключено»."""
        code = self.code(name)
        return code is None or self.live is None or self.live.get(code) is None

    def age(self, name: str) -> float | None:
        code = self.code(name)
        return None if code is None or self.live is None else self.live.age_s(code, self.now)

    def stale(self, names: Iterable[str]) -> list[str]:
        return [n for n in names if not self.known(n)]

    def code_list(self, names: Iterable[str]) -> list[str]:
        return [self.code(n) or n for n in names]

    def snapshot(self, names: Iterable[str]) -> dict[str, Any]:
        return {n: self.v(n) for n in names}
