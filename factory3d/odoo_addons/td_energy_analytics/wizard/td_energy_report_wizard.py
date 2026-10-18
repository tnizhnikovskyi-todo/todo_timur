"""M-13 `td.energy.report.wizard` — звіти (Transient; W4-B). Каркас: поля — за SPEC; `create_and_print`,
`action_print` — воркер B (замінює файл цілком).
Контракт: `create_and_print(kind, period=None, shift_name=None)` → `ir.actions.report` (API-12)."""

from odoo import fields, models


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
    shift_date = fields.Date(string="Дата зміни", default=fields.Date.context_today)
    shift_name = fields.Char(string="Зміна", size=32)

    def action_print(self):
        raise NotImplementedError("W4-B: R-18, R-19")
