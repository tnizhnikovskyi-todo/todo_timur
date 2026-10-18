"""M-40 `res.config.settings` — параметри `td.energy_control.*` (V-44). Прапори запису — лише адміністратор."""

from odoo import _, fields, models
from odoo.exceptions import AccessError

FLAGS = ("write_enabled", "automation_enabled", "remote_switching_enabled")
INTS = (
    "confirm_ttl_s", "second_ttl_s", "undo_window_min", "command_ttl_s", "exec_timeout_s", "step_timeout_s",
    "verify_timeout_s", "apply_timeout_s", "engine_tick_s", "config_poll_s", "stale_hold_s", "min_write_interval_s",
    "max_writes_per_min", "shed_restore_step_s", "export_advice_min",
)  # fmt: skip


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_energy_control_write_enabled = fields.Boolean(
        string="Керування пристроями (запобіжник 2)", config_parameter="td.energy_control.write_enabled"
    )
    td_energy_control_automation_enabled = fields.Boolean(
        string="Автоматика (запобіжник 6)", config_parameter="td.energy_control.automation_enabled"
    )
    td_energy_control_remote_switching_enabled = fields.Boolean(
        string="Дистанційне перемикання (QS, КГУ, розряд BESS, тест ДГУ)",
        config_parameter="td.energy_control.remote_switching_enabled",
    )
    td_energy_control_confirm_ttl_s = fields.Integer(
        string="Токен підтвердження, с", config_parameter="td.energy_control.confirm_ttl_s", default=60
    )
    td_energy_control_second_ttl_s = fields.Integer(
        string="Друге підтвердження, с", config_parameter="td.energy_control.second_ttl_s", default=600
    )
    td_energy_control_undo_window_min = fields.Integer(
        string="Вікно скасування, хв", config_parameter="td.energy_control.undo_window_min", default=15
    )
    td_energy_control_command_ttl_s = fields.Integer(
        string="Команда в черзі, с", config_parameter="td.energy_control.command_ttl_s", default=120
    )
    td_energy_control_exec_timeout_s = fields.Integer(
        string="Виконання інтенту, с", config_parameter="td.energy_control.exec_timeout_s", default=60
    )
    td_energy_control_step_timeout_s = fields.Integer(
        string="Крок запису, с", config_parameter="td.energy_control.step_timeout_s", default=8
    )
    td_energy_control_verify_timeout_s = fields.Integer(
        string="Верифікація, с", config_parameter="td.energy_control.verify_timeout_s", default=30
    )
    td_energy_control_apply_timeout_s = fields.Integer(
        string="Застосування конфігурації, с", config_parameter="td.energy_control.apply_timeout_s", default=60
    )
    td_energy_control_engine_tick_s = fields.Integer(
        string="Період циклу рушія, с", config_parameter="td.energy_control.engine_tick_s", default=2
    )
    td_energy_control_config_poll_s = fields.Integer(
        string="Опитування конфігурації, с", config_parameter="td.energy_control.config_poll_s", default=10
    )
    td_energy_control_stale_hold_s = fields.Integer(
        string="Несвіжий вхід → призупинення, с", config_parameter="td.energy_control.stale_hold_s", default=30
    )
    td_energy_control_min_write_interval_s = fields.Integer(
        string="Мін. інтервал повторного запису, с",
        config_parameter="td.energy_control.min_write_interval_s",
        default=10,
    )
    td_energy_control_max_writes_per_min = fields.Integer(
        string="Макс. записів за хвилину", config_parameter="td.energy_control.max_writes_per_min", default=30
    )
    td_energy_control_shed_restore_step_s = fields.Integer(
        string="Крок відновлення навантажень, с", config_parameter="td.energy_control.shed_restore_step_s", default=20
    )
    td_energy_control_export_advice_min = fields.Integer(
        string="Експорт для рекомендації EXPORT-T2, хв",
        config_parameter="td.energy_control.export_advice_min",
        default=5,
    )

    def set_values(self):
        """Прапори запису змінює лише адміністратор; зміна — запис журналу `switch_flag` і `bump()`."""
        icp = self.env["ir.config_parameter"].sudo()
        before = {f: icp.get_param("td.energy_control." + f) for f in FLAGS}
        wanted = {f: getattr(self, "td_energy_control_" + f) for f in FLAGS}
        changed = [f for f in FLAGS if str(bool(wanted[f])) != str(before[f] in ("True", "true", "1"))]
        if changed and not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Прапори керування змінює лише адміністратор."))
        res = super().set_values()
        if changed:
            self.env["td.energy.action"]._td_log_config(
                "switch_flag", "Прапори керування: %s" % ", ".join("%s=%s" % (f, wanted[f]) for f in changed)
            )
        elif any(getattr(self, "td_energy_control_" + n) for n in INTS):
            self.env["td.energy.control.state"].bump()
        return res
