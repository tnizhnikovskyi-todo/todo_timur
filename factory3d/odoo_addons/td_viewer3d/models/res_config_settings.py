"""M-06: налаштування переглядача (res.config.settings)."""

import re
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

PREFIX = "td.viewer."
HOURS_RE = re.compile(r"^\d\d:\d\d-\d\d:\d\d$")
WALL_SLIDES_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}(,[a-z][a-z0-9_]{0,31})*$")
CLOCK_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
BOOL_FIELDS = {"td_kiosk_enabled": "kiosk_enabled", "td_bus_enabled": "bus_enabled", "td_demo_enabled": "demo_enabled"}


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_snapshot_minutes = fields.Integer(
        string="Період знімків, хв", config_parameter=PREFIX + "snapshot_minutes", default=10
    )
    td_snapshot_hours = fields.Char(
        string="Вікно знімків (HH:MM-HH:MM)",
        config_parameter=PREFIX + "snapshot_hours",
        help="Порожньо — знімки цілодобово.",
    )
    td_snapshot_keep_days = fields.Integer(
        string="Зберігати знімки, днів", config_parameter=PREFIX + "snapshot_keep_days", default=14
    )
    td_event_keep_hours = fields.Integer(
        string="Зберігати події, годин", config_parameter=PREFIX + "event_keep_hours", default=48
    )
    td_delta_debounce_ms = fields.Integer(
        string="Затримка оновлень, мс", config_parameter=PREFIX + "delta_debounce_ms", default=1500
    )
    td_kiosk_enabled = fields.Boolean(string="Кіоск увімкнено", config_parameter=PREFIX + "kiosk_enabled")
    td_kiosk_refresh_s = fields.Integer(
        string="Оновлення кіоска, с", config_parameter=PREFIX + "kiosk_refresh_s", default=15
    )
    td_wall_slide_s = fields.Integer(string="Слайд «стіни», с", config_parameter=PREFIX + "wall_slide_s", default=20)
    td_wall_slides = fields.Char(
        string="Слайди «стіни»",
        config_parameter=PREFIX + "wall_slides",
        default="overview,kpi,events,orders",
        help="Ключі через кому в порядку показу: overview (3D), kpi, events, orders; модулі можуть додавати свої.",
    )
    td_bus_enabled = fields.Boolean(string="Живі оновлення (шина)", config_parameter=PREFIX + "bus_enabled")
    td_demo_enabled = fields.Boolean(string="Демо-режим", config_parameter=PREFIX + "demo_enabled")
    td_demo_clock = fields.Char(string="Демо-годинник", config_parameter=PREFIX + "demo_clock")
    td_lite_default = fields.Selection(
        [("0", "Ні"), ("1", "Так"), ("auto", "Авто")],
        string="Спрощений режим для планшетів",
        config_parameter=PREFIX + "lite_default",
        default="auto",
    )
    td_kiosk_url = fields.Char(string="Адреса кіоска", compute="_compute_f3d_kiosk_url", readonly=True)
    td_wall_url = fields.Char(string="Адреса «стіни»", compute="_compute_f3d_kiosk_url", readonly=True)

    def _td_kiosk_url(self, wall=False):
        """Адреса кіоска (з `?wall=1` для «стіни»); порожньо, якщо користувач не адміністратор «3D Завод» або токена немає."""
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            return ""
        params = self.env["ir.config_parameter"].sudo()
        token = params.get_param(PREFIX + "kiosk_token")
        if not token:
            return ""
        url = "%s/f3d/kiosk/%s" % ((params.get_param("web.base.url") or "").rstrip("/"), token)
        return url + "?wall=1" if wall else url

    @api.depends_context("uid")
    def _compute_f3d_kiosk_url(self):
        kiosk_url, wall_url = self._td_kiosk_url(), self._td_kiosk_url(wall=True)
        for rec in self:
            rec.td_kiosk_url = kiosk_url
            rec.td_wall_url = wall_url

    def _td_validate(self):
        def bad(label, expect):
            raise ValidationError(_("Невірне значення %(field)s: очікується %(expect)s", field=label, expect=expect))

        for rec in self:
            if not 5 <= rec.td_snapshot_minutes <= 60:
                bad(_("Період знімків"), _("ціле від 5 до 60"))
            if not 5 <= rec.td_kiosk_refresh_s <= 120:
                bad(_("Оновлення кіоска"), _("ціле від 5 до 120"))
            if not 5 <= rec.td_wall_slide_s <= 300:
                bad(_("Слайд «стіни»"), _("ціле від 5 до 300 с"))
            if not WALL_SLIDES_RE.match(rec.td_wall_slides or ""):
                bad(_("Слайди «стіни»"), _("ключі латиницею через кому, наприклад overview,kpi,events,orders"))
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
            raise AccessError(_("Новий токен кіоска може згенерувати лише адміністратор «3D Завод»."))
        self.env["ir.config_parameter"].sudo().set_param(PREFIX + "kiosk_token", secrets.token_hex(16))
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_td_open_wall(self):
        """Відкриває екран планірки («стіну») у новій вкладці: меню «Екран планірки (стіна)» і кнопка в налаштуваннях."""
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Відкрити «стіну» може лише адміністратор «3D Завод»."))
        params = self.env["ir.config_parameter"].sudo()
        if (params.get_param(PREFIX + "kiosk_enabled") or "").lower() not in ("true", "1"):
            raise UserError(
                _(
                    "Кіоск вимкнено, тож «стіна» не відкриється. Увімкніть «Кіоск увімкнено» "
                    "в Налаштування → Налаштування переглядача → Кіоск, збережіть і спробуйте ще раз."
                )
            )
        url = self._td_kiosk_url(wall=True)
        if not url:
            raise UserError(
                _(
                    "Токена кіоска немає. Натисніть «Новий токен кіоска» "
                    "в Налаштування → Налаштування переглядача → Кіоск і спробуйте ще раз."
                )
            )
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}
