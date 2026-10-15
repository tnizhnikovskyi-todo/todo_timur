from datetime import timedelta

from odoo import api, models
from odoo.tools import html2plaintext

from ..tools import dates
from ..tools import payload as payload_tools

QC_CODE = "QC-1"


class F3dViewerProviderQuality(models.AbstractModel):
    """M-01d: перевірки якості (лише якщо є quality.check — Enterprise)."""
    _name = "f3d.viewer.provider.quality"
    _inherit = "f3d.viewer.provider"
    _description = "3D: провайдер даних quality"

    _f3d_sequence = 45
    _f3d_sections = ("quality_checks",)

    @api.model
    def _f3d_viewer_bus_models(self):
        return ["quality.check"]

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        env = self.env
        if not payload_tools.access_ok(env, "quality.check"):
            payload["quality_checks"] = []
            ctx["sections"]["quality_checks"] = "missing" if "quality.check" not in env else "denied"
            return
        since = dates.utc(ctx["today"] + " 00:00") - timedelta(days=7)
        checks = env["quality.check"].search(["|", ("create_date", ">=", since), ("quality_state", "=", "fail")],
                                             order="id")
        quarantine = set()
        if payload_tools.access_ok(env, "stock.quant") and checks.lot_id:
            quarantine = {q.lot_id.id for q in env["stock.quant"].search([
                ("lot_id", "in", checks.lot_id.ids), ("quantity", "!=", 0), ("location_id.f3d_code", "=", QC_CODE)])}
        fields = env["quality.check"]._fields
        out = []
        for c in checks:
            title = (c.point_id.title if "point_id" in fields else "") or (
                c.test_type_id.name if "test_type_id" in fields else "") or c.name
            location = QC_CODE if c.lot_id.id in quarantine else (c.picking_id.location_dest_id.f3d_code or "")
            note = ""
            for f in ("additional_note", "note"):
                if f in fields and c[f]:
                    note = html2plaintext(c[f]).strip()
                    if note:
                        break
            rec = {"name": c.name, "title": title, "product": c.product_id.default_code or "",
                   "state": c.quality_state, "location": location, "note": note[:300]}
            if c.lot_id:
                rec["lot"] = c.lot_id.name
            if c.picking_id:
                rec["picking"] = c.picking_id.name
            if c.production_id:
                rec["production"] = c.production_id.name
            out.append(rec)
        payload["quality_checks"] = out

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """Цілком, якщо є події quality.check."""
        if (ctx.get("changes") or {}).get("quality.check"):
            tmp = {}
            self._f3d_viewer_collect(tmp, ctx)
            payload_tools.deep_merge(patch, {"quality_checks": tmp.get("quality_checks") or []})
