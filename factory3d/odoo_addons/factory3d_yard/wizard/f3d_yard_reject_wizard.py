from odoo import fields, models

from ..models.f3d_yard_visit import GRP_SEC, _f3d_yard_require


class F3dYardRejectWizard(models.TransientModel):
    _name = "f3d.yard.reject.wizard"
    _description = "Двір: відхилення рейсу"

    REASONS = [
        ("no_booking", "Немає бронювання"),
        ("wrong_docs", "Документи не збігаються"),
        ("late", "Запізнення поза вікном"),
        ("safety", "Безпека / стан машини"),
        ("other", "Інше"),
    ]

    visit_id = fields.Many2one("f3d.yard.visit", string="Рейс", readonly=True)
    reason = fields.Text(string="Причина", required=True)
    reason_code = fields.Selection(REASONS, string="Код причини", required=True, default="no_booking")

    def action_confirm(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        text = "%s: %s" % (dict(self.REASONS)[self.reason_code], self.reason)
        if self.visit_id:
            self.visit_id._do_reject(text)
        return {"type": "ir.actions.act_window_close"}
