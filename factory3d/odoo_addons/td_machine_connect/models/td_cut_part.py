import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

GRAINS = [("0", "Без текстури"), ("1", "Уздовж"), ("2", "Поперек")]
MATERIAL_ROLES = [
    ("main", "Основна плита (≥ 8 мм)"),
    ("back", "Тонка плита (< 8 мм)"),
    ("product", "Вказаний товар"),
]
PART_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,16}$")
EDGE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")
PROGRAM_RE = re.compile(r"^[A-Za-z0-9_\-\.]{1,64}$")
EDGE_FIELDS = ("edge_top", "edge_bottom", "edge_left", "edge_right")


class F3dCutPart(models.Model):
    _name = "td.cut.part"
    _description = "Розкрій: деталь виробу"
    _order = "bom_id, sequence, part_code"
    _rec_name = "name"

    bom_id = fields.Many2one("mrp.bom", string="Специфікація", required=True, index=True, ondelete="cascade")
    product_tmpl_id = fields.Many2one("product.template", related="bom_id.product_tmpl_id", store=True)
    sequence = fields.Integer(default=10)
    part_code = fields.Char(string="Код деталі", size=16, required=True)
    name = fields.Char(string="Назва", size=64, required=True)
    length_mm = fields.Integer(string="Довжина, мм", required=True)
    width_mm = fields.Integer(string="Ширина, мм", required=True)
    qty = fields.Float(string="На виріб, шт", required=True, default=1.0, digits=(8, 2))
    material_role = fields.Selection(MATERIAL_ROLES, string="Матеріал", required=True, default="main")
    material_product_id = fields.Many2one("product.product", string="Плита", domain="[('td_sheet_length_mm', '>', 0)]")
    grain = fields.Selection(GRAINS, string="Текстура", default="0", required=True)
    edge_top = fields.Char(string="Крайка верх", size=32)
    edge_bottom = fields.Char(string="Крайка низ", size=32)
    edge_left = fields.Char(string="Крайка ліво", size=32)
    edge_right = fields.Char(string="Крайка право", size=32)
    program = fields.Char(string="Програма ЧПК (MPR)", size=64)
    note = fields.Char(size=256)
    active = fields.Boolean(default=True)

    _f3d_part_uniq = models.Constraint("UNIQUE(bom_id, part_code)", "Код деталі повторюється в специфікації.")
    _f3d_part_dims = models.Constraint(
        "CHECK(length_mm BETWEEN 1 AND 5600 AND width_mm BETWEEN 1 AND 2200 AND qty > 0)",
        "Розміри деталі поза межами або кількість ≤ 0.",
    )

    @api.constrains("part_code", "name", "program", *EDGE_FIELDS, "material_role", "material_product_id")
    def _check_f3d_part(self):
        for rec in self:
            if not PART_CODE_RE.match(rec.part_code or ""):
                raise ValidationError(_("Деталь %s: %s", rec.part_code, _("код деталі: латиниця, цифри, _ і -, ≤ 16")))
            if ";" in (rec.name or "") or "\n" in (rec.name or "") or "\r" in (rec.name or ""):
                raise ValidationError(_("Деталь %s: %s", rec.part_code, _("назва без «;» і переносів")))
            for f in EDGE_FIELDS:
                if rec[f] and not EDGE_RE.match(rec[f]):
                    raise ValidationError(_("Деталь %s: %s", rec.part_code, _("крайка %s недопустима", rec[f])))
            if rec.program and not PROGRAM_RE.match(rec.program):
                raise ValidationError(_("Деталь %s: %s", rec.part_code, _("програма недопустима")))
            if rec.material_role == "product" and not rec.material_product_id:
                raise ValidationError(_("Для матеріалу «Вказаний товар» оберіть плиту."))
