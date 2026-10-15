import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    """M-28: заявка з тривоги верстата (R-08 п. 1)."""

    _inherit = "maintenance.request"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        code_map = self.env["f3d.machine"]._f3d_code_map()
        for rec in records.filtered("f3d_signal_id"):
            machine_id, role = code_map.get(rec.f3d_signal_id.sudo().code, (False, False))
            if role != "alarm":
                continue
            machine = self.env["f3d.machine"].sudo().browse(machine_id)
            dt = machine.current_downtime_id
            if dt and not dt.date_end and not dt.maintenance_request_id:
                dt.write({"maintenance_request_id": rec.id})
                machine._f3d_post_request_event(dt)
        return records
