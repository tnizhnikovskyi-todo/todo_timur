import logging
import time
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ROTATE_BATCH = 50000
ROTATE_TIME_LIMIT_S = 60


class F3dReading(models.Model):
    _name = "td.reading"
    _description = "Телеметрія: показання"
    _order = "ts desc, id desc"
    _log_access = False
    _rec_name = "ts"

    signal_id = fields.Many2one("td.signal", string="Сигнал", required=True, ondelete="cascade", index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання", related="signal_id.equipment_id", store=True, index=True
    )
    ts = fields.Datetime(string="Час", required=True)
    value = fields.Float(string="Значення")
    text = fields.Char(string="Текст")
    quality = fields.Selection(
        [("good", "Добра"), ("uncertain", "Непевна"), ("bad", "Погана")], default="good", required=True, string="Якість"
    )
    src = fields.Selection(
        [("collector", "Колектор"), ("sim_data", "Рівень 0"), ("module", "Модуль"), ("manual", "Вручну")],
        default="collector",
        required=True,
        string="Джерело даних",
    )
    received_at = fields.Datetime(
        string="Отримано", required=True, default=fields.Datetime.now, help="Час прийому показання в Odoo"
    )
    unit = fields.Char(related="signal_id.unit")
    code = fields.Char(related="signal_id.code")

    _f3d_reading_uniq = models.Constraint("UNIQUE(signal_id, ts)", "Показання для цього сигналу і часу вже є.")

    def init(self):
        tools.sql.create_index(self.env.cr, "td_reading_ts_idx", self._table, ["ts"])

    def write(self, vals):
        admin = self.env.su or self.env.user.has_group("td_factory3d.group_td_admin")
        if set(vals) != {"quality"} or not admin:
            raise UserError(_("Показання не редагуються."))
        return super().write(vals)

    @api.model
    def _delete_old(self, table, column, cutoff, deadline):
        """Видалення пакетами за `ROTATE_BATCH`; повертає кількість видалених рядків."""
        total = 0
        while True:
            self.env.cr.execute(
                "DELETE FROM {t} WHERE id IN (SELECT id FROM {t} WHERE {c} < %s ORDER BY {c} LIMIT %s)".format(
                    t=table, c=column
                ),
                (cutoff, ROTATE_BATCH),
            )
            n = self.env.cr.rowcount
            total += n
            if n < ROTATE_BATCH or time.monotonic() > deadline:
                return total

    @api.model
    def _cron_rotate(self):
        """R-10: ротація показань, годинних агрегатів і журналу push-подій."""
        icp = self.env["ir.config_parameter"].sudo()
        now = fields.Datetime.now()
        keep_days = int(icp.get_param("td.telemetry.keep_days", "30") or 30)
        keep_hours_days = int(icp.get_param("td.telemetry.keep_hours_days", "400") or 400)
        deadline = time.monotonic() + ROTATE_TIME_LIMIT_S
        readings = self._delete_old("td_reading", "ts", now - timedelta(days=keep_days), deadline)
        hours = self._delete_old("td_reading_hour", "hour", now - timedelta(days=keep_hours_days), deadline)
        events = 0
        if "td.push.event" in self.env:
            events = self._delete_old("td_push_event", "ts", now - timedelta(days=keep_days), deadline)
        self.env.invalidate_all()
        _logger.info("f3d_telemetry rotate: readings=%s hours=%s events=%s", readings, hours, events)
        return {"readings": readings, "hours": hours, "events": events}
