import logging

from odoo import api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

WRITABLE_SUFFIXES = ("/level", "/scene", "/mode", "/setpoint_day_c", "/setpoint_night_c")


class F3dSignal(models.Model):
    """M-13: розширення сигналу: обмеження запису (R-30) і хук після прийому показань (R-20)."""

    _inherit = "td.signal"

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

    @api.model_create_multi
    def create(self, vals_list):
        """R-15: `td_energy` (КГУ) і `fire_safety` можуть встановитися після `td_bms` — їхні сигнали з
        `hooks.BALANCE_OPTIONAL` привʼязуються до порожніх полів теплового балансу в момент створення."""
        recs = super().create(vals_list)
        from .. import hooks  # noqa: PLC0415 — hooks імпортує models

        wanted = recs.filtered(lambda r: r.code in hooks.BALANCE_OPTIONAL.values())
        if wanted and "td.bms.heat.balance" in self.env:
            self.env["td.bms.heat.balance"]._td_bms_link_optional(wanted)
        return recs

    @api.model
    def _td_ingest(self, readings, src="module", collector=None):
        """R-20: після прийому показань груп/установок оновити `off_since`/`low_since`/… (ізольовано)."""
        res = super()._td_ingest(readings, src=src, collector=collector)
        if self.env.context.get("f3d_bms_internal"):
            return res
        codes = [
            c for c in (res.get("changed_codes") or []) if c.startswith(("lighting/groups/", "ventilation/units/"))
        ]
        if not codes:
            return res
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param("td.bms.read_enabled", "False") not in ("True", "true", "1"):
            return res
        try:
            with self.env.cr.savepoint():
                self.env["td.bms.check"].sudo()._td_bms_on_ingest(codes)
        except Exception:
            _logger.exception("bms after ingest")
        return res
