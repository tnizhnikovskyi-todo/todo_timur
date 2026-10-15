from odoo import _, api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    f3d_energy_node_ids = fields.One2many("f3d.energy.node", "equipment_id", string="Вузли мережі")
    f3d_energy_node_count = fields.Integer(string="Вузлів мережі", compute="_compute_f3d_energy_node_count")

    @api.depends("f3d_energy_node_ids")
    def _compute_f3d_energy_node_count(self):
        counts = {}
        if self.env["f3d.energy.node"].has_access("read"):
            counts = {
                eq.id: n
                for eq, n in self.env["f3d.energy.node"]._read_group(
                    [("equipment_id", "in", self.ids)], ["equipment_id"], ["__count"]
                )
            }
        for rec in self:
            rec.f3d_energy_node_count = counts.get(rec.id, 0)

    def action_f3d_energy_nodes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Вузли мережі: %s", self.display_name),
            "res_model": "f3d.energy.node",
            "view_mode": "list,form",
            "domain": [("equipment_id", "=", self.id)],
        }
