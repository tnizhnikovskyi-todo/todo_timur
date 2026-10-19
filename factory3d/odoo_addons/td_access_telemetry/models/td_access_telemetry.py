import logging

from odoo import api, models

from odoo.addons.td_access.tools.params import CODE_RE

_logger = logging.getLogger(__name__)


class F3dAccessTelemetry(models.AbstractModel):
    _inherit = "td.access.telemetry"

    @api.model
    def _td_ensure_signals(self, devices=None):
        """M-17: створити відсутні сигнали СКУД; наявні (також архівні) не змінюються."""
        Signal = self.env["td.signal"].sudo().with_context(active_test=False)
        devices = devices or self.env["td.access.device"].sudo().search([])
        Equipment = self.env["maintenance.equipment"].sudo()
        rows = [
            (
                "access/readers/%s/last_event" % dev.code,
                "СКУД: остання подія %s" % dev.code,
                "event",
                False,
                dev.equipment_id.id or False,
            )
            for dev in devices
            if dev.code and CODE_RE.match(dev.code)
        ]
        rows.append(
            (
                "access/turnstiles/TURNSTILES/on_site",
                "СКУД: на території зараз",
                "gauge",
                "осіб",
                Equipment.search_f3d("TURNSTILES").id or False,
            )
        )
        rows.append(
            (
                "access/events",
                "СКУД: нові події за опитування",
                "event",
                False,
                Equipment.search_f3d("ACCESS").id or False,
            )
        )
        created = existing = 0
        for code, name, kind, unit, equipment_id in rows:
            if Signal.search([("code", "=", code)], limit=1):
                existing += 1
                continue
            Signal.create(
                {
                    "code": code,
                    "name": name,
                    "kind": kind,
                    "unit": unit,
                    "equipment_id": equipment_id,
                    "module": "access",
                    "origin": "module",
                    "source_id": False,
                    "address": {},
                    "period_s": 60,
                    "store_period_s": 0,
                    "create_request": False,
                    "viewer_visible": False,
                    "active": True,
                }
            )
            created += 1
        _logger.info("Сигнали СКУД: створено %d, наявних %d", created, existing)
        return {"created": created, "existing": existing}


class F3dAccessDevice(models.Model):
    _inherit = "td.access.device"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["td.access.telemetry"]._td_ensure_signals(records)
        return records

    def write(self, vals):
        res = super().write(vals)
        if "code" in vals:
            self.env["td.access.telemetry"]._td_ensure_signals(self)
        return res
