import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import params as P

GROUP = "td_factory3d.group_td_admin"

# поле -> (ключ параметра, нижня межа, верхня межа); SPEC M-11
INT_RANGES = {
    "td_access_page_size": ("page_size", 1, 2000),
    "td_access_max_pages_per_run": ("max_pages_per_run", 1, 100),
    "td_access_overlap_s": ("overlap_s", 0, 3600),
    "td_access_initial_lookback_h": ("initial_lookback_h", 1, 168),
    "td_access_dup_window_min": ("dup_window_min", 0, 120),
    "td_access_merge_gap_min": ("merge_gap_min", 0, 240),
    "td_access_max_shift_h": ("max_shift_h", 1, 24),
    "td_access_stale_close_fallback_min": ("stale_close_fallback_min", 1, 720),
    "td_access_keep_days": ("keep_days", 1, 3650),
    "td_access_visitor_default_hours": ("visitor_default_hours", 1, 72),
}
PREFIX_RE = re.compile(r"^[A-Za-z0-9_\-]{1,8}$")
GROUP_ID_RE = re.compile(r"^[0-9]{1,9}$")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_access_read_enabled = fields.Boolean(
        string="Приймати події", config_parameter="td.access.read_enabled", groups=GROUP
    )
    td_access_write_enabled = fields.Boolean(
        string="Запис у BioStar", config_parameter="td.access.write_enabled", groups=GROUP
    )
    td_access_biostar_login = fields.Char(
        string="Логін BioStar", config_parameter="td.access.biostar_login", groups=GROUP
    )
    td_access_biostar_password = fields.Char(
        string="Пароль BioStar", config_parameter="td.access.biostar_password", groups=GROUP
    )
    td_access_page_size = fields.Integer(string="Розмір сторінки", config_parameter="td.access.page_size", groups=GROUP)
    td_access_max_pages_per_run = fields.Integer(
        string="Сторінок за опитування", config_parameter="td.access.max_pages_per_run", groups=GROUP
    )
    td_access_overlap_s = fields.Integer(
        string="Перекриття вікна, с", config_parameter="td.access.overlap_s", groups=GROUP
    )
    td_access_initial_lookback_h = fields.Integer(
        string="Перше опитування: глибина, год", config_parameter="td.access.initial_lookback_h", groups=GROUP
    )
    td_access_paging_mode = fields.Selection(
        [("offset", "offset"), ("hint", "hint (BioStar 2.8+)")],
        string="Режим сторінок",
        config_parameter="td.access.paging_mode",
        groups=GROUP,
    )
    td_access_dup_window_min = fields.Integer(
        string="Вікно дублікатів, хв", config_parameter="td.access.dup_window_min", groups=GROUP
    )
    td_access_merge_gap_min = fields.Integer(
        string="Злиття виходів (обід), хв", config_parameter="td.access.merge_gap_min", groups=GROUP
    )
    td_access_max_shift_h = fields.Integer(
        string="Макс. тривалість зміни, год", config_parameter="td.access.max_shift_h", groups=GROUP
    )
    td_access_stale_close_enabled = fields.Boolean(
        string="Закривати відмітки без виходу", config_parameter="td.access.stale_close_enabled", groups=GROUP
    )
    td_access_stale_close_fallback_min = fields.Integer(
        string="Закриття без графіка: через, хв", config_parameter="td.access.stale_close_fallback_min", groups=GROUP
    )
    td_access_keep_days = fields.Integer(
        string="Зберігати події, діб", config_parameter="td.access.keep_days", groups=GROUP
    )
    td_access_keep_raw = fields.Boolean(
        string="Зберігати сирий JSON", config_parameter="td.access.keep_raw", groups=GROUP
    )
    td_access_publish_signals = fields.Boolean(
        string="Публікувати сигнали телеметрії", config_parameter="td.access.publish_signals", groups=GROUP
    )
    td_access_visitor_default_hours = fields.Integer(
        string="Тривалість візиту, год", config_parameter="td.access.visitor_default_hours", groups=GROUP
    )
    td_access_visitor_user_prefix = fields.Char(
        string="Префікс користувача відвідувача", config_parameter="td.access.visitor_user_prefix", groups=GROUP
    )
    td_access_visitor_user_group_id = fields.Char(
        string="Група користувачів BioStar (id)", config_parameter="td.access.visitor_user_group_id", groups=GROUP
    )
    td_access_server_count = fields.Integer(
        string="Серверів BioStar", compute="_compute_f3d_access_server_count", groups=GROUP
    )

    @api.depends_context("uid")
    def _compute_f3d_access_server_count(self):
        count = self.env["td.access.server"].sudo().search_count([])
        for rec in self:
            rec.td_access_server_count = count

    def set_values(self):
        for name, (_key, lo, hi) in INT_RANGES.items():
            if not lo <= self[name] <= hi:
                raise ValidationError(
                    "%(label)s: допустимо %(lo)s–%(hi)s." % {"label": self._fields[name].string, "lo": lo, "hi": hi}
                )
        prefix = self.td_access_visitor_user_prefix
        if prefix and not PREFIX_RE.match(prefix.strip()):
            raise ValidationError(
                "%s: 1–8 символів [A-Za-z0-9_-]." % self._fields["td_access_visitor_user_prefix"].string
            )
        group_id = self.td_access_visitor_user_group_id
        if group_id and not GROUP_ID_RE.match(group_id.strip()):
            raise ValidationError("%s: 1–9 цифр." % self._fields["td_access_visitor_user_group_id"].string)
        res = super().set_values()
        # Odoo стирає параметр для 0; для полів, де 0 допустимий, зберігаємо його явно
        for name, (key, lo, _hi) in INT_RANGES.items():
            if lo == 0 and self[name] == 0:
                P.set_param(self.env, key, "0")
        return res

    def action_td_access_server(self):
        return self.env["ir.actions.act_window"]._for_xml_id("td_access.action_td_access_server")

    def action_f3d_access_test(self):
        server = self.env["td.access.server"].search([("active", "=", True)], limit=1)
        if not server:
            raise UserError("Немає активного сервера BioStar.")
        return server.action_test_connection()
