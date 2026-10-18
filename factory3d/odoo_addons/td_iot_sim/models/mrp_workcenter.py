from odoo import api, fields, models


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    td_sim_device_id = fields.Many2one(
        'td.sim.device', string='Пристрій емулятора', compute='_compute_f3d_sim_device',
        search='_search_f3d_sim_device')
    td_sim_state = fields.Selection(related='td_sim_device_id.state', string='Стан в емуляторі')

    @api.depends_context('uid')
    def _compute_f3d_sim_device(self):
        devices = self.env['td.sim.device'].sudo().search([('workcenter_id', 'in', self.ids)])
        by_wc = {}
        for dev in devices:
            by_wc.setdefault(dev.workcenter_id.id, dev)
        for rec in self:
            rec.td_sim_device_id = by_wc.get(rec.id, False)

    def _search_f3d_sim_device(self, operator, value):
        devices = self.env['td.sim.device'].sudo().search([('id', operator, value)])
        return [('id', 'in', devices.workcenter_id.ids)]

    def action_f3d_sim_open_device(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Емулятор', 'res_model': 'td.sim.device',
                'view_mode': 'form', 'res_id': self.td_sim_device_id.id}
