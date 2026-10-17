import logging
import mimetypes
import os
import tempfile

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..services import convert, glb_meta as glb_mod, schemas
from .f3d_equipment_passport import F3D_CATEGORY_SELECTION

_logger = logging.getLogger(__name__)

MODEL_STATUS_SELECTION = [
    ('none', "Немає"), ('ok', "Готово"), ('pending_conversion', "Очікує перетворення"), ('error', "Помилка"),
]
# R-18: дозволені розширення оригіналу
MODEL_FORMATS = ('glb', 'gltf', 'obj', 'mtl', 'fbx', 'stl', '3mf', 'dae', 'step', 'stp', 'iges', 'igs', 'ifc')
SERVER_CONVERT_FORMATS = ('step', 'stp', 'iges', 'igs', 'ifc')
# R-23: види шарів за замовчуванням за категорією паспорта
LAYER_KINDS_BY_CATEGORY = {
    'machine': ['production'], 'rack': ['storage'], 'forklift': ['storage', 'production', 'yard'],
    'conveyor': ['production'], 'panel': ['production', 'engineering'], 'robot': ['production'], 'other': [],
}
MODEL_FIELDS = ('model_status', 'model_original_id', 'model_glb_id', 'model_meta')
META_UNITS = ('mm', 'cm', 'm', 'in')
META_AXES = ('y', 'z')
ATTACHMENT_RES_MODEL = 'f3d.equipment.variant'


class F3dModelError(UserError):
    """Помилка завантаження моделі; `code` відповідає кодам API-09 (too_large, unsupported_format, bad_glb)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def model_extension(file_name):
    return os.path.splitext(os.path.basename(file_name or ''))[1].lstrip('.').lower()


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

    # --- compute ---------------------------------------------------------------------------------------
    @api.depends('name', 'passport_id.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s · %s" % (rec.passport_id.name or '', rec.name or '')

    @api.depends('weight_kg', 'length_mm', 'width_mm')
    def _compute_floor_load(self):
        for rec in self:
            area = rec.length_mm * rec.width_mm / 1_000_000.0
            rec.floor_load_kn_m2 = rec.weight_kg * 9.80665 / 1000.0 / area if area > 0 and rec.weight_kg else 0.0

    @api.depends('model_meta', 'model_status')
    def _compute_model_warning(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        max_tri = int(get('factory3d.constructor.max_triangles', 50000) or 50000)
        for rec in self:
            meta = rec.model_meta or {}
            parts = []
            triangles = meta.get('triangles') or 0
            if triangles > max_tri or 'triangles_over_limit' in (meta.get('warnings') or []):
                parts.append("%d тис. трикутників при ліміті %d тис." % (round(triangles / 1000), round(max_tri / 1000)))
            parts += [w for w in (meta.get('warnings') or []) if w != 'triangles_over_limit']
            rec.model_warning = "; ".join(parts) or False

    def _compute_placement_count(self):
        data = dict(self.env['f3d.placement'].with_context(active_test=False)._read_group(
            [('variant_id', 'in', self.ids)], ['variant_id'], ['__count']))
        for rec in self:
            rec.placement_count = data.get(rec, 0)

    # --- create / write / unlink -----------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        Passport = self.env['f3d.equipment.passport']
        Term = self.env['f3d.term']
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            passport = Passport.browse(vals['passport_id']) if vals.get('passport_id') else Passport
            if passport:
                for field, source in (('length_mm', 'dim_l_mm'), ('width_mm', 'dim_w_mm'), ('height_mm', 'dim_h_mm'),
                                      ('power_kw', 'power_kw')):
                    if not vals.get(field):
                        vals[field] = passport[source]
                if 'allowed_layer_kind_ids' not in vals:
                    keys = LAYER_KINDS_BY_CATEGORY.get(passport.f3d_category or 'other', [])
                    if keys:
                        terms = Term.search([('term_type', '=', 'layer_kind'), ('key', 'in', keys)])
                        vals['allowed_layer_kind_ids'] = [fields.Command.set(terms.ids)]
                if 'create_workcenter' not in vals and passport.f3d_category == 'machine':
                    vals['create_workcenter'] = True
            if 'utilities' in vals:
                vals['utilities'] = self._f3d_normalize_utilities(vals['utilities'])
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if 'utilities' in vals:
            vals = dict(vals, utilities=self._f3d_normalize_utilities(vals['utilities']))
        if not self.env.su and not self.env.context.get('f3d_model_write') and set(vals) & set(MODEL_FIELDS):
            raise AccessError("Поля 3D-моделі змінюються лише через завантаження моделі.")
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if self.env['f3d.placement'].with_context(active_test=False).search_count([('variant_id', '=', rec.id)]):
                raise UserError("Варіант «%s» використовується в розміщеннях: архівуйте його." % rec.display_name)
        attachments = self.mapped('model_original_id') | self.mapped('model_glb_id')
        res = super().unlink()
        attachments.sudo().unlink()
        return res

    @api.model
    def _f3d_normalize_utilities(self, value):
        try:
            return schemas.normalize_variant_utilities(value)
        except schemas.SchemaError as exc:
            raise ValidationError(str(exc)) from None

    # --- constraints -----------------------------------------------------------------------------------
    @api.constrains('length_mm', 'width_mm', 'height_mm')
    def _check_dimensions(self):
        for rec in self:
            if min(rec.length_mm, rec.width_mm, rec.height_mm) <= 0:
                raise ValidationError("Розміри варіанта мають бути додатними.")

    @api.constrains('service_front_mm', 'service_back_mm', 'service_left_mm', 'service_right_mm', 'power_kw',
                    'weight_kg', 'floor_load_kn_m2')
    def _check_non_negative(self):
        for rec in self:
            if min(rec.service_front_mm, rec.service_back_mm, rec.service_left_mm, rec.service_right_mm) < 0:
                raise ValidationError("Зона обслуговування не може бути від'ємною.")
            if rec.power_kw < 0 or rec.weight_kg < 0 or rec.floor_load_kn_m2 < 0:
                raise ValidationError("Потужність, маса й навантаження не можуть бути від'ємними.")

    @api.constrains('utilities')
    def _check_utilities(self):
        for rec in self:
            try:
                schemas.normalize_variant_utilities(rec.utilities)
            except schemas.SchemaError as exc:
                raise ValidationError(str(exc)) from None

    @api.constrains('model_status', 'model_meta', 'model_glb_id')
    def _check_model(self):
        for rec in self:
            meta_status = (rec.model_meta or {}).get('status')
            if meta_status and meta_status != rec.model_status:
                raise ValidationError("Статус моделі не збігається з її метаданими.")
            if rec.model_status == 'ok' and not rec.model_glb_id:
                raise ValidationError("Для статусу «Готово» потрібен файл GLB.")

    # --- геометрія й навантаження ----------------------------------------------------------------------
    def _f3d_effective_floor_load(self):
        self.ensure_one()
        return self.floor_load_kn_m2

    def _f3d_local_geometry(self):
        """Геометричний опис варіанта у форматі API-03 `catalog[].variants[]` (мм), без полів моделі й etag."""
        self.ensure_one()
        return {
            'id': self.id, 'name': self.name,
            'length': self.length_mm, 'width': self.width_mm, 'height': self.height_mm,
            'service': {'front': self.service_front_mm, 'back': self.service_back_mm,
                        'left': self.service_left_mm, 'right': self.service_right_mm},
            'rotations': self.rotation_mode, 'front_side': self.front_side, 'anchor': self.anchor,
            'layer_kinds': self.allowed_layer_kind_ids.mapped('key'),
            'slot_types': self.allowed_slot_type_ids.mapped('key'),
            'utilities': self.utilities or [], 'power_kw': self.power_kw, 'panel': self.panel or '',
            'weight_kg': self.weight_kg, 'floor_load': self._f3d_effective_floor_load(),
            'create_workcenter': self.create_workcenter,
        }

    # --- 3D-модель (R-18, R-19, R-20) ------------------------------------------------------------------
    def _f3d_params(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        try:
            max_mb = float(get('factory3d.constructor.max_model_mb', 20) or 20)
        except ValueError:
            max_mb = 20.0
        try:
            max_tri = int(get('factory3d.constructor.max_triangles', 50000) or 50000)
        except ValueError:
            max_tri = 50000
        return max_mb, max_tri, get('factory3d.constructor.convert_server_enabled', 'True') == 'True'

    def _f3d_new_attachment(self, file_name, raw, mimetype=None):
        file_name = os.path.basename(file_name or 'model')[:200] or 'model'
        return self.env['ir.attachment'].sudo().create({
            'name': file_name, 'raw': raw, 'res_model': ATTACHMENT_RES_MODEL, 'res_id': self.id,
            'mimetype': mimetype or mimetypes.guess_type(file_name)[0] or 'application/octet-stream',
        })

    def _f3d_set_model(self, original=None, glb=None, meta=None, status='ok', message=''):
        """Єдина точка запису полів моделі (R-18).

        `original`, `glb` — `(ім'я файла, bytes)` або None («без змін»). `meta` — довідкові дані клієнта: серверні значення
        (`triangles`, `bbox_m`, `size_mm`, розміри файлів) перезаписують клієнтські (R-19). Повертає `{model_status, model_meta}`.
        Помилки — `F3dModelError(code, message)`: too_large, unsupported_format, bad_glb; нічого не зберігається.
        """
        self.ensure_one()
        max_mb, max_tri, _enabled = self._f3d_params()
        limit = int(max_mb * 1048576)
        too_large = F3dModelError('too_large', "Файл більший за %g МБ" % max_mb)
        meta = meta if isinstance(meta, dict) else {}
        orig_name = orig_raw = glb_name = glb_raw = None
        if original:
            orig_name, orig_raw = original
            ext = model_extension(orig_name)
            if ext not in MODEL_FORMATS:
                raise F3dModelError(
                    'unsupported_format',
                    "Формат .%s не підтримується: експортуйте модель у GLB, OBJ, STL, FBX, 3MF, DAE, STEP, IGES або IFC." % (
                        ext or '?'))
            if len(orig_raw) > limit:
                raise too_large
        info = {}
        if glb:
            glb_name, glb_raw = glb
            if len(glb_raw) > limit:
                raise too_large
            if glb_raw[:4] != b'glTF':
                raise F3dModelError('bad_glb', "Файл GLB пошкоджено: немає сигнатури glTF.")
            try:
                info = glb_mod.glb_meta(glb_raw)
            except glb_mod.GlbError as exc:
                raise F3dModelError('bad_glb', str(exc)) from None
        if status == 'ok' and not (glb or self.model_glb_id):
            raise F3dModelError('bad_glb', "Для статусу «Готово» потрібен файл GLB.")

        new_meta = {} if original else dict(self.model_meta or {})
        for key in ('format', 'file_name', 'converted_by'):
            if isinstance(meta.get(key), str):
                new_meta[key] = os.path.basename(meta[key])[:200]
        if meta.get('units') in META_UNITS:
            new_meta['units'] = meta['units']
        if meta.get('up_axis') in META_AXES:
            new_meta['up_axis'] = meta['up_axis']
        warnings = [str(w)[:200] for w in (meta.get('warnings') or [])[:10] if isinstance(w, str)] if isinstance(
            meta.get('warnings'), list) else list(new_meta.get('warnings') or [])
        if original:
            new_meta['format'] = model_extension(orig_name)
            new_meta['file_name'] = os.path.basename(orig_name)[:200]
            new_meta['size_bytes'] = len(orig_raw)
        if glb:
            new_meta['glb_size_bytes'] = len(glb_raw)
            new_meta.update(info)
        triangles = new_meta.get('triangles') or 0
        warnings = [w for w in warnings if w != 'triangles_over_limit']
        if triangles > max_tri:
            warnings.append('triangles_over_limit')
        new_meta['warnings'] = warnings
        new_meta['status'] = status
        new_meta['message'] = message or ''
        new_meta.setdefault('converted_by', None)
        if original and not glb:
            new_meta['converted_by'] = None

        old = self.env['ir.attachment']
        vals = {'model_status': status, 'model_meta': new_meta}
        if original:
            old |= self.model_original_id
            vals['model_original_id'] = self._f3d_new_attachment(orig_name, orig_raw).id
        if glb:
            old |= self.model_glb_id
            vals['model_glb_id'] = self._f3d_new_attachment(glb_name, glb_raw, 'model/gltf-binary').id
        elif original:
            old |= self.model_glb_id
            vals['model_glb_id'] = False  # нове джерело без GLB: старий превью недійсний
        self.with_context(f3d_model_write=True).write(vals)
        old.sudo().unlink()
        return {'model_status': self.model_status, 'model_meta': self.model_meta}

    def _f3d_convert_model(self):
        """R-20: серверне перетворення STEP/IGES/IFC; не кидає винятків, повертає `{'ok', 'status', 'message'}`."""
        self.ensure_one()
        meta = dict(self.model_meta or {})
        ext = (meta.get('format') or model_extension(self.model_original_id.name)).lower()
        _max_mb, _max_tri, enabled = self._f3d_params()

        def pending(message):
            self.with_context(f3d_model_write=True).write({
                'model_status': 'pending_conversion', 'model_meta': dict(meta, status='pending_conversion', message=message)})
            return {'ok': False, 'status': 'pending_conversion', 'message': message}

        if not enabled:
            return pending("Серверне перетворення вимкнено")
        entry = convert.CONVERTERS.get(ext)
        try:
            available = bool(entry and entry[0]())
        except Exception:  # noqa: BLE001 - проба необов'язкової бібліотеки не має валити завантаження
            available = False
        if not available or not self.model_original_id:
            return pending(convert.UNAVAILABLE_MESSAGE)
        try:
            with tempfile.TemporaryDirectory(prefix='f3d_convert_') as tmp:
                in_path = os.path.join(tmp, 'model.%s' % ext)
                out_path = os.path.join(tmp, 'model.glb')
                with open(in_path, 'wb') as handle:
                    handle.write(self.model_original_id.raw or b'')
                entry[1](in_path, out_path, convert.CONVERT_TIMEOUT_S)
                with open(out_path, 'rb') as handle:
                    glb_raw = handle.read()
            base = os.path.splitext(meta.get('file_name') or 'model')[0]
            result = self._f3d_set_model(
                glb=("%s.glb" % base, glb_raw), meta=dict(meta, converted_by='server'), status='ok',
                message="Перетворено на сервері")
            return {'ok': True, 'status': result['model_status'], 'message': "Перетворено на сервері"}
        except Exception as exc:  # noqa: BLE001 - помилка конвертера → статус «Помилка», не виняток
            _logger.warning("Перетворення моделі варіанта %s не вдалося: %s", self.id, exc)
            text = "Не вдалося перетворити модель: %s" % (str(exc)[:300] or exc.__class__.__name__)
            self.with_context(f3d_model_write=True).write({
                'model_status': 'error', 'model_meta': dict(meta, status='error', message=text)})
            return {'ok': False, 'status': 'error', 'message': text}

    # --- дії -------------------------------------------------------------------------------------------
    def action_clear_model(self):
        """Скидає вкладення й метадані; право — технолог/менеджер (ACL запису варіанта)."""
        for rec in self:
            if not self.env.su and not self.env.user.has_group('factory3d_constructor.group_f3d_constructor_technologist'):
                raise AccessError("Видаляти модель може технолог або менеджер конструктора.")
            old = rec.model_original_id | rec.model_glb_id
            rec.with_context(f3d_model_write=True).write({
                'model_original_id': False, 'model_glb_id': False, 'model_meta': {}, 'model_status': 'none'})
            old.sudo().unlink()
        return True

    def action_retry_convert(self):
        self.ensure_one()
        result = self._f3d_convert_model()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': "Перетворення моделі", 'message': result['message'],
                       'type': 'success' if result['ok'] else 'warning', 'sticky': not result['ok']},
        }
