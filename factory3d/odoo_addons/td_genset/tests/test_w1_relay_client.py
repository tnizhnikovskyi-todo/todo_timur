# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""клієнт ретранслятора, коди 200/201/400/401/403/404/409/5xx/таймаут, маскування токена (AC-01, AC-10, AC-57, AC-64).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
import logging

from odoo.tests import tagged

from ..models.relay_client import (RelayAuthError, RelayBadRequest, RelayBusy, RelayCommandsDisabled, RelayNotFound,
                                   RelayUnavailable)
from .common import BASE_URL, HOSTID, TOKEN, TdGensetCase, snapshot


@tagged('standard', 'at_install')
class TestW1RelayClient(TdGensetCase):

    def setUp(self):
        super().setUp()
        self.client = self.env['td.genset.relay.client']

    def test_ac01_settings_from_config_parameter(self):
        """AC-01: адреса, токен і таймаут — лише з ir.config_parameter; запит з timeout=(5, 20) і verify=True."""
        status = self.client.status()
        self.assertEqual(status['devices'][0]['hostid'], HOSTID)
        call = self.relay.calls[-1]
        self.assertEqual((call['method'], call['path']), ('GET', '/status'))
        self.assertEqual((call['timeout'], call['verify']), ((5, 20), True))
        self.env['ir.config_parameter'].sudo().set_param('td_genset.relay_token', 'інший-токен')
        with self.assertRaises(RelayAuthError) as caught:
            self.client.status()
        self.assertEqual(caught.exception.status, 401)
        self.assertNotIn('інший-токен', str(caught.exception))
        self.env['ir.config_parameter'].sudo().set_param('td_genset.relay_url', '')
        with self.assertRaises(RelayUnavailable):
            self.client.status()
        self.env['ir.config_parameter'].sudo().set_param('td_genset.relay_url', BASE_URL)

    def test_ac64_response_codes(self):
        """AC-64: коди відповідей → винятки клієнта (ТР 2.6.1); 404 «no readings yet» → None."""
        self.assertIsNone(self.client.latest(HOSTID))
        self.push_reading(snapshot())
        self.assertEqual(self.client.latest(HOSTID)['id'], 1)
        created = self.client.post_command(HOSTID, 'auto', 'Тест ' + 'x' * 200, 'odoo:' + 'y' * 100)
        self.assertEqual((created['status'], created['command']), ('queued', 'auto'))
        self.assertEqual(len(self.relay.calls[-1]['json']['requested_by']), 120)
        self.assertEqual(len(self.relay.calls[-1]['json']['source']), 60)
        self.assertEqual(self.client.command(created['id'])['status'], 'done')
        self.assertEqual([item['id'] for item in self.client.commands(0)], [created['id']])
        cases = [
            (400, RelayBadRequest), (401, RelayAuthError), (403, RelayCommandsDisabled), (404, RelayNotFound),
            (409, RelayBusy), (500, RelayUnavailable), (502, RelayUnavailable), (503, RelayUnavailable),
            ('timeout', RelayUnavailable), ('connection', RelayUnavailable),
        ]
        for code, exception in cases:
            self.relay.fail(code, path='/commands', method='POST', times=1)
            with self.assertRaises(exception, msg=str(code)) as caught:
                self.client.post_command(HOSTID, 'auto', 'Тест', 'odoo:button')
            self.assertTrue(str(caught.exception).startswith('POST /commands → '), str(caught.exception))
        self.assertEqual(caught.exception.error, 'connection error (ConnectionError)')
        for error, reason in (('modem is not connected right now', 'modem_offline'),
                              ('command format not learned yet: waiting', 'format_not_learned'),
                              ('5 commands already waiting for this modem', 'queue_full')):
            self.relay.fail(409, path='/commands', method='POST', times=1, error=error)
            with self.assertRaises(RelayBusy) as caught:
                self.client.post_command(HOSTID, 'auto', 'Тест', 'odoo:button')
            self.assertEqual(caught.exception.reason, reason)
        with self.assertRaises(RelayNotFound) as caught:
            self.client.readings('000000000000000000000000', 0)
        self.assertIn('unknown hostid', caught.exception.error)

    def test_ac64_readings_page_and_raw(self):
        """AC-64, AC-68: /readings — (знімки, next_since); raw=1 лише на вимогу; hostid у кожному запиті."""
        for _i in range(3):
            self.push_reading(snapshot())
        page, next_since = self.client.readings(HOSTID, 0, limit=2)
        self.assertEqual(([item['id'] for item in page], next_since), ([1, 2], 2))
        self.assertNotIn('regs', page[0])
        params = self.relay.calls[-1]['params']
        self.assertEqual((params['hostid'], params['since'], params['limit']), (HOSTID, '0', '2'))
        self.assertNotIn('raw', params)
        page, next_since = self.client.readings(HOSTID, 2, raw=True)
        self.assertEqual(self.relay.calls[-1]['params']['raw'], '1')
        self.assertIn('regs', page[0])
        self.assertEqual(self.client.readings(HOSTID, 3), ([], 3))

    def test_ac57_token_not_in_logs_and_messages(self):
        """AC-57: при 500 і рівні DEBUG токена немає в логах, тексті тривог і повідомленнях; лише «Bearer ***»."""
        self.relay.fail(500)
        logger = logging.getLogger('odoo.addons.td_genset')
        with self.assertLogs('odoo.addons.td_genset', level='DEBUG') as logs:
            old_level = logger.level
            logger.setLevel(logging.DEBUG)
            try:
                self.run_pull()
                self.assertTrue(self.env.ref('td_genset.cron_pull_readings').method_direct_trigger())
                result = self.genset.with_user(self.user_t).action_check_relay()
            finally:
                logger.setLevel(old_level)
        output = '\n'.join(logs.output)
        self.assertNotIn(TOKEN, output)
        self.assertIn('Bearer ***', output)
        self.assertNotIn(TOKEN, str(result))
        self.assertIn('Ретранслятор недоступний (таймаут 20 с)', result['params']['message'])
        self.assertNotIn('Traceback', result['params']['message'])
        self.relay.fail(401)
        with self.assertLogs('odoo.addons.td_genset', level='WARNING') as logs:
            self.run_pull()
        self.assertIn('GET /status → 401: missing or wrong token', logs.output[0])
        self.assertNotIn(TOKEN, '\n'.join(logs.output))
        alarms = self.env['td.genset.alarm'].search([('genset_id', '=', self.genset.id)])
        self.assertTrue(alarms)
        for alarm in alarms:
            self.assertNotIn(TOKEN, '%s %s' % (alarm.name, alarm.description))
        messages = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id)])
        self.assertFalse([body for body in messages.mapped('body') if TOKEN in (body or '')])
        self.assertTrue(all('headers' not in call for call in self.relay.calls))
