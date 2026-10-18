import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..tools import params as P

_logger = logging.getLogger(__name__)


class F3dAccessUserLink(models.Model):
    _name = 'f3d.access.user.link'
    _description = 'СКУД: користувач BioStar'
    _order = 'server_id, biostar_user_id'
    _rec_name = 'biostar_user_id'
    _rec_names_search = ['biostar_user_id', 'biostar_name']

    server_id = fields.Many2one('f3d.access.server', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='server_id.company_id', store=True, index=True)
    biostar_user_id = fields.Char(string='Користувач BioStar (user_id)', required=True, index=True, size=64)
    biostar_name = fields.Char(string="Ім'я в BioStar", size=128, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Працівник', index=True, ondelete='set null')
    match = fields.Selection(
        [('barcode', 'За бейджем'), ('alias', 'За другим кодом сцени'),
         ('code', 'За кодом сцени без дефісів'), ('manual', 'Вручну'), ('visitor', 'Відвідувач'),
         ('none', "Не зв'язано")], required=True, default='none', readonly=True)
    user_group = fields.Char(string='Група BioStar', size=64, readonly=True)
    disabled = fields.Boolean(string='Вимкнено в BioStar', readonly=True)
    start_dt = fields.Datetime(string='Діє з', readonly=True)
    expiry_dt = fields.Datetime(string='Діє до', readonly=True)
    card_count = fields.Integer(string='Карток у BioStar', readonly=True)
    has_face = fields.Boolean(string='Є шаблон обличчя', readonly=True)
    has_finger = fields.Boolean(string='Є відбиток', readonly=True)
    in_biostar = fields.Boolean(string='Є в BioStar', default=True, readonly=True)
    synced = fields.Boolean(default=False, readonly=True)
    last_sync = fields.Datetime(readonly=True)
    event_count = fields.Integer(compute='_compute_event_count')
    active = fields.Boolean(default=True)

    _f3d_access_link_uniq = models.Constraint(
        "UNIQUE(server_id, biostar_user_id)", "Користувач BioStar уже зв'язаний на цьому сервері.")
    _f3d_access_link_employee_uniq = models.Constraint(
        "UNIQUE(server_id, employee_id)", "Працівник уже має користувача BioStar на цьому сервері.")

    @api.constrains('biostar_user_id')
    def _check_biostar_user_id(self):
        for rec in self:
            if not P.BSID_RE.match(rec.biostar_user_id or ''):
                raise ValidationError(
                    "Користувач BioStar %s: 1–64 символи [0-9A-Za-z_-]." % rec.biostar_user_id)

    @api.depends('biostar_user_id', 'employee_id', 'biostar_name')
    def _compute_display_name(self):
        for rec in self:
            visitor = rec['visitor_id'] if 'visitor_id' in rec._fields else False
            who = rec.employee_id.name or (visitor.name if visitor else False) or rec.biostar_name \
                or "не зв'язано"
            rec.display_name = "%s · %s" % (rec.biostar_user_id, who)

    def _compute_event_count(self):
        if 'f3d.access.event' not in self.env:
            self.event_count = 0
            return
        for rec in self:
            rec.event_count = self.env['f3d.access.event'].search_count([('link_id', '=', rec.id)])

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._set_manual_match(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._set_manual_match(vals)
        return super().write(vals)

    def _set_manual_match(self, vals):
        if 'match' in vals or not ({'employee_id', 'visitor_id'} & set(vals)):
            return
        if vals.get('employee_id'):
            vals['match'] = 'manual'
        elif vals.get('visitor_id'):
            vals['match'] = 'visitor'
        elif not vals.get('employee_id') and not vals.get('visitor_id'):
            vals['match'] = 'none'

    # ------------------------------------------------------------------ R-03
    def _f3d_rematch(self):
        """R-03 кроки 1–6 для зв'язків; повертає self."""
        Employee = self.env['hr.employee'].sudo()
        for link in self.sudo():
            if link.match in ('manual', 'visitor'):
                continue
            uid = link.biostar_user_id
            company = [('company_id', '=', link.server_id.company_id.id)]
            employee, match = Employee, 'none'
            ambiguous = False
            for kind in ('barcode', 'alias', 'code'):
                candidates = self._candidates(kind, uid, company)
                if len(candidates) == 1:
                    employee, match = candidates, kind
                    break
                if len(candidates) > 1:
                    ambiguous = True
                    _logger.warning("Неоднозначний збіг користувача BioStar %s (%s)", uid, kind)
                    break
            vals = {'employee_id': False, 'match': 'none'}
            if employee:
                busy = self.sudo().search([('server_id', '=', link.server_id.id),
                                           ('employee_id', '=', employee.id), ('id', '!=', link.id)], limit=1)
                if busy:
                    _logger.warning("Працівник %s уже має зв'язок на сервері: користувач %s не зв'язано",
                                    employee.name, uid)
                else:
                    vals = {'employee_id': employee.id, 'match': match}
            elif not ambiguous and 'f3d.access.visitor' in self.env:
                visitor = self.env['f3d.access.visitor'].sudo().search(
                    [('biostar_user_id', '=', uid), ('server_id', '=', link.server_id.id)])
                if len(visitor) == 1:
                    vals = {'visitor_id': visitor.id, 'match': 'visitor'}
            link.write(dict(vals))
        return self

    def _candidates(self, kind, uid, company):
        Employee = self.env['hr.employee'].sudo()
        if kind == 'barcode':
            return Employee.search([('barcode', '=', uid)] + company)
        if kind == 'alias':
            return Employee.search([('f3d_alias', '=', uid)] + company)
        return Employee.search([('f3d_code', '!=', False)] + company).filtered(
            lambda e: e.f3d_code.replace('-', '') == uid)

    @api.model
    def _f3d_match_employee(self, biostar_user_id, server=None):
        """R-03: знайти або створити зв'язок (server, user) і зіставити з працівником; повертає зв'язок."""
        server = server or self.env['f3d.access.server'].sudo().search([('active', '=', True)], limit=1)
        link = self.sudo().with_context(active_test=False).search(
            [('server_id', '=', server.id), ('biostar_user_id', '=', biostar_user_id)], limit=1)
        if not link:
            link = self.sudo().create({'server_id': server.id, 'biostar_user_id': biostar_user_id})
        link._f3d_rematch()
        return link

    def action_rematch(self):
        if not self.env.su and not self.env.user.has_group('factory3d_access.group_f3d_access_admin'):
            raise AccessError("Підбирати працівників може лише адміністратор СКУД.")
        self.filtered(lambda r: r.match in ('none', 'barcode', 'alias', 'code'))._f3d_rematch()
        return True

    def action_open_events(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Події', 'res_model': 'f3d.access.event',
                'view_mode': 'list,form', 'domain': [('link_id', '=', self.id)]}
