"""Клієнт REST BioStar 2 (SPEC §7.1): сесія, повторний вхід, коди помилок, стоп-кран запису."""
import logging
import re
import time

import requests

from .dates import fmt_bs_dt

_logger = logging.getLogger(__name__)

_SECRET_PATTERNS = (
    (re.compile(r'(?i)("password"\s*:\s*")[^"]*(")'), r'\1***\2'),
    (re.compile(r'(?i)(bs-session-id\W+)[0-9a-f\-]{8,}'), r'\1***'),
)
_URL_PARAMS_RE = re.compile(r'\?[^\s\'")]*')


class SecretFilter(logging.Filter):
    """Замінює пароль і bs-session-id у повідомленні логу на `***`."""

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - некоректний формат не повинен ламати лог
            return True
        for pattern, repl in _SECRET_PATTERNS:
            message = pattern.sub(repl, message)
        record.msg, record.args = message, None
        return True


_logger.addFilter(SecretFilter())


class BioStarError(Exception):
    def __init__(self, http_status=None, bs_code=None, message=''):
        self.http_status = http_status
        self.bs_code = bs_code
        self.message = message or ''
        super().__init__(self.message)

    def __str__(self):
        if self.bs_code and str(self.bs_code) not in self.message:
            return "%s (код %s)" % (self.message, self.bs_code)
        return self.message


class BioStarAuthError(BioStarError):
    """401 або Response.code 101/10 після повторного входу."""


class BioStarWriteDisabled(BioStarError):
    """Запис при write_enabled=False (до будь-якого з'єднання)."""


class BioStarClient:

    def __init__(self, url, login, password, verify_ssl=True, timeout=(5, 30), session_id=None,
                 write_enabled=False, http=None):
        self.base = (url or '').rstrip('/')
        self.login_id = login
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session_id = session_id
        self.write_enabled = write_enabled
        self.http = http if http is not None else requests.Session()

    # ------------------------------------------------------------------ транспорт
    def _send(self, method, path, json=None, params=None, with_session=True):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if with_session and self.session_id:
            headers['bs-session-id'] = self.session_id
        started = time.monotonic()
        try:
            resp = self.http.request(method, self.base + path, json=json, params=params, headers=headers,
                                     timeout=self.timeout, verify=self.verify_ssl)
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.SSLError) as exc:
            text = _URL_PARAMS_RE.sub('', str(exc))[:200]
            raise BioStarError(None, None, "%s: %s" % (type(exc).__name__, text)) from None
        _logger.debug("%s %s → %s (%d мс)", method, path, resp.status_code,
                      int((time.monotonic() - started) * 1000))
        return resp

    @staticmethod
    def _body(resp):
        try:
            body = resp.json()
        except ValueError:
            return None
        return body if isinstance(body, dict) else None

    def request(self, method, path, json=None, params=None, write=False, _retry=True):
        if write and not self.write_enabled:
            raise BioStarWriteDisabled(None, None,
                                       "Запис у BioStar вимкнено стоп-краном factory3d.access.write_enabled")
        if not self.session_id and path != '/api/login':
            self.login()
        resp = self._send(method, path, json=json, params=params)
        status = resp.status_code
        body = self._body(resp)
        response = (body or {}).get('Response') if isinstance(body, dict) else None
        code = str(response.get('code')) if isinstance(response, dict) and response.get('code') is not None else None
        message = (response or {}).get('message') if isinstance(response, dict) else None

        if status == 401 or code in ('10', '11'):
            if _retry:
                self.session_id = None
                self.login()
                return self.request(method, path, json=json, params=params, write=write, _retry=False)
            raise BioStarAuthError(401 if status == 401 else status, code, message or "Сесія BioStar недійсна")
        if code == '101':
            raise BioStarAuthError(status, code, "Невірний логін або пароль BioStar (код 101)")
        if status == 405:
            raise BioStarError(405, None, "Метод не підтримується сервером BioStar (405)")
        if status >= 400:
            text = message or (getattr(resp, 'text', '') or '')[:200]
            raise BioStarError(status, code, text or "HTTP %s" % status)
        if body is None:
            raise BioStarError(status, None, "Невалідна відповідь JSON")
        if code is not None and code != '0':
            raise BioStarError(status, code, message or "Помилка BioStar")
        return body

    # ------------------------------------------------------------------ сесія
    def login(self):
        payload = {'User': {'login_id': self.login_id, 'password': self.password}}
        self.session_id = None
        resp = self._send('POST', '/api/login', json=payload, with_session=False)
        body = self._body(resp)
        response = (body or {}).get('Response') if isinstance(body, dict) else None
        code = str(response.get('code')) if isinstance(response, dict) and response.get('code') is not None else None
        message = response.get('message') if isinstance(response, dict) else None
        if resp.status_code == 401 or code in ('101', '10', '11'):
            raise BioStarAuthError(resp.status_code, code, "Невірний логін або пароль BioStar (код %s)" % (code or 101)
                                   if code in (None, '101') else (message or "Вхід у BioStar відхилено"))
        if resp.status_code == 405:
            raise BioStarError(405, None, "Метод не підтримується сервером BioStar (405)")
        if resp.status_code >= 400:
            raise BioStarError(resp.status_code, code, message or (getattr(resp, 'text', '') or '')[:200])
        if code is not None and code != '0':
            raise BioStarError(resp.status_code, code, message or "Помилка входу BioStar")
        session = (resp.headers or {}).get('bs-session-id')
        if not session:
            raise BioStarError(resp.status_code, None, "Відповідь входу BioStar без bs-session-id")
        self.session_id = session
        return session

    def logout(self):
        if not self.session_id:
            return
        try:
            self.request('POST', '/api/logout', json={}, _retry=False)
        except BioStarError as exc:
            _logger.debug("Вихід із BioStar: %s", exc)
        self.session_id = None

    # ------------------------------------------------------------------ читання
    def list_users(self, limit=100):
        offset = 0
        while True:
            data = self.request('GET', '/api/users', params={'limit': limit, 'offset': offset})
            collection = data.get('UserCollection') or {}
            rows = collection.get('rows') or []
            yield from rows
            offset += len(rows)
            try:
                total = int(collection.get('total'))
            except (TypeError, ValueError):
                total = None
            if len(rows) < limit or (total is not None and offset >= total):
                return

    def list_users_total(self):
        data = self.request('GET', '/api/users', params={'limit': 1, 'offset': 0})
        try:
            return int((data.get('UserCollection') or {}).get('total'))
        except (TypeError, ValueError):
            return 0

    def list_devices(self):
        return (self.request('GET', '/api/devices').get('DeviceCollection') or {}).get('rows') or []

    def list_doors(self):
        return (self.request('GET', '/api/doors').get('DoorCollection') or {}).get('rows') or []

    def search_events(self, since, until, limit, offset=None, hint=None):
        query = {
            'limit': limit,
            'conditions': [{'column': 'datetime', 'operator': 3,
                            'values': [fmt_bs_dt(since), fmt_bs_dt(until)]}],
            'orders': [{'column': 'datetime', 'descending': False}],
        }
        if hint is not None:
            query['hint'] = hint
        elif offset is not None:
            query['offset'] = offset
        data = self.request('POST', '/api/events/search', json={'Query': query})
        collection = data.get('EventCollection') or {}
        try:
            total = int(collection.get('total'))
        except (TypeError, ValueError):
            total = None
        return collection.get('rows') or [], total

    # ------------------------------------------------------------------ запис (стоп-кран)
    def create_card(self, card_id, card_type_id):
        body = {'CardCollection': {'rows': [{'card_id': str(card_id),
                                             'card_type': {'id': str(card_type_id), 'type': '1'}}]}}
        data = self.request('POST', '/api/cards', json=body, write=True)
        rows = (data.get('CardCollection') or {}).get('rows') or []
        if not rows or rows[0].get('id') is None:
            raise BioStarError(200, None, "BioStar не повернув id картки")
        return str(rows[0]['id'])

    def update_user_cards(self, user_id, cards):
        self.request('PUT', '/api/users/%s' % user_id, json={'User': {'cards': cards}}, write=True)

    def create_user(self, user_id, name, start_dt, expiry_dt, user_group_id):
        body = {'User': {
            'user_id': str(user_id), 'name': name, 'user_group_id': {'id': str(user_group_id)},
            'start_datetime': fmt_bs_dt(start_dt).replace('.000Z', '.00Z'),
            'expiry_datetime': fmt_bs_dt(expiry_dt).replace('.000Z', '.00Z'),
            'disabled': 'false'}}
        self.request('POST', '/api/users', json=body, write=True)
