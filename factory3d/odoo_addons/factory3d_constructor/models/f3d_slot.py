import math
import re
from html import escape
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services import cells as cells_mod

SLOT_TEMPLATE_SELECTION = [
    ('pallet_rack', "Паллетний стелаж"), ('cantilever', "Консольний стелаж"),
    ('shelf', "Полицевий стелаж / комірки фурнітури"), ('floor_stack', "Підлогове штабелювання"),
    ('machine_spot', "Місце під верстат"), ('zone', "Зона-контур"),
]
PREFIX_RE = re.compile(r'^[A-Z0-9]+(-[A-Z0-9]+)*$')
CELLS_HTML_LIMIT = 50


class F3dSlot(models.Model):
    _name = 'f3d.slot'
    _description = "Місце (шаблон)"
    _inherit = ['f3d.draft.mixin']
    _order = 'layer_id, code_prefix'
    _rec_name = 'code_prefix'
    _check_company_auto = True

    uid = fields.Char(string="UID", size=32, default=lambda self: uuid4().hex, copy=False, index=True, readonly=True)
    layer_id = fields.Many2one('f3d.layer', string="Шар", required=True, ondelete='cascade', index=True)
    site_id = fields.Many2one('f3d.site', related='layer_id.site_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    template = fields.Selection(SLOT_TEMPLATE_SELECTION, string="Шаблон", required=True)
    code_prefix = fields.Char(
        string="Префікс коду", size=22, required=True,
        help="Префікс кодів комірок: FG-R1 → FG-R1-B01-L1; не більше 22 символів")
    x_m = fields.Float(string="X, м", digits=(10, 3))
    y_m = fields.Float(string="Y, м", digits=(10, 3))
    rotation = fields.Integer(string="Поворот, °", default=0)
    params = fields.Json(string="Параметри шаблону", default=dict)
    overrides = fields.Json(string="Перевизначення комірок", default=dict)
    parent_location_id = fields.Many2one(
        'stock.location', string="Батьківська локація", check_company=True,
        domain=[('usage', 'in', ('internal', 'view'))], help="Куди публікувати комірки місця")
    cell_count = fields.Integer(string="Комірок", compute='_compute_cells', store=True)
    footprint_l_m = fields.Float(string="Довжина габариту, м", digits=(10, 3), compute='_compute_cells', store=True)
    footprint_w_m = fields.Float(string="Ширина габариту, м", digits=(10, 3), compute='_compute_cells', store=True)
    cells_html = fields.Html(string="Комірки", compute='_compute_cells_html', sanitize=False)
    note = fields.Text(string="Примітка")
    active = fields.Boolean(default=True)

    _f3d_slot_uid_uniq = models.Constraint(
        'UNIQUE(site_id, uid)', "UID місця має бути унікальним на площадці.")
    _f3d_slot_prefix_uniq = models.Constraint(
        'UNIQUE(site_id, code_prefix)', "Префікс місця має бути унікальним на площадці.")

    # --- комірки (R-01) --------------------------------------------------------------------------------
    @api.depends('template', 'params', 'overrides', 'code_prefix')
    def _compute_cells(self):
        for slot in self:
            try:
                slot.cell_count = cells_mod.count_cells(
                    slot.template, slot.code_prefix or '', slot.params, slot.overrides)
                slot.footprint_l_m, slot.footprint_w_m = cells_mod.footprint(slot.template, slot.params)
            except (cells_mod.CellsError, TypeError, ValueError):
                slot.cell_count, slot.footprint_l_m, slot.footprint_w_m = 0, 0.0, 0.0

    def _f3d_cells(self):
        """Комірки місця на льоту (R-01); у БД не зберігаються (DEC-15)."""
        self.ensure_one()
        return cells_mod.generate_cells(
            self.template, self.code_prefix, self.x_m, self.y_m, self.rotation, self.params, self.overrides,
            self.layer_id.elevation_m)

    def _f3d_footprint_obb(self):
        self.ensure_one()
        return cells_mod.slot_obb(self.template, self.params, self.x_m, self.y_m, self.rotation)

    @api.depends('template', 'params', 'overrides', 'code_prefix', 'x_m', 'y_m', 'rotation', 'layer_id.elevation_m')
    def _compute_cells_html(self):
        for slot in self:
            if not slot.template or not slot.code_prefix:
                slot.cells_html = False
                continue
            try:
                cells = slot._f3d_cells()
            except cells_mod.CellsError as exc:
                slot.cells_html = "<p>%s</p>" % escape(str(exc))
                continue
            rows = "".join(
                "<tr><td>%s</td><td>%d</td><td>%.2f</td><td>%.2f</td><td>%.2f</td><td>%g</td></tr>" % (
                    escape(c['code']), c['level'], c['x'], c['y'], c['z0'], c['capacity']) for c in cells[:CELLS_HTML_LIMIT])
            slot.cells_html = (
                "<table class='table table-sm'><thead><tr><th>Код</th><th>Ярус</th><th>X</th><th>Y</th><th>Z0</th>"
                "<th>Місткість</th></tr></thead><tbody>%s</tbody></table><p>Усього %d</p>" % (rows, len(cells)))

    # --- R-22 / R-11 -----------------------------------------------------------------------------------
    def _f3d_normalize_vals(self, vals):
        if 'rotation' in vals and isinstance(vals['rotation'], (int, float)) and not isinstance(vals['rotation'], bool):
            vals['rotation'] = int(round(vals['rotation'])) % 360
        template = vals.get('template') or (self[:1].template if self else None)
        if 'params' in vals and template:
            try:
                vals['params'] = cells_mod.normalize_params(template, vals['params'])
            except cells_mod.CellsError as exc:
                raise ValidationError(str(exc)) from None
        if 'overrides' in vals:
            try:
                vals['overrides'] = cells_mod.normalize_overrides(vals['overrides'])
            except cells_mod.CellsError as exc:
                raise ValidationError(str(exc)) from None
        return vals

    @api.model
    def _f3d_check_create(self, vals_list):
        layers = self.env['f3d.layer'].browse([v['layer_id'] for v in vals_list if v.get('layer_id')])
        self._f3d_assert_layers(layers)

    def _f3d_check_write(self, vals):
        layers = self.mapped('layer_id')
        if vals.get('layer_id'):
            layers |= self.env['f3d.layer'].browse(vals['layer_id'])
        self._f3d_assert_layers(layers)

    def _f3d_check_unlink(self):
        self._f3d_assert_layers(self.mapped('layer_id'))

    @api.model_create_multi
    def create(self, vals_list):
        slots = super().create(vals_list)
        slots._f3d_validate_overrides(strict_keys=[bool(v.get('overrides')) for v in vals_list])
        return slots

    def write(self, vals):
        res = super().write(vals)
        if {'template', 'params', 'code_prefix', 'overrides'} & set(vals):
            self._f3d_validate_overrides(strict_keys=['overrides' in vals] * len(self))
        return res

    def _f3d_validate_overrides(self, strict_keys):
        """AC-13: ключ `overrides`, що не відповідає комірці шаблону, — ValidationError «Комірки X немає в шаблоні.»;
        якщо `overrides` не передавали (змінились параметри), недійсні ключі мовчки відкидаються."""
        for slot, strict in zip(self, strict_keys):
            if not slot.overrides:
                continue
            codes = set(cells_mod.template_codes(slot.template, slot.params, slot.code_prefix))
            unknown = [code for code in slot.overrides if code not in codes]
            if not unknown:
                continue
            if strict:
                raise ValidationError("Комірки %s немає в шаблоні." % ", ".join(sorted(unknown)))
            slot.with_context(f3d_no_touch=True).overrides = {k: v for k, v in slot.overrides.items() if k in codes}

    # --- constraints -----------------------------------------------------------------------------------
    @api.constrains('code_prefix')
    def _check_prefix(self):
        for slot in self:
            if not PREFIX_RE.match(slot.code_prefix or '') or len(slot.code_prefix) > cells_mod.PREFIX_MAX_LEN:
                raise ValidationError(
                    "Префікс «%s»: великі латинські літери, цифри й дефіси між групами, не більше %d символів." % (
                        slot.code_prefix, cells_mod.PREFIX_MAX_LEN))

    @api.constrains('rotation')
    def _check_rotation(self):
        for slot in self:
            if slot.rotation not in (0, 90, 180, 270):
                raise ValidationError("Поворот місця кратний 90°.")

    @api.constrains('template', 'params')
    def _check_params(self):
        for slot in self:
            try:
                cells_mod.validate_params(slot.template, slot.params)
            except cells_mod.CellsError as exc:
                raise ValidationError("Місце %s: %s" % (slot.code_prefix, exc)) from None

    @api.constrains('template', 'layer_id')
    def _check_layer_allows_template(self):
        labels = dict(SLOT_TEMPLATE_SELECTION)
        for slot in self:
            allowed = slot.layer_id.sudo().allowed_slot_type_ids
            if allowed and slot.template not in allowed.mapped('key'):
                raise ValidationError("Шар «%s» не допускає тип «%s»." % (slot.layer_id.name, labels[slot.template]))

    @api.constrains('x_m', 'y_m')
    def _check_position(self):
        for slot in self:
            if not (math.isfinite(slot.x_m) and math.isfinite(slot.y_m)):
                raise ValidationError("Координати місця мають бути скінченними числами.")
