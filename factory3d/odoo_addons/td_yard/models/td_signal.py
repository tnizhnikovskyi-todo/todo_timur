import logging

from odoo import api, models

from ..tools import params as P

_logger = logging.getLogger(__name__)


class F3dSignal(models.Model):
    _inherit = "f3d.signal"

    @api.model
    def _f3d_ingest(self, readings, src="module", collector=None):
        res = super()._f3d_ingest(readings, src=src, collector=collector)
        if not isinstance(readings, list):
            return res
        bad = {x.get("i") for x in (res or {}).get("rejected", [])}
        yard = [
            r
            for i, r in enumerate(readings)
            if i not in bad
            and isinstance(r, dict)
            and str(r.get("code") or "").startswith(("yard/gates/", "yard/scale/"))
        ]
        if not yard or not P.get_bool(self.env, "read_enabled"):
            return res
        scales = [r for r in yard if r["code"].startswith("yard/scale/")]
        gates = [r for r in yard if r["code"].startswith("yard/gates/")]
        if scales:
            self._f3d_yard_safe(lambda: self.env["f3d.yard.scale"].sudo()._f3d_yard_dispatch_scales(scales))
        if gates and "f3d.yard.gate" in self.env:
            self._f3d_yard_safe(lambda: self.env["f3d.yard.gate"].sudo()._f3d_yard_dispatch(gates))
        return res

    def _f3d_yard_safe(self, func):
        try:
            with self.env.cr.savepoint():
                func()
        except Exception:
            _logger.exception("factory3d_yard: обробка показань двору")
