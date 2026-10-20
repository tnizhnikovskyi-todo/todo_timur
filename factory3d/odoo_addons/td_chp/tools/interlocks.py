"""R-07: блокування КГУ. `CHECKS[code](unit, ctx) → (ok|fail|unknown, detail)`; `ctx` — `Snapshot` (метод `get(key)`).

Підписи й тексти відмови — з мокапу (`b_sim.js:123–139`); `unknown` — вхід застарів (R-01) і блокує команду.
"""

from odoo.addons.td_telemetry.tools.titles import fmt_num

OK, FAIL, UNKNOWN = "ok", "fail", "unknown"
NO_DATA = "немає свіжих даних"


def _verdict(parts):
    """Тризначна логіка: будь-який fail → fail, інакше будь-який unknown → unknown, інакше ok."""
    if FAIL in parts:
        return FAIL
    return UNKNOWN if UNKNOWN in parts else OK


def _flag(ctx, key, want):
    val = ctx.get(key)
    if val is None:
        return UNKNOWN
    return OK if int(round(val)) == want else FAIL


def _simple(key, want, bad):
    def check(unit, ctx):
        res = _flag(ctx, key, want)
        return res, (NO_DATA if res == UNKNOWN else "" if res == OK else bad)

    return check


def _in_set(key, allowed, bad):
    def check(unit, ctx):
        val = ctx.get(key)
        if val is None:
            return UNKNOWN, NO_DATA
        return (OK, "") if int(round(val)) in allowed else (FAIL, bad)

    return check


def _limit(key, op, limit_attr, unit_txt, nd, bad_fmt):
    """Числовий поріг із паспорта: `op` — `ge|le|lt`; ok-деталь «зараз X», відмова — `bad_fmt`."""

    def check(unit, ctx):
        val = ctx.get(key)
        if val is None:
            return UNKNOWN, NO_DATA
        lim = unit[limit_attr]
        good = val >= lim if op == "ge" else val <= lim if op == "le" else val < lim
        if good:
            return OK, f"зараз {fmt_num(val, nd)} {unit_txt}"
        return FAIL, bad_fmt.format(v=fmt_num(val, nd), lim=fmt_num(lim, 2))

    return check


def _no_fire(unit, ctx):
    res = _verdict([_flag(ctx, "safe/fire", 0), _flag(ctx, "safe/ext_state", 0)])
    return res, (NO_DATA if res == UNKNOWN else "" if res == OK else "пожежна тривога / гасіння")


def _oil_estop(unit, ctx):
    oil = ctx.get("oil/level")
    oil_res = UNKNOWN if oil is None else OK if oil >= unit.oil_min_pct else FAIL
    res = _verdict([oil_res, _flag(ctx, "safe/estop_loop", 1)])
    return res, (NO_DATA if res == UNKNOWN else "" if res == OK else "рівень масла / контур аварійного стопу")


def _rsw(unit, ctx):
    return (OK, "") if unit._td_remote_switching() else (FAIL, "дистанційні перемикання не дозволені")


def _not_state(want, bad):
    def check(unit, ctx):
        val = ctx.get("ctl/state")
        if val is None:
            return UNKNOWN, NO_DATA
        return (FAIL, bad) if int(round(val)) == want else (OK, "")

    return check


# код → (підпис, функція); порядок START — порядок «умов пуску» мокапу
DEFS = {
    "not_cooling": ("КГУ не в стані «Охолодження»", _not_state(4, "КГУ охолоджується")),
    "no_alarm": ("Немає активної аварії (скинуто)", _not_state(3, "активна аварія — потрібне скидання")),
    "permit": ("«Дозвіл КГУ» (chp_permit)", _simple("ctl/permit", 1, "немає дозволу КГУ")),
    "gas_pressure": (
        "Тиск газу ≥ 1,5 бар",
        _limit("gas/p_in", "ge", "gas_min_bar", "бар", 2, "тиск газу {v} бар < {lim} бар"),
    ),
    "remote": ("Режим «Дистанційне» на щиті (ctl_remote)", _simple("ctl/remote", 1, "на щиті не «Дистанційне»")),
    "rsw": ("«Дистанційні перемикання дозволені» (настройка)", _rsw),
    "grid": ("Напруга мережі S2 наявна", _simple("safe/grid_ok", 1, "мережа S2 відсутня")),
    "no_rocof": ("Захист ROCOF / векторний зсув не спрацював", _simple("safe/rocof", 0, "спрацював захист ROCOF")),
    "lel_lt": (
        "Газоаналізатор < 10 % НКПР",
        _limit("safe/lel", "lt", "lel_warn_pct", "%", 1, "загазованість {v} % НКПР"),
    ),
    "no_fire": ("Пожежної тривоги немає, гасіння готове", _no_fire),
    "ret_temp": (
        "t зворотки ≤ 70 °C",
        _limit("ht/t_ret", "le", "ret_set_c", "°C", 0, "t зворотки {v} °C > {lim} °C"),
    ),
    "jacket_temp": (
        "t ОЖ < 95 °C",
        _limit("eng/t_jacket_out", "lt", "jacket_max_c", "°C", 0, "t ОЖ {v} °C ≥ {lim} °C"),
    ),
    "battery": (
        "АКБ 24 В ≥ 23,5 В",
        _limit("eng/bat_v", "ge", "bat_min_v", "В", 1, "АКБ {v} В < {lim} В"),
    ),
    "oil_estop": ("Рівень масла ≥ 40 %, контур аварійного стопу замкнений", _oil_estop),
    # додатково за видом команди
    "state_run": ("КГУ в стані «Пуск» або «Робота»", _in_set("ctl/state", (1, 2), "КГУ не працює")),
    "alarm_active": ("Є активна аварія", _simple("ctl/state", 3, "активної аварії немає")),
    "not_alarm": ("Немає активної аварії", _not_state(3, "КГУ в аварії")),
    "manual_mode": ("Режим «Ручний»", _simple("ctl/mode", 3, "уставка P діє лише в режимі «Ручний»")),
}


CHECKS = {code: fn for code, (_label, fn) in DEFS.items()}
START = (
    "not_cooling",
    "no_alarm",
    "permit",
    "gas_pressure",
    "remote",
    "rsw",
    "grid",
    "no_rocof",
    "lel_lt",
    "no_fire",
    "ret_temp",
    "jacket_temp",
    "battery",
    "oil_estop",
)
KIND_CHECKS = {
    "start": START,
    "stop": ("remote", "state_run"),
    "estop": ("not_alarm",),
    "reset": ("remote", "alarm_active"),
    "set_mode": ("remote",),
    "set_setpoint": ("remote", "manual_mode"),
    "set_cos": ("remote",),
    "set_heat_dir": ("remote",),
    "set_bypass": ("remote",),
}


def build_checks(unit, kind, ctx, routed=False):
    """Перевірки для виду команди: `[{code, label, state, hard, detail}]`; `routed` — вид іде через міст (без `rsw`:
    діють стоп-крани td_energy_control). Дозвіл запису (`td.chp.write_enabled`, сигнал, джерело) — окремий засув
    `signals.write_off_reason`, а не рядок переліку: `il` пуску лишається 14 умов."""
    items = []
    for code in KIND_CHECKS[kind]:
        if routed and code == "rsw":
            continue
        label, fn = DEFS[code]
        state, detail = fn(unit, ctx)
        items.append({"code": code, "label": label, "state": state, "hard": True, "detail": detail})
    return items


def verdict(checks, kind):
    """`(blocked, reason)`: `fail` або `unknown` блокують (для `estop` `unknown` не блокує)."""
    bad = []
    for c in checks:
        if not c.get("hard", True):
            continue
        if c["state"] == FAIL or (c["state"] == UNKNOWN and kind != "estop"):
            bad.append(c["detail"] or c["label"])
    return bool(bad), "; ".join(bad)
