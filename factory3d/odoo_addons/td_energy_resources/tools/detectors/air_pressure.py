"""Детектор `air_pressure` — «Тиск стисненого повітря завищений» (R-18, вкладка «Стиснене повітря»; W3-B).

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`. Уставка (сигнал `energy_control/air/setpoint_bar`, інакше
параметр `air_setpoint_bar`) проти найвибагливішого споживача, що реально працює.
"""

from ..build import rparam_float
from . import common

TITLE = "Тиск стисненого повітря завищений"
SETPOINT_SIGNAL = "energy_control/air/setpoint_bar"
RUNNING_SHARE = 0.05  # споживач «працює», якщо середня швидкість > 5 % від паспортної
MEAN_SQL = """
SELECT point_id, AVG(rate_avg) FROM td_energy_res_interval
 WHERE metric = 'main' AND point_id IN %s AND quality <> 'missing' AND day >= %s AND day <= %s
   AND ts_start >= %s AND ts_start < %s
 GROUP BY point_id
"""


def detect(env, rule, now):
    params = common.rule_params(rule)
    win = common.Window(env, rule, now)
    Point = env["td.energy.point"].sudo()
    cost_node = Point.search([("resource_id.code", "=", "air"), ("kind", "=", "source")]).cost_node_id[:1]
    consumers = Point.search(
        [("resource_id.code", "=", "air"), ("kind", "=", "consumer"), ("min_pressure_bar", ">", 0)]
    ).filtered(lambda p: p.rate_nominal > 0)
    if not cost_node or not consumers:
        return []
    p_set = common.fresh_value(env, SETPOINT_SIGNAL, now)
    if p_set is None:
        p_set = rparam_float(env, "air_setpoint_bar", 0.0)
    env.cr.execute(MEAN_SQL, (tuple(consumers.ids), win.days[0], win.days[-1], win.lo, win.hi))
    mean_rate = dict(env.cr.fetchall())
    running = consumers.filtered(lambda p: (mean_rate.get(p.id) or 0.0) > RUNNING_SHARE * p.rate_nominal)
    if not running or p_set <= 0:
        return []
    needy = max(running, key=lambda p: (p.min_pressure_bar, p.code))
    p_need = needy.min_pressure_bar
    p_target = p_need + params["margin_bar"]
    dp = p_set - p_target
    if dp < params["min_save_bar"]:
        return []
    rows = common.node_slots(env, cost_node.ids, "consumer", win.lo, win.hi)
    if win.sparse(ts for ts, _kwh, _kp in rows):
        return []
    kwh = sum(r[1] for r in rows)
    price = common.weighted(sum(r[2] for r in rows), kwh)
    if kwh <= 0 or price <= 0:
        return []
    qty = kwh * win.k_month * params["k_per_bar"] * dp
    text = "Найвибагливіший споживач (%s) потребує %s бар; уставка %s. Можна знизити до %s бар." % (
        needy.name, common.fmt_auto(p_need), common.fmt_auto(p_set), common.fmt_auto(p_target),
    )  # fmt: skip
    evidence = {
        "p_set": round(p_set, 2), "p_need": round(p_need, 2), "p_target": round(p_target, 2), "dp": round(dp, 2),
        "consumer": needy.code, "kwh_window": round(kwh, 2),
    }  # fmt: skip
    return [
        common.finding(
            "air_pressure:*",
            TITLE,
            text,
            qty * price,
            qty,
            evidence,
            node_code=cost_node.code or None,
            point_code=needy.code,
        )
    ]
