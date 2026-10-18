"""M-H7 `res.config.settings` — параметри `td.energy_mobile.*` (H.5.1); блок «Чергування» — V-H5."""

from odoo import fields, models

P = "td.energy_mobile."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_energy_mobile_keep_days = fields.Integer(
        string="Зберігати обходи, діб", config_parameter=P + "keep_days", default=730
    )
    td_energy_mobile_value_fresh_s = fields.Integer(
        string="Свіже значення сигналу, с", config_parameter=P + "value_fresh_s", default=120
    )
    td_energy_mobile_missed_event = fields.Boolean(
        string="Подія для не виконаного обходу", config_parameter=P + "missed_event", default=True
    )
    td_energy_mobile_history_limit = fields.Integer(
        string="Останніх обходів у вкладці", config_parameter=P + "history_limit", default=3
    )
