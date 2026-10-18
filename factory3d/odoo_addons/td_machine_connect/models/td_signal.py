import logging

from odoo import api, fields, models

from .td_machine import env_default, param_bool

_logger = logging.getLogger(__name__)


class F3dSignal(models.Model):
    """M-18: вхід показань (`_f3d_ingest`, `_mark_stale` з `super()` першим)."""

    _inherit = "td.signal"

    @api.model
    def _f3d_ingest(self, readings, src="module", collector=None):
        res = super()._f3d_ingest(readings, src=src, collector=collector)
        if self.env.context.get("f3d_mc_internal") or not param_bool(self.env, "read_enabled", env_default(self.env)):
            return res
        # unknown_state telemetry приймає (q='bad') і лише повідомляє — такі показання модуль обробляє сам (R-01)
        rejected = {r["i"] for r in res.get("rejected", ()) if r.get("reason") != "unknown_state"}
        code_map = self.env["td.machine"]._f3d_code_map()
        mine = [dict(r, i=i) for i, r in enumerate(readings) if i not in rejected and r.get("code") in code_map]
        if mine:
            self.env["td.machine"].sudo()._f3d_dispatch(mine, src)
        return res

    def _mark_stale(self, reason):
        res = super()._mark_stale(reason)
        code_map = self.env["td.machine"]._f3d_code_map()
        for sig in self.filtered(lambda s: code_map.get(s.code, (0, ""))[1] == "state"):
            self.env["td.machine"].sudo().browse(code_map[sig.code][0])._f3d_mark_nodata(fields.Datetime.now(), reason)
        return res
