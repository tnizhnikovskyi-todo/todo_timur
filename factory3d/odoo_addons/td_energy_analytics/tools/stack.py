"""R-08: стовпці «енергія за ділянками» (SQL по `td_energy_daily`, `scope='node'`)."""

from . import periods
from .fmt import r_int, round_half_up

NONE_CODE = "NONE"
NONE_NAME = "Без ділянки"
NONE_COLOR = "#d1d5db"
AREAS_SQL = "SELECT code, name, color FROM td_energy_area WHERE active ORDER BY sequence, id"
NODES_SQL = """
SELECT d.day, a.code, SUM(d.qty) FROM td_energy_daily d LEFT JOIN td_energy_area a ON a.id = d.area_id
 WHERE d.scope = 'node' AND d.day BETWEEN %s AND %s GROUP BY d.day, a.code
"""


def build_stack(ctx):
    """`stack` (R-08): серії за участками, стовпці за кошиками R-01, шкала `y_max = round(1,08·max)`.

    Немає жодних даних по вузлах у вікні — `bars = []` (порожній стан екрана «Немає даних»)."""
    cr = ctx.cr
    cr.execute(AREAS_SQL)
    areas = [{"code": code, "name": name, "color": color} for code, name, color in cr.fetchall()]
    buckets = periods.buckets(ctx.period, ctx.today)
    index = periods.bucket_index(ctx.period, ctx.today)
    sums = [dict() for _ in buckets]
    cr.execute(NODES_SQL, (ctx.f, ctx.t))
    for day, code, qty in cr.fetchall():
        slot = index.get(day)
        if slot is None:
            continue
        key = code or NONE_CODE
        sums[slot][key] = sums[slot].get(key, 0.0) + float(qty or 0.0)
    has_data = any(sums)
    none_total = sum(s.get(NONE_CODE, 0.0) for s in sums)
    if none_total > 0:
        areas.append({"code": NONE_CODE, "name": NONE_NAME, "color": NONE_COLOR})
    codes = [a["code"] for a in areas]
    bars = []
    for bucket, values in zip(buckets if has_data else [], sums, strict=False):
        shown = {code: r_int(values.get(code, 0.0)) for code in codes}
        bars.append({"key": bucket["key"], "label": bucket["label"], "total": sum(shown.values()), "values": shown})
    peak = max((bar["total"] for bar in bars), default=0)
    y_max = int(round_half_up(1.08 * peak)) if peak > 0 else 3
    ticks = [int(round_half_up(y_max / 3)), int(round_half_up(2 * y_max / 3)), y_max]
    return {
        "bar_unit": periods.BAR_UNITS[ctx.period], "unit": periods.UNITS[ctx.period], "y_max": y_max,
        "ticks": ticks, "areas": areas, "bars": bars,
    }  # fmt: skip


def gap_pct(ctx, stack=None):
    """`(Σ plant.qty − Σ усіх сегментів)/Σ plant.qty · 100` (R-08 п. 4); `None`, якщо споживання завода 0."""
    stack = stack or build_stack(ctx)
    plant = ctx.plant["qty"]
    if plant <= 0:
        return None
    total = sum(bar["total"] for bar in stack["bars"])
    return round_half_up((plant - total) / plant * 100, 2)
