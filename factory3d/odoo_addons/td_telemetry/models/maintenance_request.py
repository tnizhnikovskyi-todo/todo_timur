from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    td_signal_id = fields.Many2one("td.signal", string="Сигнал", ondelete="set null", index=True)
    td_equipment_code = fields.Char(related="equipment_id.td_code", store=True, string="Код обладнання")
    td_origin = fields.Selection(
        [
            ("threshold", "Поріг сигналу"),
            ("meter", "ТО за лічильником"),
            ("stale", "Немає даних"),
            ("manual", "Вручну"),
        ],
        string="Джерело заявки",
    )
    td_value = fields.Float(string="Показник при створенні")
    td_threshold = fields.Float(string="Поріг")
    td_signal_status = fields.Selection(related="td_signal_id.status", string="Стан сигналу")

    def write(self, vals):
        if "stage_id" not in vals:
            return super().write(vals)
        before = {rec.id: rec.stage_id.done for rec in self}
        res = super().write(vals)
        for rec in self:
            was, now = before.get(rec.id), rec.stage_id.done
            if was == now:
                continue
            signal = rec.td_signal_id.sudo()
            if now:
                if signal:
                    signal._on_request_closed(rec)
                if rec.td_origin == "meter":
                    rec.equipment_id._td_meter_closed(rec)
            elif signal and not signal.maintenance_request_id:
                signal.with_context(mail_notrack=True).write({"maintenance_request_id": rec.id})
        return res

    def unlink(self):
        signals = self.env["td.signal"].sudo().search([("maintenance_request_id", "in", self.ids)])
        if signals:
            signals.with_context(mail_notrack=True).write(
                {"maintenance_request_id": False, "request_closed_at": fields.Datetime.now()}
            )
        return super().unlink()
