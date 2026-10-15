from odoo import api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    f3d_genset_link_ids = fields.One2many("f3d.genset.link", "equipment_id", string="Зв'язка генератора")
    f3d_genset_link_id = fields.Many2one(
        "f3d.genset.link", compute="_compute_f3d_genset_link", string="Зв'язка генератора (перша)"
    )
    f3d_is_genset = fields.Boolean(compute="_compute_f3d_genset_link", string="Генератор")

    @api.depends("f3d_genset_link_ids", "f3d_passport_id.role")
    def _compute_f3d_genset_link(self):
        for rec in self:
            rec.f3d_genset_link_id = rec.f3d_genset_link_ids[:1]
            rec.f3d_is_genset = rec.f3d_passport_id.role == "genset"

    def action_open_f3d_genset(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Генератор",
            "res_model": "f3d.genset.link",
            "view_mode": "form",
            "target": "current",
        }
        if self.f3d_genset_link_id:
            action["res_id"] = self.f3d_genset_link_id.id
        else:
            action["context"] = {"default_equipment_id": self.id}
        return action
