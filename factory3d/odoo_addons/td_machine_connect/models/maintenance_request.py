import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    """M-28: заявка з тривоги верстата (R-08 п. 1)."""

    _inherit = "maintenance.request"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        code_map = self.env["td.machine"]._td_code_map()
        for rec in records.filtered("td_signal_id"):
            machine_id, role = code_map.get(rec.td_signal_id.sudo().code, (False, False))
            if role != "alarm":
                continue
            machine = self.env["td.machine"].sudo().browse(machine_id)
            dt = machine.current_downtime_id
            # Стенд ТК-02: заявка з тривоги створюється раніше за перехід у `fault` (показання сигналу йдуть до диспетчера
            # верстата) — тоді поточний простій ще `idle`/`setup`; заявку на нього не вішаємо, її забере `_td_link_request`.
            if dt and not dt.date_end and not dt.maintenance_request_id and dt.state_kind == "fault":
                dt.write({"maintenance_request_id": rec.id})
                machine._td_post_request_event(dt)
        return records
