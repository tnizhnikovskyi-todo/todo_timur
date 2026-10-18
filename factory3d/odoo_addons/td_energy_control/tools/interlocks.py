"""R-41: Odoo-реалізація реєстру блокувань (підказка в діалозі, `confirm` блокується). Чисті функції + збирач контексту.

`CHECKS[code](ctx, params, extra) -> Result`. Код перевірок не береться з БД; рядок `td.energy.interlock` лише
налаштовує `hard`, `fail_closed`, `params`, `where`. Та сама таблиця золотих випадків (SPEC R-41 п.5) — у збирачі.
"""

import math
from dataclasses import dataclass, field
from datetime import timedelta

from odoo import fields

from . import kinds

OK, FAIL, UNKNOWN = "ok", "fail", "unknown"
MAX_AGE_DEFAULT = 60


@dataclass
class Result:
    state: str
    detail: str = ""
    values: dict = field(default_factory=dict)


class Ctx:
    """Свіжі значення логічних входів. `v(name)` — число або None (немає/несвіже), `t(name)` — текст."""

    def __init__(self, values=None, texts=None, absent=()):
        self.values = dict(values or {})
        self.texts = dict(texts or {})
        self.absent = set(absent)

    def v(self, name):
        return self.values.get(name)

    def t(self, name):
        return self.texts.get(name)

    def known(self, name):
        return self.values.get(name) is not None or self.texts.get(name) is not None

    @classmethod
    def from_env(cls, env, now=None, max_age_s=MAX_AGE_DEFAULT):
        """Один пошук `td.signal` за кодами SIGNALS ∪ INPUTS; свіжість: age ≤ max(3·period_s, max_age_s)."""
        now = now or fields.Datetime.now()
        names = {**kinds.SIGNALS, **kinds.INPUTS, **kinds.ODOO_INPUTS}
        by_code = {}
        for sig in env["td.signal"].sudo().search_read([("code", "in", list(names.values()))], _SIG_FIELDS):
            by_code[sig["code"]] = sig
        values, texts, absent = {}, {}, set()
        for name, code in names.items():
            sig = by_code.get(code)
            if sig is None:
                absent.add(name)
                continue
            if sig["status"] == "stale" or not sig["last_ts"]:
                continue
            age = (now - sig["last_ts"]).total_seconds()
            if age > max(3 * (sig["period_s"] or 0), max_age_s):
                continue
            if sig["last_ts"] and sig["status"] != "unknown":
                values[name] = sig["last_value"]
            texts[name] = sig["last_text"] or None
        return cls(values, texts, absent)


_SIG_FIELDS = ["code", "last_value", "last_text", "last_ts", "status", "period_s"]


def _round5(x):
    return int(5 * round(x / 5.0))


def _src1_ok(c):
    txt, val = c.t("src1_ok"), c.v("src1_ok")
    if txt is None and val is None:
        return None
    return txt == "available" or (txt is None and val == 1)


def _controller_remote(c, p, x):
    v = c.v("remote")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if v == 1 else FAIL, "remote=%d" % v)


def _no_island(c, p, x):
    pos, src = c.v("ats_pos"), _src1_ok(c)
    if (pos is not None and pos != 2) or src is False:
        return Result(FAIL, "острівний режим або мережі немає")
    if pos is None or src is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK, "мережа є")


def _ats_parallel_lock(c, p, x):
    v = c.v("ats_lock")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if v == 1 else FAIL, "lock=%d" % v)


def _qs_current_ok(c, p, x):
    rating = p.get("rating_a", 1600)
    if (c.t("qs_state") or "") == "closed":
        return Result(OK, "QS уже замкнений", {"i_a": 0, "rating_a": rating})
    p1, p2 = c.v("s1_p"), c.v("s2_p")
    if p1 is None or p2 is None:
        return Result(UNKNOWN, "немає даних", {"rating_a": rating})
    cos = p.get("cos_phi", 0.95) or 0.95
    amps = abs(p1 - p2) / 2.0 / (math.sqrt(3) * 0.4 * cos)
    limit = rating * p.get("max_ratio", 0.8)
    values = {"i_a": _round5(amps), "rating_a": rating}
    return Result(OK if amps <= limit else FAIL, "%d А ≤ %d А" % (values["i_a"], limit), values)


def _bess_ok(c, p, x):
    v = c.v("bess_state")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if int(v) in (1, 2, 4) else FAIL, "стан %d" % v)


def _bess_soc_lt_limit(c, p, x):
    soc, limit = c.v("bess_soc"), x.get("soc_limit_pct", p.get("limit", 95))
    values = {"soc": kinds.fmt(soc), "limit": kinds.fmt(limit)}
    if soc is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if soc < limit else FAIL, "Заряд %s %% < %s %%" % (values["soc"], values["limit"]), values)


def _bess_reserve_kept(c, p, x):
    soc = c.v("bess_soc")
    reserve = c.v("bess_reserve") if c.v("bess_reserve") is not None else x.get("reserve_pct", 30)
    values = {"reserve": kinds.fmt(reserve)}
    if soc is None:
        return Result(UNKNOWN, "немає даних", values)
    after = soc - x.get("power_kw", 0) * x.get("duration_min", 60) / 60.0 / p.get("capacity_kwh", 387) * 100
    return Result(OK if after >= reserve else FAIL, "залишок після розряду %s %%" % kinds.fmt(after, 1), values)


def _bess_temp_ok(c, p, x):
    t = c.v("bess_temp")
    values = {"t": kinds.fmt(t)}
    if t is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if t <= p.get("max_c", 40) else FAIL, "%s °C" % values["t"], values)


def _chp_ready(c, p, x):
    v = c.v("chp_state")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if int(v) == 0 else FAIL, "стан %d" % v)


def _chp_gas_pressure(c, p, x):
    gas = c.v("chp_gas")
    values = {"bar": gas, "min": p.get("min_bar", 1.5)}
    if gas is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if gas >= p.get("min_bar", 1.5) else FAIL, "%s бар" % kinds.fmt(gas, 1), values)


def _chp_permit(c, p, x):
    v = c.v("chp_permit")
    if v is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if v == 1 else FAIL, "permit=%d" % v)


def _chp_min_run(c, p, x):
    state, hours, need = c.v("chp_state"), c.v("chp_hours"), p.get("min_run_h", 2)
    values = {"h": kinds.fmt(need)}
    if state is None:
        return Result(UNKNOWN, "немає даних", values)
    if int(state) == 0:
        return Result(OK, "КГУ не працює", values)
    if hours is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if hours >= need else FAIL, "%s год" % kinds.fmt(hours, 1), values)


def _no_fire_alarm(c, p, x):
    if "fire_state" in c.absent:
        return Result(OK, "не підключено")
    if not c.known("fire_state"):
        return Result(UNKNOWN, "немає даних")
    return Result(FAIL if (c.t("fire_state") or "") == "alarm" else OK, c.t("fire_state") or "")


def _air_setpoint_min(c, p, x):
    sp, low = x.get("setpoint_bar"), c.v("air_min")
    values = {"min": low}
    if sp is None or low is None:
        return Result(UNKNOWN, "немає даних", values)
    ok = low + p.get("margin_bar", 0.2) - 1e-9 <= sp <= p.get("max_bar", 8.5)
    return Result(OK if ok else FAIL, "уставка %s бар" % kinds.fmt(sp, 1), values)


def _aisle_lux_ge(c, p, x):
    lux = [v for v in (x.get("lux") or []) if v is not None]
    values = {"lux": kinds.fmt(min(lux)) if lux else "—"}
    if not lux:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if min(lux) >= p.get("min_lux", 75) else FAIL, "%s лк" % values["lux"], values)


def _co2_lt(c, p, x):
    ppm = c.v("co2_ppm")
    values = {"ppm": kinds.fmt(ppm), "limit": kinds.fmt(p.get("max_ppm", 1000))}
    if ppm is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if ppm < p.get("max_ppm", 1000) else FAIL, "%s ppm" % values["ppm"], values)


def _genset_fuel(c, p, x):
    fuel = (x.get("genset") or {}).get("fuel_pct")
    values = {"pct": kinds.fmt(fuel)}
    if fuel is None:
        return Result(UNKNOWN, "немає даних", values)
    return Result(OK if fuel >= p.get("min_pct", 30) else FAIL, "%s %%" % values["pct"], values)


def _genset_heater(c, p, x):
    cool = (x.get("genset") or {}).get("coolant_c")
    if cool is None:
        return Result(UNKNOWN, "немає даних")
    return Result(OK if cool >= 30 else FAIL, "%s °C" % kinds.fmt(cool))


def _genset_idle(c, p, x):
    g = x.get("genset") or {}
    if not g:
        return Result(UNKNOWN, "немає даних")
    busy = bool(g.get("running")) or bool(g.get("test_running")) or bool(g.get("island"))
    return Result(FAIL if busy else OK, "ДГУ в роботі, тест або острів" if busy else "")


def _data_fresh(c, p, x):
    stale = [n for n in x.get("fresh_names", ()) if not c.known(n)]
    if stale:
        return Result(
            FAIL,
            "немає свіжих даних: %s"
            % ", ".join({**kinds.SIGNALS, **kinds.INPUTS, **kinds.ODOO_INPUTS}.get(n, n) for n in stale),
        )
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
    "genset_fuel": _genset_fuel,
    "genset_heater": _genset_heater,
    "genset_idle": _genset_idle,
    "aisle_lux_ge": _aisle_lux_ge,
    "co2_lt": _co2_lt,
    "air_setpoint_min": _air_setpoint_min,
}


def is_blocking(hard, fail_closed, state):
    """R-41 п.3: жорстка перевірка блокує при `fail` або при `unknown` з `fail_closed`."""
    return bool(hard and (state == FAIL or (state == UNKNOWN and fail_closed)))


def evaluate(check_specs, interlocks, ctx, extra=None):
    """Перевірки виду → (список для діалогу/журналу, blocked, blocked_reason).

    `check_specs` — `kind.checks` (`[{"code","soft"}]`), `interlocks` — {code: dict(name, hard, fail_closed, where,
    params, active)}. `where='collector'` → `unknown` «перевіряє збирач» і не блокує в Odoo.
    """
    extra = extra or {}
    rows, blocked, reason = [], False, None
    for spec in check_specs or ():
        row = interlocks.get(spec["code"])
        if row is None or not row.get("active", True):
            continue
        hard = bool(row["hard"]) and not spec.get("soft")
        if row["where"] == "collector":
            res = Result(UNKNOWN, "перевіряє збирач")
            blocks = False
        else:
            res = CHECKS[spec["code"]](ctx, row.get("params") or {}, extra)
            blocks = is_blocking(hard, row.get("fail_closed", True), res.state)
        label = kinds.render_template(row["name"], res.values)
        rows.append({"code": spec["code"], "label": label, "state": res.state, "hard": hard, "detail": res.detail})
        if blocks and not blocked:
            blocked = True
            base = label.rsplit(" — ", 1)[0]
            reason = "%s — %s" % (base, "не виконано" if res.state == FAIL else "немає даних")
    return rows, blocked, reason


def aisle_lux(env, now=None, max_age_s=MAX_AGE_DEFAULT):
    """Свіжі `e_now` груп освітлення проходів (`fixture_kind='highbay_rack'`) — вхід `aisle_lux_ge`."""
    now = now or fields.Datetime.now()
    if "td.bms.light.group" not in env:
        return []
    groups = env["td.bms.light.group"].sudo().search([("fixture_kind", "=", "highbay_rack")])
    codes = ["lighting/groups/%s/e_now" % g.code for g in groups]
    out = []
    for sig in env["td.signal"].sudo().search([("code", "in", codes)]):
        if sig.last_ts and sig.status != "stale" and now - sig.last_ts <= timedelta(seconds=max_age_s):
            out.append(sig.last_value)
    return out
