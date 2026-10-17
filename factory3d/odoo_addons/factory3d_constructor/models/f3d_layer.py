import re
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services import schemas

LAYER_KIND_SELECTION = [
    ('building', "Будівля"),
    ('storage', "Склади"),
    ('production', "Виробництво"),
    ('engineering', "Інженерні мережі"),
    ('yard', "Двір"),
    ('custom', "Свій шар"),
]
# R-11: вміст шару, який можуть писати ролі зі списку edit_group_ids; решту полів — лише менеджер
LAYER_CONTENT_FIELDS = frozenset({'aisles', 'fire_paths', 'utilities', 'underlay_attachment_id', 'underlay_params'})
COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _new_uid():
    return uuid4().hex


class F3dLayer(models.Model):
    _name = 'f3d.layer'
    _description = "Шар розкладки"
    _inherit = ['f3d.draft.mixin']
    _order = 'site_id, sequence, elevation_m, id'
    _rec_name = 'name'

    uid = fields.Char(string="UID", size=32, default=lambda self: _new_uid(), copy=False, index=True, readonly=True)
    site_id = fields.Many2one('f3d.site', string="Площадка", required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    name = fields.Char(string="Назва", required=True)
    kind = fields.Selection(LAYER_KIND_SELECTION, string="Вид", required=True, default='custom')
    sequence = fields.Integer(default=10)
    elevation_m = fields.Float(string="Відмітка, м", digits=(8, 3), default=0.0)
    grid_step_m = fields.Float(string="Крок сітки, м", digits=(6, 3), default=0.5)
    aisle_width_m = fields.Float(string="Ширина проходу, м", digits=(6, 3), default=3.0)
    max_floor_load_kn_m2 = fields.Float(
        string="Макс. навантаження на підлогу, кН/м²",
        digits=(8, 2),
        default=0.0,
        help="0 — перевірка «Навантаження» для шару вимкнена",
    )
    bounds = fields.Json(string="Контур", help="[[x, y], …] у метрах, ≥3 точки; порожньо — габарит будівлі")
    allowed_slot_type_ids = fields.Many2many(
        'f3d.term',
        'f3d_layer_slot_type_rel',
        'layer_id',
        'term_id',
        string="Дозволені типи місць",
        domain=[('term_type', '=', 'slot_type')],
        help="Порожньо — усі типи",
    )
    edit_group_ids = fields.Many2many(
        'res.groups',
        'f3d_layer_edit_group_rel',
        'layer_id',
        'group_id',
        string="Хто редагує",
        help="Групи, що пишуть місця й розміщення шару; порожньо — лише менеджер",
    )
    color = fields.Char(string="Колір", size=7, default='#8d99ae')
    opacity = fields.Float(string="Прозорість", digits=(3, 2), default=1.0)
    style = fields.Selection(
        [('solid', "Суцільний"), ('wire', "Каркас"), ('dashed', "Пунктир")], string="Стиль", default='solid'
    )
    visible = fields.Boolean(string="Видимий за замовчуванням", default=True)
    aisles = fields.Json(string="Проходи", default=list)
    fire_paths = fields.Json(string="Пожежні проходи й виходи", default=list)
    utilities = fields.Json(string="Мережі", default=list)
    underlay_attachment_id = fields.Many2one('ir.attachment', string="Підкладка", ondelete='set null', copy=False)
    underlay_format = fields.Selection(
        [('dxf', "DXF"), ('dwg', "DWG")], string="Формат підкладки", compute='_compute_underlay', store=True
    )
    underlay_status = fields.Selection(
        [('none', "Немає"), ('ready', "Готово"), ('pending_conversion', "Очікує перетворення")],
        string="Статус підкладки",
        compute='_compute_underlay',
        store=True,
        default='none',
    )
    underlay_params = fields.Json(string="Параметри підкладки", default=lambda self: dict(schemas.UNDERLAY_DEFAULT))
    slot_count = fields.Integer(string="Місць", compute='_compute_counts')
    placement_count = fields.Integer(string="Розміщень", compute='_compute_counts')
    is_manager = fields.Boolean(compute='_compute_is_manager')
    active = fields.Boolean(default=True)

    _f3d_layer_uid_uniq = models.Constraint('UNIQUE(site_id, uid)', "UID шару має бути унікальним на площадці.")

    # --- compute ---------------------------------------------------------------------------------------
    @api.depends('underlay_attachment_id', 'underlay_attachment_id.name')
    def _compute_underlay(self):
        for layer in self:
            name = (layer.underlay_attachment_id.name or '').lower()
            if name.endswith('.dxf'):
                layer.underlay_format, layer.underlay_status = 'dxf', 'ready'
            elif name.endswith('.dwg'):
                layer.underlay_format, layer.underlay_status = 'dwg', 'pending_conversion'
            else:
                layer.underlay_format, layer.underlay_status = False, 'none'

    def _compute_counts(self):
        def counts(model):
            return dict(
                self.env[model]
                .with_context(active_test=False)
                ._read_group([('layer_id', 'in', self.ids)], ['layer_id'], ['__count'])
            )

        slots, placements = counts('f3d.slot'), counts('f3d.placement')
        for layer in self:
            layer.slot_count = slots.get(layer, 0)
            layer.placement_count = placements.get(layer, 0)

    def _compute_is_manager(self):
        is_manager = self._f3d_is_manager()
        for layer in self:
            layer.is_manager = is_manager

    # --- constraints -----------------------------------------------------------------------------------
    @api.constrains('grid_step_m', 'aisle_width_m', 'opacity', 'color', 'max_floor_load_kn_m2')
    def _check_values(self):
        for layer in self:
            if layer.grid_step_m <= 0:
                raise ValidationError("Крок сітки має бути додатним.")
            if layer.aisle_width_m < 0:
                raise ValidationError("Ширина проходу не може бути від'ємною.")
            if layer.max_floor_load_kn_m2 < 0:
                raise ValidationError("Навантаження на підлогу не може бути від'ємним.")
            if not 0 <= layer.opacity <= 1:
                raise ValidationError("Прозорість має бути від 0 до 1.")
            if not COLOR_RE.match(layer.color or ''):
                raise ValidationError("Колір має бути у форматі #RRGGBB.")

    @api.constrains('bounds', 'aisles', 'fire_paths', 'utilities', 'underlay_params')
    def _check_json(self):
        for layer in self:
            try:
                schemas.normalize_bounds(layer.bounds)
                schemas.normalize_aisles(layer.aisles)
                schemas.normalize_fire_paths(layer.fire_paths)
                schemas.normalize_layer_utilities(layer.utilities)
                schemas.normalize_underlay_params(layer.underlay_params)
            except schemas.SchemaError as exc:
                raise ValidationError(str(exc)) from None

    @api.constrains('edit_group_ids')
    def _check_edit_groups(self):
        privilege = self.env.ref('factory3d_constructor.privilege_f3d_constructor')
        for layer in self:
            if any(group.privilege_id != privilege for group in layer.edit_group_ids):
                raise ValidationError("Лише ролі конструктора.")

    # --- R-22 / R-11 -----------------------------------------------------------------------------------
    def _f3d_normalize_vals(self, vals):
        if 'bounds' in vals:
            vals['bounds'] = schemas.normalize_bounds(vals['bounds']) or None
        if 'aisles' in vals:
            vals['aisles'] = schemas.normalize_aisles(vals['aisles'])
        if 'fire_paths' in vals:
            vals['fire_paths'] = schemas.normalize_fire_paths(vals['fire_paths'])
        if 'utilities' in vals:
            vals['utilities'] = schemas.normalize_layer_utilities(vals['utilities'])
        if 'underlay_params' in vals:
            vals['underlay_params'] = schemas.normalize_underlay_params(vals['underlay_params'])
        return vals

    @api.model
    def _f3d_check_create(self, vals_list):
        self._f3d_assert_manager("Створювати шари")

    def _f3d_check_write(self, vals):
        if self.env.su or self._f3d_is_manager():
            return
        foreign = set(vals) - LAYER_CONTENT_FIELDS
        if foreign:
            raise AccessError(
                "Змінювати налаштування шару (%s) може лише менеджер конструктора."
                % ", ".join(self._fields[name].string or name for name in sorted(foreign) if name in self._fields)
            )
        self._f3d_assert_layers(self)

    def _f3d_check_unlink(self):
        self._f3d_assert_manager("Видаляти шари")
        for layer in self:
            slots = self.env['f3d.slot'].with_context(active_test=False).search_count([('layer_id', '=', layer.id)])
            placements = (
                self.env['f3d.placement'].with_context(active_test=False).search_count([('layer_id', '=', layer.id)])
            )
            if slots or placements:
                raise UserError("Шар не порожній: архівуйте його або перенесіть об'єкти.")
