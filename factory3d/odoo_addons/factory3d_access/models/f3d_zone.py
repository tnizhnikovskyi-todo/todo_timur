from odoo import fields, models


class F3dZone(models.Model):
    _inherit = 'f3d.zone'

    f3d_people_now = fields.Integer(string='Людей зараз', compute='_compute_f3d_people')
    f3d_people_employee_ids = fields.Many2many('hr.employee', compute='_compute_f3d_people')
    # W3: f3d_people_visitor_ids (Many2many f3d.access.visitor) і розширення _f3d_people_visitors()

    def _f3d_people_visitors(self):
        """{zone_id: [visitor ids]} — перекривається в W3 (відвідувачі `present` у зоні)."""
        return {}

    def _compute_f3d_people(self):
        employees = self.env['hr.employee'].sudo().search(
            [('f3d_access_present', '=', True), ('f3d_access_zone_id', 'in', self.ids)])
        by_zone = {}
        for emp in employees:
            by_zone.setdefault(emp.f3d_access_zone_id.id, self.env['hr.employee'])
            by_zone[emp.f3d_access_zone_id.id] |= emp
        visitors = self._f3d_people_visitors()
        for zone in self:
            emps = by_zone.get(zone.id, self.env['hr.employee'])
            zone.f3d_people_employee_ids = emps
            zone.f3d_people_now = len(emps) + len(visitors.get(zone.id, ()))

    def action_view_people(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Люди: %s' % self.name, 'res_model': 'f3d.access.presence',
            'view_mode': 'kanban,list', 'domain': [('zone_id', '=', self.id)],
        }
