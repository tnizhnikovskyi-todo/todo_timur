# Part of td_genset (ToDo). Власник файлу: W5 «Стенд і документація».
"""Стенд готовий до сценаріїв ТК-01…ТК-14 (AC-65; ТР А.13): емулятор зі змінних оточення, власний екземпляр
з керованим годинником, налаштування модуля на емулятор.

Ці тести не залежать від реалізації W1–W4 (лише API емулятора і каркас W0) і мають бути зеленими завжди:
якщо вони червоні — несправний стенд, а не модуль.
"""
from datetime import datetime, timezone

from odoo.tests import tagged

from .stand_common import STAND_CONFIG, TdGensetStandCase


def _ts(value):
    """``ts`` знімка / ``*_utc`` ретранслятора → naive UTC."""
    if isinstance(value, str):
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandHarnessEnv(TdGensetStandCase):
    """Емулятор, піднятий ``run_stand_tests.sh`` (версія 1.1.3)."""

    def test_ac65_env_relay_contract(self):
        """AC-65 (передумова ТК-01…ТК-14): емулятор з оточення відповідає за ``relay_api.md`` — токен перевіряється
        першим (401), ``/status`` з hostid генератора «Стенд», знімки за курсором, ``/_sim`` скинуто; модуль
        налаштовано на емулятор (``td_genset.relay_url``/``relay_token``), налаштування стенду застосовано."""
        self.assertEqual(self.relay.api('GET', '/status', token='wrong-token'),
                         (401, {'error': 'missing or wrong token'}))
        status = self.relay.status()
        self.assertEqual(status['relay']['version'], '1.1.3')
        self.assertEqual(status['devices'][0]['hostid'], self.genset.relay_hostid)
        self.assertTrue(status['devices'][0]['commands_ready'])
        first = self.relay.readings()
        self.assertTrue(first)
        self.assertEqual(first[0]['reason'], 'first')
        last_id = self.relay.snapshot()
        page = self.relay.api_ok('GET', '/readings', params={'since': first[-1]['id'], 'limit': 500})
        self.assertEqual(page['next_since'], last_id)
        self.assertIn('fuel_level_sensor_ohm', page['readings'][-1]['values'])
        icp = self.env['ir.config_parameter'].sudo()
        self.assertEqual(icp.get_param('td_genset.relay_url'), self.relay.api_url)
        self.assertEqual(icp.get_param('td_genset.relay_token'), self.relay.token)
        for name, value in STAND_CONFIG.items():
            self.assertEqual(self.config[name], value, name)


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandHarnessOwn(TdGensetStandCase):
    """Власний екземпляр емулятора: версія 1.1.1 і керований годинник."""

    relay_mode = 'own'
    relay_version = '1.1.1'

    def test_ac65_ac68_own_relay_version_and_clock(self):
        """AC-65, AC-68 (передумова ТК-14.11): власний емулятор 1.1.1 — без ключів ``*_sensor_ohm`` у ``values``,
        оми лише в сирому образі (``regs`` 22/18/20); ``advance()`` зсуває годинник емулятора і Odoo синхронно,
        знімки після зсуву мають «новий» час."""
        status = self.relay.status()
        self.assertEqual(status['relay']['version'], '1.1.1')
        latest = self.relay.latest(raw=True)
        self.assertNotIn('fuel_level_sensor_ohm', latest['values'])
        self.assertNotIn('water_temp_sensor_ohm', latest['values'])
        self.assertEqual(latest['regs']['18'], 5154)
        self.assertEqual(latest['regs']['20'], 95)
        self.assertGreater(latest['regs']['22'], 0)
        self.assertLess(abs((_ts(status['relay']['time_utc']) - self.now()).total_seconds()), 5)
        self.advance(minutes=30)
        self.assertLess(abs((_ts(self.relay.status()['relay']['time_utc']) - self.now()).total_seconds()), 5)
        self.relay.snapshot()
        self.assertLess(abs((_ts(self.relay.latest()['ts']) - self.now()).total_seconds()), 5)
        self.relay.sim(link=False)
        self.advance(minutes=4)
        device = self.relay.device()
        self.assertFalse(device['online'])
        self.assertGreaterEqual(device['seconds_since_seen'], 240)
        self.assertFalse(device['commands_ready'])
