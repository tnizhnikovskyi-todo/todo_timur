import secrets

from odoo import fields, models

ADMIN = 'td_factory3d.group_td_admin'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    td_sim_url = fields.Char(
        string='Адреса сервісу емулятора', config_parameter='td.iot_sim.url', groups=ADMIN)
    td_sim_token = fields.Char(
        string='Токен /sim/v1', config_parameter='td.iot_sim.token', groups=ADMIN)
    td_sim_export_token = fields.Char(
        string='Токен експорту (емулятор → Odoo)', config_parameter='td.iot_sim.export_token', groups=ADMIN)
    td_sim_read_enabled = fields.Boolean(
        string='Опитувати стан сервісу', config_parameter='td.iot_sim.read_enabled', groups=ADMIN)
    td_sim_write_enabled = fields.Boolean(
        string='Дозволити команди (сценарії, збої, час)', config_parameter='td.iot_sim.write_enabled',
        groups=ADMIN)
    td_sim_mode = fields.Selection(
        [('scenario', 'Сценарій'), ('follow_odoo', 'За Odoo')], string='Режим за замовчуванням',
        config_parameter='td.iot_sim.mode', groups=ADMIN)
    td_sim_level0_enabled = fields.Boolean(
        string='Рівень 0 при офлайні', config_parameter='td.iot_sim.level0_enabled', groups=ADMIN)
    td_sim_level0_after_min = fields.Integer(
        string='Вмикати рівень 0 через, хв', config_parameter='td.iot_sim.level0_after_min', groups=ADMIN)
    td_sim_timeout_s = fields.Integer(
        string='Таймаут запитів, с', config_parameter='td.iot_sim.timeout_s', groups=ADMIN)
    td_sim_keep_days = fields.Integer(
        string='Зберігати події, діб', config_parameter='td.iot_sim.keep_days', groups=ADMIN)

    def action_f3d_sim_generate_export_token(self):
        self.td_sim_export_token = secrets.token_hex(32)
        return True

    def action_f3d_sim_check(self):
        return self.env['td.sim.panel'].get_panel().action_check()
