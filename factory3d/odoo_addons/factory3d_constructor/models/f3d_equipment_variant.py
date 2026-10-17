from odoo import api, fields, models

from .f3d_equipment_passport import F3D_CATEGORY_SELECTION

MODEL_STATUS_SELECTION = [
    ('none', "Немає"), ('ok', "Готово"), ('pending_conversion', "Очікує перетворення"), ('error', "Помилка"),
]


class F3dEquipmentVariant(models.Model):
    _name = 'f3d.equipment.variant'
    _description = "Варіант обладнання"
    _order = 'passport_id, sequence, id'

    passport_id = fields.Many2one(
        'f3d.equipment.passport', string="Тип (паспорт)", required=True, ondelete='cascade', index=True)
    name = fields.Char(string="Назва варіанта", required=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection(
        F3D_CATEGORY_SELECTION, string="Категорія", related='passport_id.f3d_category', store=True, readonly=True)
    length_mm = fields.Integer(string="Довжина, мм")
    width_mm = fields.Integer(string="Ширина, мм")
    height_mm = fields.Integer(string="Висота, мм")
    service_front_mm = fields.Integer(string="Сервіс спереду, мм", default=0)
    service_back_mm = fields.Integer(string="Сервіс ззаду, мм", default=0)
    service_left_mm = fields.Integer(string="Сервіс ліворуч, мм", default=0)
    service_right_mm = fields.Integer(string="Сервіс праворуч, мм", default=0)
    front_side = fields.Selection(
        [('s', "Південь (−Y)"), ('n', "Північ (+Y)"), ('e', "Схід (+X)"), ('w', "Захід (−X)")],
        string="Сторона фронту", default='s', required=True, help="Сторона фронту при повороті 0°")
    anchor = fields.Selection(
        [('center', "Центр"), ('front', "Центр фронту"), ('back', "Центр тилу"), ('corner', "Лівий передній кут")],
        string="Прив'язка", default='center', required=True,
        help="Точка, якою виріб прив'язаний до (x, y) розміщення")
    rotation_mode = fields.Selection(
        [('q', "0/90/180/270°"), ('h', "0/180°"), ('z', "Лише 0°"), ('any', "Будь-який кут")],
        string="Повороти", default='q', required=True)
    allowed_layer_kind_ids = fields.Many2many(
        'f3d.term', 'f3d_variant_layer_kind_rel', 'variant_id', 'term_id', string="Дозволені види шарів",
        domain=[('term_type', '=', 'layer_kind')], help="Порожньо — будь-який шар")
    allowed_slot_type_ids = fields.Many2many(
        'f3d.term', 'f3d_variant_slot_type_rel', 'variant_id', 'term_id', string="Дозволені типи місць",
        domain=[('term_type', '=', 'slot_type')], help="Порожньо — без обмежень")
    utilities = fields.Json(
        string="Точки підключення", default=list,
        help="[{kind: electric|air|dust, x_mm, y_mm, z_mm}], початок — центр габариту")
    power_kw = fields.Float(string="Потужність, кВт", digits=(8, 2))
    panel = fields.Char(string="Щит", size=64)
    weight_kg = fields.Float(string="Маса, кг", digits=(10, 1))
    floor_load_kn_m2 = fields.Float(
        string="Навантаження на підлогу, кН/м²", digits=(8, 2), compute='_compute_floor_load', store=True,
        readonly=False)
    create_workcenter = fields.Boolean(string="Створювати робочий центр", default=False)
    model_original_id = fields.Many2one('ir.attachment', string="Оригінал моделі", ondelete='set null', copy=False)
    model_glb_id = fields.Many2one('ir.attachment', string="GLB для перегляду", ondelete='set null', copy=False)
    model_meta = fields.Json(string="Метадані моделі", default=dict, copy=False)
    model_status = fields.Selection(
        MODEL_STATUS_SELECTION, string="Статус моделі", default='none', readonly=True, index=True, copy=False)
    model_warning = fields.Char(string="Попередження моделі", compute='_compute_model_warning')
    image = fields.Image(string="Мініатюра", max_width=512, max_height=512)
    placement_count = fields.Integer(string="Розміщень", compute='_compute_placement_count')
    note = fields.Text(string="Примітка")
    active = fields.Boolean(default=True)

    @api.depends('name', 'passport_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s · %s" % (rec.passport_id.name or '', rec.name or '')

    @api.depends('weight_kg', 'length_mm', 'width_mm')
    def _compute_floor_load(self):
        for rec in self:
            area = rec.length_mm * rec.width_mm / 1_000_000.0
            rec.floor_load_kn_m2 = rec.weight_kg * 9.80665 / 1000.0 / area if area and rec.weight_kg else 0.0

    @api.depends('model_meta', 'model_status')
    def _compute_model_warning(self):
        for rec in self:
            rec.model_warning = False

    def _compute_placement_count(self):
        data = dict(self.env['f3d.placement'].with_context(active_test=False)._read_group(
            [('variant_id', 'in', self.ids)], ['variant_id'], ['__count']))
        for rec in self:
            rec.placement_count = data.get(rec, 0)
