import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

P = "td.bms."
ADMIN = "td_factory3d.group_td_admin"


class ResConfigSettings(models.TransientModel):
    """M-17: налаштування модуля «Будівля» (FR-19)."""

    _inherit = "res.config.settings"

    td_bms_read_enabled = fields.Boolean(string="Читати освітлення й вентиляцію", config_parameter=P + "read_enabled")
    td_bms_write_enabled = fields.Boolean(
        string="Дозволити керування", config_parameter=P + "write_enabled", groups=ADMIN
    )
    td_bms_calendar_id = fields.Many2one(
        "resource.calendar", string="Робочий календар", config_parameter=P + "calendar_id"
    )
    td_bms_light_check_delay_min = fields.Integer(
        string="Затримка перевірки освітлення, хв", config_parameter=P + "light_check_delay_min"
    )
    td_bms_light_norm_tolerance_pct = fields.Float(
        string="Допуск до норми, %", config_parameter=P + "light_norm_tolerance_pct"
    )
    td_bms_hvac_check_delay_min = fields.Integer(
        string="Затримка перевірки установок, хв", config_parameter=P + "hvac_check_delay_min"
    )
    td_bms_cold_delay_min = fields.Integer(string="Затримка «холодно», хв", config_parameter=P + "cold_delay_min")
    td_bms_indoor_min_work_c = fields.Float(
        string="Мінімум у зоні в робочий час, °C", config_parameter=P + "indoor_min_work_c"
    )
    td_bms_indoor_min_off_c = fields.Float(
        string="Мінімум у зоні поза робочим часом, °C", config_parameter=P + "indoor_min_off_c"
    )
    td_bms_heat_deficit_kw = fields.Float(string="Дефіцит тепла, кВт", config_parameter=P + "heat_deficit_kw")
    td_bms_heat_deficit_delay_min = fields.Integer(
        string="Затримка «дефіцит тепла», хв", config_parameter=P + "heat_deficit_delay_min"
    )
    td_bms_check_heartbeat_min = fields.Integer(
        string="Повторний запис перевірки, хв", config_parameter=P + "check_heartbeat_min"
    )
    td_bms_light_uf = fields.Float(string="UF (коефіцієнт використання)", config_parameter=P + "light_uf")
    td_bms_light_mf = fields.Float(string="MF (коефіцієнт запасу)", config_parameter=P + "light_mf")
    td_bms_install_state = fields.Char(string="Установка даних", compute="_compute_f3d_bms_install_state")

    @api.depends_context("uid")
    def _compute_f3d_bms_install_state(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(P + "install_report", "{}") or "{}"
        try:
            state = json.loads(raw).get("state", "—")
        except ValueError:
            state = "—"
        for rec in self:
            rec.td_bms_install_state = state

    def _td_bms_check_ranges(self):
        def bad(label):
            raise ValidationError("Налаштування «Будівля»: %s поза допустимими межами." % label)

        for rec in self:
            for name, label in (
                ("td_bms_light_check_delay_min", "затримка перевірки освітлення"),
                ("td_bms_hvac_check_delay_min", "затримка перевірки установок"),
                ("td_bms_cold_delay_min", "затримка «холодно»"),
                ("td_bms_heat_deficit_delay_min", "затримка «дефіцит тепла»"),
            ):
                if not 1 <= rec[name] <= 240:
                    bad("%s (1…240 хв)" % label)
            if not 0 <= rec.td_bms_light_norm_tolerance_pct <= 50:
                bad("допуск до норми (0…50 %)")
            for name, label in (
                ("td_bms_indoor_min_work_c", "мінімум у зоні"),
                ("td_bms_indoor_min_off_c", "мінімум"),
            ):
                if not -30 <= rec[name] <= 40:
                    bad("%s (−30…40 °C)" % label)
            if not 0 <= rec.td_bms_heat_deficit_kw <= 2000:
                bad("дефіцит тепла (0…2 000 кВт)")

    def set_values(self):
        icp = self.env["ir.config_parameter"].sudo()
        old_read = icp.get_param(P + "read_enabled") in ("True", "true", "1")
        old_write = icp.get_param(P + "write_enabled") in ("True", "true", "1")
        is_admin = self.env.user.has_group(ADMIN)
        self._td_bms_check_ranges()
        if not is_admin and any(rec.sudo().td_bms_write_enabled != old_write for rec in self):
            raise AccessError("Керування будівлею вмикає лише адміністратор «Завод 3D».")
        super().set_values()
        from .. import hooks  # noqa: PLC0415

        new_read = icp.get_param(P + "read_enabled") in ("True", "true", "1")
        new_write = icp.get_param(P + "write_enabled") in ("True", "true", "1")
        if new_read != old_read:
            hooks.read_flags(self.env)
        if new_write != old_write:
            hooks.write_flags(self.env)

    def action_td_bms_reinstall(self):
        return self.env["td.bms.check"].f3d_bms_reinstall_data()
