"""M-07 `res.config.settings` — параметри `td.chp.*` (блок «Когенерація», V-07); стоп-крани — лише адміністратор."""

from odoo import _, fields, models
from odoo.exceptions import AccessError

FLAGS = ("read_enabled", "write_enabled", "remote_switching_enabled")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_chp_read_enabled = fields.Boolean(string="Читання КГУ", config_parameter="td.chp.read_enabled")
    td_chp_write_enabled = fields.Boolean(string="Керування КГУ", config_parameter="td.chp.write_enabled")
    td_chp_remote_switching_enabled = fields.Boolean(
        string="Дистанційний пуск", config_parameter="td.chp.remote_switching_enabled"
    )
    td_chp_confirm_ttl_s = fields.Integer(
        string="Токен підтвердження, с", config_parameter="td.chp.confirm_ttl_s", default=60
    )
    td_chp_second_ttl_s = fields.Integer(
        string="Друге підтвердження, с", config_parameter="td.chp.second_ttl_s", default=600
    )
    td_chp_verify_timeout_s = fields.Integer(
        string="Верифікація, с", config_parameter="td.chp.verify_timeout_s", default=30
    )
    td_chp_command_ttl_s = fields.Integer(
        string="Команда в черзі, с", config_parameter="td.chp.command_ttl_s", default=60
    )
    td_chp_stale_s = fields.Integer(string="Дані застаріли через, с", config_parameter="td.chp.stale_s", default=30)
    td_chp_event_keep_days = fields.Integer(
        string="Зберігати події, діб", config_parameter="td.chp.event_keep_days", default=365
    )
    td_chp_bus_throttle_s = fields.Integer(
        string="Шина: не частіше, с", config_parameter="td.chp.bus_throttle_s", default=1
    )

    def set_values(self):
        """Стоп-крани КГУ змінює лише адміністратор (`group_td_admin`)."""
        icp = self.env["ir.config_parameter"].sudo()
        wanted = {f: bool(getattr(self, "td_chp_" + f)) for f in FLAGS}
        changed = [f for f in FLAGS if wanted[f] != (icp.get_param("td.chp." + f) in ("True", "true", "1"))]
        if changed and not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Стоп-крани КГУ змінює лише адміністратор."))
        return super().set_values()
