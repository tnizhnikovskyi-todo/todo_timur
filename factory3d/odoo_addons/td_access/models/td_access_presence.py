from odoo import fields, models, tools
from odoo.exceptions import UserError

EMPLOYEE_SQL = """
  SELECT e.id * 2 AS id, 'employee' AS person_type, e.id AS employee_id, NULL::int AS visitor_id,
         e.name AS name, e.td_code AS code, e.td_access_zone_id AS zone_id,
         e.td_access_zone_since AS zone_since, e.td_access_last_in AS last_in,
         e.td_home_zone_id AS home_zone_id, NULL::int AS host_employee_id, e.company_id AS company_id
    FROM hr_employee e WHERE e.active AND e.td_access_present"""
VISITOR_SQL = """
  UNION ALL
  SELECT v.id * 2 + 1, 'visitor', NULL::int, v.id, v.name, 'V-' || v.id, v.zone_id, v.zone_since, v.arrived_at,
         NULL::int, v.host_employee_id, v.company_id
    FROM td_access_visitor v WHERE v.present AND v.state = 'on_site'"""


class F3dAccessPresence(models.Model):
    _name = 'td.access.presence'
    _description = 'СКУД: люди на території'
    _auto = False
    _order = 'zone_id, name'

    person_type = fields.Selection([('employee', 'Працівник'), ('visitor', 'Відвідувач')], readonly=True)
    employee_id = fields.Many2one('hr.employee', readonly=True)
    # W3: visitor_id (Many2one td.access.visitor) — у models/td_access_visitor.py
    name = fields.Char(readonly=True)
    code = fields.Char(readonly=True)
    zone_id = fields.Many2one('td.zone', readonly=True)
    zone_since = fields.Datetime(readonly=True)
    last_in = fields.Datetime(readonly=True)
    home_zone_id = fields.Many2one('td.zone', readonly=True)
    host_employee_id = fields.Many2one('hr.employee', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("SELECT to_regclass('td_access_visitor')")
        has_visitor = self.env.cr.fetchone()[0] is not None
        self.env.cr.execute("CREATE OR REPLACE VIEW %s AS (%s%s)" % (
            self._table, EMPLOYEE_SQL, VISITOR_SQL if has_visitor else ''))

    def action_f3d_show(self):
        self.ensure_one()
        if self.employee_id and self.employee_id.sudo().td_code:
            return self.employee_id.sudo().action_f3d_show()
        if self.zone_id:
            return self.zone_id.action_f3d_show()
        raise UserError("Немає куди показувати: людина без коду сцени й без зони.")

    def action_open_person(self):
        self.ensure_one()
        if 'visitor_id' in self._fields and self.visitor_id:
            return {'type': 'ir.actions.act_window', 'res_model': 'td.access.visitor',
                    'res_id': self.visitor_id.id, 'view_mode': 'form'}
        model = 'hr.employee' if self.env['hr.employee'].has_access('read') else 'hr.employee.public'
        return {'type': 'ir.actions.act_window', 'res_model': model, 'res_id': self.employee_id.id,
                'view_mode': 'form'}
