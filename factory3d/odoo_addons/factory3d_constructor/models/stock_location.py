from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    f3d_site_id = fields.Many2one(
        'f3d.site', string="Площадка конструктора", index=True, copy=False, readonly=True, ondelete='set null',
        help="Запис керується конструктором розкладки (CC-01)")
    f3d_slot_uid = fields.Char(string="UID місця", size=32, copy=False, readonly=True)
