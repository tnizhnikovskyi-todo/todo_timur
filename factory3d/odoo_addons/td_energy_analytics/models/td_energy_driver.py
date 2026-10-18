"""M-02 `td.energy.driver`, M-03 `td.energy.driver.value` (W4-A): драйвери нормалізації й їх суточні значення."""

import logging
from datetime import timedelta

from odoo import api, fields, models

from odoo.addons.td_energy.tools import dates

from ..tools import daily as daily_tools
from ..tools import drivers as driver_tools
from ..tools import periods

_logger = logging.getLogger(__name__)


class TdEnergyDriver(models.Model):
    _name = "td.energy.driver"
    _description = "Енергетика: драйвер"
    _order = "sequence, id"

    code = fields.Char(string="Код", size=16, required=True, index=True)
    name = fields.Char(string="Назва", size=64, required=True)
    source_kind = fields.Selection(
        [("mrp_area", "Площа плит з MRP"), ("weather_hdd", "Градусо-доби опалення"), ("manual", "Вручну")],
        string="Джерело",
        required=True,
    )
    uom = fields.Char(string="Одиниця", size=16)
    base_temp_c = fields.Float(string="Базова температура, °C", digits=(4, 1), default=18.0)
    temp_signal_code = fields.Char(string="Сигнал температури", size=64, default="ventilation/totals/outdoor_c")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    value_ids = fields.One2many("td.energy.driver.value", "driver_id", string="Значення")

    _code_uniq = models.Constraint("UNIQUE(code)", "Код драйвера має бути унікальним.")

    @api.model
    def _cron_values(self):
        """R-03: значення за вчора й пропуски останніх `catchup_days` діб для кожного автоматичного драйвера."""
        if not dates.param_bool(self.env, "read_enabled"):
            return 0
        self.env.flush_all()
        now = dates.now_utc(self.env)
        today = dates.local_day(now)
        catchup = max(1, periods.param_int(self.env, "catchup_days", 14))
        window = [today - timedelta(days=k) for k in range(1, catchup + 1)]
        cr, written = self.env.cr, 0
        plate_days = set()
        for driver in self.sudo().search([("source_kind", "!=", "manual")]):
            cr.execute(
                "SELECT day FROM td_energy_driver_value WHERE driver_id = %s AND day >= %s", (driver.id, window[-1])
            )
            have = {row[0] for row in cr.fetchall()}
            for day in window:
                if day in have and day != window[0]:
                    continue
                try:
                    with cr.savepoint():
                        d0, d1 = dates.local_day_bounds(day)
                        res = driver_tools.day_value(cr, driver, d0, d1)
                        if res is None:
                            continue
                        driver_tools.upsert(cr, driver.id, day, *res)
                        written += 1
                        if driver.source_kind == "mrp_area":
                            plate_days.add(day)
                except Exception:
                    _logger.exception("Енергетика: драйвер %s, доба %s", driver.code, day)
        self.env["td.energy.driver.value"].invalidate_model()
        if plate_days:
            daily_tools.refresh_plate(self.env, plate_days)
        return written


class TdEnergyDriverValue(models.Model):
    _name = "td.energy.driver.value"
    _description = "Енергетика: значення драйвера"
    _log_access = False
    _order = "day desc, driver_id"

    driver_id = fields.Many2one("td.energy.driver", string="Драйвер", required=True, index=True, ondelete="cascade")
    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    value = fields.Float(string="Значення", digits=(14, 3), required=True)
    quality = fields.Selection(
        [("measured", "Виміряно"), ("estimated", "Оцінка"), ("manual", "Вручну")],
        string="Якість",
        required=True,
        default="manual",
    )
    source_note = fields.Char(string="Джерело (примітка)", size=128)

    _driver_day_uniq = models.Constraint("UNIQUE(driver_id, day)", "Значення драйвера за цю добу вже є.")

    @api.model
    def get_series(self, driver_code, day_from, day_to):
        """API-15: `{iso_день: значення}` драйвера за `[day_from, day_to]`."""
        day_from, day_to = fields.Date.to_date(day_from), fields.Date.to_date(day_to)
        rows = self.search(
            [("driver_id.code", "=", driver_code), ("day", ">=", day_from), ("day", "<=", day_to)], order="day"
        )
        return {row.day.isoformat(): row.value for row in rows}
