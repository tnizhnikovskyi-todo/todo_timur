import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..services import cells as cells_mod
from ..services.schemas import SchemaError, check_json_limits
from .td_slot import SLOT_TEMPLATE_SELECTION

CODE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_]{0,31}$')
MANAGER_XMLID = 'td_constructor.group_td_constructor_manager'

SLOT_TYPE_GROUP_SELECTION = [
    ('rack', "Стелажні"),
    ('floor', "Підлогові"),
    ('special', "Спеціальні"),
    ('zone', "Буферні та технологічні зони"),
    ('mobile', "Мобільні носії"),
]
# значення stock.location.td_loc_kind (td_factory3d)
LOC_KIND_SELECTION = [
    ('stack', "Стос плит"),
    ('bin', "Комірка фурнітури"),
    ('shelf', "Полиця крайки"),
    ('pallet_cell', "Комірка палет ГП"),
    ('kit', "Візок / етажерка комплекту"),
    ('area', "Майданчик"),
]


class TdSlotType(models.Model):
    """Тип місця (F08, O-01): генератор, параметри за замовчуванням, форма 3D, група. Каталог (50 типів) сіє S1."""

    _name = 'td.slot.type'
    _description = "Тип місця"
    _order = 'group, sequence, id'
    _rec_name = 'name'
    _rec_names_search = ['name', 'code', 'ref']

    code = fields.Char(string="Ключ", size=32, required=True, index=True, help="Стабільний ключ типу (латиниця)")
    ref = fields.Char(string="Позначення", size=16, help="Позначення в каталозі: R01, FL2, SP3 …")
    name = fields.Char(string="Назва", required=True)
    description = fields.Text(string="Опис")
    group = fields.Selection(SLOT_TYPE_GROUP_SELECTION, string="Група", required=True, default='rack', index=True)
    template = fields.Selection(
        SLOT_TEMPLATE_SELECTION, string="Генератор", help="Порожньо — об'єкт будівлі (ворота/док), без комірок"
    )
    shape = fields.Char(string="Форма 3D", size=32, help="Ключ форми з реєстру shapes ядра")
    params = fields.Json(string="Параметри за замовчуванням", default=dict)
    relevance = fields.Integer(
        string="Важливість",
        default=0,
        help="0 — немає на фабриці (—), 1 — буває (○), 2 — є (●); за замовчуванням показуються 1 і 2 (Q9)",
    )
    loc_kind = fields.Selection(LOC_KIND_SELECTION, string="Вид локації Odoo")
    is_custom = fields.Boolean(string="Власний тип", default=False, help="Створено користувачем; типи каталогу — ні")
    company_id = fields.Many2one(
        'res.company', string="Компанія", index=True, help="Порожньо — тип каталогу, спільний для всіх компаній"
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _td_slot_type_code_uniq = models.UniqueIndex(
        '(code, COALESCE(company_id, 0))', "Ключ типу має бути унікальним у межах компанії."
    )
    _td_slot_type_relevance_check = models.Constraint(
        'CHECK(relevance BETWEEN 0 AND 2)', "Важливість типу: 0, 1 або 2."
    )

    # --- R-22: параметри типу ------------------------------------------------------------------------
    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not CODE_RE.match(rec.code or ''):
                raise ValidationError("Ключ типу «%s»: латиниця, цифри та _ (до 32 символів)." % rec.code)

    @api.constrains('template', 'params', 'shape')
    def _check_params(self):
        for rec in self:
            params = rec.params or {}
            if not isinstance(params, dict):
                raise ValidationError("Тип «%s»: параметри мають бути об'єктом." % rec.name)
            try:
                check_json_limits(params)
            except SchemaError as exc:
                raise ValidationError("Тип «%s»: %s" % (rec.name, exc)) from None
            if rec.shape and rec.shape not in cells_mod.SHAPE_KEYS:
                raise ValidationError("Тип «%s»: невідома форма 3D «%s»." % (rec.name, rec.shape))
            if not rec.template:
                continue  # об'єкт будівлі (ворота/док): параметри — довільні, без генератора
            try:
                cells_mod.normalize_params(rec.template, params)
            except cells_mod.CellsError as exc:
                raise ValidationError("Тип «%s»: %s" % (rec.name, exc)) from None

    @api.constrains('template', 'loc_kind')
    def _check_template_spot(self):
        for rec in self:
            if rec.template in ('machine_spot', 'zone'):
                raise ValidationError(
                    "Тип «%s»: генератор «%s» не має комірок — тип місця будується іншими." % (rec.name, rec.template)
                )

    # --- права (§3.5): каталог змінює менеджер, свої типи — проєктувальники, видаляє менеджер -------------
    @api.model
    def _f3d_is_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_XMLID)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._f3d_is_manager():
            out = []
            for vals in vals_list:
                if vals.get('is_custom') is False or vals.get('company_id') is False:
                    raise AccessError("Типи каталогу створює лише менеджер конструктора; власні типи — «is_custom».")
                out.append(dict(vals, is_custom=True, company_id=vals.get('company_id') or self.env.company.id))
            vals_list = out
        return super().create(vals_list)

    def write(self, vals):
        if not self._f3d_is_manager():
            if any(not rec.is_custom or not rec.company_id for rec in self):
                raise AccessError("Тип каталогу змінює лише менеджер конструктора.")
            if vals.get('is_custom') is False or ('company_id' in vals and not vals['company_id']):
                raise AccessError("Власний тип не можна зробити типом каталогу.")
        return super().write(vals)

    def unlink(self):
        if not self._f3d_is_manager():
            raise AccessError("Видаляти типи з бібліотеки може лише менеджер конструктора.")
        return super().unlink()
