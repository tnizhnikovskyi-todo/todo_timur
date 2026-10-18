import re
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.exceptions import ValidationError

ROLE_RE = re.compile(r'^[a-z][a-z0-9_]*$')


class F3dEquipmentPassport(models.Model):
    _name = 'td.equipment.passport'
    _description = "Паспорт обладнання"
    _order = 'manufacturer, model'
    _rec_name = 'name'
    _rec_names_search = ['name', 'role', 'manufacturer', 'model']

    role = fields.Char(
        string="Роль", size=64, required=True, index=True,
        help="Ключ ролі з equipment_specs.json: beam_saw, compressor, facp…")
    name = fields.Char(compute='_compute_name', store=True)
    manufacturer = fields.Char(string="Виробник", size=128, required=True)
    model = fields.Char(string="Модель", size=255, required=True)
    reason = fields.Text(string="Чому обрано")
    dim_l_mm = fields.Integer(string="Довжина, мм")
    dim_w_mm = fields.Integer(string="Ширина, мм")
    dim_h_mm = fields.Integer(string="Висота, мм")
    dimensions = fields.Char(string="Д×Ш×В, мм", compute='_compute_dimensions', store=True)
    power_kw = fields.Float(string="Потужність, кВт", digits=(8, 2))
    connected_kw = fields.Float(string="Потужність підключення, кВт", digits=(8, 2))
    connected_note = fields.Text(string="Про потужність підключення")
    note = fields.Text(string="Примітка")
    spec_ids = fields.One2many('td.equipment.spec', 'passport_id', string="Параметри")
    source_ids = fields.One2many('td.equipment.source', 'passport_id', string="Джерела")
    equipment_ids = fields.One2many('maintenance.equipment', 'td_passport_id', string="Одиниці")
    component_of_ids = fields.Many2many(
        'maintenance.equipment', relation='td_equipment_component_passport_rel',
        column1='passport_id', column2='equipment_id', string="У складі одиниць")
    unit_count = fields.Integer(string="Одиниць під паспортом", compute='_compute_counts')
    component_count = fields.Integer(compute='_compute_counts')
    active = fields.Boolean(default=True)

    _f3d_passport_role_uniq = models.Constraint(
        'UNIQUE(role)', "Роль паспорта має бути унікальною.")

    @api.depends('manufacturer', 'model')
    def _compute_name(self):
        for rec in self:
            rec.name = "%s %s" % (rec.manufacturer or '', rec.model or '')

    @api.depends('dim_l_mm', 'dim_w_mm', 'dim_h_mm')
    def _compute_dimensions(self):
        for rec in self:
            values = (rec.dim_l_mm, rec.dim_w_mm, rec.dim_h_mm)
            rec.dimensions = (
                " × ".join(str(v) if v else "—" for v in values) if any(values) else False)

    @api.depends('equipment_ids', 'component_of_ids')
    def _compute_counts(self):
        for rec in self:
            rec.unit_count = len(rec.equipment_ids)
            rec.component_count = len(rec.component_of_ids)

    @api.constrains('role')
    def _check_role(self):
        for rec in self:
            if not rec.role or not ROLE_RE.match(rec.role):
                raise ValidationError("Роль: латиниця, цифри, підкреслення.")

    def get_num(self, key):
        self.ensure_one()
        if key == 'power_kw':
            return self.power_kw or None
        if key == 'connected_kw':
            return self.connected_kw or None
        spec = self.spec_ids.filtered(lambda s: s.key == key)[:1]
        if not spec:
            return None
        if spec.value_num or not spec.value_text:
            return spec.value_num
        try:  # Float у ORM не має «порожнього» значення: текстові параметри (controller, списки) — не числа
            return float(spec.value_text)
        except ValueError:
            return None

    def action_view_equipment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'maintenance.equipment',
            'view_mode': 'list,form',
            'domain': [('td_passport_id', '=', self.id)],
        }


class F3dEquipmentSpec(models.Model):
    _name = 'td.equipment.spec'
    _description = "Параметр паспорта обладнання"
    _order = 'passport_id, sequence, id'
    _rec_name = 'name'

    passport_id = fields.Many2one(
        'td.equipment.passport', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    key = fields.Char(
        string="Ключ", size=64, index=True,
        help="Машинний ключ для розрахунків (lumen, airflow_m3h, kva); порожній — лише для показу")
    name = fields.Char(string="Параметр", size=128, required=True)
    value_text = fields.Char(string="Значення", size=512)
    value_num = fields.Float(string="Число", digits=(16, 4))
    uom = fields.Char(string="Одиниця", size=32)
    kind = fields.Selection(
        [('published', "Опубліковано виробником"), ('estimate', "Оцінка"),
         ('derived', "Розрахунок")], default='published', required=True)

    _f3d_spec_key_uniq = models.Constraint(
        'UNIQUE(passport_id, key)', "Ключ параметра повторюється в паспорті.")

    @api.constrains('value_text', 'value_num')
    def _check_value(self):
        for rec in self:
            if not rec.value_text and not rec.value_num:
                raise ValidationError("Параметр %s: задайте значення." % rec.name)


class F3dEquipmentSource(models.Model):
    _name = 'td.equipment.source'
    _description = "Джерело паспорта обладнання"
    _order = 'passport_id, kind, sequence, id'

    passport_id = fields.Many2one(
        'td.equipment.passport', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    url = fields.Char(string="Посилання", size=1024, required=True)
    name = fields.Char(string="Назва", size=128, compute='_compute_name', store=True,
                       readonly=False)
    kind = fields.Selection(
        [('main', "Паспорт"), ('connected', "Потужність підключення")],
        default='main', required=True)
    attachment_id = fields.Many2one('ir.attachment', string="PDF", ondelete='set null')

    @api.depends('url')
    def _compute_name(self):
        for rec in self:
            if not rec.name and rec.url:
                rec.name = urlparse(rec.url).netloc

    @api.constrains('url')
    def _check_url(self):
        for rec in self:
            if not (rec.url or '').startswith(('http://', 'https://')):
                raise ValidationError("Посилання має починатися з http(s)://")
