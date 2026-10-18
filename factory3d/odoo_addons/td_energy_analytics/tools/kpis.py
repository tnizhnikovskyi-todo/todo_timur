"""R-07: контекст запиту аналітики (вікно, база, спільні вибірки) і 7 KPI екрана.

`Context` кешує спільні SQL-вибірки на один запит API (≤ 60 SQL на `get_dashboard`); KPI збирає `build_kpis`.
"""

from functools import cached_property

from odoo.addons.td_energy.tools import dates

from . import periods
from .fmt import fmt_dec, fmt_int, fmt_signed, r_int, round_half_up, spec_value

COST_GROUP = "td_energy.group_td_energy_cost"
MANAGER_GROUP = "td_energy.group_td_energy_manager"
NO_BASE = "База не задана"
NO_DATA = "Недостатньо даних бази"
HDD_COLD, HDD_WARM = 1.10, 0.90

PLANT_SQL = """
SELECT COALESCE(SUM(qty), 0), COALESCE(SUM(import_qty), 0), COALESCE(SUM(export_qty), 0),
       COALESCE(SUM(gen_pv_qty), 0), COALESCE(SUM(gen_chp_qty), 0), COUNT(*),
       COUNT(*) FILTER (WHERE quality = 'partial')
  FROM td_energy_daily WHERE scope = 'plant' AND day BETWEEN %s AND %s
"""
RESOURCES_SQL = """
SELECT r.code, r.name, r.sequence, r.in_energy_cost, COALESCE(SUM(d.qty), 0), COALESCE(SUM(d.cost), 0),
       COALESCE(SUM(d.co2_kg), 0)
  FROM td_energy_daily d JOIN td_energy_resource r ON r.id = d.resource_id
 WHERE d.scope = 'resource' AND d.day BETWEEN %s AND %s
 GROUP BY r.id ORDER BY r.sequence, r.id
"""
SPEC_SQL = """
SELECT COALESCE(SUM(p.qty), 0), COALESCE(SUM(v.value), 0)
  FROM td_energy_daily p
  JOIN td_energy_driver_value v ON v.day = p.day AND v.value > 0
  JOIN td_energy_driver d ON d.id = v.driver_id AND d.code = 'plate_m2'
 WHERE p.scope = 'plant' AND p.day BETWEEN %s AND %s
"""
ENPI_SQL = """
SELECT COALESCE(SUM(actual), 0), COALESCE(SUM(expected), 0), COUNT(*) FROM td_energy_enpi
 WHERE baseline_id = %s AND day BETWEEN %s AND %s AND expected IS NOT NULL AND quality != 'no_driver'
"""
HDD_SQL = """
SELECT AVG(v.value) FROM td_energy_driver_value v JOIN td_energy_driver d ON d.id = v.driver_id
 WHERE d.code = 'hdd' AND v.day BETWEEN %s AND %s
"""
COGS_SQL = """
SELECT COALESCE(SUM(mp.td_energy_cost), 0), COALESCE(SUM(v.val), 0)
  FROM mrp_production mp
  LEFT JOIN LATERAL (SELECT SUM(sm.value) AS val FROM stock_move sm
                      WHERE sm.production_id = mp.id AND sm.state = 'done') v ON TRUE
 WHERE mp.state = 'done' AND mp.date_finished >= %s AND mp.date_finished < %s
"""


class Context:
    """Вікно періоду, права, база й кешовані вибірки одного виклику API."""

    def __init__(self, env, period, today=None):
        env.flush_all()  # сирі SQL нижче бачать незбережені ORM-записи
        self.env = env
        self.cr = env.cr
        self.period = period
        self.now = dates.now_utc(env)
        self.today = today or dates.local_day(self.now)
        self.f, self.t = periods.window(period, self.today)
        self.cost_access = env.is_superuser() or env.user.has_group(COST_GROUP)
        self.manager = env.is_superuser() or env.user.has_group(MANAGER_GROUP)
        self._baselines = {}

    # --- база -------------------------------------------------------------------------------------------
    def baseline(self, code="el"):
        """Затверджена модель `code/plant` або порожній рекордсет."""
        if code not in self._baselines:
            self._baselines[code] = (
                self.env["td.energy.baseline"]
                .sudo()
                .search(
                    [
                        ("state", "=", "approved"), ("resource_id.code", "=", code), ("scope", "=", "plant"),
                        ("company_id", "in", self.env.companies.ids),
                    ],
                    order="period_to desc, id desc", limit=1,
                )
            )  # fmt: skip
        return self._baselines[code]

    def baseline_window(self, code="el"):
        base = self.baseline(code)
        return (base.period_from, base.period_to) if base else None

    def meta_baseline(self):
        base = self.baseline("el")
        if not base:
            return None
        first, last = base.period_from, base.period_to
        label = str(first.year) if first.year == last.year else "%d–%d" % (first.year, last.year)
        return {
            "id": base.id, "label": label, "const_per_day": round(base.const_per_day, 3),
            "coefs": [{"driver": line.driver_id.code, "coef": round(line.coef, 6)} for line in base.line_ids],
            "r2": round(base.r2, 2), "state": base.state,
        }  # fmt: skip

    # --- спільні вибірки --------------------------------------------------------------------------------
    @cached_property
    def plant(self):
        self.cr.execute(PLANT_SQL, (self.f, self.t))
        qty, imp, exp, pv, chp, days, partial = self.cr.fetchone()
        return {
            "qty": float(qty), "import": float(imp), "export": float(exp), "pv": float(pv), "chp": float(chp),
            "days": days, "partial": partial,
        }  # fmt: skip

    @cached_property
    def resources(self):
        self.cr.execute(RESOURCES_SQL, (self.f, self.t))
        return {
            code: {
                "name": name, "sequence": seq, "in_cost": bool(in_cost), "qty": float(qty), "cost": float(cost),
                "co2": float(co2),
            }
            for code, name, seq, in_cost, qty, cost, co2 in self.cr.fetchall()
        }  # fmt: skip

    def spec_sums(self, first, last):
        """`(Σ plant.qty, Σ plate_m2)` за доби з площею плит > 0."""
        self.cr.execute(SPEC_SQL, (first, last))
        qty, plate = self.cr.fetchone()
        return float(qty), float(plate)

    def enpi_sums(self, baseline, first, last):
        """`(Σ actual, Σ expected, n)` за рядками EnPI з очікуванням."""
        self.cr.execute(ENPI_SQL, (baseline.id, first, last))
        actual, expected, count = self.cr.fetchone()
        return float(actual), float(expected), count

    def avg_hdd(self, first, last):
        self.cr.execute(HDD_SQL, (first, last))
        value = self.cr.fetchone()[0]
        return None if value is None else float(value)

    def cogs(self, first, last):
        """`(Σ td_energy_cost, Σ value)` завершених МО з `date_finished` у вікні."""
        d0, d1 = dates.local_day_bounds(first)[0], dates.local_day_bounds(last)[1]
        self.cr.execute(COGS_SQL, (d0, d1))
        energy, value = self.cr.fetchone()
        return float(energy), float(value)


def _tone(delta):
    if delta is None:
        return "neutral"
    if delta <= -1:
        return "good"
    if delta >= 1:
        return "bad"
    return "neutral"


def _delta(ctx, code):
    """`(delta_pct | None, причина)` за EnPI-рядками вікна утвердженої бази `code/plant`."""
    base = ctx.baseline(code)
    if not base:
        return None, NO_BASE
    actual, expected, _n = ctx.enpi_sums(base, ctx.f, ctx.t)
    if expected <= 0:
        return None, NO_DATA
    return round_half_up((actual / expected - 1) * 100, 1), None


def kpi(kid, label, value, unit, delta_pct, note, tone):
    return {"id": kid, "label": label, "value": value, "unit": unit, "delta_pct": delta_pct, "note": note, "tone": tone}


def _kpi_el(ctx):
    delta, reason = _delta(ctx, "el")
    note = reason if delta is None else "%s %% до бази" % fmt_signed(delta)
    return kpi("el", "Електроенергія", r_int(ctx.plant["qty"]), "кВт·год", delta, note, _tone(delta))


def _kpi_gas(ctx):
    gas = ctx.resources.get("gas")
    value = r_int(gas["qty"]) if gas else None
    delta, reason = _delta(ctx, "gas")
    if delta is None:
        return kpi("gas", "Газ", value, "м³", None, reason, "neutral")
    note = "%s %% до бази" % fmt_signed(delta)
    first, last = ctx.baseline_window("gas")
    now, base = ctx.avg_hdd(ctx.f, ctx.t), ctx.avg_hdd(first, last)
    if now is not None and base:
        if now > HDD_COLD * base:
            note += " · похолодання"
        elif now < HDD_WARM * base:
            note += " · тепліше"
    return kpi("gas", "Газ", value, "м³", delta, note, _tone(delta))


def _kpi_cost(ctx):
    rows = [r for r in ctx.resources.values() if r["in_cost"]]
    total = sum(r["cost"] for r in rows)
    parts = []
    if total > 0:
        parts = [
            "%s %d %%" % (r["name"].lower(), round_half_up(r["cost"] / total * 100)) for r in rows if r["cost"] > 0
        ]
    return kpi("cost", "Вартість енергії", r_int(total), "₴", None, " · ".join(parts) or "—", "neutral")


def _kpi_spec(ctx):
    label, unit = "Питома енергоємність", "кВт·год/м² плити"
    energy, plate = ctx.spec_sums(ctx.f, ctx.t)
    if plate <= 0:
        return kpi("spec", label, None, unit, None, "—", "neutral")
    spec = energy / plate
    window = ctx.baseline_window("el")
    if not window:
        return kpi("spec", label, spec_value(spec), unit, None, NO_BASE, "neutral")
    base_energy, base_plate = ctx.spec_sums(*window)
    if base_plate <= 0:
        return kpi("spec", label, spec_value(spec), unit, None, NO_DATA, "neutral")
    base = base_energy / base_plate
    delta = round_half_up((spec / base - 1) * 100, 1)
    note = "база %s · %s %%" % (fmt_dec(base, 2), fmt_signed(delta))
    tone = "good" if delta < 0 else "bad" if delta > 0 else "neutral"
    return kpi("spec", label, spec_value(spec), unit, delta, note, tone)


def _kpi_cogs(ctx):
    label, unit = "Енергія в собівартості", "%"
    energy, value = ctx.cogs(ctx.f, ctx.t)
    if value <= 0:
        return kpi("cogs", label, None, unit, None, "—", "neutral")
    ratio = 100 * energy / value
    window = ctx.baseline_window("el")
    if not window:
        return kpi("cogs", label, round_half_up(ratio, 1), unit, None, NO_BASE, "neutral")
    base_energy, base_value = ctx.cogs(*window)
    if base_value <= 0:
        return kpi("cogs", label, round_half_up(ratio, 1), unit, None, NO_DATA, "neutral")
    base = 100 * base_energy / base_value
    note = "база %s %%" % fmt_dec(base, 1)
    return kpi("cogs", label, round_half_up(ratio, 1), unit, None, note, "good" if ratio <= base else "bad")


def _kpi_selfgen(ctx):
    p = ctx.plant
    label, unit = "Власна генерація", "%"
    note = "СЕС %s кВт·год" % fmt_int(p["pv"])
    if p["qty"] <= 0:
        return kpi("selfgen", label, None, unit, None, note, "neutral")
    value = 100 * (p["pv"] + p["chp"] - p["export"]) / p["qty"]
    return kpi("selfgen", label, r_int(value), unit, None, note, "good")


def _kpi_co2(ctx):
    res = ctx.resources
    total = sum(r["co2"] for r in res.values()) / 1000
    el, gas = res.get("el", {}).get("co2", 0.0) / 1000, res.get("gas", {}).get("co2", 0.0) / 1000
    note = "мережа %s т · газ %s т за період" % (fmt_int(el), fmt_int(gas))
    return kpi("co2", "Викиди CO₂", r_int(total), "т", None, note, "neutral")


def build_kpis(ctx):
    """7 KPI (R-07); `cost` — лише з групою вартості."""
    out = [_kpi_el(ctx), _kpi_gas(ctx)]
    if ctx.cost_access:
        out.append(_kpi_cost(ctx))
    out += [_kpi_spec(ctx), _kpi_cogs(ctx), _kpi_selfgen(ctx), _kpi_co2(ctx)]
    return out
