"""R-02: побудова добових фактів `td.energy.daily` одним SQL на пачку діб.

Атомарність: `DELETE … WHERE day = ANY(...)` + `INSERT` у транзакції виклику. Повторний запуск ідемпотентний.
"""

import time
from collections import defaultdict
from datetime import timedelta

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy_resources.tools import shifts

CHUNK = 31
PARTIAL_SHARE = 0.10
PLANT_SQL = """
SELECT i.day, i.ts_start,
       COALESCE(SUM(i.kwh) FILTER (WHERE i.role = 'feeder'), 0),
       COALESCE(SUM(i.cost) FILTER (WHERE i.role = 'feeder'), 0),
       COALESCE(SUM(i.kwh) FILTER (WHERE i.role = 'incomer'), 0),
       COALESCE(SUM(i.kwh_export) FILTER (WHERE i.role = 'incomer'), 0),
       COALESCE(SUM(i.cost) FILTER (WHERE i.role = 'incomer'), 0),
       COALESCE(SUM(i.kwh) FILTER (WHERE i.role = 'generation' AND m.model = 'sun2000'), 0),
       COALESCE(SUM(i.kwh) FILTER (WHERE i.role = 'generation' AND m.model = 'tedom'), 0),
       COALESCE(SUM(i.kwh) FILTER (WHERE i.role = 'consumer' AND n.alloc_role = 'direct'), 0),
       COUNT(*) FILTER (WHERE i.role = 'feeder'),
       COUNT(*) FILTER (WHERE i.role = 'feeder' AND i.quality = 'missing')
  FROM td_energy_interval i
  JOIN td_energy_meter m ON m.id = i.meter_id
  LEFT JOIN td_energy_node n ON n.id = i.node_id
 WHERE i.day = ANY(%s) AND i.role IN ('incomer', 'feeder', 'generation', 'consumer')
 GROUP BY i.day, i.ts_start
"""
NODE_SQL = """
SELECT i.day, i.node_id, n.area_id, SUM(i.kwh), SUM(COALESCE(i.cost, 0))
  FROM td_energy_interval i JOIN td_energy_node n ON n.id = i.node_id
 WHERE i.day = ANY(%s) AND i.role = 'consumer'
 GROUP BY i.day, i.node_id, n.area_id
"""
ALLOC_SQL = """
SELECT day, node_id, SUM(minutes) FILTER (WHERE kind = 'direct'), SUM(kwh) FILTER (WHERE kind = 'idle')
  FROM td_energy_alloc WHERE day = ANY(%s) AND node_id IS NOT NULL GROUP BY day, node_id
"""
NODE_AREA_SQL = "SELECT id, area_id FROM td_energy_node WHERE id = ANY(%s)"
USAGE_SQL = """
SELECT u.day, u.resource_id, SUM(u.qty), SUM(COALESCE(u.cost, 0)), SUM(u.co2_kg)
  FROM td_energy_usage u JOIN td_energy_resource r ON r.id = u.resource_id
 WHERE u.day = ANY(%s) AND ((r.code = 'el' AND u.flow = 'import') OR (r.code != 'el' AND u.flow = 'supply'))
 GROUP BY u.day, u.resource_id
"""
PLATE_SQL = """
SELECT v.day, v.value FROM td_energy_driver_value v JOIN td_energy_driver d ON d.id = v.driver_id
 WHERE d.code = 'plate_m2' AND v.day = ANY(%s)
"""
EL_SQL = "SELECT id FROM td_energy_resource WHERE code = 'el' ORDER BY id LIMIT 1"
COLUMNS = (
    "day, scope, resource_id, node_id, area_id, qty, cost, co2_kg, import_qty, export_qty, gen_pv_qty, gen_chp_qty, "
    "shift1_qty, shift2_qty, off_qty, cost_s1, cost_s2, cost_off, direct_s1, direct_s2, direct_off, plate_s1, "
    "plate_s2, plate_off, minutes, idle_qty, quality, built_at"
)
INSERT_SQL = "INSERT INTO td_energy_daily (%s) VALUES %%s" % COLUMNS
PLATE_UPDATE_SQL = """
UPDATE td_energy_daily SET
    plate_s1 = CASE WHEN direct_s1 + direct_s2 + direct_off > 0 THEN %(v)s * direct_s1 / (direct_s1 + direct_s2 + direct_off) ELSE %(v)s END,
    plate_s2 = CASE WHEN direct_s1 + direct_s2 + direct_off > 0 THEN %(v)s * direct_s2 / (direct_s1 + direct_s2 + direct_off) ELSE 0 END,
    plate_off = CASE WHEN direct_s1 + direct_s2 + direct_off > 0 THEN %(v)s * direct_off / (direct_s1 + direct_s2 + direct_off) ELSE 0 END
 WHERE scope = 'plant' AND day = %(d)s
"""  # noqa: E501


def split_plate(plate, direct):
    """R-02 п. 3: площа плит по змінах пропорційно прямим станкам; `Σ direct = 0` — усе в `plate_s1` (A-12)."""
    total = sum(direct)
    if total <= 0:
        return [plate, 0.0, 0.0]
    return [plate * d / total for d in direct]


def shift_slot(windows, ts):
    """Зміна слота за початком: 0 — перша, 1 — друга й далі, 2 — поза змінами; `windows` — `[(name, from, to)]`."""
    for pos, (_name, start, end) in enumerate(windows):
        if start <= ts < end:
            return min(pos, 1)
    return 2


def _chunks(days, size=CHUNK):
    days = sorted(set(days))
    for i in range(0, len(days), size):
        yield days[i : i + size]


def build(env, days, now=None):
    """Побудувати факти за `days` (київські дати); повертає `{"days": n, "rows": n, "seconds": f}`."""
    started = time.monotonic()
    now = now or dates.now_utc(env)
    cr = env.cr
    env.flush_all()
    calendar = shifts.load_windows(env)
    cr.execute(EL_SQL)
    el_row = cr.fetchone()
    el_id = el_row[0] if el_row else None
    total_days = total_rows = 0
    for chunk in _chunks(days):
        rows, built = _rows_for(cr, chunk, calendar, el_id, now)
        cr.execute("DELETE FROM td_energy_daily WHERE day = ANY(%s)", (chunk,))
        if rows:
            cr.execute_values(INSERT_SQL, rows, page_size=2000)
        total_days += len(built)
        total_rows += len(rows)
    env["td.energy.daily"].invalidate_model()
    return {"days": total_days, "rows": total_rows, "seconds": round(time.monotonic() - started, 3)}


def _rows_for(cr, chunk, calendar, el_id, now):
    cr.execute(PLATE_SQL, (chunk,))
    plate = {day: float(value) for day, value in cr.fetchall()}
    windows = {day: calendar.windows_for(day) for day in chunk}
    plant = defaultdict(lambda: defaultdict(float))
    cr.execute(PLANT_SQL, (chunk,))
    for day, ts, f_kwh, f_cost, i_kwh, i_exp, i_cost, pv, chp, direct, f_n, f_miss in cr.fetchall():
        p = plant[day]
        idx = shift_slot(windows[day], ts)
        p["qty"] += f_kwh
        p["import_qty"] += i_kwh
        p["export_qty"] += i_exp
        p["cost"] += i_cost
        p["gen_pv_qty"] += pv
        p["gen_chp_qty"] += chp
        p["shift", idx] += f_kwh
        p["cost_shift", idx] += f_cost
        p["direct", idx] += direct
        p["slots"] += f_n
        p["missing"] += f_miss
    node = defaultdict(dict)
    cr.execute(NODE_SQL, (chunk,))
    for day, node_id, area_id, kwh, cost in cr.fetchall():
        node[day][node_id] = {"area": area_id, "qty": kwh, "cost": cost, "minutes": 0.0, "idle": 0.0}
    cr.execute(ALLOC_SQL, (chunk,))
    alloc = cr.fetchall()
    extra = {nid for day, nid, _m, _i in alloc if nid not in node[day]}
    areas = {}
    if extra:
        cr.execute(NODE_AREA_SQL, (list(extra),))
        areas = dict(cr.fetchall())
    for day, node_id, minutes, idle in alloc:
        row = node[day].setdefault(
            node_id, {"area": areas.get(node_id), "qty": 0.0, "cost": 0.0, "minutes": 0.0, "idle": 0.0}
        )
        row["minutes"] += minutes or 0.0
        row["idle"] += idle or 0.0
    usage = defaultdict(list)
    cr.execute(USAGE_SQL, (chunk,))
    for day, resource_id, qty, cost, co2 in cr.fetchall():
        usage[day].append((resource_id, qty or 0.0, cost or 0.0, co2 or 0.0))
    rows, built = [], []
    for day in chunk:
        if day not in plant and not node.get(day) and not usage.get(day):
            continue
        built.append(day)
        p = plant.get(day) or defaultdict(float)
        share_missing = p["missing"] / p["slots"] if p["slots"] else 0.0
        quality = "partial" if share_missing > PARTIAL_SHARE else "ok"
        direct = [p["direct", 0], p["direct", 1], p["direct", 2]]
        plates = split_plate(plate.get(day, 0.0), direct)
        rows.append(
            (day, "plant", el_id, None, None, p["qty"], p["cost"], 0.0, p["import_qty"], p["export_qty"],
             p["gen_pv_qty"], p["gen_chp_qty"], p["shift", 0], p["shift", 1], p["shift", 2], p["cost_shift", 0],
             p["cost_shift", 1], p["cost_shift", 2], direct[0], direct[1], direct[2], plates[0], plates[1], plates[2],
             0.0, 0.0, quality, now)
        )  # fmt: skip
        for node_id, n in node.get(day, {}).items():
            rows.append(
                (day, "node", el_id, node_id, n["area"], n["qty"], n["cost"], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, n["minutes"], n["idle"], "ok", now)
            )  # fmt: skip
        for resource_id, qty, cost, co2 in usage.get(day, ()):
            rows.append(
                (day, "resource", resource_id, None, None, qty, cost, co2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, "ok", now)
            )  # fmt: skip
    return rows, built


def refresh_plate(env, days):
    """Перерахувати `plate_s1/s2/off` рядків `plant` після появи/зміни значення драйвера `plate_m2` (R-02 п. 3)."""
    cr = env.cr
    env.flush_all()
    days = sorted(set(days))
    cr.execute(PLATE_SQL, (days,))
    plate = dict(cr.fetchall())
    for day in days:
        cr.execute(PLATE_UPDATE_SQL, {"v": float(plate.get(day, 0.0)), "d": day})
    env["td.energy.daily"].invalidate_model()


def local_days_back(now, n):
    """`[today − n, …, today]` (київські дати) — для догону."""
    today = dates.local_day(now)
    return [today - timedelta(days=k) for k in range(n, -1, -1)]
