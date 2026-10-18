"""R-41: реєстр блокувань збирача (жорстке виконання). `CHECKS[code](ctx, params, extra) -> Result`.

Та сама таблиця золотих випадків (SPEC R-41 п.5), що в `td_energy_control/tools/interlocks.py` (Odoo, підказка):
AC-195…AC-199 (Odoo) і AC-241, AC-242 (тут). Код перевірок не береться з конфігу: рядок `interlocks` лише задає `hard`,
`fail_closed`, `params`. `where='odoo'` збирач не виконує (`genset_*` тут немає).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .config import Config

OK, FAIL, UNKNOWN = "ok", "fail", "unknown"


@dataclass
class Result:
    state: str
    detail: str = ""
    values: dict[str, Any] = field(default_factory=dict)


class Ctx:
    """Свіжі значення логічних входів: `v(name)` — число або `None` (немає/несвіже), `t(name)` — текст."""

    def __init__(
        self,
        values: dict[str, float | None] | None = None,
        texts: dict[str, str | None] | None = None,
        absent: Iterable[str] = (),
    ) -> None:
        self.values = dict(values or {})
        self.texts = dict(texts or {})
        self._absent = set(absent)

    def v(self, name: str) -> float | None:
        return self.values.get(name)

    def t(self, name: str) -> str | None:
        return self.texts.get(name)

    def known(self, name: str) -> bool:
        return self.values.get(name) is not None or self.texts.get(name) is not None

    def absent(self, name: str) -> bool:
        return name in self._absent

    @classmethod
    def from_inputs(cls, inputs: Any, names: Iterable[str]) -> Ctx:
        names = list(names)
        return cls(
            {n: inputs.v(n) for n in names}, {n: inputs.t(n) for n in names}, [n for n in names if inputs.absent(n)]
        )


def _fmt(x: float | None, nd: int = 0) -> str:
    if x is None:
        return "—"
    return f"{x:.{nd}f}".rstrip("0").rstrip(".") if nd else f"{round(x):d}"


def _round5(x: float) -> int:
    return int(5 * round(x / 5.0))


def _src1_ok(c: Ctx) -> bool | None:
    txt, val = c.t("src1_ok"), c.v("src1_ok")
    if txt is None and val is None:
        return None
    return txt == "available" or (txt is None and val == 1)


def _controller_remote(c: Ctx, p: dict, x: dict) -> Result:
    v = c.v("remote")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if v == 1 else FAIL, f"remote={int(v)}")


def _no_island(c: Ctx, p: dict, x: dict) -> Result:
    pos, src = c.v("ats_pos"), _src1_ok(c)
    if (pos is not None and pos != 2) or src is False:
        return Result(FAIL, "острівний режим або мережі немає")
    if pos is None or src is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK, "мережа є")


def _ats_parallel_lock(c: Ctx, p: dict, x: dict) -> Result:
    v = c.v("ats_lock")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if v == 1 else FAIL, f"lock={int(v)}")


def _qs_current_ok(c: Ctx, p: dict, x: dict) -> Result:
    rating = p.get("rating_a", 1600)
    closed = (c.t("qs_state") or "") == "closed" or (c.t("qs_state") is None and c.v("qs_state") == 1)
    if closed:
        return Result(OK, "QS уже замкнений", {"i_a": 0, "rating_a": rating})
    p1, p2 = c.v("s1_p"), c.v("s2_p")
    if p1 is None or p2 is None:
        return Result(UNKNOWN, "немає даних", {"rating_a": rating})
    cos = p.get("cos_phi", 0.95) or 0.95
    amps = abs(p1 - p2) / 2.0 / (math.sqrt(3) * 0.4 * cos)
    limit = rating * p.get("max_ratio", 0.8)
    values = {"i_a": _round5(amps), "rating_a": rating}
    return Result(OK if amps <= limit else FAIL, f"≈ {values['i_a']} А з {rating} А", values)


def _bess_ok(c: Ctx, p: dict, x: dict) -> Result:
    v = c.v("bess_state")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if int(v) in (1, 2, 4) else FAIL, f"стан {int(v)}")


def _bess_soc_lt_limit(c: Ctx, p: dict, x: dict) -> Result:
    soc, limit = c.v("bess_soc"), x.get("soc_limit_pct", p.get("limit", 95))
    values = {"soc": _fmt(soc), "limit": _fmt(limit)}
    if soc is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if soc < limit else FAIL, f"Заряд {values['soc']} % < {values['limit']} %", values)


def _bess_reserve_kept(c: Ctx, p: dict, x: dict) -> Result:
    soc = c.v("bess_soc")
    reserve = c.v("bess_reserve") if c.v("bess_reserve") is not None else x.get("reserve_pct", 30)
    values = {"reserve": _fmt(reserve)}
    if soc is None:
        return Result(UNKNOWN, "немає даних", values)
    after = soc - x.get("power_kw", 0) * x.get("duration_min", 60) / 60.0 / p.get("capacity_kwh", 387) * 100
    return Result(OK if after >= reserve else FAIL, f"залишок після розряду {_fmt(after, 1)} %", values)


def _bess_temp_ok(c: Ctx, p: dict, x: dict) -> Result:
    t = c.v("bess_temp")
    values = {"t": _fmt(t)}
    if t is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if t <= p.get("max_c", 40) else FAIL, f"{values['t']} °C", values)


def _chp_ready(c: Ctx, p: dict, x: dict) -> Result:
    v = c.v("chp_state")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if int(v) == 0 else FAIL, f"стан {int(v)}")


def _chp_gas_pressure(c: Ctx, p: dict, x: dict) -> Result:
    gas, need = c.v("chp_gas"), p.get("min_bar", 1.5)
    values = {"bar": gas, "min": need}
    if gas is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if gas >= need else FAIL, f"{_fmt(gas, 1)} бар", values)


def _chp_permit(c: Ctx, p: dict, x: dict) -> Result:
    v = c.v("chp_permit")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if v == 1 else FAIL, f"permit={int(v)}")


def _chp_min_run(c: Ctx, p: dict, x: dict) -> Result:
    state, hours, need = c.v("chp_state"), x.get("run_h", c.v("chp_hours")), p.get("min_run_h", 2)
    values = {"h": _fmt(need)}
    if state is None:
        return Result(UNKNOWN, "немає даних", values)
    if int(state) == 0:
        return Result(OK, "КГУ не працює", values)
    if hours is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if hours >= need else FAIL, f"{_fmt(hours, 1)} год", values)


def _no_fire_alarm(c: Ctx, p: dict, x: dict) -> Result:
    if c.absent("fire_state"):
        return Result(OK, "не підключено")
    if not c.known("fire_state"):
        return Result(UNKNOWN, "немає даних")
    return Result(FAIL if (c.t("fire_state") or "") == "alarm" else OK, c.t("fire_state") or "")


def _air_setpoint_min(c: Ctx, p: dict, x: dict) -> Result:
    sp, low = x.get("setpoint_bar"), c.v("air_min")
    values = {"min": low}
    if sp is None or low is None:
        return Result(UNKNOWN, "немає даних", values)
    ok = low + p.get("margin_bar", 0.2) - 1e-9 <= sp <= p.get("max_bar", 8.5)
    return Result(OK if ok else FAIL, f"уставка {_fmt(sp, 1)} бар", values)


def _aisle_lux_ge(c: Ctx, p: dict, x: dict) -> Result:
    lux = [v for v in (x.get("lux") or []) if v is not None]
    values = {"lux": _fmt(min(lux)) if lux else "—"}
    if not lux:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if min(lux) >= p.get("min_lux", 75) else FAIL, f"{values['lux']} лк", values)


def _co2_lt(c: Ctx, p: dict, x: dict) -> Result:
    ppm = c.v("co2_ppm")
    limit = p.get("max_ppm", 1000)
    values = {"ppm": _fmt(ppm), "limit": _fmt(limit)}
    if ppm is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if ppm < limit else FAIL, f"{values['ppm']} ppm", values)


def _data_fresh(c: Ctx, p: dict, x: dict) -> Result:
    stale = [n for n in x.get("fresh_names", ()) if not c.known(n)]
    if stale:
        codes = x.get("codes") or {}
        return Result(FAIL, "немає свіжих даних: " + ", ".join(codes.get(n, n) for n in stale))
    return Result(OK, "")


CHECKS = {
    "controller_remote": _controller_remote,
    "data_fresh": _data_fresh,
    "no_island": _no_island,
    "ats_parallel_lock": _ats_parallel_lock,
    "qs_current_ok": _qs_current_ok,
    "bess_ok": _bess_ok,
    "bess_soc_lt_limit": _bess_soc_lt_limit,
    "bess_reserve_kept": _bess_reserve_kept,
    "bess_temp_ok": _bess_temp_ok,
    "chp_ready": _chp_ready,
    "chp_gas_pressure": _chp_gas_pressure,
    "chp_permit": _chp_permit,
    "chp_min_run": _chp_min_run,
    "no_fire_alarm": _no_fire_alarm,
    "aisle_lux_ge": _aisle_lux_ge,
    "co2_lt": _co2_lt,
    "air_setpoint_min": _air_setpoint_min,
}


def is_blocking(hard: bool, fail_closed: bool, state: str) -> bool:
    """R-41 п.3: жорстка перевірка блокує при `fail` або при `unknown` з `fail_closed`."""
    return bool(hard and (state == FAIL or (state == UNKNOWN and fail_closed)))


def evaluate(
    specs: Iterable[dict[str, Any]], cfg: Config, ctx: Ctx, extra: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Перевірки виду (`[{"code","soft"}]`) → (рядки `{code,state,hard,detail}`, blocked, причина блокування)."""
    extra = extra or {}
    rows, blocked, reason = [], False, None
    for spec in specs:
        code = spec["code"]
        fn = CHECKS.get(code)
        if fn is None:
            continue
        row = cfg.interlock(code)
        hard = row.hard and not spec.get("soft")
        res = fn(ctx, row.params, extra)
        rows.append({"code": code, "state": res.state, "hard": hard, "detail": res.detail})
        if not blocked and is_blocking(hard, row.fail_closed, res.state):
            blocked = True
            reason = f"Блокування: {code} — {'не виконано' if res.state == FAIL else 'немає даних'} ({res.detail})"
    return rows, blocked, reason
