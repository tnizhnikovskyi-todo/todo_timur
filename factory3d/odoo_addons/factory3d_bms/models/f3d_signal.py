from odoo import api, models
from odoo.exceptions import ValidationError

WRITABLE_SUFFIXES = ("/level", "/scene", "/mode", "/setpoint_day_c", "/setpoint_night_c")


class F3dSignal(models.Model):
    """M-13: розширення сигналу. Цей файл — частина W3 (обмеження запису R-30); `_f3d_ingest` (R-20) додає W4."""

    _inherit = "f3d.signal"

    @api.constrains("write_enabled")
    def _check_f3d_bms_write_enabled(self):
        for rec in self:
            if rec.module != "bms" or not rec.write_enabled:
                continue
            code = rec.code or ""
            parts = code.split("/")
            forbidden = (
                not code.endswith(WRITABLE_SUFFIXES)
                or (len(parts) > 2 and (parts[2].startswith("EF-") or parts[2] == "BOILER"))
                or code.startswith("equipment/BOILER/")
            )
            if forbidden:
                raise ValidationError("Сигнал %s модуля «Будівля» не керується (ARCH §1.4)." % code)
