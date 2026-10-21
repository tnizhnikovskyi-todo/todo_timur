"""R-59 (SPEC 8.4.5): добові серії енергії для 3D — один запит на добу, 96 слотів по 15 хв за місцевим часом (Київ).

Джерело — `td.energy.interval` (ті самі записи, що рахує `td_energy_analytics`): вводи (`incomer`: імпорт, експорт,
вартість = кВт·год × ціна зони тарифу, збережена при побудові слота), власна генерація (`generation`), споживачі
(`consumer`: середня кВт слота). Читання — SQL лише потрібних колонок; вартість віддається тільки коли викликач
має право на неї (`with_cost`), інакше ключів `cost` у відповіді немає.

Лічильник «Енергія з мережі з початку доби» = визначення пульта ГРЩ («З мережі сьогодні»): імпорт, нетований за слотом
(Σ вводів: імпорт − віддача, не менше 0) × ціна слота; `grid.kwh` лишається сумою імпорту вводів (потоки в 3D), а
нетований імпорт — `grid.net`. Віддача СЕС в ₴ не зараховується (ціна віддачі тарифу сюди не входить).
"""

from odoo.addons.td_energy.tools import dates

P = "td.energy_viewer3d."
SLOTS = 96
SLOT_MIN = 15
SCHEMA = 1
KIOSK_COST_PARAM = P + "kiosk_cost"
COST_GROUP = "td_energy.group_td_energy_cost"
# слот за місцевим часом (як `dates.local_slot_index`): доба переходу годинника має 92/100 слотів — колізію сумуємо
SQL = """
SELECT EXTRACT(HOUR FROM l.t)::int * 4 + EXTRACT(MINUTE FROM l.t)::int / 15 AS slot,
       i.role, n.code, SUM(i.kwh), SUM(i.kwh_export), AVG(i.kw_avg), SUM(i.cost)
  FROM td_energy_interval i
  JOIN td_energy_node n ON n.id = i.node_id
 CROSS JOIN LATERAL (SELECT i.ts_start AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv' AS t) l
 WHERE i.day = %s AND i.role IN ('incomer', 'generation', 'consumer')
 GROUP BY 1, i.role, n.code
"""  # noqa: E501


def cost_allowed(env, kiosk=False):
    """Вартість у серіях: користувач з `group_td_energy_cost`; у киоску (AC-65: вартості немає) — лише коли
    адміністратор явно ввімкнув `td.energy_viewer3d.kiosk_cost` (екран планірки «стіна»)."""
    if kiosk or env.context.get("kiosk"):
        raw = env["ir.config_parameter"].sudo().get_param(KIOSK_COST_PARAM, "False")
        return raw in ("True", "true", "1")
    return env.user.has_group(COST_GROUP)


def build(env, day, with_cost):
    """`day` — місцева дата (`date`). Повертає словник відповіді `GET …/energy/day` (JSON-сумісний)."""
    env["td.energy.interval"].flush_model()
    cr = env.cr
    cr.execute(SQL, (day,))
    kwh = [0.0] * SLOTS
    exp = [0.0] * SLOTS
    cost = [0.0] * SLOTS
    gen = [0.0] * SLOTS
    consumers = {}
    built_to = -1
    for slot, role, code, s_kwh, s_exp, a_kw, s_cost in cr.fetchall():
        if role == "incomer":
            kwh[slot] += float(s_kwh or 0.0)
            exp[slot] += float(s_exp or 0.0)
            cost[slot] += float(s_cost or 0.0)
            built_to = max(built_to, slot)
        elif role == "generation":
            gen[slot] += float(s_kwh or 0.0)
        else:
            consumers.setdefault(code, [0.0] * SLOTS)[slot] = round(float(a_kw or 0.0), 2)
    net = [max(0.0, kwh[s] - exp[s]) for s in range(SLOTS)]
    cost_net = [cost[s] * net[s] / kwh[s] if kwh[s] > 0 else 0.0 for s in range(SLOTS)]  # ціна слота = cost / kwh
    peak_slot = max(range(SLOTS), key=net.__getitem__) if built_to >= 0 else -1
    tariff = env["td.energy.tariff"].sudo()._td_tariff_at(dates.local_day_bounds(day)[0])
    totals = {
        "kwh": round(sum(kwh), 3),
        "export_kwh": round(sum(exp), 3),
        "gen_kwh": round(sum(gen), 3),
        "peak_kw": round(net[peak_slot] * 4, 2) if peak_slot >= 0 else 0.0,
        "peak_slot": peak_slot,
    }
    totals["net_kwh"] = round(sum(net), 3)
    grid = {"kwh": [round(v, 3) for v in kwh], "export": [round(v, 3) for v in exp], "net": [round(v, 3) for v in net]}
    if with_cost:
        grid["cost"] = [round(v, 2) for v in cost_net]
        totals["cost"] = round(sum(cost_net), 2)
    return {
        "schema": SCHEMA,
        "day": day.isoformat(),
        "slot_min": SLOT_MIN,
        "built_to": built_to,
        "contract_kw": tariff.contract_kw if tariff else None,
        "cost": bool(with_cost),
        "grid": grid,
        "gen": {"kwh": [round(v, 3) for v in gen]},
        "consumers": consumers,
        "totals": totals,
    }
