"""R-09: теплокарта «година × день тижня» (SQL по `td_energy_interval`)."""

from .fmt import ceil_to, round_half_up
from .periods import WEEKDAYS

LEVELS = 5
HEAT_SQL = """
SELECT EXTRACT(ISODOW FROM day)::int, hour_local, SUM(kwh), COUNT(DISTINCT day)
  FROM td_energy_interval
 WHERE role = 'feeder' AND day BETWEEN %s AND %s AND quality != 'missing'
 GROUP BY 1, 2
"""


def build_heatmap(ctx):
    """`heatmap` (R-09): 7 рядків (пн…нд) × 24 години, кВт (середнє за той самий день тижня), `null` — немає даних."""
    ctx.cr.execute(HEAT_SQL, (ctx.f, ctx.t))
    cells = [[None] * 24 for _ in range(7)]
    for isodow, hour, kwh, n_days in ctx.cr.fetchall():
        if 0 <= hour < 24 and n_days:
            cells[isodow - 1][hour] = round(float(kwh) / n_days, 1)
    values = [v for row in cells for v in row if v is not None]
    if not values:
        return {"days": list(WEEKDAYS), "cells": cells, "max_ref": 50, "levels": LEVELS, "base_load_kw": None}
    return {
        "days": list(WEEKDAYS), "cells": cells, "max_ref": int(max(50, ceil_to(max(values), 50))), "levels": LEVELS,
        "base_load_kw": int(round_half_up(min(values) / 5) * 5),
    }  # fmt: skip
