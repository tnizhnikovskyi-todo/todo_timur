"""M-05: модуль-власник `chp`, незмінність коду сигналу, хук прийому показань (R-04, R-09)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import bus
from ..tools.signals import PREFIX, cparam_bool


class TdSignal(models.Model):
    _inherit = "td.signal"

    module = fields.Selection(selection_add=[("chp", "Когенерація")], ondelete={"chp": "set default"})

    def write(self, vals):
        if "code" in vals:
            for rec in self:
                if rec.module == "chp" and vals["code"] != rec.code:
                    raise ValidationError(_("Код сигналу КГУ незмінний: на нього спирається пульт."))
        return super().write(vals)

    @api.model
    def _td_chp_snapshot(self, readings):
        """Стан сигналів `chp/…` пакета ДО прийому: `{code: (status, last_value, last_ts)}`."""
        codes = {
            str(r.get("code", ""))
            for r in readings or ()
            if isinstance(r, dict) and str(r.get("code", "")).startswith(PREFIX)
        }
        if not codes:
            return {}
        rows = self.sudo().search_read([("code", "in", sorted(codes))], ["code", "status", "last_value", "last_ts"])
        return {r["code"]: (r["status"], r["last_value"], r["last_ts"]) for r in rows}

    @api.model
    def _td_ingest(self, readings, src="module", collector=None):
        before = self._td_chp_snapshot(readings)
        res = super()._td_ingest(readings, src=src, collector=collector)
        if before:
            bus.tick(self.env, "state")
            if cparam_bool(self.env, "read_enabled"):
                self.env["td.chp.event"].sudo()._td_on_ingest(before, readings)  # R-04
                self.env["td.chp.command"].sudo()._td_on_ingest(before, readings)  # R-09
        return res
