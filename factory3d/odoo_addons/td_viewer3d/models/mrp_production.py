from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    f3d_has_3d = fields.Boolean(string="Є що показати в 3D", compute="_compute_f3d_has_3d")

    @api.depends("workorder_ids.workcenter_id.f3d_code")
    def _compute_f3d_has_3d(self):
        for rec in self:
            rec.f3d_has_3d = any(wo.workcenter_id.f3d_code for wo in rec.workorder_ids)

    def action_f3d_show(self):
        """M-08: відкрити переглядач на вкладці виробництва з виділенням МО (для кількох записів — перший)."""
        rec = self[:1]
        return {
            "type": "ir.actions.client",
            "tag": "f3d_viewer.action",
            "name": "3D: " + (rec.name or ""),
            "params": {"mo": rec.name, "tab": "production"},
        }
