"""Детектор `air_leaks` — «Витоки стисненого повітря» (R-17, вкладка «Стиснене повітря»; W3-B).

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`. Нічний мінімум витрати магістралі (лічильники
`source`-точки повітря, `rate_avg` слотів ночі за R-21) відносно денної витрати в зміни.
"""

import math

from . import common

TITLE = "Витоки стисненого повітря"
DEFAULT_SPEC = 5.3 / 60.0  # кВт·год на норм. м³ (0,0883), коли немає даних вузла вартості
HOURS_MONTH = 730.0  # витоки працюють цілодобово


def detect(env, rule, now):
    params = common.rule_params(rule)
    win = common.Window(env, rule, now)
    sources = env["td.energy.point"].sudo().search([("resource_id.code", "=", "air"), ("kind", "=", "source")])
    meters = sources.meter_ids.filtered("active")
    rows = common.res_slots(env, meters.ids, win)
    if win.sparse(ts for ts, _rate, _qty in rows):
        return []
    night_min = []
    for day in win.days:
        n_lo, n_hi = win.shifts.night_window(day)
        expected = math.ceil((n_hi - n_lo) / common.SLOT)
        values = [rate for ts, rate, _qty in rows if n_lo <= ts < n_hi]
        if expected and len(values) / expected >= common.MIN_COVERAGE:
            night_min.append(min(values))
    if len(night_min) < common.MIN_DAYS:
        return []
    day_values = [rate for ts, rate, _qty in rows if win.is_shift(ts)]
    if not day_values:
        return []
    night_flow, day_flow = common.median(night_min), common.mean(day_values)
    if day_flow <= 0 or night_flow < params["min_flow"] or night_flow / day_flow < params["ratio_min"]:
        return []
    cost_nodes = sources.cost_node_id
    node_rows = common.node_slots(env, cost_nodes.ids, "consumer", win.lo, win.hi)
    kwh = sum(r[1] for r in node_rows)
    qty_total = sum(qty for _ts, _rate, qty in rows)
    spec = kwh / qty_total if kwh > 0 and qty_total > 0 else DEFAULT_SPEC
    price = common.weighted(sum(r[2] for r in node_rows), kwh)
    if price <= 0:
        return []
    saved_flow = night_flow * params["reducible"]
    qty = saved_flow * 60.0 * HOURS_MONTH * spec
    share = night_flow / day_flow * 100.0
    text = (
        "Нічна витрата %s м³/хв — %s %% від денної (%s м³/хв). Усунувши витоки, можна зекономити близько %s м³/хв."
    ) % (common.fmt_auto(night_flow), common.fmt_int(share), common.fmt_auto(day_flow), common.fmt_auto(saved_flow))
    evidence = {
        "night_flow": round(night_flow, 3), "day_flow": round(day_flow, 3), "share_pct": round(share, 1),
        "spec": round(spec, 5), "reducible": params["reducible"], "nights": len(night_min),
    }  # fmt: skip
    node = cost_nodes[:1]
    point = sources[:1]
    return [
        common.finding(
            "air_leaks:*",
            TITLE,
            text,
            qty * price,
            qty,
            evidence,
            node_code=node.code or None,
            point_code=point.code or None,
        )
    ]
