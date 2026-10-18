import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

PROTOCOLS = [('P-%02d' % n, 'P-%02d' % n) for n in range(1, 14)] + [('none', 'Пасивний / власник — модуль')]
DRIVERS = [(d, d) for d in (
    'opcua_ww', 'modbus_pm5560', 'modbus_sun2000', 'modbus_luna2000', 'modbus_elektronikon', 'modbus_atys',
    'modbus_tedom', 'modbus_adam6050', 'modbus_adam6060', 'modbus_adam6017', 'modbus_adam6015',
    'bacnet_roofvent', 'bacnet_ahu', 'bacnet_fan', 'bacnet_boiler', 'bacnet_facp', 'helvarnet_router',
    'mqtt_mobile', 'rest_woodstore', 'rest_biostar', 'http_lpr', 'sics_scale', 'genset_relay', 'passive')]
# I/O-модулі ADAM: на одному unit id живуть кілька пристроїв (різні канали, params)
SHARED_UNIT_DRIVERS = ('modbus_adam6050', 'modbus_adam6060', 'modbus_adam6017', 'modbus_adam6015')
CODE_RE = re.compile(r'^[A-Z0-9][A-Z0-9\-\.]{0,31}$')


class F3dSimDevice(models.Model):
    _name = 'td.sim.device'
    _description = 'Пристрій емулятора'
    _inherit = ['td.sim.client']
    _order = 'protocol, code'
    _rec_name = 'code'

    code = fields.Char(string='Код сцени', required=True, index=True)
    name = fields.Char(string='Назва', required=True)
    equipment_id = fields.Many2one('maintenance.equipment', string='Обладнання', ondelete='set null', index=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Робочий центр', ondelete='set null')
    zone_id = fields.Many2one('td.zone', string='Зона', ondelete='set null')
    protocol = fields.Selection(PROTOCOLS, string='Протокол', required=True, default='none')
    driver = fields.Selection(DRIVERS, string='Драйвер', required=True, default='passive')
    unit_id = fields.Integer(string='Modbus unit id', help='0 = н/д')
    instance = fields.Integer(string='BACnet device instance', help='0 = н/д')
    address = fields.Char(string='Адреса')
    params = fields.Json(string='Параметри')
    enabled = fields.Boolean(string='Увімкнено в емуляторі', default=True)
    state = fields.Selection(
        [('unknown', 'Невідомо'), ('ok', 'Норма'), ('fault', 'Збій'), ('offline', 'Офлайн'),
         ('passive', 'Пасивний')], string='Стан', default='unknown', readonly=True)
    fault_reason = fields.Char(string='Причина збою', readonly=True)
    last_update = fields.Datetime(string='Оновлено', readonly=True)
    signal_ids = fields.One2many('td.sim.signal', 'device_id', string='Сигнали')
    signal_count = fields.Integer(string='Сигналів', compute='_compute_signal_count')
    note = fields.Text(string='Примітка')
    role = fields.Char(related='equipment_id.td_role', string='Роль', readonly=True)
    model = fields.Char(related='equipment_id.td_model', string='Модель', readonly=True)
    write_enabled = fields.Boolean(compute='_compute_write_enabled')

    _device_code_uniq = models.Constraint('UNIQUE(code)', 'Код пристрою має бути унікальним')

    # --- compute ---
    @api.depends('signal_ids')
    def _compute_signal_count(self):
        data = self.env['td.sim.signal']._read_group(
            [('device_id', 'in', self.ids)], ['device_id'], ['__count'])
        counts = {dev.id: cnt for dev, cnt in data}
        for rec in self:
            rec.signal_count = counts.get(rec.id, 0)

    def _compute_write_enabled(self):
        flag = self._sim_flag('write_enabled')
        for rec in self:
            rec.write_enabled = flag

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s — %s" % (rec.code, rec.name) if rec.name else (rec.code or '')

    # --- constraints ---
    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not CODE_RE.match(rec.code or ''):
                raise ValidationError(
                    "Код пристрою «%s» не відповідає формату A-Z, 0-9, «-», «.» (до 32 символів, першим — літера або цифра)"
                    % rec.code)

    @api.constrains('unit_id')
    def _check_unit(self):
        for rec in self:
            if not 0 <= rec.unit_id <= 247:
                raise ValidationError("Modbus unit id має бути в межах 0…247")

    @api.constrains('unit_id', 'driver', 'params')
    def _check_unit_unique(self):
        for rec in self.filtered(lambda r: r.unit_id > 0 and r.driver not in SHARED_UNIT_DRIVERS):
            clash = self.search([('unit_id', '=', rec.unit_id), ('driver', '=', rec.driver),
                                 ('id', '!=', rec.id)], limit=1)
            if clash:
                raise ValidationError("Modbus unit id %s вже зайнятий пристроєм %s" % (rec.unit_id, clash.code))

    @api.constrains('instance')
    def _check_instance_unique(self):
        for rec in self.filtered(lambda r: r.instance > 0):
            clash = self.search([('instance', '=', rec.instance), ('id', '!=', rec.id)], limit=1)
            if clash:
                raise ValidationError(
                    "BACnet device instance %s вже зайнятий пристроєм %s" % (rec.instance, clash.code))

    # --- зв'язок з обладнанням: stored compute td_sim_device_id перераховується за кодом ---
    def _touch_equipment(self, codes):
        codes = [c for c in codes if c]
        if not codes:
            return
        equipment = self.env['maintenance.equipment'].sudo().search([('td_code', 'in', codes)])
        if equipment:
            self.env.add_to_compute(equipment._fields['td_sim_device_id'], equipment)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._touch_equipment(records.mapped('code'))
        return records

    def write(self, vals):
        old_codes = self.mapped('code') if 'code' in vals else []
        res = super().write(vals)
        if 'code' in vals:
            self._touch_equipment(old_codes + self.mapped('code'))
        return res

    def unlink(self):
        codes = self.mapped('code')
        res = super().unlink()
        self._touch_equipment(codes)
        return res

    # --- дії ---
    def action_fault(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Поставити збій', 'res_model': 'td.sim.fault.wizard',
                'view_mode': 'form', 'target': 'new', 'context': {'default_device_id': self.id}}

    def action_clear(self):
        self.ensure_one()
        self._sim_require_write()
        self._sim_post('/device/%s/clear' % self.code)
        self.sudo().write({'state': 'ok', 'fault_reason': False, 'last_update': fields.Datetime.now()})

    def _set_fault(self, reason, note=None):
        self.ensure_one()
        self._sim_require_write()
        body = {'reason': reason}
        if note:
            body['note'] = note
        self._sim_post('/device/%s/fault' % self.code, json=body)
        self.sudo().write({'state': 'fault', 'fault_reason': reason, 'last_update': fields.Datetime.now()})

    def action_open_signals(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': 'Сигнали %s' % self.code, 'res_model': 'td.sim.signal',
                'view_mode': 'list,form', 'domain': [('device_id', '=', self.id)]}
