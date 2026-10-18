"""Сценарії (R-45…R-50) і крок `slots` — чисті функції `step(env) -> Output` без введення-виведення."""

from __future__ import annotations

from collections.abc import Callable

from ..model import Env, Output
from . import backup, chp, night, peak, pfc, selfcons, slots

# порядок виконання за тік і пріоритет арбітражу (R-44 п.2, п.4)
ORDER: tuple[tuple[str, Callable[[Env], Output]], ...] = (
    ("backup", backup.step),
    ("peak", peak.step),
    ("self", selfcons.step),
    ("slots", slots.step),
    ("chp", chp.step),
    ("night", night.step),
    ("pfc", pfc.step),
)
CARDS = ("peak", "self", "pfc", "night", "backup", "chp")  # сценарії з карткою статусу (`slots` — крок без картки)
