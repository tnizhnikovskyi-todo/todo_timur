"""W1-A: R-28 — факт доби за 15-хв слотами, типовий день і прогноз до кінця доби. Без залежності від UI."""

from datetime import timedelta

from . import dates
from .dates import local_slot_index

SLOTS = 96
SLOT_H = 0.25  # година
FACT_SQL = """
SELECT i.ts_start, i.role, m.model, SUM(i.kwh), SUM(i.kwh_export), MAX(i.price)
  FROM td_energy_interval i JOIN td_energy_meter m ON m.id = i.meter_id
 WHERE i.ts_start >= %s AND i.ts_start < %s
   AND (i.role IN ('feeder', 'incomer') OR (i.role = 'generation' AND m.model = 'sun2000'))
 GROUP BY i.ts_start, i.role, m.model
"""
TYPICAL_SQL = """
SELECT i.day, i.ts_start, i.role, SUM(i.kwh), COUNT(*), COUNT(*) FILTER (WHERE i.quality = 'missing')
  FROM td_energy_interval i JOIN td_energy_meter m ON m.id = i.meter_id
 WHERE i.day IN %s AND (i.role = 'feeder' OR (i.role = 'generation' AND m.model = 'sun2000'))
 GROUP BY i.day, i.ts_start, i.role
"""


def slot_table(cr, start, end):
    """`{ts_start: {"cons": кВт·год фідерів, "pv": кВт·год СЕС, "net": Σ(kwh − kwh_export) вводів, "price": грн}}`."""
    cr.execute(FACT_SQL, (start, end))
    table = {}
    for ts, role, _model, kwh, kwh_export, price in cr.fetchall():
        row = table.setdefault(ts, {"cons": None, "pv": None, "net": None, "price": None})
        if role == "feeder":
            row["cons"] = kwh or 0.0
        elif role == "generation":
            row["pv"] = kwh or 0.0
        else:
            row["net"] = (kwh or 0.0) - (kwh_export or 0.0)
            row["price"] = price
    return table


def day_arrays(table):
    """Добові масиви (96) за локальними індексами слотів: `cons`, `pv`, `grid` у кВт; `None` — немає даних."""
    cons, pv, net = [None] * SLOTS, [None] * SLOTS, [None] * SLOTS
    for ts, row in sorted(table.items()):
        idx = local_slot_index(ts)
        if row["cons"] is not None:
            cons[idx] = row["cons"] * 4
        if row["pv"] is not None:
            pv[idx] = row["pv"] * 4
        if row["net"] is not None:
            net[idx] = row["net"] * 4
    return cons, pv, net


def typical_day(cr, today, weeks, min_days):
    """R-28 п. 2: `{"cons": [96], "pv": [96], "days_used": n, "ok": bool}` за `weeks` однакових днів тижня."""
    cands = [today - timedelta(days=7 * k) for k in range(1, int(weeks) + 1)]
    if not cands:
        return {"cons": [None] * SLOTS, "pv": [None] * SLOTS, "days_used": 0, "ok": False}
    cr.execute(TYPICAL_SQL, (tuple(cands),))
    per_day = {}
    for day, ts, role, kwh, cnt, missing in cr.fetchall():
        d = per_day.setdefault(day, {"feeder_rows": 0, "feeder_missing": 0, "cons": {}, "pv": {}})
        idx = local_slot_index(ts)
        if role == "feeder":
            d["feeder_rows"] += cnt
            d["feeder_missing"] += missing
            d["cons"][idx] = (kwh or 0.0) * 4
        else:
            d["pv"][idx] = (kwh or 0.0) * 4
    valid = [d for d in per_day.values() if d["feeder_rows"] and d["feeder_missing"] <= 0.1 * d["feeder_rows"]]
    cons, pv = [None] * SLOTS, [None] * SLOTS
    for s in range(SLOTS):
        cs = [d["cons"][s] for d in valid if s in d["cons"]]
        ps = [d["pv"][s] for d in valid if s in d["pv"]]
        cons[s] = sum(cs) / len(cs) if cs else None
        pv[s] = sum(ps) / len(ps) if ps else None
    return {"cons": cons, "pv": pv, "days_used": len(valid), "ok": len(valid) >= int(min_days)}


def forecast(typ, pv_fact, now_slot, cons_live=None, pv_live=None, grid_live=None):
    """R-28 п. 3: `(cons_fc, grid_fc, k_pv)`; без достатньої історії — `None, None, None`."""
    if not typ["ok"]:
        return None, None, None
    num = den = 0.0
    for s in range(min(now_slot, SLOTS)):
        if pv_fact[s] is not None and typ["pv"][s] is not None:
            num += pv_fact[s]
            den += typ["pv"][s]
    k_pv = max(0.3, min(1.5, num / den)) if den else 1.0
    cons_fc, grid_fc = [None] * SLOTS, [None] * SLOTS
    for s in range(now_slot, SLOTS):
        typ_cons = typ["cons"][s]
        if s == now_slot:
            cons = cons_live if cons_live is not None else typ_cons
            if grid_live is not None:
                grid = grid_live
            else:
                typ_pv = typ["pv"][s] or 0.0
                pv = pv_live if pv_live is not None else typ_pv * k_pv
                grid = cons - pv if cons is not None else None
        else:
            cons = typ_cons
            grid = None if cons is None else cons - (typ["pv"][s] or 0.0) * k_pv
        cons_fc[s] = None if cons is None else round(cons, 1)
        grid_fc[s] = None if grid is None else round(grid, 1)
    return cons_fc, grid_fc, k_pv


def forecast_energy(grid_fc, now_slot):
    """Σ_{s>now_slot} max(0, grid_fc[s])·0,25 — кВт·год до кінця доби."""
    if grid_fc is None:
        return None
    return sum(max(0.0, g) * SLOT_H for g in grid_fc[now_slot + 1 :] if g is not None)


def day_start_slot(now_utc):
    """Індекс поточного слота доби (0…95) за локальним часом."""
    return local_slot_index(dates.floor15(now_utc))
