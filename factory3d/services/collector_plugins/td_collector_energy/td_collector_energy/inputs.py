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
from .derived import Derived, compute
from .inputs_text import text_value

MAX_AGE_DEFAULT = 60.0


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
        self._derived: dict[str, Derived] = {}

    # --- доступ -------------------------------------------------------------------------------
    def code(self, name: str) -> str | None:
        return self.cfg.inp(name) or (name if "/" in name else None)

    def _period(self, code: str) -> float | None:
        return self.periods(code) if callable(self.periods) else (self.periods or {}).get(code)

    def derived(self, code: str) -> Derived | None:
        """Похідний вхід (D-47): `None`, якщо `code` не входить до `cfg.derived`."""
        formula = self.cfg.derived.get(code)
        if formula is None:
            return None
        if code not in self._derived:
            self._derived[code] = compute(code, formula, self.live, self.now, self.max_age_s, self._period)
        return self._derived[code]

    def reading(self, name: str) -> Reading | None:
        """Свіже показання (`None`: немає, несвіже, погана якість); похідні входи рахуються з термів `derived`."""
        code = self.code(name)
        if code is None or self.live is None:
            return None
        d = self.derived(code)
        if d is not None:
            return d.reading
        r = self.live.get(code)
        if r is None or r.q == "bad":
            return None
        age = self.live.age_s(code, self.now)
        period = self._period(code)
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
        if code is None or self.live is None:
            return True
        d = self.derived(code)
        return not d.seen if d is not None else self.live.get(code) is None

    def age(self, name: str) -> float | None:
        code = self.code(name)
        if code is None or self.live is None:
            return None
        d = self.derived(code)
        if d is not None:  # вік похідного входу — вік найстарішого терма
            return None if d.oldest is None else (self.now - d.oldest).total_seconds()
        return self.live.age_s(code, self.now)

    def stale(self, names: Iterable[str]) -> list[str]:
        return [n for n in names if not self.known(n)]

    def code_list(self, names: Iterable[str]) -> list[str]:
        return [self.code(n) or n for n in names]

    def snapshot(self, names: Iterable[str]) -> dict[str, Any]:
        return {n: self.v(n) for n in names}
