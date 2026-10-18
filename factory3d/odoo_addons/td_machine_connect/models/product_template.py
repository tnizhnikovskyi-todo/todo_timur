import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    td_sheet_length_mm = fields.Integer(default=0, string="Лист: довжина, мм")
    td_sheet_width_mm = fields.Integer(default=0, string="Лист: ширина, мм")
    td_thickness_mm = fields.Integer(default=0, string="Лист: товщина, мм")

    _f3d_sheet_dims = models.Constraint(
        "CHECK(td_sheet_length_mm >= 0 AND td_sheet_width_mm >= 0 AND td_thickness_mm >= 0)",
        "Розміри листа не можуть бути від'ємними.",
    )

    @api.constrains("td_sheet_length_mm", "td_sheet_width_mm", "td_thickness_mm")
    def _check_f3d_sheet(self):
        for rec in self:
            flags = {rec.td_sheet_length_mm > 0, rec.td_sheet_width_mm > 0, rec.td_thickness_mm > 0}
            if len(flags) > 1:
                raise ValidationError(_("Задайте всі три розміри листа або жодного."))
