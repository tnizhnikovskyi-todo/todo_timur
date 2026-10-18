"""R-04, R-05: ряди фактів і драйверів для моделі бази, EnPI за добами, підсумки періоду (SQL + чисті функції)."""

from collections import defaultdict

from .fmt import ceil_to, floor_to, round_half_up

ENPI_UPSERT_SQL = """
INSERT INTO td_energy_enpi (baseline_id, day, actual, expected, enpi, drivers, quality)
VALUES %s
ON CONFLICT (baseline_id, day) DO UPDATE SET actual = EXCLUDED.actual, expected = EXCLUDED.expected,
    enpi = EXCLUDED.enpi, drivers = EXCLUDED.drivers, quality = EXCLUDED.quality
"""
MIN_COVERAGE = 0.5


def actual_series(cr, resource_code, scope, area_id, d_from, d_to):
    """`{day: (qty, quality)}` — фактичне споживання за R-04 п. 1 (`quality` — з рядка `plant`; газ — `ok`)."""
    out = {}
    if resource_code == "gas":
        cr.execute(
            """SELECT d.day, d.qty FROM td_energy_daily d JOIN td_energy_resource r ON r.id = d.resource_id
                WHERE d.scope = 'resource' AND r.code = 'gas' AND d.day BETWEEN %s AND %s""",
            (d_from, d_to),
        )
        return {day: (float(qty or 0.0), "ok") for day, qty in cr.fetchall()}
    cr.execute(
        "SELECT day, qty, quality FROM td_energy_daily WHERE scope = 'plant' AND day BETWEEN %s AND %s",
        (d_from, d_to),
    )
    plant = {day: (float(qty or 0.0), quality) for day, qty, quality in cr.fetchall()}
    if scope != "area":
        return plant
    cr.execute(
        """SELECT day, SUM(qty) FROM td_energy_daily WHERE scope = 'node' AND area_id = %s AND day BETWEEN %s AND %s
            GROUP BY day""",
        (area_id, d_from, d_to),
    )
    for day, qty in cr.fetchall():
        out[day] = (float(qty or 0.0), plant.get(day, (0.0, "ok"))[1])
    return out


def driver_series(cr, driver_ids, d_from, d_to):
    """`{driver_id: {day: value}}`."""
    out = defaultdict(dict)
    if not driver_ids:
        return out
    cr.execute(
        "SELECT driver_id, day, value FROM td_energy_driver_value WHERE driver_id = ANY(%s) AND day BETWEEN %s AND %s",
        (list(driver_ids), d_from, d_to),
    )
    for driver_id, day, value in cr.fetchall():
        out[driver_id][day] = float(value)
    return out


def fit_rows(actual, series, driver_ids):
    """Доби для підгонки: є факт (`quality='ok'`) і значення **всіх** драйверів → `[(day, [x…], y)]`."""
    rows = []
    for day in sorted(actual):
        qty, quality = actual[day]
        if quality != "ok":
            continue
        values = [series.get(driver_id, {}).get(day) for driver_id in driver_ids]
        if any(v is None for v in values):
            continue
        rows.append((day, values, qty))
    return rows


def expected(const, coefs, values):
    """`const + Σ coef·x`; немає значення драйвера → `None`."""
    if any(v is None for v in values):
        return None
    return const + sum(c * v for c, v in zip(coefs, values, strict=True))


def enpi_rows(baseline_id, const, coefs, driver_ids, codes, actual, series, days):
    """Рядки `td_energy_enpi` за `days` (R-05 п. 1): `(baseline_id, day, actual, expected, enpi, drivers, quality)`."""
    from psycopg2.extras import Json

    rows = []
    for day in sorted(days):
        if day not in actual:
            continue
        qty, quality = actual[day]
        values = [series.get(driver_id, {}).get(day) for driver_id in driver_ids]
        exp = expected(const, coefs, values)
        drivers = {code: value for code, value in zip(codes, values, strict=True) if value is not None}
        if exp is None:
            row_quality = "no_driver"
        else:
            row_quality = "partial" if quality == "partial" else "ok"
        ratio = qty / exp if exp is not None and exp > 0 else None
        rows.append((baseline_id, day, qty, exp, ratio, Json(drivers), row_quality))
    return rows


def totals(sum_actual, sum_expected, count, window_days, avg_price=None):
    """R-05 п. 2: `{enpi, saving_pct, saving_qty, coverage, actual, expected, n[, saving_cost]}`."""
    coverage = count / window_days if window_days else 0.0
    out = {
        "n": count, "coverage": round(coverage, 4), "actual": sum_actual or 0.0, "expected": sum_expected or 0.0,
        "enpi": None, "saving_pct": None, "saving_qty": None,
    }  # fmt: skip
    if count and sum_expected and sum_expected > 0 and coverage >= MIN_COVERAGE:
        out["enpi"] = round(sum_actual / sum_expected, 4)
        out["saving_pct"] = round_half_up((1 - sum_actual / sum_expected) * 100, 1)
        out["saving_qty"] = round(sum_expected - sum_actual, 3)
        if avg_price is not None:
            out["saving_cost"] = round(out["saving_qty"] * avg_price, 2)
    return out


def week_axis(values_mwh):
    """R-05 п. 3: `y_min = floor5(0,95·min)`, `y_max = ceil5(1,05·max)` (кратно 5 МВт·год)."""
    values = [v for v in values_mwh if v is not None]
    if not values:
        return 0, 5
    return int(floor_to(0.95 * min(values), 5)), int(ceil_to(1.05 * max(values), 5))
