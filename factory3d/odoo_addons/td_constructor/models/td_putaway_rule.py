from uuid import uuid4

from odoo import fields, models

PUTAWAY_SUBLOCATION_SELECTION = [('no', "Ні"), ('last_used', "Остання використана"), ('closest_location', "Найближча")]


class TdPutawayRule(models.Model):
    """Правило розміщення (F04): чернетка; у `stock.putaway.rule` потрапляє лише публікацією (Q4)."""

    _name = 'td.putaway.rule'
    _description = "Правило розміщення (чернетка)"
    _inherit = ['td.draft.mixin']
    _order = 'site_id, sequence, id'

    site_id = fields.Many2one('td.site', string="Площадка", required=True, ondelete='cascade', index=True)
    uid = fields.Char(string="UID", size=32, default=lambda self: uuid4().hex, copy=False, index=True, readonly=True)
    product_id = fields.Many2one('product.product', string="Товар", ondelete='cascade')
    category_id = fields.Many2one('product.category', string="Категорія товару", ondelete='cascade')
    package_type_ids = fields.Many2many(
        'stock.package.type',
        'td_putaway_rule_package_type_rel',
        'rule_id',
        'package_type_id',
        string="Типи упаковки",
    )
    in_location_id = fields.Many2one('stock.location', string="Звідки", ondelete='cascade')
    out_code = fields.Char(string="Код місця призначення", size=32, help="Код комірки чернетки, ще не опублікованої")
    out_location_id = fields.Many2one('stock.location', string="Куди", ondelete='cascade')
    sublocation = fields.Selection(PUTAWAY_SUBLOCATION_SELECTION, string="Підлокація", default='no')
    storage_category_id = fields.Many2one('stock.storage.category', string="Категорія зберігання", ondelete='cascade')
    sequence = fields.Integer(default=10)
    odoo_rule_id = fields.Many2one(
        'stock.putaway.rule', string="Правило в Odoo", copy=False, readonly=True, ondelete='set null', index=True
    )
    deleted = fields.Boolean(string="Видалено в чернетці", copy=False, help="Публікація видалить правило в Odoo")
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    active = fields.Boolean(default=True)

    _td_putaway_uid_uniq = models.Constraint('UNIQUE(site_id, uid)', "UID правила має бути унікальним на площадці.")
