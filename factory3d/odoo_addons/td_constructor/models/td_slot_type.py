from odoo import fields, models

from .td_slot import SLOT_TEMPLATE_SELECTION

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
