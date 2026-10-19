from odoo import api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    td_sim_device_id = fields.Many2one(
        "td.sim.device",
        string="Пристрій емулятора",
        compute="_compute_f3d_sim_device",
        store=True,
        readonly=True,
        ondelete="set null",
    )
    td_sim_state = fields.Selection(related="td_sim_device_id.state", string="Стан в емуляторі")
    td_sim_fault_reason = fields.Char(related="td_sim_device_id.fault_reason", string="Причина збою")
    td_sim_protocol = fields.Selection(related="td_sim_device_id.protocol", string="Протокол")

    @api.depends("td_code")
    def _compute_f3d_sim_device(self):
        codes = [c for c in self.mapped("td_code") if c]
        devices = {d.code: d for d in self.env["td.sim.device"].sudo().search([("code", "in", codes)])} if codes else {}
        for rec in self:
            rec.td_sim_device_id = devices.get(rec.td_code, False)

    def action_f3d_sim_fault(self):
        self.ensure_one()
        return self.td_sim_device_id.action_fault()

    def action_f3d_sim_clear(self):
        self.ensure_one()
        return self.td_sim_device_id.action_clear()
