from odoo import fields, models

PUBLISH_OP_SELECTION = [
    ('create', "Створено"),
    ('move', "Переміщено"),
    ('rename', "Перейменовано"),
    ('attrs', "Змінено атрибути"),
    ('archive', "Архівовано"),
]
PUBLISH_RES_MODEL_SELECTION = [
    ('stock.location', "Локація"),
    ('maintenance.equipment', "Обладнання"),
    ('mrp.workcenter', "Робочий центр"),
    ('stock.warehouse.orderpoint', "Правило поповнення"),
    ('stock.putaway.rule', "Правило розміщення"),
]


class TdPublishOp(models.Model):
    """Журнал публікації (F02-08): операція в Odoo з прежніми й новими значеннями; за ним працює відкат."""

    _name = 'td.publish.op'
    _description = "Операція публікації"
    _order = 'version_id, seq, id'

    version_id = fields.Many2one(
        'td.layout.version', string="Версія", required=True, ondelete='cascade', index=True, readonly=True
    )
    seq = fields.Integer(string="№ п/п", readonly=True)
    op = fields.Selection(PUBLISH_OP_SELECTION, string="Операція", required=True, readonly=True)
    res_model = fields.Selection(PUBLISH_RES_MODEL_SELECTION, string="Модель", required=True, readonly=True)
    res_id = fields.Integer(string="ID запису", readonly=True)
    code = fields.Char(string="Код", readonly=True)
    before = fields.Json(string="Було", readonly=True)
    after = fields.Json(string="Стало", readonly=True)
    rolled_back = fields.Boolean(string="Відкочено", readonly=True, default=False)
