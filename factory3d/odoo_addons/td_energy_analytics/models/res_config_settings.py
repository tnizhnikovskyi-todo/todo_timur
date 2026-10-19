"""M-15 `res.config.settings` — параметри `td.energy_analytics.*` (W4-A): поля за SPEC 5.1; валідація
`r2_min ∈ [0, 1]`, `forecast_min_days ≤ forecast_weeks`, `daily_close_h ∈ [0, 12]`."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

P = "td.energy_analytics."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_energy_analytics_daily_close_h = fields.Integer(
        string="Закриття вчорашньої доби до, год", config_parameter=P + "daily_close_h", default=2
    )
    td_energy_analytics_catchup_days = fields.Integer(
        string="Глибина догону, діб", config_parameter=P + "catchup_days", default=14
    )
    td_energy_analytics_forecast_weeks = fields.Integer(
        string="Тижнів для типових діб", config_parameter=P + "forecast_weeks", default=8
    )
    td_energy_analytics_forecast_min_days = fields.Integer(
        string="Мінімум діб для типових", config_parameter=P + "forecast_min_days", default=3
    )
    td_energy_analytics_r2_min = fields.Float(
        string="Мінімальний R² для затвердження", digits=(3, 2), config_parameter=P + "r2_min", default=0.6
    )
    td_energy_analytics_baseline_min_days = fields.Integer(
        string="Мінімальна довжина періоду бази, діб", config_parameter=P + "baseline_min_days", default=30
    )
    td_energy_analytics_refresh_s = fields.Integer(
        string="Автооновлення екрана, с", config_parameter=P + "refresh_s", default=300
    )
    td_energy_analytics_top_equipment = fields.Integer(
        string="Рядків у розрізі «Обладнання»", config_parameter=P + "top_equipment", default=15
    )
    td_energy_analytics_top_mo = fields.Integer(
        string="Рядків у розрізі «Замовлення»", config_parameter=P + "top_mo", default=20
    )

    @api.constrains(
        "td_energy_analytics_r2_min", "td_energy_analytics_forecast_min_days", "td_energy_analytics_forecast_weeks",
        "td_energy_analytics_daily_close_h",
    )  # fmt: skip
    def _check_td_energy_analytics(self):
        for rec in self:
            if not 0.0 <= rec.td_energy_analytics_r2_min <= 1.0:
                raise ValidationError(_("Мінімальний R² має бути в межах від 0 до 1."))
            if rec.td_energy_analytics_forecast_min_days > rec.td_energy_analytics_forecast_weeks:
                raise ValidationError(_("Мінімум діб для типових не може перевищувати число тижнів."))
            if not 0 <= rec.td_energy_analytics_daily_close_h <= 12:
                raise ValidationError(_("Година закриття доби має бути від 0 до 12."))
