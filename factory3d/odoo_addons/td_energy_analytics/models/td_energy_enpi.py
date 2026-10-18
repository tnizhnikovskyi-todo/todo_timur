"""M-06 `td.energy.enpi` — EnPI за добами (W4-A). Каркас: поля — за SPEC; `enpi` (compute), `UNIQUE`, `_cron_enpi`,
`recompute`, `period_totals` — воркер A (замінює файл цілком)."""

from odoo import fields, models


class TdEnergyEnpi(models.Model):
    _name = "td.energy.enpi"
    _description = "Енергетика: EnPI за добу"
    _log_access = False
    _order = "day desc, baseline_id"

    baseline_id = fields.Many2one(
        "td.energy.baseline", string="Модель бази", required=True, index=True, ondelete="cascade"
    )
    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    actual = fields.Float(string="Факт", digits=(16, 3), required=True)
    expected = fields.Float(string="Очікування", digits=(16, 3))
    enpi = fields.Float(string="EnPI", digits=(8, 4))
    drivers = fields.Json(string="Значення драйверів")
    quality = fields.Selection(
        [("ok", "Повні"), ("no_driver", "Немає драйвера"), ("partial", "Неповні")], string="Якість"
    )
