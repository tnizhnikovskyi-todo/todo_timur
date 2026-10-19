"""M-10 `product.template.td_plate_area_m2` (W4-A): площа плити на одиницю продукту для драйвера `plate_m2`."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    td_plate_area_m2 = fields.Float(string="Площа плити, м²/од.", digits=(10, 4), default=0.0)

    @api.constrains("td_plate_area_m2")
    def _check_td_plate_area_m2(self):
        if any(rec.td_plate_area_m2 < 0 for rec in self):
            raise ValidationError(_("Площа плити не може бути від'ємною."))
