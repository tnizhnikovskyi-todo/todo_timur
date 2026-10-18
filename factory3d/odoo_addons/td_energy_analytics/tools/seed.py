"""R-20: демо-сид «Аналітики» (`td.energy.analytics._td_seed_demo`, API-14).

Передумова — електричний `_td_backfill` (W1 R-36). Кроки: ділянки → продукти → драйвери (`plate_m2`, `hdd`) → МО з
нарядами й журналом часу → розподіл енергії штатним рушієм W1 → добові факти → база й EnPI → бюджети.
Детермінізм — `td_energy.tools.backfill.rnd(seed, …)`; МО й значення драйверів сидуються з міткою
(`origin='td_energy_seed'`, `source_note='демо-сид'`, `note='демо-сид'`), тож `purge` видаляє лише сидоване.
"""

import csv
import io
import math
import statistics
import time
from datetime import datetime, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tools import file_open

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.backfill import rnd
from odoo.addons.td_energy_resources.tools import shifts

from .. import hooks
from . import budget as budget_tools
from . import drivers as driver_tools
from . import periods
from .fmt import round_half_up

ORIGIN = "td_energy_seed"
NOTE = "демо-сид"
BASE_KW_DAY = 5040.0  # 210 кВт × 24 год
PLATE_PEAK = 1290.0
EFF_GROWTH = 0.20  # приріст випуску в останні 12 тижнів при тій самій енергії (R-20 п. 3 дає 0,06 → EnPI ≈ 0,98)
RAMP_DAYS = 84
BASE_SHARE = 0.6
PRODUCTS = (
    ("DEMO-ENR-1", "Шафа-купе 2000", 3.1, 0.35),
    ("DEMO-ENR-2", "Кухня «Модерн» (комплект)", 8.4, 0.20),
    ("DEMO-ENR-3", "Фасад МДФ «Лофт», м²", 1.0, 0.25),
    ("DEMO-ENR-4", "Тумба ТВ-1600", 1.7, 0.10),
    ("DEMO-ENR-5", "Стіл письмовий", 1.2, 0.10),
)  # fmt: skip
FEEDER_SQL = """
SELECT day, SUM(kwh) FROM td_energy_interval WHERE role = 'feeder' AND day BETWEEN %s AND %s GROUP BY day ORDER BY day
"""
RANGE_SQL = "SELECT MIN(day), MAX(day), COUNT(DISTINCT day) FROM td_energy_interval WHERE role = 'feeder'"


def _check_access(env):
    if not (env.is_superuser() or env.user.has_group("td_factory3d.group_td_admin")):
        raise AccessError(env._("Генерувати демо-дані може лише адміністратор."))


def _csv_rows(name):
    with file_open("td_energy/data/%s" % name, "rb") as f:
        return list(csv.DictReader(io.StringIO(f.read().decode("utf-8"), newline="")))


def _local(day, hour):
    return datetime(day.year, day.month, day.day, hour)


def _ensure_direct_nodes(env):
    """Прямі споживачі (CSV `alloc_role=direct`) без робочого центру: створити РЦ і прив'язати вузол."""
    Node, WC = env["td.energy.node"].with_context(active_test=False), env["mrp.workcenter"]
    nodes = {n.code: n for n in Node.search([("kind", "=", "consumer")])}
    fixed = 0
    for row in _csv_rows("energy_nodes.csv"):
        if row["kind"] != "consumer" or row["alloc_role"] != "direct":
            continue
        node = nodes.get(row["code"])
        if node is None or (node.workcenter_id and node.alloc_role == "direct"):
            continue
        if not node.workcenter_id:
            name = row["workcenter"] or row["code"]
            node.workcenter_id = WC.search([("name", "=", name)], limit=1) or WC.create(
                {"name": name, "code": row["code"]}
            )
        node.alloc_role = "direct"
        fixed += 1
    return fixed


def _ensure_products(env):
    Product = env["product.product"].with_context(active_test=False)
    out = []
    for code, name, area, weight in PRODUCTS:
        product = Product.search([("default_code", "=", code)], limit=1)
        if not product:
            product = Product.create({"name": name, "default_code": code, "type": "consu", "td_plate_area_m2": area})
        out.append((product, area, weight))
    return out


def _pick(items, value):
    """Вибір за кумулятивними вагами (остання колонка — вага)."""
    total, acc = sum(item[-1] for item in items), 0.0
    for item in items:
        acc += item[-1] / total
        if value < acc:
            return item
    return items[-1]


def _range(env, days, today):
    """`(first, until)` — останні `days` діб із електричними даними; без сьогоднішньої (неповної) доби."""
    env.cr.execute(RANGE_SQL)
    lo, hi, count = env.cr.fetchone()
    if not count:
        raise UserError(
            env._("Немає електричних даних: спершу виконайте td.energy.interval._td_backfill(days=%s).", days)
        )
    until = min(hi, today - timedelta(days=1))
    first = max(lo, until - timedelta(days=days - 1))
    if until < first:
        raise UserError(env._("Немає завершених діб електричних даних: виконайте td.energy.interval._td_backfill."))
    return first, until


def _plate_series(env, first, until):
    """R-20 п. 3: `{day: (plate, act)}`; `act = max(0, E_D − 5040)/E_ref`, `E_ref` — медіана за буднями."""
    env.cr.execute(FEEDER_SQL, (first, until))
    energy = {day: float(kwh) for day, kwh in env.cr.fetchall()}
    weekday = [e - BASE_KW_DAY for d, e in energy.items() if d.weekday() < 5]
    if not weekday or statistics.median(weekday) <= 0:
        raise UserError(env._("Замало електричних даних для сиду: потрібні будні доби з навантаженням."))
    e_ref = statistics.median(weekday)
    out = {}
    for day, kwh in energy.items():
        act = max(0.0, kwh - BASE_KW_DAY) / e_ref
        r = min(1.0, max(0.0, ((day - (until - timedelta(days=RAMP_DAYS))).days) / RAMP_DAYS))
        out[day] = (PLATE_PEAK * act * (1.0 + EFF_GROWTH * r), act)
    return out


def _hdd(day):
    """R-20 п. 4: `T_mean = 8,5 + 11,5·cos(2π(doy − 200)/365)`, `hdd = max(0, 18 − T_mean)`."""
    t_mean = 8.5 + 11.5 * math.cos(2 * math.pi * (day.timetuple().tm_yday - 200) / 365)
    return max(0.0, 18.0 - t_mean)


def _seed_drivers(env, plates, first, until):
    cr = env.cr
    plate = env["td.energy.driver"].search([("code", "=", "plate_m2")], limit=1)
    hdd = env["td.energy.driver"].search([("code", "=", "hdd")], limit=1)
    if not plate or not hdd:
        raise UserError(env._("Немає драйверів plate_m2 і hdd (оновіть модуль)."))
    count, day = 0, first
    while day <= until:
        if day in plates:
            driver_tools.upsert(cr, plate.id, day, round(plates[day][0], 3), "estimated", NOTE)
            count += 1
        driver_tools.upsert(cr, hdd.id, day, round(_hdd(day), 3), "estimated", NOTE)
        day += timedelta(days=1)
    env["td.energy.driver.value"].invalidate_model()
    return count


def purge(env):
    """Видалити лише сидоване: МО `td_energy_seed` (з нарядами, журналом, розподілом), значення драйверів
    `демо-сид`, бази й бюджети `демо-сид` (EnPI баз — каскадом)."""
    cr = env.cr
    env.flush_all()
    cr.execute("SELECT id FROM mrp_production WHERE origin = %s", (ORIGIN,))
    mo_ids = [row[0] for row in cr.fetchall()]
    stats = {"mos": len(mo_ids)}
    if mo_ids:
        cr.execute("DELETE FROM td_energy_alloc WHERE production_id = ANY(%s)", (mo_ids,))
        cr.execute(
            """DELETE FROM mrp_workcenter_productivity WHERE workorder_id IN
                   (SELECT id FROM mrp_workorder WHERE production_id = ANY(%s))""",
            (mo_ids,),
        )
        cr.execute("DELETE FROM mrp_workorder WHERE production_id = ANY(%s)", (mo_ids,))
        cr.execute(
            "DELETE FROM stock_move WHERE production_id = ANY(%s) OR raw_material_production_id = ANY(%s)",
            (mo_ids, mo_ids),
        )
        cr.execute("DELETE FROM mrp_production WHERE id = ANY(%s)", (mo_ids,))
    cr.execute("DELETE FROM td_energy_driver_value WHERE source_note = %s", (NOTE,))
    stats["driver_values"] = cr.rowcount
    cr.execute(
        "DELETE FROM td_energy_enpi WHERE baseline_id IN (SELECT id FROM td_energy_baseline WHERE note = %s)", (NOTE,)
    )
    cr.execute("DELETE FROM td_energy_baseline WHERE note = %s", (NOTE,))
    stats["baselines"] = cr.rowcount
    cr.execute("DELETE FROM td_energy_budget WHERE note = %s", (NOTE,))
    stats["budgets"] = cr.rowcount
    env.invalidate_all()
    return stats


# --- МО, наряди, журнал часу ----------------------------------------------------------------------------------
def _window(calendar, day, i):
    """Інтервал доби для МО `i`: зміна з календаря (1-ша/2-га), у вихідні — 08:00–14:00 за Києвом."""
    wins = calendar.windows_for(day)
    if wins:
        _name, start, end = wins[i % len(wins)]
        return start, end
    return dates.to_utc(_local(day, 8)), dates.to_utc(_local(day, 14))


def _seed_orders(env, plates, seed, first, until):
    """R-20 п. 5: для діб із `plate > 0` — 3…5 МО (`origin='td_energy_seed'`), 2…4 наряди, журнал у вікнах змін."""
    ctx = dict(tracking_disable=True, mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True)
    Production = env["mrp.production"].with_context(**ctx)
    Workorder = env["mrp.workorder"].with_context(**ctx)
    Productivity = env["mrp.workcenter.productivity"].with_context(**ctx)
    cr = env.cr
    products = _ensure_products(env)
    nodes = env["td.energy.node"].search(
        [("kind", "=", "consumer"), ("alloc_role", "=", "direct"), ("workcenter_id", "!=", False)], order="code"
    )
    if not nodes:
        raise UserError(env._("Немає прямих споживачів із робочими центрами для сиду МО."))
    loss = env.ref("mrp.block_reason7")
    calendar = shifts.load_windows(env)
    stats = {"mos": 0, "workorders": 0}
    day = first
    while day <= until:
        plate = plates.get(day, (0.0, 0.0))[0]
        if plate >= 1.0:
            n = 3 + int(3 * rnd(seed, day, "n"))
            weights = [0.5 + rnd(seed, day, "w", i) for i in range(n)]
            picks = [_pick(products, rnd(seed, day, "p", i)) for i in range(n)]
            vals = []
            for i in range(n):
                product, area, _w = picks[i]
                qty = max(1, int(round(plate * weights[i] / sum(weights) / area))) if area > 0 else 1
                start, end = _window(calendar, day, i)
                vals.append(
                    {"product_id": product.id, "product_qty": qty, "origin": ORIGIN, "date_start": start,
                     "date_finished": end}
                )  # fmt: skip
            orders = Production.create(vals)
            wo_vals, logs = [], []
            for i, mo in enumerate(orders):
                start, end = _window(calendar, day, i)
                span = (end - start).total_seconds() / 60.0
                k = 2 + int(3 * rnd(seed, day, "k", i))
                for pos, j in enumerate(sorted(range(len(nodes)), key=lambda j: rnd(seed, day, "node", i, j))[:k]):
                    node = nodes[j]
                    minutes = min(span, 60 + int(120 * rnd(seed, day, "dur", i, pos)))
                    s = start + timedelta(minutes=max(0.0, span - minutes) * rnd(seed, day, "off", i, pos))
                    wo_vals.append(
                        {"name": "Операція %s" % node.code, "production_id": mo.id,
                         "workcenter_id": node.workcenter_id.id, "date_start": s,
                         "date_finished": s + timedelta(minutes=minutes)}
                    )  # fmt: skip
                    logs.append((s, s + timedelta(minutes=minutes), node.workcenter_id.id))
            workorders = Workorder.create(wo_vals)
            Productivity.create(
                [
                    {"workorder_id": wo.id, "workcenter_id": wc, "date_start": s, "date_end": e, "loss_id": loss.id,
                     "company_id": wo.company_id.id or env.company.id}
                    for wo, (s, e, wc) in zip(workorders, logs, strict=True)
                ]
            )  # fmt: skip
            env.flush_all()
            # завершення — SQL; складських проводок немає (допущення демо, A-17)
            cr.execute("UPDATE mrp_production SET state = 'done' WHERE id = ANY(%s)", (orders.ids,))
            cr.execute("UPDATE mrp_workorder SET state = 'done' WHERE id = ANY(%s)", (workorders.ids,))
            stats["mos"] += len(orders)
            stats["workorders"] += len(workorders)
            orders.invalidate_recordset()
            workorders.invalidate_recordset()
        day += timedelta(days=1)
    return stats


# --- база й бюджети -------------------------------------------------------------------------------------------
def _seed_baselines(env, first, until):
    """R-20 п. 7: `el/plant` — перші 60 % діб (не менше `baseline_min_days`); `gas/plant` — якщо є газові факти."""
    min_days = periods.param_int(env, "baseline_min_days", 30)
    length = max(min_days, int(((until - first).days + 1) * BASE_SHARE))
    specs = [("el", "plate_m2", True)]
    env.cr.execute(
        """SELECT COUNT(*) FROM td_energy_daily d JOIN td_energy_resource r ON r.id = d.resource_id
            WHERE d.scope = 'resource' AND r.code = 'gas' AND d.day BETWEEN %s AND %s""",
        (first, until),
    )
    if env.cr.fetchone()[0] >= max(min_days, 20):
        specs.append(("gas", "hdd", False))
    made = 0
    for resource, driver, required in specs:
        driver_rec = env["td.energy.driver"].search([("code", "=", driver)], limit=1)
        base = env["td.energy.baseline"].create(
            {
                "resource_id": env["td.energy.resource"].get_by_code(resource).id, "scope": "plant",
                "period_from": first, "period_to": min(until, first + timedelta(days=length - 1)), "note": NOTE,
                "line_ids": [(0, 0, {"driver_id": driver_rec.id})],
            }
        )  # fmt: skip
        try:
            base.action_fit()
            base.action_approve()
            made += 1
        except UserError:
            base.unlink()
            if required:
                raise
    return made


def _seed_budgets(env, today):
    """R-20 п. 8: поточний і 3 попередні місяці (затверджені); минулі — `round(1,02·факт, −3)`, поточний — прогноз."""
    cr = env.cr
    start = periods.shift_months(today, -3)
    cr.execute(
        """SELECT d.day, SUM(d.cost) FROM td_energy_daily d JOIN td_energy_resource r ON r.id = d.resource_id
            WHERE d.scope = 'resource' AND r.in_energy_cost AND d.day >= %s GROUP BY d.day""",
        (start - timedelta(days=60),),
    )
    costs = {day: float(cost or 0.0) for day, cost in cr.fetchall()}
    made = 0
    for back in range(3, -1, -1):
        first = periods.shift_months(today, -back)
        actual = {d: v for d, v in costs.items() if first <= d < periods.shift_months(first, 1)}
        if not actual:
            continue
        if back == 0:
            typical = budget_tools.typical_by_weekday(costs, today, periods.param_int(env, "forecast_weeks", 8), 1)
            res = budget_tools.status(1.0, first, today, actual, typical)
            value = res["forecast"] if res["forecast"] is not None else sum(actual.values())
        else:
            value = sum(actual.values())
        amount = float(round_half_up(1.02 * value / 1000.0)) * 1000.0
        if amount <= 0:
            continue
        rec = env["td.energy.budget"].search([("month", "=", first), ("resource_id", "=", False)], limit=1)
        if rec and rec.note != NOTE:
            continue  # бюджет, введений людиною, не чіпаємо
        if rec:
            rec.write({"amount_uah": amount, "state": "draft"})
        else:
            rec = env["td.energy.budget"].create({"month": first, "amount_uah": amount, "note": NOTE})
        rec.action_approve()
        made += 1
    return made


# --- вхід -----------------------------------------------------------------------------------------------------
def run(env, days=400, seed=20261018, purge_only=False, with_mo=True, with_baseline=True, with_budget=True):
    """R-20: `{"days", "products", "mos", "workorders", "alloc_rows", "baselines", "budgets", "seconds"}`.

    `env` — користувач-адміністратор; сам сид виконується від імені суперкористувача."""
    _check_access(env)
    env = env(su=True, context=dict(env.context, tracking_disable=True))
    started = time.monotonic()
    now = dates.now_utc(env)
    today = dates.local_day(now)
    if purge_only:
        stats = purge(env)
        stats["seconds"] = round(time.monotonic() - started, 2)
        return stats
    days = int(days)
    if not 1 <= days <= 400:
        raise UserError(env._("Кількість діб має бути від 1 до 400."))
    env.flush_all()
    first, until = _range(env, days, today)
    purge(env)
    hooks._assign_areas(env)
    _ensure_direct_nodes(env)
    products = _ensure_products(env)
    plates = _plate_series(env, first, until)
    _seed_drivers(env, plates, first, until)
    total = (until - first).days + 1
    stats = {"days": total, "products": len(products), "mos": 0, "workorders": 0, "alloc_rows": 0}
    day_list = [first + timedelta(days=i) for i in range(total)]
    if with_mo:
        stats.update(_seed_orders(env, plates, seed, first, until))
        stats["alloc_rows"] = env["td.energy.alloc"]._f3d_alloc_days(day_list, now=now).get("rows", 0)
    env["td.energy.daily"]._td_build_days(day_list)
    stats["baselines"] = _seed_baselines(env, first, until) if with_baseline else 0
    stats["budgets"] = _seed_budgets(env, today) if with_budget else 0
    env.invalidate_all()
    stats["seconds"] = round(time.monotonic() - started, 2)
    return stats
