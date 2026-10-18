"""Похідні входи API-24 `derived` (D-47, W2_SPEC §7.3 п.8): плагін рахує їх сам із `LiveCache` (E-03: без Odoo).

Формули (ключ — код входу): `sum` — `terms:[{"code","k"[,"min"]}]`, значення `Σ k·max(min, x)`, `clamp_min`
(нижня межа результату) і `zero_if:{"code","eq"}` (результат 0, якщо сигнал = `eq`; сигналу немає — умова
ігнорується); `ge` — `1.0`, якщо `code` ≥ `value`, інакше `0.0`. Терм (крім `zero_if`) відсутній або старший за
`max_age_s` → вхід відсутній (fail-closed); свіжість результату — за найстарішим термом. Невідома операція чи
некоректна формула → вхід відсутній і одне попередження в журнал.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from collector.core.live import LiveCache
from collector.core.types import Reading

from .inputs_text import text_value

log = logging.getLogger("collector.plugin.energy_ctl")
OPS = ("sum", "ge")
_warned: set[tuple[str, str]] = set()


@dataclass
class Derived:
    reading: Reading | None  # `None`: терм відсутній/несвіжий або формула некоректна
    oldest: datetime | None  # час найстарішого терма (незалежно від свіжості) — для `age()`
    seen: bool  # усі терми мали показання хоч раз («підключено»)


def validate(code: str, f: Any) -> str | None:
    """Текст проблеми формули (для попередження при розборі конфігу) або `None`."""
    if not isinstance(f, dict) or f.get("op") not in OPS:
        return f"derived.{code}: невідома операція {f.get('op') if isinstance(f, dict) else f!r}"
    try:
        if f["op"] == "sum":
            terms = f["terms"]
            if not isinstance(terms, list) or not all(
                isinstance(t["code"], str) and _num(t["k"]) is not None for t in terms
            ):
                raise ValueError("terms")
            if any("min" in t and _num(t["min"]) is None for t in terms):
                raise ValueError("min")
            if "clamp_min" in f and _num(f["clamp_min"]) is None:
                raise ValueError("clamp_min")
            z = f.get("zero_if")
            if z is not None and not (isinstance(z["code"], str) and _num(z["eq"]) is not None):
                raise ValueError("zero_if")
        elif not (isinstance(f["code"], str) and _num(f["value"]) is not None):
            raise ValueError("ge")
    except (KeyError, TypeError, ValueError) as exc:
        return f"derived.{code}: некоректна формула ({exc})"
    return None


def _num(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _warn(code: str, why: str) -> None:
    if (code, why) not in _warned:
        _warned.add((code, why))
        log.warning("%s — вхід вважається відсутнім", why)


def compute(
    code: str,
    f: Any,
    live: LiveCache | None,
    now: datetime,
    max_age_s: float,
    period_of: Callable[[str], float | None] | None = None,
) -> Derived:
    problem = validate(code, f)
    if problem is not None or live is None:
        if problem is not None:
            _warn(code, problem)
        return Derived(None, None, False)
    stamps: list[datetime] = []
    seen = True

    def term(tcode: str) -> float | None:
        """Свіже числове значення терма; `None` — немає/несвіже/погана якість (час терма — у `stamps`)."""
        nonlocal seen
        r = live.get(tcode)
        if r is None:
            seen = False
            return None
        stamps.append(r.ts)
        age = live.age_s(tcode, now)
        limit = max(3.0 * float((period_of(tcode) if period_of else 0.0) or 0.0), max_age_s)
        if r.q == "bad" or age is None or age > limit:
            return None
        return text_value(tcode, r)

    if f["op"] == "ge":
        x = term(f["code"])
        value = None if x is None else (1.0 if x >= float(f["value"]) else 0.0)
    else:
        terms = f["terms"]
        parts = [(t, term(t["code"])) for t in terms]
        value = None
        if terms and all(x is not None for _t, x in parts):
            value = sum(float(t["k"]) * (max(float(t["min"]), x) if "min" in t else x) for t, x in parts)  # type: ignore[type-var,arg-type]
            z = f.get("zero_if")
            if z is not None:
                zr = live.get(z["code"])
                zv = text_value(z["code"], zr)
                zage = live.age_s(z["code"], now)
                if (
                    zr is not None
                    and zv is not None
                    and zage is not None
                    and zage <= max_age_s
                    and zv == float(z["eq"])
                ):
                    value = 0.0
            if "clamp_min" in f:
                value = max(float(f["clamp_min"]), value)
        elif not terms:
            seen = False
    oldest = min(stamps) if stamps else None
    reading = None if value is None or oldest is None else Reading(code, oldest, value=float(value))
    return Derived(reading, oldest, seen and bool(stamps))
