from uuid import uuid4

from odoo import fields, models


class TdReplenishRule(models.Model):
    """Правило поповнення min/max (F03-07): чернетка; у `stock.warehouse.orderpoint` потрапляє лише публікацією (Q4)."""

    _name = 'td.replenish.rule'
    _description = "Правило поповнення (чернетка)"
    _inherit = ['td.draft.mixin']
    _order = 'site_id, cell_code, id'

    site_id = fields.Many2one('td.site', string="Площадка", required=True, ondelete='cascade', index=True)
    uid = fields.Char(string="UID", size=32, default=lambda self: uuid4().hex, copy=False, index=True, readonly=True)
    product_id = fields.Many2one('product.product', string="Товар", required=True, ondelete='cascade')
    cell_code = fields.Char(string="Код комірки", size=32, help="Код комірки чернетки, ще не опублікованої")
    location_id = fields.Many2one('stock.location', string="Локація", ondelete='cascade')
    min_qty = fields.Float(string="Мінімум", digits='Product Unit')
    max_qty = fields.Float(string="Максимум", digits='Product Unit')
    odoo_orderpoint_id = fields.Many2one(
        'stock.warehouse.orderpoint',
        string="Правило в Odoo",
        copy=False,
        readonly=True,
        ondelete='set null',
        index=True,
    )
    deleted = fields.Boolean(string="Видалено в чернетці", copy=False, help="Публікація видалить правило в Odoo")
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)

    _td_replenish_uid_uniq = models.Constraint('UNIQUE(site_id, uid)', "UID правила має бути унікальним на площадці.")
