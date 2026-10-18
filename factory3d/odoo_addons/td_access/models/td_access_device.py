from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import params as P
from ..tools.dates import local_day_start_utc


class F3dAccessDevice(models.Model):
    _name = 'f3d.access.device'
    _description = 'СКУД: пристрій BioStar'
    _order = 'server_id, code'
    _rec_names_search = ['code', 'name', 'biostar_id']

    name = fields.Char(string='Назва', required=True, size=128)
    code = fields.Char(
        string='Код сцени', required=True, index=True, size=32,
        help='ACR-IN, ACR-ELEC… (plant/infra.py:DOOR_READERS)')
    server_id = fields.Many2one('f3d.access.server', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='server_id.company_id', store=True, index=True)
    biostar_id = fields.Char(string='ID у BioStar', size=64, index=True)
    device_type = fields.Char(string='Тип', size=64, readonly=True)
    ip = fields.Char(string='IP', size=64, readonly=True, groups='factory3d_access.group_f3d_access_admin')
    status = fields.Selection(
        [('online', 'У мережі'), ('offline', 'Не в мережі'), ('unknown', 'Невідомо')],
        default='unknown', readonly=True)
    status_ts = fields.Datetime(readonly=True)
    sync_fail_count = fields.Integer(default=0, readonly=True)
    direction = fields.Selection(
        [('in', 'Вхід'), ('out', 'Вихід'), ('tna', 'За клавішею T&A')],
        string='Напрямок', required=True, default='in',
        help='tna: вхід/вихід за tna_key події (1 — вхід, 2 — вихід)')
    equipment_id = fields.Many2one(
        'maintenance.equipment', string='Обладнання', ondelete='set null',
        domain=[('f3d_code', '!=', False)])
    x = fields.Float(string='X, м', digits=(8, 2))
    y = fields.Float(string='Y, м', digits=(8, 2))
    zone_id = fields.Many2one(
        'f3d.zone', string='Зона', ondelete='set null',
        help='Зона, звідки підходять до зчитувача (зона «з» дверей)')
    door_ids = fields.One2many('f3d.access.door', 'entry_device_id', string='Двері (вхід)')
    last_event_ts = fields.Datetime(readonly=True)
    last_event_code = fields.Integer(readonly=True)
    events_today = fields.Integer(compute='_compute_events_today')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Примітка')

    _f3d_access_device_code_uniq = models.Constraint("UNIQUE(code)", "Код пристрою має бути унікальним.")
    _f3d_access_device_bsid_uniq = models.Constraint(
        "UNIQUE(server_id, biostar_id)", "Пристрій із таким ID BioStar уже є на цьому сервері.")

    @api.constrains('code', 'biostar_id')
    def _check_codes(self):
        for rec in self:
            if not rec.code or len(rec.code) > 32 or not P.CODE_RE.match(rec.code):
                raise ValidationError(
                    "Код пристрою %s: лише великі латинські літери, цифри й дефіси (напр. ACR-IN)." % rec.code)
            if rec.biostar_id and not P.BSID_RE.match(rec.biostar_id):
                raise ValidationError("ID BioStar %s: 1–64 символи [0-9A-Za-z_-]." % rec.biostar_id)

    def _compute_events_today(self):
        if 'f3d.access.event' not in self.env:
            self.events_today = 0
            return
        start = local_day_start_utc(fields.Datetime.now())
        for rec in self:
            rec.events_today = self.env['f3d.access.event'].search_count(
                [('device_id', '=', rec.id), ('ts', '>=', start)])

    def action_f3d_show(self):
        self.ensure_one()
        if self.equipment_id and self.equipment_id.f3d_code:
            return self.equipment_id.action_f3d_show()
        if self.zone_id:
            return self.zone_id.action_f3d_show()
        raise UserError("Пристрій не прив'язаний ні до обладнання, ні до зони.")

    def action_open_events(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Події', 'res_model': 'f3d.access.event',
                'view_mode': 'list,form', 'domain': [('device_id', '=', self.id)]}
