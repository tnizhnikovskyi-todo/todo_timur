"""R-03: суточні значення драйверів нормалізації (SQL). Без ORM-циклів: одне читання на доби/драйвер."""

PLATE_SQL = """
SELECT COALESCE(SUM(sm.quantity * mu.factor / NULLIF(pu.factor, 0) * pt.td_plate_area_m2), 0)
  FROM stock_move sm
  JOIN product_product pp ON pp.id = sm.product_id
  JOIN product_template pt ON pt.id = pp.product_tmpl_id
  JOIN uom_uom mu ON mu.id = sm.product_uom
  JOIN uom_uom pu ON pu.id = pt.uom_id
 WHERE sm.production_id IS NOT NULL AND sm.state = 'done' AND sm.date >= %s AND sm.date < %s
"""
HOUR_SQL = """
SELECT AVG(h.v_avg), COUNT(*) FROM td_reading_hour h JOIN td_signal s ON s.id = h.signal_id
 WHERE s.code = %s AND h.hour >= %s AND h.hour < %s
"""
RAW_SQL = """
SELECT AVG(r.value), COUNT(*) FROM td_reading r JOIN td_signal s ON s.id = r.signal_id
 WHERE s.code = %s AND r.ts >= %s AND r.ts < %s
"""
UPSERT_SQL = """
INSERT INTO td_energy_driver_value (driver_id, day, value, quality, source_note)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (driver_id, day) DO UPDATE SET value = EXCLUDED.value, quality = EXCLUDED.quality,
    source_note = EXCLUDED.source_note
 WHERE td_energy_driver_value.quality != 'manual'
"""
MIN_HOURS = 18
MIN_RAW = 50


def has_plate_products(cr):
    cr.execute("SELECT 1 FROM product_template WHERE td_plate_area_m2 > 0 LIMIT 1")
    return bool(cr.fetchone())


def plate_value(cr, d0, d1):
    """Площа плит доби `[d0, d1)` (UTC): Σ (кількість готової продукції МО × `td_plate_area_m2`)."""
    cr.execute(PLATE_SQL, (d0, d1))
    return float(cr.fetchone()[0] or 0.0)


def mean_temperature(cr, signal_code, d0, d1):
    """Середня температура доби: часові агрегати (≥ 18 год), інакше сирі показання (≥ 50), інакше `None`."""
    cr.execute(HOUR_SQL, (signal_code, d0, d1))
    avg, count = cr.fetchone()
    if avg is not None and count >= MIN_HOURS:
        return float(avg)
    cr.execute(RAW_SQL, (signal_code, d0, d1))
    avg, count = cr.fetchone()
    if avg is not None and count >= MIN_RAW:
        return float(avg)
    return None


def hdd(t_mean, base_temp):
    return max(0.0, float(base_temp) - float(t_mean))


def day_value(cr, driver, d0, d1):
    """`(value, quality, note)` драйвера за добу `[d0, d1)` (UTC) або `None` — рядок не створюється."""
    if driver.source_kind == "mrp_area":
        if not has_plate_products(cr):
            return None
        return plate_value(cr, d0, d1), "estimated", "MRP"
    if driver.source_kind == "weather_hdd":
        t_mean = mean_temperature(cr, driver.temp_signal_code, d0, d1)
        if t_mean is None:
            return None
        return hdd(t_mean, driver.base_temp_c), "measured", "T_mean %.1f" % t_mean
    return None


def upsert(cr, driver_id, day, value, quality, note):
    cr.execute(UPSERT_SQL, (driver_id, day, round(value, 3), quality, note))
