import json
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

F3D_KIND_SELECTION = [
    ('location', 'Місце зберігання'),
    ('workcenter', 'Робочий центр'),
    ('equipment', 'Обладнання'),
    ('employee', 'Працівник'),
    ('dock', 'Ворота'),
    ('zone', 'Зона'),
    ('vehicle', 'Транспорт'),
    ('other', 'Інше'),
]


class F3dSceneMixin(models.AbstractModel):
    _name = 'f3d.scene.mixin'
    _description = 'Код сцени 3D'

    _f3d_kind = 'other'
    _f3d_resolve_order = ['f3d.zone', 'stock.location', 'mrp.workcenter',
                          'maintenance.equipment', 'hr.employee', 'stock.picking.batch']
    F3D_CODE_RE = re.compile(r'^[A-Z0-9]+(-[A-Z0-9]+)*$')

    f3d_code = fields.Char(
        string='Код сцени', index=True, copy=False,
        help="Код об'єкта в 3D-моделі (glTF extras code), напр. SAW-1, FG-R1-B01-L1, DOCK-W1")
    f3d_alias = fields.Char(
        string='Другий код сцени', index=True, copy=False,
        help="Ще один код того самого запису в 3D, якщо модель малює його двома об'єктами "
             "(ворота DOCK-W1 і майданчик UNLOAD-1)")
    f3d_kind = fields.Selection(
        F3D_KIND_SELECTION, string='Вид у сцені', required=True, index=True,
        default=lambda self: self._f3d_kind)
    f3d_viewer_available = fields.Boolean(compute='_compute_f3d_viewer_available')
    is_f3d_manager = fields.Boolean(compute='_compute_is_f3d_manager')

    _f3d_code_uniq = models.Constraint(
        'UNIQUE(f3d_code)', 'Код сцени має бути унікальним у межах моделі.')
    _f3d_alias_uniq = models.Constraint(
        'UNIQUE(f3d_alias)', 'Другий код сцени має бути унікальним у межах моделі.')

    # --- compute ---
    def _compute_f3d_viewer_available(self):
        available = self._f3d_viewer_installed()
        for rec in self:
            rec.f3d_viewer_available = available

    def _compute_is_f3d_manager(self):
        is_manager = self.env.user.has_group('factory3d_base.group_f3d_manager')
        for rec in self:
            rec.is_f3d_manager = is_manager

    # --- constraints ---
    @api.constrains('f3d_code', 'f3d_alias')
    def _check_f3d_codes(self):
        Model = self.with_context(active_test=False)
        for rec in self:
            code, alias = rec.f3d_code, rec.f3d_alias
            if code and (len(code) > 32 or not self.F3D_CODE_RE.match(code)):
                raise ValidationError(
                    "Код сцени %s: лише великі латинські літери, цифри й дефіси між групами "
                    "(напр. FG-R1-B01-L1)." % code)
            if alias and (len(alias) > 32 or not self.F3D_CODE_RE.match(alias)):
                raise ValidationError(
                    "Код сцени %s: лише великі латинські літери, цифри й дефіси між групами "
                    "(напр. FG-R1-B01-L1)." % alias)
            if alias and not code:
                raise ValidationError("Другий код сцени можна задати лише разом з основним.")
            if alias and alias == code:
                raise ValidationError("Другий код сцени збігається з основним.")
            for value, own in ((alias, 'f3d_alias'), (code, 'f3d_code')):
                if not value:
                    continue
                other = 'f3d_code' if own == 'f3d_alias' else 'f3d_alias'
                clash = Model.search([(other, '=', value), ('id', '!=', rec.id)], limit=1)
                if clash:
                    raise ValidationError(
                        "Код %s уже використаний записом %s." % (value, clash.display_name))

    # --- R-04 ---
    @api.model
    def _f3d_check_code_rights(self, vals):
        if (not self.env.su and {'f3d_code', 'f3d_alias', 'f3d_kind'} & set(vals)
                and not self.env.user.has_group('factory3d_base.group_f3d_manager')):
            raise AccessError("Змінювати код сцени може лише менеджер «Завод 3D».")

    def write(self, vals):
        self._f3d_check_code_rights(vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._f3d_check_code_rights(vals)
        return super().create(vals_list)

    # --- API ---
    @api.model
    def search_f3d(self, code):
        if not code:
            return self.browse()
        return self.with_context(active_test=False).search(
            ['|', ('f3d_code', '=', code), ('f3d_alias', '=', code)], limit=1)

    @api.model
    def f3d_resolve(self, code):
        for model in self._f3d_resolve_order:
            # носій може ще не мати домішки (модулі збираються поетапно) — пропускаємо
            if model in self.env and hasattr(self.env[model], 'search_f3d'):
                found = self.env[model].search_f3d(code)
                if found:
                    return found
        return None

    @api.model
    def f3d_resolve_all(self, code):
        result = {}
        for cls in self.env.registry.descendants(['f3d.scene.mixin'], '_inherit'):
            model = self.env.registry[cls] if isinstance(cls, str) else cls
            name = model._name
            if name not in self.env or self.env[name]._abstract:
                continue
            found = self.env[name].search_f3d(code)
            if found:
                result[name] = found
        return result

    def f3d_codes(self):
        self.ensure_one()
        return [c for c in (self.f3d_code, self.f3d_alias) if c]

    @api.model
    def _f3d_viewer_installed(self):
        return self.env['ir.module.module'].sudo().search_count(
            [('name', '=', 'factory3d_viewer'), ('state', '=', 'installed')]) > 0

    def action_f3d_show(self):
        self.ensure_one()
        if not self.f3d_code:
            raise UserError(
                "Запис не має коду сцени. Заповніть «Код сцени» на вкладці «Завод 3D».")
        if self._f3d_viewer_installed():
            return {
                'type': 'ir.actions.client',
                'tag': 'f3d_viewer.action',
                'name': 'Завод 3D',
                'target': 'current',
                'params': {
                    'code': self.f3d_code,
                    'alias': self.f3d_alias or False,
                    'model': self._name,
                    'res_id': self.id,
                    'kind': self.f3d_kind,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Модуль 3D-переглядача не встановлено',
                'message': 'Установіть factory3d_viewer, щоб показати %s у 3D.' % self.f3d_code,
                'type': 'warning',
                'sticky': False,
            },
        }

    @api.model
    def f3d_run_migration(self):
        if not self.env.user.has_group('factory3d_base.group_f3d_admin'):
            raise AccessError("Запускати міграцію може лише адміністратор «Завод 3D».")
        from .. import hooks
        report = hooks.run_all(self.sudo().env)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Завод 3D',
                'message': 'Міграцію виконано: %s' % json.dumps(report, ensure_ascii=False),
                'type': 'success',
                'sticky': True,
            },
        }
