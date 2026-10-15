import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    f3d_sheet_length_mm = fields.Integer(default=0, string="Лист: довжина, мм")
    f3d_sheet_width_mm = fields.Integer(default=0, string="Лист: ширина, мм")
    f3d_thickness_mm = fields.Integer(default=0, string="Лист: товщина, мм")

    _f3d_sheet_dims = models.Constraint(
        "CHECK(f3d_sheet_length_mm >= 0 AND f3d_sheet_width_mm >= 0 AND f3d_thickness_mm >= 0)",
        "Розміри листа не можуть бути від'ємними.",
    )

    @api.constrains("f3d_sheet_length_mm", "f3d_sheet_width_mm", "f3d_thickness_mm")
    def _check_f3d_sheet(self):
        for rec in self:
            flags = {rec.f3d_sheet_length_mm > 0, rec.f3d_sheet_width_mm > 0, rec.f3d_thickness_mm > 0}
            if len(flags) > 1:
                raise ValidationError(_("Задайте всі три розміри листа або жодного."))
