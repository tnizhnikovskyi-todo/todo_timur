from odoo import fields, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    f3d_signal_id = fields.Many2one("f3d.signal", string="Сигнал", ondelete="set null", index=True)
    f3d_equipment_code = fields.Char(related="equipment_id.f3d_code", store=True, string="Код обладнання")
    f3d_origin = fields.Selection(
        [
            ("threshold", "Поріг сигналу"),
            ("meter", "ТО за лічильником"),
            ("stale", "Немає даних"),
            ("manual", "Вручну"),
        ],
        string="Джерело заявки",
    )
    f3d_value = fields.Float(string="Показник при створенні")
    f3d_threshold = fields.Float(string="Поріг")
    f3d_signal_status = fields.Selection(related="f3d_signal_id.status", string="Стан сигналу")

    def write(self, vals):
        if "stage_id" not in vals:
            return super().write(vals)
        before = {rec.id: rec.stage_id.done for rec in self}
        res = super().write(vals)
        for rec in self:
            was, now = before.get(rec.id), rec.stage_id.done
            if was == now:
                continue
            signal = rec.f3d_signal_id.sudo()
            if now:
                if signal:
                    signal._on_request_closed(rec)
                if rec.f3d_origin == "meter":
                    rec.equipment_id._f3d_meter_closed(rec)
            elif signal and not signal.maintenance_request_id:
                signal.with_context(mail_notrack=True).write({"maintenance_request_id": rec.id})
        return res

    def unlink(self):
        signals = self.env["f3d.signal"].sudo().search([("maintenance_request_id", "in", self.ids)])
        if signals:
            signals.with_context(mail_notrack=True).write(
                {"maintenance_request_id": False, "request_closed_at": fields.Datetime.now()}
            )
        return super().unlink()
