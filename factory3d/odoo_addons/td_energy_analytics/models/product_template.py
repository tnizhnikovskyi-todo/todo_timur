"""M-10 `product.template.td_plate_area_m2` (W4-A). Каркас: обмеження `≥ 0` — воркер A (замінює файл цілком)."""

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    td_plate_area_m2 = fields.Float(string="Площа плити, м²/од.", digits=(10, 4), default=0.0)
