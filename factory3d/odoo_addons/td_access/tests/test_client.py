import logging
from unittest import mock

import requests

from odoo.tests import tagged

from ..tools.biostar_client import (
    BioStarAuthError, BioStarClient, BioStarError, BioStarWriteDisabled, SecretFilter)
from ..tools.dates import parse_bs_dt
from .common import AccessCase


def _resp(status=200, body=None, headers=None, text=None, bad_json=False):
    resp = mock.MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.text = text if text is not None else ''
    if bad_json:
        resp.json.side_effect = ValueError('no json')
    else:
        resp.json.return_value = body if body is not None else {}
    return resp


def _login(session='s1'):
    return _resp(200, {'Response': {'code': '0'}}, {'bs-session-id': session})


def _client(responses, write_enabled=False, session_id=None):
    http = mock.MagicMock(spec=requests.Session)
    http.request.side_effect = list(responses)
    return BioStarClient('https://iot-sim:8443/', 'admin', 'test-pass', http=http,
                         write_enabled=write_enabled, session_id=session_id), http


def _logins(http):
    return [c for c in http.request.call_args_list if c.args[1].endswith('/api/login')]


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestClient(AccessCase):

    def test_login_header(self):
        devices = _resp(200, {'DeviceCollection': {'rows': [{'id': '1'}]}})
        client, http = _client([_login('s1'), devices])
        client.login()
        self.assertEqual(client.list_devices(), [{'id': '1'}])
        first, second = http.request.call_args_list
        self.assertEqual(first.args[:2], ('POST', 'https://iot-sim:8443/api/login'))
        self.assertNotIn('bs-session-id', first.kwargs['headers'])
        self.assertEqual(first.kwargs['json'], {'User': {'login_id': 'admin', 'password': 'test-pass'}})
        self.assertEqual(second.kwargs['headers']['bs-session-id'], 's1')
        self.assertEqual(second.kwargs['timeout'], (5, 30))

    def test_relogin_once(self):
        ok = _resp(200, {'DeviceCollection': {'rows': [{'id': '7'}]}})
        client, http = _client([_login('s1'), _resp(401, {'Response': {'code': '10'}}), _login('s2'), ok])
        client.login()
        self.assertEqual(client.list_devices(), [{'id': '7'}])
        self.assertEqual(len(_logins(http)), 2)
        self.assertEqual(http.request.call_args_list[-1].kwargs['headers']['bs-session-id'], 's2')
        self.assertEqual(client.session_id, 's2')

    def test_auth_error_no_loop(self):
        denied = _resp(401, {'Response': {'code': '10'}})
        client, http = _client([_login('s1'), denied, _login('s2'), denied])
        client.login()
        with self.assertRaises(BioStarAuthError):
            client.list_devices()
        self.assertEqual(len(_logins(http)), 2)
        self.assertEqual(http.request.call_count, 4)

    def test_search_body_offset(self):
        client, http = _client([_resp(200, {'EventCollection': {'total': '1', 'rows': [{'id': '1'}]}})],
                               session_id='s1')
        rows, total = client.search_events(
            parse_bs_dt('2026-10-12T06:57:10Z'), parse_bs_dt('2026-10-12T07:05:30Z'), limit=500, offset=0)
        self.assertEqual((rows, total), ([{'id': '1'}], 1))
        call = http.request.call_args
        self.assertEqual(call.args[:2], ('POST', 'https://iot-sim:8443/api/events/search'))
        self.assertEqual(call.kwargs['json'], {"Query": {
            "limit": 500, "offset": 0,
            "conditions": [{"column": "datetime", "operator": 3,
                            "values": ["2026-10-12T06:57:10.000Z", "2026-10-12T07:05:30.000Z"]}],
            "orders": [{"column": "datetime", "descending": False}]}})

    def test_search_body_hint(self):
        client, http = _client([_resp(200, {'EventCollection': {'rows': []}})], session_id='s1')
        client.search_events(parse_bs_dt('2026-10-12T06:57:10Z'), parse_bs_dt('2026-10-12T07:05:30Z'),
                             limit=2, offset=None, hint='H1')
        query = http.request.call_args.kwargs['json']['Query']
        self.assertEqual(query['hint'], 'H1')
        self.assertNotIn('offset', query)

    def test_write_disabled_no_network(self):
        client, http = _client([], write_enabled=False)
        now = parse_bs_dt('2026-10-12T05:00:00Z')
        for call in (lambda: client.create_card('555', 0),
                     lambda: client.update_user_cards('OPSAW1', []),
                     lambda: client.create_user('V-1', 'Гість', now, now, 1)):
            with self.assertRaises(BioStarWriteDisabled):
                call()
        self.assertEqual(http.request.call_count, 0)

    def test_http_405(self):
        client, _http = _client([_resp(405, {})], session_id='s1')
        with self.assertRaises(BioStarError) as cm:
            client.request('POST', '/api/cards')
        self.assertEqual(cm.exception.http_status, 405)

    def test_invalid_json(self):
        client, _http = _client([_resp(200, bad_json=True)], session_id='s1')
        with self.assertRaises(BioStarError) as cm:
            client.list_devices()
        self.assertEqual(cm.exception.message, 'Невалідна відповідь JSON')

    def test_response_code_nonzero(self):
        client, _http = _client([_resp(200, {'Response': {'code': '7', 'message': 'Boom'}})], session_id='s1')
        with self.assertRaises(BioStarError) as cm:
            client.list_doors()
        self.assertEqual((cm.exception.bs_code, cm.exception.message), ('7', 'Boom'))

    def test_wrong_password(self):
        client, _http = _client([_resp(401, {'Response': {'code': '101', 'message': 'Failed to login'}})])
        with self.assertRaises(BioStarAuthError) as cm:
            client.login()
        self.assertIn('101', str(cm.exception))
        self.assertNotIn('test-pass', str(cm.exception))

    def test_network_error(self):
        client, _http = _client([requests.ConnectionError('refused http://x/api?password=abc')], session_id='s1')
        with self.assertRaises(BioStarError) as cm:
            client.list_devices()
        self.assertTrue(cm.exception.message.startswith('ConnectionError'))
        self.assertNotIn('password=abc', cm.exception.message)


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestSecretFilter(AccessCase):

    @staticmethod
    def _filtered(msg):
        record = logging.LogRecord('x', logging.DEBUG, __file__, 1, msg, None, None)
        SecretFilter().filter(record)
        return record.getMessage()

    def test_password_masked(self):
        out = self._filtered('{"User": {"login_id": "admin", "password": "test-pass"}}')
        self.assertNotIn('test-pass', out)
        self.assertIn('"password": "***"', out)

    def test_session_masked(self):
        out = self._filtered('headers bs-session-id: 0123abcd-4567-89ef-0123')
        self.assertNotIn('0123abcd', out)
        self.assertIn('bs-session-id: ***', out)

    def test_logs_clean(self):
        client, _http = _client([_login('abcdef12-3456'), _resp(200, {'DeviceCollection': {'rows': []}})])
        with self.assertLogs('odoo.addons.factory3d_access', 'DEBUG') as logs:
            client.login()
            client.list_devices()
        text = '\n'.join(logs.output)
        self.assertIn('/api/devices', text)
        self.assertNotIn('test-pass', text)
        self.assertNotIn('abcdef12-3456', text)
