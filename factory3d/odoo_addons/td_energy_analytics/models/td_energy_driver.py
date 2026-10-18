"""M-02 `td.energy.driver`, M-03 `td.energy.driver.value` (W4-A). Каркас: поля — за SPEC; `UNIQUE`, `_cron_values`,
`get_series` — воркер A (замінює файл цілком)."""

from odoo import fields, models


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


class TdEnergyDriverValue(models.Model):
    _name = "td.energy.driver.value"
    _description = "Енергетика: значення драйвера"
    _log_access = False
    _order = "day desc, driver_id"

    driver_id = fields.Many2one("td.energy.driver", string="Драйвер", required=True, index=True, ondelete="cascade")
    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    value = fields.Float(string="Значення", digits=(14, 3), required=True)
    quality = fields.Selection(
        [("measured", "Виміряно"), ("estimated", "Оцінка"), ("manual", "Вручну")], string="Якість", required=True
    )
    source_note = fields.Char(string="Джерело (примітка)", size=128)
