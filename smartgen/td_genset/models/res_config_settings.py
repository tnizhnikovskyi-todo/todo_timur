# Part of td_genset (ToDo). Власник файлу: W3 «UI». Каркас: W0.
"""Адреса і токен ретранслятора у стандартних Налаштуваннях — ТР 2.3.10, А.10; SPEC 5.10, 13.

Значення живуть лише в ``ir.config_parameter`` (``base.group_system``). Токен у форму не повертається
(лише ознака «встановлено»); порожнє значення при збереженні не затирає наявний токен (AC-01, AC-57).
"""
from odoo import api, fields, models

TOKEN_PARAM = 'td_genset.relay_token'
# Адреса проду в коді не зберігається (ТР А.10, «Налаштування системи»; BUILD_PLAN 1.4) — вводиться вручну.


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    td_genset_relay_url = fields.Char(
        string='Адреса API ретранслятора', config_parameter='td_genset.relay_url',
        help='Адреса API ретранслятора без завершального «/» (на тесті — адреса емулятора).')
    td_genset_relay_token = fields.Char(
        string='Токен ретранслятора',
        help='Токен доступу до API ретранслятора. Після збереження не показується; порожнє поле не змінює токен.')
    td_genset_relay_token_set = fields.Boolean(
        string='Токен встановлено', compute='_compute_td_genset_relay_token_set',
        help='Чи збережено токен у системних параметрах.')
    td_genset_http_timeout = fields.Integer(
        string='Таймаут, с', config_parameter='td_genset.http_timeout', default=20,
        help="Таймаут читання відповіді ретранслятора, с (з'єднання — 5 с).")

    @api.depends('td_genset_relay_token')
    def _compute_td_genset_relay_token_set(self):
        token_set = bool(self.env['ir.config_parameter'].sudo().get_param(TOKEN_PARAM))
        for settings in self:
            settings.td_genset_relay_token_set = token_set

    def set_values(self):
        """Токен зберігається лише якщо введено нове значення (TODO: W3 — AC-01, AC-55, AC-57)."""
        super().set_values()
        for settings in self:
            if settings.td_genset_relay_token:
                self.env['ir.config_parameter'].sudo().set_param(TOKEN_PARAM, settings.td_genset_relay_token.strip())
