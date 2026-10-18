from odoo import fields, models


class TdPublishWizardLine(models.TransientModel):
    """MERGE.md §3.3: розширення рядка плану (F02) — нові види рядків і моделі, залежності, область, прежні значення.

    Розширення тут, а не в `td_publish_wizard.py`, щоб скелет W0-B не чіпав файл слайса S2; S2 може перенести поля."""

    _inherit = 'td.publish.wizard.line'

    kind = fields.Selection(
        selection_add=[
            ('move', "Буде переміщено"),
            ('rename', "Буде перейменовано"),
            ('attrs', "Буде змінено атрибути"),
        ],
        ondelete={'move': 'cascade', 'rename': 'cascade', 'attrs': 'cascade'},
    )
    res_model = fields.Selection(
        selection_add=[
            ('stock.warehouse.orderpoint', "Правило поповнення"),
            ('stock.putaway.rule', "Правило розміщення"),
        ],
        ondelete={'stock.warehouse.orderpoint': 'cascade', 'stock.putaway.rule': 'cascade'},
    )
    depends_code = fields.Char(string="Залежить від коду", help="Код рядка, який має бути застосований раніше")
    scope_uid = fields.Char(string="UID області", size=32, help="UID місця або зони, до якої належить рядок")
    before = fields.Json(string="Було", help="Прежні значення полів запису в Odoo")
