import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

P = "factory3d.telemetry."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    f3d_telemetry_read_enabled = fields.Boolean(string="Приймати показання", config_parameter=P + "read_enabled")
    f3d_telemetry_write_enabled = fields.Boolean(
        string="Дозволяти команди на пристрої", config_parameter=P + "write_enabled")
    f3d_telemetry_keep_days = fields.Integer(string="Зберігати показання, діб", config_parameter=P + "keep_days")
    f3d_telemetry_keep_hours_days = fields.Integer(
        string="Зберігати годинні агрегати, діб", config_parameter=P + "keep_hours_days")
    f3d_telemetry_default_store_period_s = fields.Integer(
        string="Період збереження за умовчанням, с", config_parameter=P + "default_store_period_s")
    f3d_telemetry_stale_periods = fields.Integer(
        string="Періодів до «немає даних»", config_parameter=P + "stale_periods")
    f3d_telemetry_stale_min_s = fields.Integer(
        string="Мінімум до «немає даних», с", config_parameter=P + "stale_min_s")
    f3d_telemetry_bus_min_interval_s = fields.Integer(
        string="Мін. інтервал шини, с", config_parameter=P + "bus_min_interval_s")
    f3d_telemetry_realarm_cooldown_s = fields.Integer(
        string="Пауза до нової заявки, с", config_parameter=P + "realarm_cooldown_s")
    f3d_telemetry_push_max_readings = fields.Integer(
        string="Макс. показань у пакеті", config_parameter=P + "push_max_readings")
    f3d_telemetry_push_rate_per_min = fields.Integer(
        string="Макс. пакетів на хвилину", config_parameter=P + "push_rate_per_min")
    f3d_telemetry_meter_lead_pct = fields.Float(
        string="Планувати ТО за лічильником за, %", config_parameter=P + "meter_lead_pct")
    f3d_telemetry_default_team_id = fields.Many2one("maintenance.team", string="Команда ТО за умовчанням")
    f3d_telemetry_drop_level0 = fields.Boolean(
        string="Видалити дані рівня 0 після міграції", config_parameter=P + "drop_level0")
    f3d_telemetry_level0_state = fields.Char(string="Міграція рівня 0", compute="_compute_f3d_telemetry_info")
    f3d_telemetry_collector_count = fields.Integer(
        string="Активних колекторів", compute="_compute_f3d_telemetry_info")

    @api.depends_context("uid")
    def _compute_f3d_telemetry_info(self):
        icp = self.env["ir.config_parameter"].sudo()
        try:
            state = json.loads(icp.get_param(P + "level0_migrated", "{}") or "{}").get("state", "—")
        except ValueError:
            state = "—"
        count = self.env["f3d.collector"].sudo().search_count([("active", "=", True)])
        for rec in self:
            rec.f3d_telemetry_level0_state = state
            rec.f3d_telemetry_collector_count = count

    @api.model
    def get_values(self):
        res = super().get_values()
        param = self.env["ir.config_parameter"].sudo().get_param(P + "default_team_id") or ""
        res["f3d_telemetry_default_team_id"] = int(param) if param.isdigit() else False
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        for rec in self:
            icp.set_param(P + "default_team_id", str(rec.f3d_telemetry_default_team_id.id or ""))

    def action_f3d_collector(self):
        return self.env["ir.actions.act_window"]._for_xml_id("factory3d_telemetry.action_f3d_collector")

    def action_f3d_run_migration(self):
        if not self.env.user.has_group("factory3d_base.group_f3d_admin"):
            raise UserError(_("Лише для адміністратора Завод 3D."))
        try:
            from .. import hooks  # noqa: PLC0415
        except ImportError:
            hooks = None
        run = getattr(hooks, "run_level0_migration", None)
        if run is None:
            raise UserError(_("Міграція рівня 0 недоступна в цій збірці."))
        run(self.env)
        return True
