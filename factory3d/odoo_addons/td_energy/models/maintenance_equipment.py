from odoo import _, api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    td_energy_node_ids = fields.One2many("td.energy.node", "equipment_id", string="Вузли мережі")
    td_energy_node_count = fields.Integer(string="Вузлів мережі", compute="_compute_f3d_energy_node_count")

    @api.depends("td_energy_node_ids")
    def _compute_f3d_energy_node_count(self):
        counts = {}
        if self.env["td.energy.node"].has_access("read"):
            counts = {
                eq.id: n
                for eq, n in self.env["td.energy.node"]._read_group(
                    [("equipment_id", "in", self.ids)], ["equipment_id"], ["__count"]
                )
            }
        for rec in self:
            rec.td_energy_node_count = counts.get(rec.id, 0)

    def action_f3d_energy_nodes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Вузли мережі: %s", self.display_name),
            "res_model": "td.energy.node",
            "view_mode": "list,form",
            "domain": [("equipment_id", "=", self.id)],
        }
