from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    td_site_id = fields.Many2one(
        'td.site',
        string="Площадка конструктора",
        index=True,
        copy=False,
        readonly=True,
        ondelete='set null',
        help="Запис керується конструктором розкладки (CC-01)",
    )
    td_slot_uid = fields.Char(string="UID місця", size=32, copy=False, readonly=True)
