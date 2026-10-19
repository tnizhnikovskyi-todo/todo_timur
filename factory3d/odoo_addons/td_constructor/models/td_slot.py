import math
import re
from html import escape
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..services import addr as addr_mod, cells as cells_mod
from .td_site import DEPTH_MODE_SELECTION

SLOT_TEMPLATE_SELECTION = [
    ('pallet_rack', "Паллетний стелаж"),
    ('cantilever', "Консольний стелаж"),
    ('shelf', "Полицевий стелаж / комірки фурнітури"),
    ('floor_stack', "Підлогове штабелювання"),
    ('floor_spot', "Місце на підлозі (одна локація)"),
    ('machine_spot', "Місце під верстат"),
    ('zone', "Зона-контур"),
]
PREFIX_RE = re.compile(r'^[A-Z0-9]+(-[A-Z0-9]+)*$')
CELLS_HTML_LIMIT = 50


class F3dSlot(models.Model):
    _name = 'td.slot'
    _description = "Місце (шаблон)"
    _inherit = ['td.draft.mixin']
    _order = 'layer_id, code_prefix'
    _rec_name = 'code_prefix'
    _check_company_auto = True

    uid = fields.Char(string="UID", size=32, default=lambda self: uuid4().hex, copy=False, index=True, readonly=True)
    layer_id = fields.Many2one('td.layer', string="Шар", required=True, ondelete='cascade', index=True)
    site_id = fields.Many2one('td.site', related='layer_id.site_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    template = fields.Selection(SLOT_TEMPLATE_SELECTION, string="Шаблон", required=True)
    code_prefix = fields.Char(
        string="Префікс коду",
        size=22,
        required=True,
        help="Префікс кодів комірок: AB-R1 → AB-R1-B01-L1; не більше 22 символів",
    )
    x_m = fields.Float(string="X, м", digits=(10, 3))
    y_m = fields.Float(string="Y, м", digits=(10, 3))
    rotation = fields.Integer(string="Поворот, °", default=0)
    params = fields.Json(string="Параметри шаблону", default=dict)
    overrides = fields.Json(string="Перевизначення комірок", default=dict)
    parent_location_id = fields.Many2one(
        'stock.location',
        string="Батьківська локація",
        check_company=True,
        domain=[('usage', 'in', ('internal', 'view'))],
        help="Куди публікувати комірки місця",
    )
    # --- MERGE.md §3.3 (волни 1–2): поля без логіки; наповнюють слайси ---------------------------------
    type_id = fields.Many2one('td.slot.type', string="Тип місця", index=True, ondelete='restrict')
    storage_category_id = fields.Many2one(
        'stock.storage.category',
        string="Категорія зберігання",
        ondelete='set null',
        help="Діє на вкладені рівні, якщо там не задано своєї (F03-02)",
    )
    removal_strategy_id = fields.Many2one(
        'product.removal',
        string="Стратегія списання",
        ondelete='set null',
        help="Діє на вкладені рівні, якщо там не задано своєї (F03-06)",
    )
    function_id = fields.Many2one(
        'td.term',
        string="Функція зони",
        domain=[('term_type', '=', 'zone_function')],
        ondelete='set null',
    )
    attr_ids = fields.Many2many(
        'td.term',
        'td_slot_attr_rel',
        'slot_id',
        'term_id',
        string="Атрибути зони",
        domain=[('term_type', '=', 'zone_attr')],
    )
    temp_min_c = fields.Float(string="Температура від, °C", digits=(5, 1), help="Обидві межі 0 — режим не задано")
    temp_max_c = fields.Float(string="Температура до, °C", digits=(5, 1))
    tech = fields.Char(string="Техніка зони", size=32, help="Ключ техніки зони; порожньо — як у площадки")
    addr = fields.Json(
        string="Адресація місця", default=dict, help="R-22: порожньо — успадкувати від зони або площадки"
    )
    depth_mode = fields.Selection(
        DEPTH_MODE_SELECTION, string="Глибина локацій", help="Порожньо — успадкувати від зони або площадки"
    )
    cell_count = fields.Integer(string="Комірок", compute='_compute_cells', store=True)
    footprint_l_m = fields.Float(string="Довжина габариту, м", digits=(10, 3), compute='_compute_cells', store=True)
    footprint_w_m = fields.Float(string="Ширина габариту, м", digits=(10, 3), compute='_compute_cells', store=True)
    cells_html = fields.Html(string="Комірки", compute='_compute_cells_html', sanitize=False)
    note = fields.Text(string="Примітка")
    active = fields.Boolean(default=True)

    _f3d_slot_uid_uniq = models.Constraint('UNIQUE(site_id, uid)', "UID місця має бути унікальним на площадці.")
    _f3d_slot_prefix_uniq = models.Constraint(
        'UNIQUE(site_id, code_prefix)', "Префікс місця має бути унікальним на площадці."
    )

    # --- комірки (R-01) --------------------------------------------------------------------------------
    @api.depends(
        'template',
        'params',
        'overrides',
        'code_prefix',
        'addr',
        'depth_mode',
        'x_m',
        'y_m',
        'rotation',
        'layer_id',
        'site_id.addr',
        'site_id.depth_mode',
    )
    def _compute_cells(self):
        for slot in self:
            try:
                ctx = slot._td_addr_context() if isinstance(slot.id, int) else None
                slot.cell_count = cells_mod.count_cells(
                    slot.template, slot.code_prefix or '', slot.params, slot.overrides, ctx
                )
                slot.footprint_l_m, slot.footprint_w_m = cells_mod.footprint(slot.template, slot.params)
            except (cells_mod.CellsError, TypeError, ValueError):
                slot.cell_count, slot.footprint_l_m, slot.footprint_w_m = 0, 0.0, 0.0

    # --- адресація (F01): контекст місця, коди комірок, перенумерація ----------------------------------
    def _td_addr_dict(self):
        """Вхід `addr.address_context`: словник місця."""
        self.ensure_one()
        return {
            'uid': self.uid,
            'id': self.id,
            'layer_id': self.layer_id.id,
            'template': self.template,
            'code_prefix': self.code_prefix or '',
            'x': self.x_m,
            'y': self.y_m,
            'rotation': self.rotation,
            'params': self.params or {},
            'addr': self.addr or {},
            'depth_mode': self.depth_mode or None,
        }

    @api.model
    def _td_addr_contexts(self, site):
        """{uid: контекст адресації} активних місць площадки; кеш у курсорі (скидається в create/write/unlink)."""
        memo = self.env.cr.cache.setdefault('f3d_addr_memo', {})
        key = (site.id, site.addr and str(site.addr), site.depth_mode)
        if key not in memo:
            slots = self.sudo().search([('site_id', '=', site.id)])
            memo[key] = addr_mod.address_context(
                [slot._td_addr_dict() for slot in slots], site.addr or {}, site.depth_mode or 'level'
            )
        return memo[key]

    @api.model
    def _td_addr_memo_clear(self):
        self.env.cr.cache.pop('f3d_addr_memo', None)

    def _td_recompute_counts(self):
        """Місця залежать від зон (адресація, глибина): після зміни зони `cell_count` інших місць перераховується."""
        sites = self.mapped('site_id')
        if sites:
            others = self.sudo().search([('site_id', 'in', sites.ids), ('template', '!=', 'zone')]) - self
            self.env.add_to_compute(self._fields['cell_count'], others)

    def _td_addr_context(self):
        """Контекст адресації місця для `cells.generate_cells`; None — коди legacy і ярус як остання локація."""
        self.ensure_one()
        if not isinstance(self.id, int) or not self.site_id:
            return None
        ctx = self._td_addr_contexts(self.site_id).get(self.uid)
        if ctx and (ctx['addr'] or ctx['depth_mode'] == 'cell'):
            return ctx
        return None

    def _td_cells(self):
        """Комірки місця на льоту (R-01); у БД не зберігаються (DEC-15)."""
        self.ensure_one()
        return cells_mod.generate_cells(
            self.template,
            self.code_prefix,
            self.x_m,
            self.y_m,
            self.rotation,
            self.params,
            self.overrides,
            self.layer_id.elevation_m,
            self._td_addr_context(),
        )

    @api.model
    def _td_codes_map(self, sites):
        """{slot.id: [коди комірок]} усіх місць площадок (до перевизначень) — для перенумерації."""
        out = {}
        for site in sites:
            slots = self.sudo().search([('site_id', '=', site.id), ('template', '!=', 'zone')])
            contexts = self._td_addr_contexts(site)
            for slot in slots:
                ctx = contexts.get(slot.uid)
                try:
                    out[slot.id] = cells_mod.template_codes(
                        slot.template,
                        slot.params,
                        slot.code_prefix,
                        ctx if ctx and (ctx['addr'] or ctx['depth_mode'] == 'cell') else None,
                    )
                except (cells_mod.CellsError, addr_mod.AddrError):
                    out[slot.id] = []
        return out

    @api.model
    def _td_renumber(self, old_codes):
        """Після зміни адресації переносить ручні правки комірок (`overrides`) і розміщення (`cell_code`) на нові коди.

        `old_codes` — результат `_td_codes_map` до зміни. Зіставлення за порядком комірок; якщо їх число змінилось
        (глибина «комірка»), ключі без пари відкидаються з `overrides`, а розміщення лишаються без змін."""
        slots = self.sudo().browse(list(old_codes)).exists()
        self._td_addr_memo_clear()
        new_codes = self._td_codes_map(slots.mapped('site_id'))
        Placement = self.env['td.placement'].sudo()
        for slot in slots:
            old, new = old_codes[slot.id], new_codes.get(slot.id) or []
            if old == new:
                continue
            mapping = dict(zip(old, new, strict=False)) if len(old) == len(new) else {}
            if slot.overrides:
                keys = set(new)
                renamed = {mapping.get(k, k): v for k, v in slot.overrides.items() if mapping.get(k, k) in keys}
                if renamed != slot.overrides:
                    slot.with_context(f3d_no_touch=True).overrides = renamed
            for placement in Placement.search([('slot_id', '=', slot.id), ('cell_code', 'in', list(mapping))]):
                if mapping[placement.cell_code] != placement.cell_code:
                    placement.cell_code = mapping[placement.cell_code]

    def _td_footprint_obb(self):
        self.ensure_one()
        return cells_mod.slot_obb(self.template, self.params, self.x_m, self.y_m, self.rotation)

    @api.depends('template', 'params', 'overrides', 'code_prefix', 'x_m', 'y_m', 'rotation', 'layer_id.elevation_m')
    def _compute_cells_html(self):
        for slot in self:
            if not slot.template or not slot.code_prefix:
                slot.cells_html = False
                continue
            try:
                cells = slot._td_cells()
            except cells_mod.CellsError as exc:
                slot.cells_html = "<p>%s</p>" % escape(str(exc))
                continue
            rows = "".join(
                "<tr><td>%s</td><td>%d</td><td>%.2f</td><td>%.2f</td><td>%.2f</td><td>%g</td></tr>"
                % (escape(c['code']), c['level'], c['x'], c['y'], c['z0'], c['capacity'])
                for c in cells[:CELLS_HTML_LIMIT]
            )
            slot.cells_html = (
                "<table class='table table-sm'><thead><tr><th>Код</th><th>Ярус</th><th>X</th><th>Y</th><th>Z0</th>"
                "<th>Місткість</th></tr></thead><tbody>%s</tbody></table><p>Усього %d</p>" % (rows, len(cells))
            )

    # --- R-22 / R-11 -----------------------------------------------------------------------------------
    def _td_normalize_vals(self, vals):
        if isinstance(vals.get('code_prefix'), str) and len(vals['code_prefix']) > cells_mod.PREFIX_MAX_LEN:
            raise ValidationError("Префікс довший за %d символів." % cells_mod.PREFIX_MAX_LEN)
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
        if 'addr' in vals:
            try:
                vals['addr'] = addr_mod.normalize_addr(vals['addr'])
            except addr_mod.AddrError as exc:
                raise ValidationError("Адресація місця: %s" % exc) from None
        return vals

    @api.model
    def _td_check_create(self, vals_list):
        layers = self.env['td.layer'].browse([v['layer_id'] for v in vals_list if v.get('layer_id')])
        self._td_assert_layers(layers)

    def _td_check_write(self, vals):
        layers = self.mapped('layer_id')
        if vals.get('layer_id'):
            layers |= self.env['td.layer'].browse(vals['layer_id'])
        self._td_assert_layers(layers)

    def _td_check_unlink(self):
        self._td_assert_layers(self.mapped('layer_id'))

    @api.model_create_multi
    def create(self, vals_list):
        self._td_addr_memo_clear()
        try:
            slots = super().create(vals_list)
        finally:
            self._td_addr_memo_clear()
        if any(slot.template == 'zone' for slot in slots):
            slots._td_recompute_counts()
        slots._td_validate_overrides(strict_keys=[bool(v.get('overrides')) for v in vals_list])
        return slots

    def write(self, vals):
        renumber = bool({'addr', 'depth_mode'} & set(vals)) and not self.env.context.get('f3d_no_renumber')
        old_codes = self._td_codes_map(self.mapped('site_id')) if renumber else None
        self._td_addr_memo_clear()
        try:
            res = super().write(vals)
        finally:
            self._td_addr_memo_clear()
        if renumber:
            self._td_renumber(old_codes)
        if any(slot.template == 'zone' for slot in self) and {
            'addr',
            'depth_mode',
            'x_m',
            'y_m',
            'rotation',
            'params',
        } & set(vals):
            self._td_recompute_counts()
        if {'template', 'params', 'code_prefix', 'overrides'} & set(vals):
            self._td_validate_overrides(strict_keys=['overrides' in vals] * len(self))
        return res

    def unlink(self):
        zones = self.filtered(lambda slot: slot.template == 'zone')
        sites = zones.mapped('site_id')
        self._td_addr_memo_clear()
        try:
            res = super().unlink()
        finally:
            self._td_addr_memo_clear()
        if sites:
            self.env.add_to_compute(self._fields['cell_count'], self.sudo().search([('site_id', 'in', sites.ids)]))
        return res

    def _td_validate_overrides(self, strict_keys):
        """AC-13: ключ `overrides`, що не відповідає комірці шаблону, — ValidationError «Комірки X немає в шаблоні.»;
        якщо `overrides` не передавали (змінились параметри), недійсні ключі мовчки відкидаються."""
        for slot, strict in zip(self, strict_keys, strict=False):
            if not slot.overrides:
                continue
            codes = set(cells_mod.template_codes(slot.template, slot.params, slot.code_prefix, slot._td_addr_context()))
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
                    "Префікс «%s»: великі латинські літери, цифри й дефіси між групами, не більше %d символів."
                    % (slot.code_prefix, cells_mod.PREFIX_MAX_LEN)
                )

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

    @api.constrains('type_id', 'template')
    def _check_type(self):
        for slot in self:
            stype = slot.type_id
            if not stype:
                continue
            if not stype.template:
                raise ValidationError("Тип «%s» — об'єкт будівлі, а не місце зберігання." % stype.name)
            if stype.template != slot.template:
                raise ValidationError(
                    "Тип «%s» будується генератором «%s», а місце — «%s»." % (stype.name, stype.template, slot.template)
                )

    @api.constrains('depth_mode', 'addr')
    def _check_addr(self):
        for slot in self:
            try:
                addr_mod.normalize_addr(slot.addr)
            except addr_mod.AddrError as exc:
                raise ValidationError("Адресація місця %s: %s" % (slot.code_prefix, exc)) from None

    @api.constrains('x_m', 'y_m')
    def _check_position(self):
        for slot in self:
            if not (math.isfinite(slot.x_m) and math.isfinite(slot.y_m)):
                raise ValidationError("Координати місця мають бути скінченними числами.")
