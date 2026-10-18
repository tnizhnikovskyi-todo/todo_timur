"""Детектор `idle_machines` — «Холостий хід верстатів під напругою» (R-16, вкладка «Електрика»; W3-B).

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`. Джерело — `td.energy.alloc` за доби вікна: частка простою
`kind='idle'` у кВт·год рядків `direct` + `idle`.
"""

from . import common

TITLE = "Холостий хід верстатів під напругою"


def detect(env, rule, now):
    params = common.rule_params(rule)
    win = common.Window(env, rule, now)
    Alloc = env["td.energy.alloc"].sudo()
    domain = [("day", ">=", win.days[0]), ("day", "<=", win.days[-1]), ("kind", "in", ("direct", "idle"))]
    groups = Alloc._read_group(domain, ["kind", "node_id", "workcenter_id"], ["kwh:sum", "cost:sum"])
    if not groups:
        return []
    days = Alloc._read_group(domain, ["day:day"], ["__count"])
    if len(days) < common.MIN_DAYS:
        return []
    rc_kwh = sum(kwh or 0.0 for _kind, _node, _wc, kwh, _cost in groups)
    idle = [(node, wc, kwh or 0.0, cost or 0.0) for kind, node, wc, kwh, cost in groups if kind == "idle"]
    idle_kwh, idle_cost = sum(g[2] for g in idle), sum(g[3] for g in idle)
    if rc_kwh <= 0 or idle_kwh <= 0:
        return []
    share = idle_kwh / rc_kwh
    price = common.weighted(idle_cost, idle_kwh)
    if share < params["idle_share_min"] or price <= 0:
        return []
    per_node = {}
    for node, wc, kwh, _cost in idle:
        label = node.code if node else (wc.name if wc else "—")
        per_node[label] = per_node.get(label, 0.0) + kwh
    top = sorted(per_node.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    qty = idle_kwh * win.k_month * params["recoverable"]
    text = "Між завданнями верстати стоять увімкненими: %s кВт·год за %s діб, найбільше %s." % (
        common.fmt_int(idle_kwh), win.length, ", ".join(label for label, _kwh in top),
    )  # fmt: skip
    evidence = {
        "idle_kwh": round(idle_kwh, 2), "rc_kwh": round(rc_kwh, 2), "share": round(share, 4),
        "top_nodes": [label for label, _kwh in top],
    }  # fmt: skip
    top_node = env["td.energy.node"].sudo().search([("code", "=", top[0][0])], limit=1)
    return [common.finding("idle_machines:*", TITLE, text, qty * price, qty, evidence, node_code=top_node.code or None)]
