import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..tools import cutcsv

_logger = logging.getLogger(__name__)
MAX_ERRORS = 50


class F3dCutPartImportWizard(models.TransientModel):
    """M-26: імпорт деталей (CSV, Додаток E)."""

    _name = "td.cut.part.import.wizard"
    _description = "Розкрій: імпорт деталей"

    bom_id = fields.Many2one("mrp.bom", required=True)
    file = fields.Binary(required=True)
    filename = fields.Char()
    replace = fields.Boolean(default=False, string="Замінити наявні")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if "bom_id" in fields_list and not res.get("bom_id") and ctx.get("active_id"):
            if ctx.get("active_model") == "mrp.bom":
                res["bom_id"] = ctx["active_id"]
            elif ctx.get("active_model") == "td.cut.part":
                res["bom_id"] = self.env["td.cut.part"].browse(ctx["active_id"]).bom_id.id
        return res

    def action_import(self):
        self.ensure_one()
        try:
            text = base64.b64decode(self.file).decode("utf-8")
        except ValueError as e:
            raise UserError(_("Файл деталей: не UTF-8 (%s).", e)) from e
        rows, errors = cutcsv.parse_parts_csv(text)
        Product = self.env["product.product"]
        for row in rows:
            code = row["material"]
            row["material_product_id"] = False
            if code:
                plate = Product.search([("default_code", "=", code), ("td_sheet_length_mm", ">", 0)], limit=1)
                if plate:
                    row["material_product_id"] = plate.id
                else:
                    errors.append("рядок %d: material: плиту %s не знайдено" % (row["lineno"], code))
        if errors:
            extra = len(errors) - MAX_ERRORS
            shown = errors[:MAX_ERRORS] + ([_("… і ще %d", extra)] if extra > 0 else [])
            raise UserError("\n".join(shown))
        Part = self.env["td.cut.part"]
        if self.replace:
            Part.with_context(active_test=False).search([("bom_id", "=", self.bom_id.id)]).unlink()
        existing = {
            p.part_code: p for p in Part.with_context(active_test=False).search([("bom_id", "=", self.bom_id.id)])
        }
        for row in rows:
            vals = {k: v for k, v in row.items() if k not in ("lineno", "material")}
            vals["bom_id"] = self.bom_id.id
            part = existing.get(row["part_code"])
            if part:
                part.write({**vals, "active": True})
            else:
                Part.create(vals)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Імпорт деталей"),
                "message": _("Імпортовано %d деталей", len(rows)),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
