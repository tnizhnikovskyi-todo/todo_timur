from odoo import api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    td_genset_link_ids = fields.One2many("td.genset.link", "equipment_id", string="Зв'язка генератора")
    td_genset_link_id = fields.Many2one(
        "td.genset.link", compute="_compute_f3d_genset_link", string="Зв'язка генератора (перша)"
    )
    td_is_genset = fields.Boolean(compute="_compute_f3d_genset_link", string="Генератор")

    @api.depends("td_genset_link_ids", "td_passport_id.role")
    def _compute_f3d_genset_link(self):
        for rec in self:
            rec.td_genset_link_id = rec.td_genset_link_ids[:1]
            rec.td_is_genset = rec.td_passport_id.role == "genset"

    def action_open_f3d_genset(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Генератор",
            "res_model": "td.genset.link",
            "view_mode": "form",
            "target": "current",
        }
        if self.td_genset_link_id:
            action["res_id"] = self.td_genset_link_id.id
        else:
            action["context"] = {"default_equipment_id": self.id}
        return action
