from odoo import api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    f3d_sim_device_id = fields.Many2one(
        'f3d.sim.device', string='Пристрій емулятора', compute='_compute_f3d_sim_device',
        store=True, readonly=True, ondelete='set null')
    f3d_sim_state = fields.Selection(related='f3d_sim_device_id.state', string='Стан в емуляторі')
    f3d_sim_fault_reason = fields.Char(related='f3d_sim_device_id.fault_reason', string='Причина збою')
    f3d_sim_protocol = fields.Selection(related='f3d_sim_device_id.protocol', string='Протокол')

    @api.depends('f3d_code')
    def _compute_f3d_sim_device(self):
        codes = [c for c in self.mapped('f3d_code') if c]
        devices = {d.code: d for d in self.env['f3d.sim.device'].sudo().search([('code', 'in', codes)])} if codes else {}
        for rec in self:
            rec.f3d_sim_device_id = devices.get(rec.f3d_code, False)

    def action_f3d_sim_fault(self):
        self.ensure_one()
        return self.f3d_sim_device_id.action_fault()

    def action_f3d_sim_clear(self):
        self.ensure_one()
        return self.f3d_sim_device_id.action_clear()
