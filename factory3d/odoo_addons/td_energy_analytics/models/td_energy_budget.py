"""M-07 `td.energy.budget` — бюджет енергії (W4-A): R-06."""

from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.td_energy.tools import dates

from ..tools import budget as budget_tools
from ..tools import periods

COST = "td_energy.group_td_energy_cost"
CHIEF = "td_energy.group_td_energy_chief"
GUARDED = ("month", "resource_id", "amount_uah", "amount_qty", "company_id")


class TdEnergyBudget(models.Model):
    _name = "td.energy.budget"
    _description = "Енергетика: бюджет"
    _inherit = ["mail.thread"]
    _order = "month desc, resource_id"

    month = fields.Date(string="Місяць", required=True, index=True)
    resource_id = fields.Many2one(
        "td.energy.resource", string="Ресурс", help="Порожньо — «Усі ресурси (вартість енергії)»."
    )
    amount_uah = fields.Float(string="Бюджет, ₴", digits=(14, 2), required=True, groups=COST)
    amount_qty = fields.Float(string="Бюджет, од. ресурсу", digits=(14, 2))
    state = fields.Selection(
        [("draft", "Чернетка"), ("approved", "Затверджено")], string="Стан", default="draft", tracking=True
    )
    approved_by = fields.Many2one("res.users", string="Затвердив", readonly=True)
    approved_at = fields.Datetime(string="Затверджено", readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)
    note = fields.Char(string="Примітка", size=256)

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS td_energy_budget_uniq ON %s (company_id, month, COALESCE(resource_id, 0))"
            % self._table
        )
        tools.sql.create_index(self.env.cr, "td_energy_budget_month_idx", self._table, ["month"])

    @api.constrains("month")
    def _check_month(self):
        if any(rec.month and rec.month.day != 1 for rec in self):
            raise ValidationError(_("Місяць бюджету — перше число місяця."))

    @api.constrains("amount_uah")
    def _check_amount(self):
        if any(rec.amount_uah <= 0 for rec in self):
            raise ValidationError(_("Сума бюджету має бути більшою за нуль."))

    # --- права ----------------------------------------------------------------------------------------
    def _td_is_chief(self):
        return self.env.is_superuser() or self.env.user.has_group(CHIEF)

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("state") == "approved" for vals in vals_list) and not self._td_is_chief():
            raise AccessError(_("Затверджувати бюджет може лише головний енергетик."))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("state") == "approved" and not self._td_is_chief():
            raise AccessError(_("Затверджувати бюджет може лише головний енергетик."))
        edits = any(key in vals for key in GUARDED)
        if edits and "state" not in vals:
            approved = self.filtered(lambda rec: rec.state == "approved")
            if approved:
                if not self._td_is_chief():
                    raise AccessError(_("Редагувати затверджений бюджет може лише головний енергетик."))
                vals = dict(vals, state="draft", approved_by=False, approved_at=False)
        return super().write(vals)

    def action_approve(self):
        """R-06: затвердження бюджету (право «Головний енергетик»)."""
        if not self._td_is_chief():
            raise AccessError(_("Затверджувати бюджет може лише головний енергетик."))
        for rec in self:
            if rec.state == "approved":
                raise UserError(_("Бюджет уже затверджено."))
        self.write({"state": "approved", "approved_by": self.env.user.id, "approved_at": fields.Datetime.now()})
        return True

    # --- API-11: статус -------------------------------------------------------------------------------
    @api.model
    def get_status(self, month=None, resource_code=None):
        """R-06: `{month, month_label, plan_uah, fact_uah, fact_pct, month_share_pct, forecast_uah, delta_pct, text}`.

        Лише за затвердженим бюджетом і лише з групою вартості; інакше `None`."""
        if not (self.env.is_superuser() or self.env.user.has_group("td_energy.group_td_energy_user")):
            raise AccessError(_("Немає доступу до Енергетики."))
        if not (self.env.is_superuser() or self.env.user.has_group(COST)):
            return None
        today = dates.local_day(dates.now_utc(self.env))
        first = periods.parse_month(month, today)
        env = self.sudo().env
        resource = False
        if resource_code:
            resource = env["td.energy.resource"].search([("code", "=", resource_code)], limit=1)
            if not resource:
                raise UserError(_("Невідомий ресурс: %s.", resource_code))
        budget = env["td.energy.budget"].search(
            [
                ("state", "=", "approved"), ("month", "=", first), ("resource_id", "=", resource.id or False),
                ("company_id", "in", self.env.companies.ids),
            ],
            limit=1,
        )  # fmt: skip
        if not budget:
            return None
        weeks = max(1, periods.param_int(self.env, "forecast_weeks", 8))
        min_days = max(1, periods.param_int(self.env, "forecast_min_days", 3))
        last = first + timedelta(days=periods.month_days(first) - 1)
        low = min(first, today - timedelta(days=7 * weeks))
        costs = self._td_day_costs(resource, low, min(last, today))
        actual = {d: v for d, v in costs.items() if first <= d <= last}
        typical = budget_tools.typical_by_weekday(costs, today, weeks, min_days)
        res = budget_tools.status(budget.amount_uah, first, today, actual, typical)
        out = {
            "month": first.strftime("%Y-%m"), "month_label": budget_tools.month_label(first),
            "plan_uah": budget.amount_uah, "fact_uah": res["fact"], "fact_pct": res["fact_pct"],
            "month_share_pct": res["month_share"], "forecast_uah": res["forecast"], "delta_pct": res["delta_pct"],
            "text": res["text"],
        }  # fmt: skip
        return out

    @api.model
    def _td_day_costs(self, resource, day_from, day_to):
        """`{day: Σ resource.cost}` за `[day_from, day_to]`: ресурс бюджету або всі з `in_energy_cost`."""
        cr = self.env.cr
        self.env.flush_all()
        if resource:
            cr.execute(
                """SELECT day, SUM(cost) FROM td_energy_daily
                    WHERE scope = 'resource' AND resource_id = %s AND day BETWEEN %s AND %s GROUP BY day""",
                (resource.id, day_from, day_to),
            )
        else:
            cr.execute(
                """SELECT d.day, SUM(d.cost) FROM td_energy_daily d JOIN td_energy_resource r ON r.id = d.resource_id
                    WHERE d.scope = 'resource' AND r.in_energy_cost AND d.day BETWEEN %s AND %s GROUP BY d.day""",
                (day_from, day_to),
            )
        return {day: float(cost or 0.0) for day, cost in cr.fetchall()}
