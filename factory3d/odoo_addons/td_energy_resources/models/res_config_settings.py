"""M-11 `res.config.settings` — розширення: параметри `td.energy_resources.*` (блок «Енергоресурси» у налаштуваннях
`td_energy`; поля — `td_energy_resources_<ключ параметра>`)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

P = "td.energy_resources."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_energy_resources_boiler_eff = fields.Float(
        string="Проєктний ККД котельні", digits=(4, 3), config_parameter=P + "boiler_eff"
    )
    td_energy_resources_boiler_eff_norm = fields.Float(
        string="Норма ККД котельні, %", digits=(5, 1), config_parameter=P + "boiler_eff_norm"
    )
    td_energy_resources_night_from_h = fields.Float(
        string="Початок «ночі», год", digits=(4, 2), config_parameter=P + "night_from_h"
    )
    td_energy_resources_night_to_h = fields.Float(
        string="Кінець «ночі», год", digits=(4, 2), config_parameter=P + "night_to_h"
    )
    td_energy_resources_air_spec_norm = fields.Float(
        string="Норма питомої потужності повітря, кВт/(м³/хв)", digits=(5, 2), config_parameter=P + "air_spec_norm"
    )
    td_energy_resources_water_night_norm = fields.Float(
        string="Норма нічної витрати води, м³/год", digits=(5, 3), config_parameter=P + "water_night_norm"
    )
    td_energy_resources_boiler_makeup_norm = fields.Float(
        string="Норма підживлення котельні, м³/добу", digits=(5, 2), config_parameter=P + "boiler_makeup_norm"
    )
    td_energy_resources_air_setpoint_bar = fields.Float(
        string="Уставка тиску повітря (запасна, без сигналу energy_control/air/setpoint_bar), бар",
        digits=(4, 2),
        config_parameter=P + "air_setpoint_bar",
    )
    td_energy_resources_gap_max_s = fields.Integer(
        string="Макс. розрив показань для інтерполяції, с", config_parameter=P + "gap_max_s"
    )
    td_energy_resources_min_coverage = fields.Float(
        string="Мінімальне покриття слота даними", digits=(3, 2), config_parameter=P + "min_coverage"
    )
    td_energy_resources_export_max_days = fields.Integer(
        string="Макс. діб в одному xlsx", config_parameter=P + "export_max_days"
    )
    td_energy_resources_weeks_per_month = fields.Float(
        string="Тижнів на місяць (для резервів)", digits=(4, 2), config_parameter=P + "weeks_per_month"
    )
    td_energy_resources_no_price_count = fields.Integer(
        string="Ресурсів без ціни", compute="_compute_td_energy_resources_no_price_count"
    )

    def _compute_td_energy_resources_no_price_count(self):
        count = self.env["td.energy.resource"].td_no_price_count()
        for rec in self:
            rec.td_energy_resources_no_price_count = count

    @api.constrains(
        "td_energy_resources_night_from_h", "td_energy_resources_night_to_h", "td_energy_resources_gap_max_s",
        "td_energy_resources_min_coverage",
    )  # fmt: skip
    def _check_td_energy_resources(self):
        for rec in self:
            if not 0 <= rec.td_energy_resources_night_from_h < 24:
                raise ValidationError(_("Початок «ночі» має бути в межах 0…24 год."))
            if not 0 <= rec.td_energy_resources_night_to_h < 24:
                raise ValidationError(_("Кінець «ночі» має бути в межах 0…24 год."))
            if rec.td_energy_resources_gap_max_s < 300:
                raise ValidationError(_("Макс. розрив показань — не менше 300 с."))
            if not 0 < rec.td_energy_resources_min_coverage <= 1:
                raise ValidationError(_("Мінімальне покриття слота — в межах (0; 1]."))

    def set_values(self):
        self._check_td_energy_resources()
        return super().set_values()
