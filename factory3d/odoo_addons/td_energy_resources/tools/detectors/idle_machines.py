"""Детектор `idle_machines` — «Холостий хід верстатів під напругою» (R-16, вкладка «Електрика»; W3-B).

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`. Джерело — `td.energy.alloc` за доби вікна: частка простою
`kind='idle'` у кВт·год рядків `direct` + `idle`. Простій рахується лише в змінах (R-21) і лише понад
«рівень стоянки» вузла (медіана його слотів поза змінами, `td.energy.interval`): нижче нього простій не зменшити. Вузол
без слотів поза змінами — частка доби в змінах за календарем. Ніч і вихідні — не «між завданнями».
"""

from collections import defaultdict

from odoo.addons.td_energy.tools import dates

from . import common

TITLE = "Холостий хід верстатів під напругою"
SLOTS_SQL = """
SELECT node_id, ts_start, kwh FROM td_energy_interval
 WHERE role = 'consumer' AND node_id IN %s AND quality <> 'missing' AND ts_start >= %s AND ts_start < %s
"""


def shift_profiles(env, win, node_ids):
    """`{(node_id, доба): [понад рівень стоянки в змінах, кВт·год; рівень стоянки за добу, кВт·год]}` за слотами вузла.

    Рівень стоянки вузла — медіана його слотів поза змінами (ніч, вихідні): нижче нього простій не зменшити.
    Вузол без слотів поза змінами в вікні в результат не потрапляє."""
    if not node_ids:
        return {}
    env.cr.execute(SLOTS_SQL, (tuple(node_ids), win.lo, win.hi))
    by_node = defaultdict(list)
    for node_id, ts, kwh in env.cr.fetchall():
        by_node[node_id].append((ts, kwh or 0.0))
    out = {}
    for node_id, rows in by_node.items():
        off = [kwh for ts, kwh in rows if not win.is_shift(ts)]
        if not off:
            continue
        floor = common.median(off)
        for ts, kwh in rows:
            item = out.setdefault((node_id, dates.local_day(ts)), [0.0, 0.0])
            item[1] += floor
            if win.is_shift(ts):
                item[0] += max(kwh - floor, 0.0)
    return out


def calendar_share(win, day):
    """Частка доби в змінах за календарем змін (R-21): запасний варіант, коли слотів вузла поза змінами немає."""
    return sum((b - a).total_seconds() for _name, a, b in win.shifts.windows_for(day)) / 86400.0


def detect(env, rule, now):
    params = common.rule_params(rule)
    win = common.Window(env, rule, now)
    Alloc = env["td.energy.alloc"].sudo()
    domain = [("day", ">=", win.days[0]), ("day", "<=", win.days[-1]), ("kind", "in", ("direct", "idle"))]
    groups = Alloc._read_group(domain, ["kind", "node_id", "workcenter_id", "day:day"], ["kwh:sum", "cost:sum"])
    if not groups:
        return []
    days = Alloc._read_group(domain, ["day:day"], ["__count"])
    if len(days) < common.MIN_DAYS:
        return []
    profiles = shift_profiles(env, win, {g[1].id for g in groups if g[0] == "idle" and g[1]})
    direct_kwh = sum(kwh or 0.0 for kind, _node, _wc, _day, kwh, _cost in groups if kind == "direct")
    idle, idle_total = [], 0.0  # idle — лише в змінах і лише понад рівень стоянки; ніч і вихідні — не «між завданнями»
    for kind, node, wc, day, kwh, cost in groups:
        if kind != "idle":
            continue
        kwh, cost = kwh or 0.0, cost or 0.0
        idle_total += kwh
        profile = profiles.get((node.id, day)) if node else None
        if profile is not None and kwh > 0:
            share = min(profile[0], max(kwh - profile[1], 0.0)) / kwh
        else:
            share = calendar_share(win, day)
        idle.append((node, wc, kwh * share, cost * share))
    idle_kwh, idle_cost = sum(g[2] for g in idle), sum(g[3] for g in idle)
    rc_kwh = direct_kwh + idle_kwh
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
    text = "Між завданнями в зміни верстати споживають понад нічний рівень %s кВт·год за %s діб, найбільше %s." % (
        common.fmt_int(idle_kwh), win.length, ", ".join(label for label, _kwh in top),
    )  # fmt: skip
    evidence = {
        "idle_kwh": round(idle_kwh, 2), "idle_kwh_all_day": round(idle_total, 2), "rc_kwh": round(rc_kwh, 2),
        "share": round(share, 4), "top_nodes": [label for label, _kwh in top],
    }  # fmt: skip
    top_node = env["td.energy.node"].sudo().search([("code", "=", top[0][0])], limit=1)
    return [common.finding("idle_machines:*", TITLE, text, qty * price, qty, evidence, node_code=top_node.code or None)]
