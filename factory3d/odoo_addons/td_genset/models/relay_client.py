# Part of td_genset (ToDo). Власник файлу: W1 «Моніторинг». Каркас: W0.
"""Клієнт ретранслятора ``td.genset.relay.client`` (AbstractModel, без таблиці) — ТР 2.6.1, А.11, SPEC 5.15.

Контракт:

* ``requests.Session`` з ``timeout=(5, http_timeout)``, ``verify=True``; ``hostid`` у кожному запиті;
* адреса/токен/таймаут — лише ``ir.config_parameter`` (``td_genset.relay_url``, ``td_genset.relay_token``,
  ``td_genset.http_timeout``), читаються через ``sudo()``;
* заголовки ніколи не логуються, токен не потрапляє в текст винятку (AC-57);
* публічні методи — ``@api.private``: через JSON-RPC (``/web/dataset/call_kw``) їх не викликати (ACL до
  AbstractModel не застосовуються, а права перевіряє викликач — cron, майстер, кнопка; AC-24, AC-66);
* коди → винятки: таймаут / ``RequestException`` / 5xx → ``RelayUnavailable``; 401 → ``RelayAuthError``;
  403 → ``RelayCommandsDisabled``; 409 → ``RelayBusy(reason)``; 404 (крім ``no readings yet`` → ``None``)
  → ``RelayNotFound``; 400 → ``RelayBadRequest``.

У тестах HTTP замокано (``tests/common.py: RelayMock`` патчить ``requests.Session.request``).
"""
import logging

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20
CONNECT_TIMEOUT = 5
REQUESTED_BY_MAX = 120
SOURCE_MAX = 60


# --------------------------------------------------------------------------- винятки (контракт А.11 — готові)
class RelayError(Exception):
    """Помилка ретранслятора. Текст: ``"<METHOD> <path> → <status>: <error>"`` — без заголовків і тіла запиту."""

    def __init__(self, status=None, error='', method='', path=''):
        self.status = status
        self.error = error or ''
        self.method = method or ''
        self.path = path or ''
        super().__init__('%s %s → %s: %s' % (self.method, self.path, self.status, self.error))


class RelayUnavailable(RelayError):
    """Таймаут, ``requests.RequestException``, 5xx / 502–504 — ретранслятор недоступний."""


class RelayAuthError(RelayError):
    """401 — немає токена або токен неправильний."""


class RelayCommandsDisabled(RelayError):
    """403 — команди вимкнено на ретрансляторі (RELAY_COMMANDS_ENABLED=0)."""


class RelayBusy(RelayError):
    """409 — команду зараз виконати не можна; ``reason`` ∈ {modem_offline, format_not_learned, queue_full}."""

    def __init__(self, status=409, error='', method='', path='', reason=None):
        super().__init__(status, error, method, path)
        self.reason = reason or self.reason_from_error(error)

    @staticmethod
    def reason_from_error(error):
        text = (error or '').lower()
        if 'not connected' in text:
            return 'modem_offline'
        if 'format not learned' in text:
            return 'format_not_learned'
        if 'already waiting' in text:
            return 'queue_full'
        return None


class RelayNotFound(RelayError):
    """404, крім ``no readings yet`` (той повертається як ``None``)."""


class RelayBadRequest(RelayError):
    """400 — помилка коду (невідома команда, не JSON, ``since`` не число)."""


class TdGensetRelayClient(models.AbstractModel):
    _name = 'td.genset.relay.client'
    _description = 'Генератори: клієнт ретранслятора'

    # ------------------------------------------------------------------ параметри (W0 — працюють)
    @api.model
    def _base_url(self):
        """Адреса API з ``td_genset.relay_url`` (без завершального ``/``); ``sudo()`` — параметр читає лише system."""
        url = self.env['ir.config_parameter'].sudo().get_param('td_genset.relay_url') or ''
        return url.rstrip('/')

    @api.model
    def _timeout(self):
        """Таймаут читання, с (``td_genset.http_timeout``, за замовчуванням 20)."""
        value = self.env['ir.config_parameter'].sudo().get_param('td_genset.http_timeout')
        try:
            return int(value) if value else DEFAULT_TIMEOUT
        except (TypeError, ValueError):
            return DEFAULT_TIMEOUT

    @api.model
    def _headers(self):
        """``{'Authorization': 'Bearer …', 'Accept': 'application/json'}``. НІКОЛИ не логувати (AC-57)."""
        token = self.env['ir.config_parameter'].sudo().get_param('td_genset.relay_token') or ''
        return {'Authorization': 'Bearer %s' % token, 'Accept': 'application/json'}

    @api.model
    def _masked_headers(self):
        """Заголовки для логів: значення токена замасковано (``Authorization: Bearer ***``, AC-57)."""
        return {'Authorization': 'Bearer ***', 'Accept': 'application/json'}

    # ------------------------------------------------------------------ HTTP (W1)
    @api.model
    def _request(self, method, path, params=None, json=None):
        """Один HTTP-запит ``requests.Session.request(timeout=(5, http_timeout), verify=True)``.

        Маппінг кодів на винятки — ТР 2.6.1: таймаут / ``RequestException`` / 5xx → ``RelayUnavailable``;
        401 → ``RelayAuthError``; 403 → ``RelayCommandsDisabled``; 409 → ``RelayBusy``; 404 → ``RelayNotFound``;
        400 → ``RelayBadRequest``. У логах і текстах винятків — лише метод, шлях, статус і ``error``
        (заголовки й токен — ніколи, AC-57). Повертає розібране тіло JSON (dict).
        """
        method = (method or 'GET').upper()
        base = self._base_url()
        if not base:
            raise RelayUnavailable(None, 'relay url is not configured', method, path)
        try:
            with requests.Session() as session:
                response = session.request(
                    method, base + path, params=params, json=json, headers=self._headers(),
                    timeout=(CONNECT_TIMEOUT, self._timeout()), verify=True)
        except requests.exceptions.Timeout:
            _logger.debug('%s %s -> timeout %s', method, path, self._masked_headers())
            raise RelayUnavailable(None, 'timeout', method, path) from None
        except requests.exceptions.RequestException as exc:
            _logger.debug('%s %s -> %s %s', method, path, exc.__class__.__name__, self._masked_headers())
            raise RelayUnavailable(None, 'connection error (%s)' % exc.__class__.__name__, method, path) from None
        status = response.status_code
        _logger.debug('%s %s -> %s %s', method, path, status, self._masked_headers())
        try:
            body = response.json()
        except ValueError:
            body = None
        if 200 <= status < 300:
            if body is None:
                raise RelayUnavailable(status, 'response is not JSON', method, path)
            return body
        error = body.get('error') if isinstance(body, dict) else None
        error = str(error) if error else 'HTTP %s' % status
        if status == 401:
            raise RelayAuthError(status, error, method, path)
        if status == 403:
            raise RelayCommandsDisabled(status, error, method, path)
        if status == 409:
            raise RelayBusy(status, error, method, path)
        if status == 404:
            raise RelayNotFound(status, error, method, path)
        if status == 400:
            raise RelayBadRequest(status, error, method, path)
        if status >= 500:
            raise RelayUnavailable(status, error, method, path)
        raise RelayError(status, error, method, path)

    @api.private
    @api.model
    def status(self):
        """``GET /status`` як є (dict)."""
        return self._request('GET', '/status')

    @api.private
    @api.model
    def device_status(self, status, hostid):
        """Елемент ``devices[]`` для ``hostid`` або ``None`` (готово з W0 — чиста функція)."""
        for device in (status or {}).get('devices') or []:
            if device.get('hostid') == hostid:
                return device
        return None

    @api.private
    @api.model
    def latest(self, hostid):
        """``GET /latest?hostid=`` — останній знімок (dict); ``None`` при ``404 no readings yet``."""
        try:
            return self._request('GET', '/latest', params={'hostid': hostid} if hostid else None)
        except RelayNotFound as exc:
            if 'no readings yet' in (exc.error or ''):
                return None
            raise

    @api.private
    @api.model
    def readings(self, hostid, since, limit=500, raw=False):
        """``GET /readings?hostid&since&limit[&raw=1]`` → ``(readings, next_since)``.

        ``raw=True`` додає ``regs``/``coils`` (лише для омів датчиків, AC-68).
        """
        since = int(since or 0)
        params = {'since': since, 'limit': int(limit)}
        if hostid:
            params['hostid'] = hostid
        if raw:
            params['raw'] = 1
        body = self._request('GET', '/readings', params=params)
        readings = body.get('readings') or []
        next_since = body.get('next_since')
        if next_since is None:
            next_since = max([int(reading['id']) for reading in readings] or [since])
        return readings, int(next_since)

    @api.private
    @api.model
    def post_command(self, hostid, command, requested_by, source):
        """``POST /commands``; ``requested_by`` обрізається до 120, ``source`` до 60 символів; тіло ``201``."""
        payload = {'command': command}
        if hostid:
            payload['hostid'] = hostid
        if requested_by:
            payload['requested_by'] = str(requested_by)[:REQUESTED_BY_MAX]
        if source:
            payload['source'] = str(source)[:SOURCE_MAX]
        return self._request('POST', '/commands', json=payload)

    @api.private
    @api.model
    def command(self, relay_cmd_id):
        """``GET /commands/<id>`` (dict)."""
        return self._request('GET', '/commands/%d' % int(relay_cmd_id))

    @api.private
    @api.model
    def commands(self, since, limit=200):
        """``GET /commands?since=&limit=`` → список записів (журнал ретранслятора, без ``next_since``)."""
        body = self._request('GET', '/commands', params={'since': int(since or 0), 'limit': int(limit)})
        return body.get('commands') or []
