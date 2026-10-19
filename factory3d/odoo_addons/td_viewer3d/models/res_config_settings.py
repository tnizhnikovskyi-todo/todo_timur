"""M-06: налаштування переглядача (res.config.settings)."""
import re
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

PREFIX = "td.viewer."
HOURS_RE = re.compile(r"^\d\d:\d\d-\d\d:\d\d$")
CLOCK_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
BOOL_FIELDS = {"td_kiosk_enabled": "kiosk_enabled", "td_bus_enabled": "bus_enabled",
               "td_demo_enabled": "demo_enabled"}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_snapshot_minutes = fields.Integer(
        string="Період знімків, хв", config_parameter=PREFIX + "snapshot_minutes", default=10)
    td_snapshot_hours = fields.Char(
        string="Вікно знімків (HH:MM-HH:MM)", config_parameter=PREFIX + "snapshot_hours",
        help="Порожньо — знімки цілодобово.")
    td_snapshot_keep_days = fields.Integer(
        string="Зберігати знімки, днів", config_parameter=PREFIX + "snapshot_keep_days", default=14)
    td_event_keep_hours = fields.Integer(
        string="Зберігати події, годин", config_parameter=PREFIX + "event_keep_hours", default=48)
    td_delta_debounce_ms = fields.Integer(
        string="Затримка оновлень, мс", config_parameter=PREFIX + "delta_debounce_ms", default=1500)
    td_kiosk_enabled = fields.Boolean(string="Кіоск увімкнено", config_parameter=PREFIX + "kiosk_enabled")
    td_kiosk_refresh_s = fields.Integer(
        string="Оновлення кіоска, с", config_parameter=PREFIX + "kiosk_refresh_s", default=15)
    td_bus_enabled = fields.Boolean(string="Живі оновлення (шина)", config_parameter=PREFIX + "bus_enabled")
    td_demo_enabled = fields.Boolean(string="Демо-режим", config_parameter=PREFIX + "demo_enabled")
    td_demo_clock = fields.Char(string="Демо-годинник", config_parameter=PREFIX + "demo_clock")
    td_lite_default = fields.Selection(
        [("0", "Ні"), ("1", "Так"), ("auto", "Авто")], string="Спрощений режим для планшетів",
        config_parameter=PREFIX + "lite_default", default="auto")
    td_kiosk_url = fields.Char(string="Адреса кіоска", compute="_compute_f3d_kiosk_url", readonly=True)

    @api.depends_context("uid")
    def _compute_f3d_kiosk_url(self):
        admin = self.env.user.has_group("td_factory3d.group_td_admin")
        params = self.env["ir.config_parameter"].sudo()
        base = params.get_param("web.base.url") or ""
        token = params.get_param(PREFIX + "kiosk_token")
        for rec in self:
            rec.td_kiosk_url = "%s/f3d/kiosk/%s" % (base.rstrip("/"), token) if admin and token else ""

    def _td_validate(self):
        def bad(label, expect):
            raise ValidationError(_("Невірне значення %(field)s: очікується %(expect)s", field=label, expect=expect))

        for rec in self:
            if not 5 <= rec.td_snapshot_minutes <= 60:
                bad(_("Період знімків"), _("ціле від 5 до 60"))
            if not 5 <= rec.td_kiosk_refresh_s <= 120:
                bad(_("Оновлення кіоска"), _("ціле від 5 до 120"))
            if rec.td_snapshot_hours and not HOURS_RE.match(rec.td_snapshot_hours):
                bad(_("Вікно знімків"), _("HH:MM-HH:MM або порожньо"))
            if rec.td_demo_clock and not CLOCK_RE.match(rec.td_demo_clock):
                bad(_("Демо-годинник"), _("YYYY-MM-DD HH:MM або порожньо"))

    def set_values(self):
        self._td_validate()
        res = super().set_values()
        params = self.env["ir.config_parameter"].sudo()
        for rec in self:
            # Boolean False стандартно видаляє параметр, а відсутній параметр читається як «увімкнено»
            for fname, key in BOOL_FIELDS.items():
                params.set_param(PREFIX + key, "True" if rec[fname] else "False")
            cron = self.env.ref("td_viewer3d.cron_td_snapshot", raise_if_not_found=False)
            if cron and rec.td_snapshot_minutes and cron.interval_number != rec.td_snapshot_minutes:
                cron.sudo().interval_number = rec.td_snapshot_minutes
        return res

    def action_td_new_kiosk_token(self):
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Новий токен кіоска може згенерувати лише адміністратор «Завод 3D»."))
        self.env["ir.config_parameter"].sudo().set_param(PREFIX + "kiosk_token", secrets.token_hex(16))
        return {"type": "ir.actions.client", "tag": "reload"}
