from datetime import timedelta

from odoo import api, fields, models

GC_BATCH = 5000


class F3dSimEvent(models.Model):
    _name = "td.sim.event"
    _description = "Подія емулятора"
    _order = "ts desc, id desc"

    ts = fields.Datetime(string="Час", required=True, index=True, default=fields.Datetime.now)
    kind = fields.Selection(
        [
            ("scenario", "Сценарій"),
            ("fault", "Збій"),
            ("alarm", "Тривога"),
            ("info", "Інформація"),
            ("error", "Помилка"),
            ("command", "Команда"),
        ],
        string="Вид",
        required=True,
    )
    device_code = fields.Char(string="Код пристрою", index=True)
    device_id = fields.Many2one(
        "td.sim.device", string="Пристрій", compute="_compute_device_id", store=True, ondelete="set null"
    )
    run_id = fields.Many2one("td.sim.run", string="Запуск", ondelete="set null")
    message = fields.Char(string="Повідомлення", required=True)
    payload = fields.Json(string="Дані")

    @api.depends("device_code")
    def _compute_device_id(self):
        codes = {c for c in self.mapped("device_code") if c}
        devices = {d.code: d for d in self.env["td.sim.device"].sudo().search([("code", "in", list(codes))])}
        for rec in self:
            rec.device_id = devices.get(rec.device_code, False)

    @api.model
    def _gc(self, days):
        """Видалити події старіші за `days` діб (крон C-02), батчами по 5000."""
        limit_dt = fields.Datetime.now() - timedelta(days=int(days or 14))
        while True:
            batch = self.sudo().search([("ts", "<", limit_dt)], limit=GC_BATCH)
            if not batch:
                break
            batch.unlink()
            if len(batch) < GC_BATCH:
                break

    @api.model
    def _cron_gc(self):
        keep = self.env["ir.config_parameter"].sudo().get_param("td.iot_sim.keep_days", "14")
        self._gc(int(keep or 14))
