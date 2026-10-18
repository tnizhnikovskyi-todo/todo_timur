import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import params as P

GROUP = 'factory3d_base.group_f3d_admin'

# поле -> (ключ параметра, нижня межа, верхня межа); SPEC M-11
INT_RANGES = {
    'f3d_access_page_size': ('page_size', 1, 2000),
    'f3d_access_max_pages_per_run': ('max_pages_per_run', 1, 100),
    'f3d_access_overlap_s': ('overlap_s', 0, 3600),
    'f3d_access_initial_lookback_h': ('initial_lookback_h', 1, 168),
    'f3d_access_dup_window_min': ('dup_window_min', 0, 120),
    'f3d_access_merge_gap_min': ('merge_gap_min', 0, 240),
    'f3d_access_max_shift_h': ('max_shift_h', 1, 24),
    'f3d_access_stale_close_fallback_min': ('stale_close_fallback_min', 1, 720),
    'f3d_access_keep_days': ('keep_days', 1, 3650),
    'f3d_access_visitor_default_hours': ('visitor_default_hours', 1, 72),
}
PREFIX_RE = re.compile(r'^[A-Za-z0-9_\-]{1,8}$')
GROUP_ID_RE = re.compile(r'^[0-9]{1,9}$')


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    f3d_access_read_enabled = fields.Boolean(
        string='Приймати події', config_parameter='factory3d.access.read_enabled', groups=GROUP)
    f3d_access_write_enabled = fields.Boolean(
        string='Запис у BioStar', config_parameter='factory3d.access.write_enabled', groups=GROUP)
    f3d_access_biostar_login = fields.Char(
        string='Логін BioStar', config_parameter='factory3d.access.biostar_login', groups=GROUP)
    f3d_access_biostar_password = fields.Char(
        string='Пароль BioStar', config_parameter='factory3d.access.biostar_password', groups=GROUP)
    f3d_access_page_size = fields.Integer(
        string='Розмір сторінки', config_parameter='factory3d.access.page_size', groups=GROUP)
    f3d_access_max_pages_per_run = fields.Integer(
        string='Сторінок за опитування', config_parameter='factory3d.access.max_pages_per_run', groups=GROUP)
    f3d_access_overlap_s = fields.Integer(
        string='Перекриття вікна, с', config_parameter='factory3d.access.overlap_s', groups=GROUP)
    f3d_access_initial_lookback_h = fields.Integer(
        string='Перше опитування: глибина, год', config_parameter='factory3d.access.initial_lookback_h',
        groups=GROUP)
    f3d_access_paging_mode = fields.Selection(
        [('offset', 'offset'), ('hint', 'hint (BioStar 2.8+)')], string='Режим сторінок',
        config_parameter='factory3d.access.paging_mode', groups=GROUP)
    f3d_access_dup_window_min = fields.Integer(
        string='Вікно дублікатів, хв', config_parameter='factory3d.access.dup_window_min', groups=GROUP)
    f3d_access_merge_gap_min = fields.Integer(
        string="Злиття виходів (обід), хв", config_parameter='factory3d.access.merge_gap_min', groups=GROUP)
    f3d_access_max_shift_h = fields.Integer(
        string='Макс. тривалість зміни, год', config_parameter='factory3d.access.max_shift_h', groups=GROUP)
    f3d_access_stale_close_enabled = fields.Boolean(
        string='Закривати відмітки без виходу', config_parameter='factory3d.access.stale_close_enabled',
        groups=GROUP)
    f3d_access_stale_close_fallback_min = fields.Integer(
        string='Закриття без графіка: через, хв', config_parameter='factory3d.access.stale_close_fallback_min',
        groups=GROUP)
    f3d_access_keep_days = fields.Integer(
        string='Зберігати події, діб', config_parameter='factory3d.access.keep_days', groups=GROUP)
    f3d_access_keep_raw = fields.Boolean(
        string='Зберігати сирий JSON', config_parameter='factory3d.access.keep_raw', groups=GROUP)
    f3d_access_publish_signals = fields.Boolean(
        string='Публікувати сигнали телеметрії', config_parameter='factory3d.access.publish_signals',
        groups=GROUP)
    f3d_access_visitor_default_hours = fields.Integer(
        string='Тривалість візиту, год', config_parameter='factory3d.access.visitor_default_hours', groups=GROUP)
    f3d_access_visitor_user_prefix = fields.Char(
        string='Префікс користувача відвідувача', config_parameter='factory3d.access.visitor_user_prefix',
        groups=GROUP)
    f3d_access_visitor_user_group_id = fields.Char(
        string='Група користувачів BioStar (id)', config_parameter='factory3d.access.visitor_user_group_id',
        groups=GROUP)
    f3d_access_server_count = fields.Integer(string='Серверів BioStar', compute='_compute_f3d_access_server_count',
                                             groups=GROUP)

    @api.depends_context('uid')
    def _compute_f3d_access_server_count(self):
        count = self.env['f3d.access.server'].sudo().search_count([])
        for rec in self:
            rec.f3d_access_server_count = count

    def set_values(self):
        for name, (_key, lo, hi) in INT_RANGES.items():
            if not lo <= self[name] <= hi:
                raise ValidationError("%(label)s: допустимо %(lo)s–%(hi)s." % {
                    'label': self._fields[name].string, 'lo': lo, 'hi': hi})
        prefix = self.f3d_access_visitor_user_prefix
        if prefix and not PREFIX_RE.match(prefix.strip()):
            raise ValidationError("%s: 1–8 символів [A-Za-z0-9_-]." % self._fields[
                'f3d_access_visitor_user_prefix'].string)
        group_id = self.f3d_access_visitor_user_group_id
        if group_id and not GROUP_ID_RE.match(group_id.strip()):
            raise ValidationError("%s: 1–9 цифр." % self._fields['f3d_access_visitor_user_group_id'].string)
        res = super().set_values()
        # Odoo стирає параметр для 0; для полів, де 0 допустимий, зберігаємо його явно
        for name, (key, lo, _hi) in INT_RANGES.items():
            if lo == 0 and self[name] == 0:
                P.set_param(self.env, key, '0')
        return res

    def action_f3d_access_server(self):
        return self.env['ir.actions.act_window']._for_xml_id('factory3d_access.action_f3d_access_server')

    def action_f3d_access_test(self):
        server = self.env['f3d.access.server'].search([('active', '=', True)], limit=1)
        if not server:
            raise UserError("Немає активного сервера BioStar.")
        return server.action_test_connection()
