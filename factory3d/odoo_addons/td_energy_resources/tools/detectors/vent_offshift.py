"""Детектор `vent_offshift` — «Вентиляція працює поза змінами» (R-15, вкладка «Електрика»; W3-B).

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`. Вузли `consumer` групи `params.group` (`vent`); рівень
потужності в зміни й поза ними (R-21); знахідка, якщо `off_level ≥ ratio_min × day_level`.
"""

from . import common

TITLE = "Вентиляція працює поза змінами"


def detect(env, rule, now):
    params = common.rule_params(rule)
    nodes = (
        env["td.energy.node"].sudo().search([("kind", "=", "consumer"), ("group", "=", params.get("group", "vent"))])
    )
    if not nodes:
        return []
    win = common.Window(env, rule, now)
    price_at = common.zone_price_at(env, now)  # ніч дешевша за 8,4: рахуємо за зонами, не за плоскою ціною слота
    rows = common.node_slots(env, nodes.ids, "consumer", win.lo, win.hi)
    if win.sparse(ts for ts, _kwh, _kp in rows):
        return []
    day_kw, off_kw, off_kwh, off_weighted = [], [], 0.0, 0.0
    for ts, kwh, kwh_price in rows:
        if win.is_shift(ts):
            day_kw.append(kwh * 4.0)
        else:
            off_kw.append(kwh * 4.0)
            off_kwh += kwh
            zone = price_at(ts) if price_at else None
            off_weighted += kwh_price if zone is None else kwh * zone
    if not day_kw or not off_kw:
        return []
    day_level, off_level = common.mean(day_kw), common.mean(off_kw)
    if day_level <= 0 or off_level < params["ratio_min"] * day_level:
        return []
    saving_kw = off_level - params["target_ratio"] * day_level
    price = common.weighted(off_weighted, off_kwh)
    if saving_kw <= 0 or price <= 0:
        return []
    off_hours = len(off_kw) / 4.0
    qty = saving_kw * off_hours * win.k_month
    ratio = off_level / day_level
    text = "Поза змінами вентиляція споживає %s кВт — %s %% від денного рівня (%s кВт). Можна знизити до %s кВт." % (
        common.fmt_int(off_level), common.fmt_int(ratio * 100), common.fmt_int(day_level),
        common.fmt_int(params["target_ratio"] * day_level),
    )  # fmt: skip
    evidence = {
        "day_level_kw": round(day_level, 2), "off_level_kw": round(off_level, 2), "ratio": round(ratio, 3),
        "off_hours": round(off_hours, 2), "off_price": round(price, 4), "nodes": sorted(nodes.mapped("code")),
    }  # fmt: skip
    return [common.finding("vent_offshift:*", TITLE, text, qty * price, qty, evidence)]
