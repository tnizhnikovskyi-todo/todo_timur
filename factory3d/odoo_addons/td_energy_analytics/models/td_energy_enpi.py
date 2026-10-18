"""M-06 `td.energy.enpi` — EnPI за добами (W4-A): R-05."""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.td_energy.tools import dates

from ..tools import enpi as enpi_tools
from ..tools import periods

_logger = logging.getLogger(__name__)

MANAGER = "td_energy.group_td_energy_manager"
COST = "td_energy.group_td_energy_cost"


class TdEnergyEnpi(models.Model):
    _name = "td.energy.enpi"
    _description = "Енергетика: EnPI за добу"
    _log_access = False
    _order = "day desc, baseline_id"

    baseline_id = fields.Many2one(
        "td.energy.baseline", string="Модель бази", required=True, index=True, ondelete="cascade"
    )
    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    actual = fields.Float(string="Факт", digits=(16, 3), required=True)
    expected = fields.Float(string="Очікування", digits=(16, 3))
    enpi = fields.Float(string="EnPI", digits=(8, 4), compute="_compute_enpi", store=True)
    drivers = fields.Json(string="Значення драйверів")
    quality = fields.Selection(
        [("ok", "Повні"), ("no_driver", "Немає драйвера"), ("partial", "Неповні")], string="Якість"
    )

    _baseline_day_uniq = models.Constraint("UNIQUE(baseline_id, day)", "EnPI за цю добу вже є.")

    @api.depends("actual", "expected")
    def _compute_enpi(self):
        for rec in self:
            rec.enpi = rec.actual / rec.expected if rec.expected and rec.expected > 0 else 0.0

    # --- розрахунок -----------------------------------------------------------------------------------
    @api.model
    def _td_recompute_baseline(self, baseline, days):
        """R-05 п. 1 для однієї моделі: upsert рядків за `days`; повертає кількість рядків."""
        cr = self.env.cr
        resource, scope, area_id, driver_ids, codes = baseline._td_context()
        days = sorted(set(days))
        if not days:
            return 0
        actual = enpi_tools.actual_series(cr, resource, scope, area_id, days[0], days[-1])
        series = enpi_tools.driver_series(cr, driver_ids, days[0], days[-1])
        coefs = [line.coef for line in baseline.line_ids.sorted("sequence")]
        rows = enpi_tools.enpi_rows(
            baseline.id, baseline.const_per_day, coefs, driver_ids, codes, actual, series, days
        )
        if rows:
            cr.execute_values(enpi_tools.ENPI_UPSERT_SQL, rows, page_size=1000)
        self.invalidate_model()
        return len(rows)

    @api.model
    def recompute(self, date_from, date_to, baseline=None):
        """Перерахунок EnPI за `[date_from, date_to]` (право «Енергетик»): для `baseline` або всіх затверджених."""
        if not (self.env.is_superuser() or self.env.user.has_group(MANAGER)):
            raise AccessError(_("Перераховувати EnPI може лише енергетик."))
        date_from, date_to = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        self.env.flush_all()
        env = self.sudo().env
        baselines = baseline.sudo() if baseline else env["td.energy.baseline"].search([("state", "=", "approved")])
        days = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
        rows = 0
        for rec in baselines:
            rows += env["td.energy.enpi"]._td_recompute_baseline(rec, [d for d in days if d >= rec.period_from])
        return {"baselines": len(baselines), "rows": rows}

    @api.model
    def _cron_enpi(self):
        """R-05 п. 1: вчора й пропуски останніх `catchup_days` по кожній затвердженій базі."""
        if not dates.param_bool(self.env, "read_enabled"):
            return 0
        today = dates.local_day(dates.now_utc(self.env))
        catchup = max(1, periods.param_int(self.env, "catchup_days", 14))
        window = [today - timedelta(days=k) for k in range(1, catchup + 1)]
        env, rows = self.sudo().env, 0
        for baseline in env["td.energy.baseline"].search([("state", "=", "approved")]):
            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute(
                        "SELECT day FROM td_energy_enpi WHERE baseline_id = %s AND day >= %s",
                        (baseline.id, window[-1]),
                    )
                    have = {row[0] for row in self.env.cr.fetchall()}
                    todo = [d for d in window if d >= baseline.period_from and (d not in have or d == window[0])]
                    rows += env["td.energy.enpi"]._td_recompute_baseline(baseline, todo)
            except Exception:
                _logger.exception("Енергетика: EnPI бази %s", baseline.id)
        return rows

    # --- підсумки періоду -----------------------------------------------------------------------------
    @api.model
    def period_totals(self, baseline, day_from, day_to):
        """R-05 п. 2: `{enpi, saving_pct, saving_qty, coverage, …[, saving_cost]}` за `[day_from, day_to]`.

        `saving_cost` — лише з групою вартості."""
        cr = self.env.cr
        self.env.flush_all()
        day_from, day_to = fields.Date.to_date(day_from), fields.Date.to_date(day_to)
        cr.execute(
            """SELECT SUM(actual), SUM(expected), COUNT(*) FROM td_energy_enpi
                WHERE baseline_id = %s AND day BETWEEN %s AND %s AND expected IS NOT NULL AND quality != 'no_driver'""",
            (baseline.id, day_from, day_to),
        )
        sum_a, sum_e, count = cr.fetchone()
        window_days = (day_to - day_from).days + 1
        cost_access = self.env.is_superuser() or self.env.user.has_group(COST)
        price = self._td_avg_price(baseline.resource_id.code, day_from, day_to) if cost_access else None
        return enpi_tools.totals(float(sum_a or 0.0), float(sum_e or 0.0), count, window_days, avg_price=price)

    @api.model
    def _td_avg_price(self, resource_code, day_from, day_to):
        """Середня ціна: `Σ plant.cost / Σ plant.import_qty` (електрика) або `Σ cost / Σ qty` ресурсу (газ)."""
        cr = self.env.cr
        if resource_code == "gas":
            cr.execute(
                """SELECT SUM(d.cost), SUM(d.qty)
                     FROM td_energy_daily d JOIN td_energy_resource r ON r.id = d.resource_id
                    WHERE d.scope = 'resource' AND r.code = 'gas' AND d.day BETWEEN %s AND %s""",
                (day_from, day_to),
            )
        else:
            cr.execute(
                """SELECT SUM(cost), SUM(import_qty) FROM td_energy_daily
                    WHERE scope = 'plant' AND day BETWEEN %s AND %s""",
                (day_from, day_to),
            )
        cost, qty = cr.fetchone()
        return float(cost) / float(qty) if cost is not None and qty else None
