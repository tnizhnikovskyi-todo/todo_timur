import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .td_machine import P

_logger = logging.getLogger(__name__)

ADMIN_FIELDS = (
    "td_mc_read_enabled",
    "td_mc_auto_start_enabled",
    "td_mc_write_enabled",
    "td_mc_cutting_mode",
    "td_mc_export_token_ttl_s",
    "td_mc_keep_log_days",
    "td_mc_keep_event_days",
)
# Межі M-23: поле → (мін, макс); `None` — без обмеження.
BOUNDS = {
    "td_mc_micro_stop_s": (0, 3600),
    "td_mc_pause_after_min": (1, 240),
    "td_mc_finish_idle_s": (0, 3600),
    "td_mc_qty_sync_s": (30, 3600),
    "td_mc_coverage_min": (0, 1),
    "td_mc_oee_good": (0, 1),
    "td_mc_oee_warn": (0, 1),
    "td_mc_stack_diff_tolerance": (0, 60),
    "td_mc_stack_diff_confirm_min": (1, 240),
    "td_mc_export_token_ttl_s": (60, 3600),
    "td_mc_keep_log_days": (30, None),
    "td_mc_keep_event_days": (7, None),
}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_mc_read_enabled = fields.Boolean(string="Читати з верстатів", config_parameter=P + "read_enabled")
    td_mc_auto_start_enabled = fields.Boolean(string="Автостарт завдань", config_parameter=P + "auto_start_enabled")
    td_mc_write_enabled = fields.Boolean(string="Запис на пристрої", config_parameter=P + "write_enabled")
    td_mc_micro_stop_s = fields.Integer(string="Мікрозупинка, с", config_parameter=P + "micro_stop_s")
    td_mc_pause_after_min = fields.Integer(string="Пауза завдання після, хв", config_parameter=P + "pause_after_min")
    td_mc_finish_idle_s = fields.Integer(string="Завершення після зупинки, с", config_parameter=P + "finish_idle_s")
    td_mc_qty_sync_mode = fields.Selection(
        [("finish", "При завершенні"), ("live", "Наживо")],
        string="Синхронізація лічильника",
        config_parameter=P + "qty_sync_mode",
    )
    td_mc_qty_sync_s = fields.Integer(string="Період синхронізації, с", config_parameter=P + "qty_sync_s")
    td_mc_coverage_min = fields.Float(string="Мінімальна повнота даних OEE", config_parameter=P + "coverage_min")
    td_mc_oee_good = fields.Float(string="OEE: добре від", config_parameter=P + "oee_good")
    td_mc_oee_warn = fields.Float(string="OEE: увага від", config_parameter=P + "oee_warn")
    td_mc_no_job_activity_min = fields.Integer(
        string="Робота без завдання, хв", config_parameter=P + "no_job_activity_min"
    )
    td_mc_stack_diff_tolerance = fields.Integer(
        string="Допуск розбіжності стосу, арк.", config_parameter=P + "stack_diff_tolerance"
    )
    td_mc_stack_diff_confirm_min = fields.Integer(
        string="Підтвердження розбіжності, хв", config_parameter=P + "stack_diff_confirm_min"
    )
    td_mc_gantry_auto_replenish = fields.Boolean(
        string="Авто-поповнення під портал", config_parameter=P + "gantry_auto_replenish"
    )
    td_mc_gantry_auto_feed = fields.Boolean(string="Авто-подача порталу", config_parameter=P + "gantry_auto_feed")
    td_mc_cutting_mode = fields.Selection(
        [("collector", "Через колектор"), ("manual", "Вручну")],
        string="Режим карт розкрою",
        config_parameter=P + "cutting_mode",
    )
    td_mc_export_token_ttl_s = fields.Integer(
        string="Строк токена експорту, с", config_parameter=P + "export_token_ttl_s"
    )
    td_mc_keep_log_days = fields.Integer(string="Зберігати журнал станів, діб", config_parameter=P + "keep_log_days")
    td_mc_keep_event_days = fields.Integer(
        string="Зберігати події верстатів, діб", config_parameter=P + "keep_event_days"
    )
    td_mc_migration_state = fields.Char(string="Міграція демо-даних", compute="_compute_f3d_mc_migration_state")

    @api.depends_context("uid")
    def _compute_f3d_mc_migration_state(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(P + "migration_report", "{}")
        try:
            state = json.loads(raw).get("state", "—")
        except (ValueError, AttributeError):
            state = "—"
        for rec in self:
            rec.td_mc_migration_state = state

    def _f3d_mc_current(self, fname):
        """Поточне збережене значення поля налаштувань (за `config_parameter`) у типі поля."""
        field = self._fields[fname]
        raw = self.env["ir.config_parameter"].sudo().get_param(field.config_parameter)
        if field.type == "boolean":
            return raw in ("True", "true", "1")
        if field.type == "integer":
            return int(raw or 0)
        if field.type == "float":
            return float(raw or 0)
        return raw or False

    def set_values(self):
        """M-23: стоп-крани й служби — лише `group_td_admin`; межі значень."""
        is_admin = self.env.su or self.env.user.has_group("td_factory3d.group_td_admin")
        for rec in self:
            changed = [f for f in rec._fields if f.startswith("td_mc_") and f != "td_mc_migration_state"
                       and rec[f] != rec._f3d_mc_current(f)]  # fmt: skip
            if not is_admin and any(f in ADMIN_FIELDS for f in changed):
                raise AccessError(_("Стоп-крани змінює лише адміністратор «Завод 3D»."))
            for fname in changed:
                lo, hi = BOUNDS.get(fname, (None, None))
                value = rec[fname]
                if (lo is not None and value < lo) or (hi is not None and value > hi):
                    raise ValidationError(
                        _(
                            "%(name)s: поза межами %(lo)s…%(hi)s.",
                            name=rec._fields[fname].string,
                            lo=lo,
                            hi=hi if hi is not None else "∞",
                        )
                    )
            if {"td_mc_oee_good", "td_mc_oee_warn"} & set(changed) and not rec.td_mc_oee_warn < rec.td_mc_oee_good:
                raise ValidationError(_("OEE: поріг «увага» має бути меншим за поріг «добре»."))
        return super().set_values()

    def action_td_mc_run_migration(self):
        """Кнопка «Повторити міграцію демо-даних» (лише `group_td_admin`)."""
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Запускати міграцію може лише адміністратор «Завод 3D»."))
        return self.env["td.machine"]._f3d_run_migration()
