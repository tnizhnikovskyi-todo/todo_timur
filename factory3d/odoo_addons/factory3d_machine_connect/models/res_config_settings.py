import json
import logging

from odoo import api, fields, models

from .f3d_machine import P

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    f3d_mc_read_enabled = fields.Boolean(string="Читати з верстатів", config_parameter=P + "read_enabled")
    f3d_mc_auto_start_enabled = fields.Boolean(string="Автостарт завдань", config_parameter=P + "auto_start_enabled")
    f3d_mc_write_enabled = fields.Boolean(string="Запис на пристрої", config_parameter=P + "write_enabled")
    f3d_mc_micro_stop_s = fields.Integer(string="Мікрозупинка, с", config_parameter=P + "micro_stop_s")
    f3d_mc_pause_after_min = fields.Integer(string="Пауза завдання після, хв", config_parameter=P + "pause_after_min")
    f3d_mc_finish_idle_s = fields.Integer(string="Завершення після зупинки, с", config_parameter=P + "finish_idle_s")
    f3d_mc_qty_sync_mode = fields.Selection(
        [("finish", "При завершенні"), ("live", "Наживо")],
        string="Синхронізація лічильника",
        config_parameter=P + "qty_sync_mode",
    )
    f3d_mc_qty_sync_s = fields.Integer(string="Період синхронізації, с", config_parameter=P + "qty_sync_s")
    f3d_mc_coverage_min = fields.Float(string="Мінімальна повнота даних OEE", config_parameter=P + "coverage_min")
    f3d_mc_oee_good = fields.Float(string="OEE: добре від", config_parameter=P + "oee_good")
    f3d_mc_oee_warn = fields.Float(string="OEE: увага від", config_parameter=P + "oee_warn")
    f3d_mc_no_job_activity_min = fields.Integer(
        string="Робота без завдання, хв", config_parameter=P + "no_job_activity_min"
    )
    f3d_mc_stack_diff_tolerance = fields.Integer(
        string="Допуск розбіжності стосу, арк.", config_parameter=P + "stack_diff_tolerance"
    )
    f3d_mc_stack_diff_confirm_min = fields.Integer(
        string="Підтвердження розбіжності, хв", config_parameter=P + "stack_diff_confirm_min"
    )
    f3d_mc_gantry_auto_replenish = fields.Boolean(
        string="Авто-поповнення під портал", config_parameter=P + "gantry_auto_replenish"
    )
    f3d_mc_gantry_auto_feed = fields.Boolean(string="Авто-подача порталу", config_parameter=P + "gantry_auto_feed")
    f3d_mc_cutting_mode = fields.Selection(
        [("collector", "Через колектор"), ("manual", "Вручну")],
        string="Режим карт розкрою",
        config_parameter=P + "cutting_mode",
    )
    f3d_mc_export_token_ttl_s = fields.Integer(
        string="Строк токена експорту, с", config_parameter=P + "export_token_ttl_s"
    )
    f3d_mc_keep_log_days = fields.Integer(string="Зберігати журнал станів, діб", config_parameter=P + "keep_log_days")
    f3d_mc_keep_event_days = fields.Integer(
        string="Зберігати події верстатів, діб", config_parameter=P + "keep_event_days"
    )
    f3d_mc_migration_state = fields.Char(string="Міграція демо-даних", compute="_compute_f3d_mc_migration_state")

    @api.depends_context("uid")
    def _compute_f3d_mc_migration_state(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(P + "migration_report", "{}")
        try:
            state = json.loads(raw).get("state", "—")
        except (ValueError, AttributeError):
            state = "—"
        for rec in self:
            rec.f3d_mc_migration_state = state
