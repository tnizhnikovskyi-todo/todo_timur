from odoo import _, api, models
from odoo.exceptions import ValidationError


class F3dSignal(models.Model):
    """M-15: заборона запису уставок у пристрої енергетики (A-15).
    Перевизначення `_f3d_ingest` (R-13, R-14) додає W3 разом з `f3d.energy.event`."""

    _inherit = "f3d.signal"

    @api.constrains("write_enabled", "module")
    def _check_f3d_energy_write(self):
        for rec in self:
            if rec.module == "energy" and rec.write_enabled:
                raise ValidationError(
                    _("Запис уставок у пристрої енергетики заборонено у v1 (factory3d.energy.write_enabled).")
                )
