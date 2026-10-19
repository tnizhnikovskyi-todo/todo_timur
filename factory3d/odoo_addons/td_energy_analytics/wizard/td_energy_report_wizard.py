"""M-13 `td.energy.report.wizard` — звіти (Transient; W4-B): «Звіт для керівництва» й «Звіт за зміну».

`create_and_print(kind, period=None, shift_name=None)` (API-12, `api.model`) створює запис і повертає
`ir.actions.report`; `action_print()` — те саме для відкритої форми. Права: `group_td_energy_user`;
суми ₴ у PDF — за групою вартості (R-18).
Дані звітів збирає `report/report_data.py` (AbstractModel `report.td_energy_analytics.*`).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.td_energy.tools import dates

from ..tools import periods

REPORTS = {
    "management": "td_energy_analytics.report_td_energy_management",
    "shift": "td_energy_analytics.report_td_energy_shift",
}


class TdEnergyReportWizard(models.TransientModel):
    _name = "td.energy.report.wizard"
    _description = "Енергетика: майстер звіту"

    kind = fields.Selection(
        [("management", "Для керівництва"), ("shift", "За зміну")],
        string="Вид звіту",
        required=True,
        default="management",
    )
    period = fields.Selection(
        [("w", "7 днів"), ("m", "30 днів"), ("q", "Квартал"), ("y", "Рік")], string="Період", default="m"
    )
    shift_date = fields.Date(string="Дата зміни", default=lambda self: dates.local_day(dates.now_utc(self.env)))
    shift_name = fields.Char(string="Зміна", size=32)

    @api.model
    def create_and_print(self, kind, period=None, shift_name=None):
        """API-12: запис майстра + `ir.actions.report` (dict) звіту `kind`; невідомий вид — `UserError`."""
        self.env["td.energy.analytics"]._td_check_access()
        if kind not in REPORTS:
            raise UserError(_("Невідомий вид звіту: %s.", kind))
        if period and period not in periods.PERIODS:
            raise UserError(_("Невідомий період: %s.", period))
        vals = {"kind": kind}
        if period:
            vals["period"] = period
        if shift_name:
            vals["shift_name"] = shift_name[:32]
        return self.create(vals).action_print()

    def action_print(self):
        """`ir.actions.report` за видом звіту відкритої форми (`report_action` з `docids = self.ids`)."""
        self.ensure_one()
        self.env["td.energy.analytics"]._td_check_access()
        if self.kind not in REPORTS:
            raise UserError(_("Невідомий вид звіту: %s.", self.kind))
        return self.env.ref(REPORTS[self.kind]).report_action(self)
