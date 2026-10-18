"""M-09 `td.energy.alloc.product_id` (W4-A). Каркас; заповнення для наявних рядків — `hooks._fill_alloc_product` (A)."""

from odoo import fields, models


class TdEnergyAlloc(models.Model):
    _inherit = "td.energy.alloc"

    product_id = fields.Many2one(
        "product.product", string="Продукт", related="production_id.product_id", store=True, index=True, readonly=True
    )
