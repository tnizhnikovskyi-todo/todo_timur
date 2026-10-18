import logging

from odoo import api, models, tools
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class F3dSignal(models.Model):
    _inherit = "f3d.signal"

    @api.constrains("write_enabled", "module", "source_id")
    def _check_f3d_fire_readonly(self):
        for rec in self:
            if rec.write_enabled and (rec.module == "fire_safety" or rec.source_id.f3d_fire_readonly):
                raise ValidationError("Сигнал пожежної безпеки %s працює лише на читання (D-07)." % rec.code)

    @api.model
    def _f3d_ingest(self, readings, src="module", collector=None):
        res = super()._f3d_ingest(readings, src=src, collector=collector)
        try:
            extra = self._f3d_fire_extra_codes()
            codes = [c for c in (res or {}).get("changed_codes") or [] if c.startswith("fire/") or c in extra]
            panel = self.env["f3d.fire.panel"].sudo()
            if codes and panel._get_param("read_enabled", True):
                with self.env.cr.savepoint():
                    panel._f3d_fire_sync(codes=codes)
        except Exception:
            _logger.exception("fire sync after ingest")
        return res

    @api.model
    @tools.ormcache()
    def _f3d_fire_extra_codes(self):
        """Коди `pressure_signal_id` систем (A-22)."""
        systems = self.env["f3d.fire.system"].sudo().with_context(active_test=False).search([])
        return frozenset(systems.pressure_signal_id.mapped("code"))
