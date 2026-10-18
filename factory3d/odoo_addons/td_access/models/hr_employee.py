from odoo import api, fields, models

SECURITY = 'factory3d_access.group_f3d_access_security'


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    f3d_access_present = fields.Boolean(string='На території', readonly=True, index=True, default=False)
    f3d_access_zone_id = fields.Many2one('f3d.zone', string='Зона зараз', readonly=True, index=True,
                                         ondelete='set null')
    f3d_access_zone_since = fields.Datetime(string='У зоні з', readonly=True)
    f3d_access_last_in = fields.Datetime(string='Останній вхід (СКУД)', readonly=True)
    f3d_access_last_out = fields.Datetime(string='Останній вихід (СКУД)', readonly=True)
    f3d_home_zone_id = fields.Many2one(
        'f3d.zone', string='Домашня зона', ondelete='set null', tracking=True,
        help="Зона робочого місця: сюди людину ставить вхід через периметр і повернення з технічних "
             "приміщень (A-15)")
    f3d_access_zone_door_id = fields.Many2one(
        'f3d.access.door', string='Двері входу в зону', readonly=True, ondelete='set null',
        groups='hr.group_hr_user')
    f3d_access_last_event_id = fields.Many2one(
        'f3d.access.event', string='Остання подія СКУД', readonly=True, ondelete='set null', groups=SECURITY)
    # W3: f3d_access_card_ids (One2many f3d.access.card, groups=SECURITY) — у models/f3d_access_card.py
    f3d_access_link_ids = fields.One2many(
        'f3d.access.user.link', 'employee_id', string='Користувачі BioStar', groups=SECURITY)

    def _f3d_access_set(self, vals, event=None):
        """Записати присутність/зону (sudo); зміна present/zone -> шина (R-12 крок 6)."""
        vals = dict(vals)
        if event is not None:
            vals.setdefault('f3d_access_last_event_id', event.id)
        changed = self.browse()
        before = {emp.id: (emp.f3d_access_present, emp.f3d_access_zone_id.id) for emp in self.sudo()}
        self.sudo().write(vals)
        for emp in self.sudo():
            if before[emp.id] != (emp.f3d_access_present, emp.f3d_access_zone_id.id):
                changed |= emp
        if changed:
            codes = {c for c in changed.mapped('f3d_code') if c}
            collector = self.env.context.get('f3d_bus_collector')
            if collector is not None:
                collector.setdefault('hr.employee', set()).update(codes)
            else:
                self.env['f3d.access.event']._f3d_bus('hr.employee', codes)
        return changed

    @api.model
    def _f3d_access_public_presence(self, codes=None):
        """Публічна присутність для провайдера (A-21): без raw_user_id, імен і карток."""
        domain = [('f3d_code', '!=', False), ('active', '=', True)]
        if codes:
            domain.append(('f3d_code', 'in', list(codes)))
        emps = self.sudo().search_read(
            domain, ['f3d_code', 'f3d_access_present', 'f3d_access_zone_id', 'f3d_access_zone_since',
                     'f3d_access_last_event_id'])
        event_ids = [e['f3d_access_last_event_id'][0] for e in emps if e['f3d_access_last_event_id']]
        events = {e['id']: e for e in self.env['f3d.access.event'].sudo().browse(event_ids).read(
            ['ts', 'door_id', 'direction', 'event_type'])}
        door_codes = {d.id: d.code for d in self.env['f3d.access.door'].sudo().browse(
            [ev['door_id'][0] for ev in events.values() if ev['door_id']])}
        zone_codes = {z.id: z.f3d_code for z in self.env['f3d.zone'].sudo().browse(
            [e['f3d_access_zone_id'][0] for e in emps if e['f3d_access_zone_id']])}
        res = {}
        for e in emps:
            last = events.get(e['f3d_access_last_event_id'][0]) if e['f3d_access_last_event_id'] else None
            res[e['f3d_code']] = {
                'present': bool(e['f3d_access_present']),
                'zone': zone_codes.get(e['f3d_access_zone_id'][0]) if e['f3d_access_zone_id'] else None,
                'zone_since': e['f3d_access_zone_since'] or None,
                'last_event': {
                    'ts': last['ts'], 'door': door_codes.get(last['door_id'][0]) if last['door_id'] else None,
                    'direction': last['direction'], 'type': last['event_type'],
                } if last else None,
            }
        return res

    def action_f3d_access_events(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Проходи: %s' % self.name,
                'res_model': 'f3d.access.event', 'view_mode': 'list,form',
                'domain': [('employee_id', '=', self.id)]}


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    f3d_access_present = fields.Boolean(string='На території', readonly=True)
    f3d_access_zone_id = fields.Many2one('f3d.zone', string='Зона зараз', readonly=True)
    f3d_access_zone_since = fields.Datetime(string='У зоні з', readonly=True)
    f3d_access_last_in = fields.Datetime(string='Останній вхід (СКУД)', readonly=True)
    f3d_access_last_out = fields.Datetime(string='Останній вихід (СКУД)', readonly=True)
    f3d_home_zone_id = fields.Many2one('f3d.zone', string='Домашня зона', readonly=True)
