from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    f3d_has_3d = fields.Boolean(string="Є що показати в 3D", compute="_compute_f3d_has_3d")

    @api.depends("batch_id.dock_id.f3d_code", "move_line_ids.location_id.f3d_code",
                 "move_line_ids.location_dest_id.f3d_code")
    def _compute_f3d_has_3d(self):
        for rec in self:
            rec.f3d_has_3d = bool(
                rec.batch_id.dock_id.f3d_code
                or any(ml.location_id.f3d_code or ml.location_dest_id.f3d_code for ml in rec.move_line_ids))

    def action_f3d_show(self):
        """M-08: відкрити переглядач на вкладці логістики з виділенням переміщення."""
        rec = self[:1]
        return {
            "type": "ir.actions.client",
            "tag": "f3d_viewer.action",
            "name": "3D: " + (rec.name or ""),
            "params": {"picking": rec.name, "tab": "logistics"},
        }
