import logging
import re

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'td.iot_sim.'
WRITE_OFF_MSG = "Команди на емулятор вимкнено стоп-краном td.iot_sim.write_enabled"
READ_OFF_MSG = "Опитування емулятора вимкнено стоп-краном td.iot_sim.read_enabled"


def truthy(value):
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


class F3dSimClient(models.AbstractModel):
    """Домішка: HTTP-клієнт сервісу емулятора /sim/v1 (SPEC §2.10)."""
    _name = 'td.sim.client'
    _description = 'Клієнт сервісу емулятора'

    # --- параметри ---
    @api.model
    def _sim_param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(PARAM_PREFIX + key, default) or default

    @api.model
    def _sim_flag(self, key):
        return truthy(self._sim_param(key, ''))

    @api.model
    def _sim_url(self):
        base = (self._sim_param('url') or '').strip().rstrip('/')
        if not base:
            raise UserError("Адресу сервісу емулятора не налаштовано (Налаштування → Емулятор обладнання)")
        return base + '/sim/v1'

    @api.model
    def _sim_headers(self):
        # Токен ніколи не потрапляє в лог і в payload подій.
        return {'Authorization': 'Bearer ' + (self._sim_param('token') or ''),
                'Accept': 'application/json'}

    @api.model
    def _sim_require_write(self):
        if not self._sim_flag('write_enabled'):
            raise UserError(WRITE_OFF_MSG)

    # --- запити ---
    @api.model
    def _sim_request(self, method, path, params=None, json=None):
        if method == 'POST':
            self._sim_require_write()
        elif not self._sim_flag('read_enabled'):
            raise UserError(READ_OFF_MSG)
        url = self._sim_url() + path
        try:
            timeout = int(self._sim_param('timeout_s', '5') or 5)
        except ValueError:
            timeout = 5
        try:
            resp = requests.Session().request(
                method, url, headers=self._sim_headers(), params=params, json=json, timeout=timeout)
        except requests.RequestException as exc:
            raise UserError("Сервіс емулятора недоступний: %s" % exc.__class__.__name__) from exc
        status = resp.status_code
        if method == 'POST':
            self._sim_log_command(path, json, status)
        if 200 <= status < 300:
            try:
                return resp.json()
            except ValueError:
                return {}
        detail = self._sim_detail(resp)
        if status == 401:
            raise UserError("Емулятор відхилив токен")
        if status == 423:
            raise UserError("Емулятор заблоковано стоп-краном (SIM_ENABLED=0)")
        if status == 404:
            raise UserError("Невідомий об'єкт: %s" % (detail or path))
        if status in (409, 422):
            raise UserError(detail or "Помилка запиту до емулятора (%s)" % status)
        raise UserError("Сервіс емулятора недоступний: HTTP %s" % status)

    @api.model
    def _sim_detail(self, resp):
        try:
            data = resp.json()
        except ValueError:
            return ''
        detail = data.get('detail') if isinstance(data, dict) else ''
        return detail if isinstance(detail, str) else str(detail or '')

    @api.model
    def _sim_get(self, path, params=None):
        return self._sim_request('GET', path, params=params)

    @api.model
    def _sim_post(self, path, json=None):
        return self._sim_request('POST', path, json=json)

    @api.model
    def _sim_log_command(self, path, body, status):
        match = re.match(r'^/device/([^/]+)/', path)
        self.env['td.sim.event'].sudo().create({
            'ts': fields.Datetime.now(),
            'kind': 'command',
            'device_code': match.group(1) if match else False,
            'run_id': self.env.context.get('f3d_sim_run_id') or False,
            'message': "POST %s → %s" % (path, status),
            'payload': {'path': path, 'body': body or {}, 'status': status},
        })
