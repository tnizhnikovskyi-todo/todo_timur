from odoo import _, api, models
from odoo.exceptions import ValidationError

from ..tools.dates import param_bool


class F3dSignal(models.Model):
    """M-15: заборона запису уставок (A-15) і журнал подій після прийому показань (R-13).
    Похідні й відключення АВР (R-14) додає W4 у `td.energy.event._f3d_on_ingest`."""

    _inherit = "td.signal"

    ENERGY_PREFIXES = ("energy/", "infra/pv/", "infra/bess/", "infra/chp/", "infra/ats/", "infra/totals/")

    @api.constrains("write_enabled", "module")
    def _check_f3d_energy_write(self):
        for rec in self:
            if rec.module == "energy" and rec.write_enabled:
                raise ValidationError(
                    _("Запис уставок у пристрої енергетики заборонено у v1 (td.energy.write_enabled).")
                )

    @api.model
    def _f3d_ingest(self, readings, src="module", collector=None):
        if self.env.context.get("f3d_energy_internal"):
            return super()._f3d_ingest(readings, src=src, collector=collector)
        before = self._f3d_energy_snapshot(readings)
        res = super()._f3d_ingest(readings, src=src, collector=collector)
        if before and param_bool(self.env, "read_enabled"):
            self.env["td.energy.event"].sudo()._f3d_on_ingest(before, readings)  # R-13, R-14
        return res

    @api.model
    def _f3d_energy_snapshot(self, readings):
        codes = set()
        for r in readings or ():
            code = str(r.get("code", "")) if isinstance(r, dict) else ""
            if code.startswith(self.ENERGY_PREFIXES) or (
                code.startswith("workcenters/") and code.endswith("/machine_state")
            ):
                codes.add(code)
        if not codes:
            return {}
        rows = self.sudo().search_read([("code", "in", list(codes))], ["code", "status", "last_text", "last_value"])
        return {s["code"]: (s["status"], s["last_text"], s["last_value"]) for s in rows}

    @api.model
    def _f3d_energy_put(self, readings):
        """Власні обчислені показання модуля: контекст `f3d_energy_internal`; події за змінами статусу — як для
        зовнішнього пакета (R-13 п. 1)."""
        if not readings:
            return None
        before = self._f3d_energy_snapshot(readings)
        res = self.with_context(f3d_energy_internal=True)._f3d_ingest(readings, src="module")
        if before:
            self.env["td.energy.event"].sudo()._f3d_on_ingest(before, readings)
        return res
