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
    # MERGE.md §3.3: номери сегментів адреси (заміна posx/posy/posz) — для сортування й пошуку; 0 — не задано
    td_row = fields.Integer(string="Ряд", copy=False, readonly=True, index=True)
    td_bay = fields.Integer(string="Секція", copy=False, readonly=True)
    td_level = fields.Integer(string="Ярус", copy=False, readonly=True)
    td_pos = fields.Integer(string="Позиція", copy=False, readonly=True)
