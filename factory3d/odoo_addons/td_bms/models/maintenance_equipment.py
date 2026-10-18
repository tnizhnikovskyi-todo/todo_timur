from odoo import _, fields, models
from odoo.exceptions import UserError

BMS_MODELS = (
    ("group", "f3d.bms.light.group"),
    ("panel", "f3d.bms.light.panel"),
    ("unit", "f3d.bms.hvac.unit"),
)


class MaintenanceEquipment(models.Model):
    """M-16: посилання обладнання на об'єкт модуля «Будівля»."""

    _inherit = "maintenance.equipment"

    f3d_bms_object = fields.Char(string="Об'єкт «Будівля»", compute="_compute_f3d_bms_object")

    def _compute_f3d_bms_object(self):
        for rec in self:
            res = False
            if rec.id:
                for key, model in BMS_MODELS:
                    obj = self.env[model].sudo().search([("equipment_id", "=", rec.id)], limit=1)
                    if obj:
                        res = "%s:%d" % (key, obj.id)
                        break
                if not res:
                    bal = (
                        self.env["f3d.bms.heat.balance"].sudo().search([("boiler_equipment_id", "=", rec.id)], limit=1)
                    )
                    res = "balance:%d" % bal.id if bal else False
            rec.f3d_bms_object = res

    def action_f3d_bms_open(self):
        self.ensure_one()
        if not self.f3d_bms_object:
            raise UserError(_("Для обладнання немає об'єкта модуля «Будівля»."))
        key, res_id = self.f3d_bms_object.split(":")
        model = dict(BMS_MODELS, balance="f3d.bms.heat.balance")[key]
        return {
            "type": "ir.actions.act_window",
            "res_model": model,
            "res_id": int(res_id),
            "view_mode": "form",
            "target": "current",
        }
