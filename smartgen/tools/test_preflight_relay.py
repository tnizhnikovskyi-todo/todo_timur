#!/usr/bin/env python3
"""Тест preflight_relay.py на локальному емуляторі fake_relay.py (лише стандартна бібліотека).

    python3 smartgen/tools/test_preflight_relay.py -v

Кожен сценарій піднімає свій емулятор на вільному порту з випадковим токеном; перевіряє код виходу, підсумок звіту,
що токена немає у виводі і що на ретранслятор не пішло жодного POST (журнал запитів емулятора).
"""
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PREFLIGHT = os.path.join(HERE, 'preflight_relay.py')
FAKE_RELAY = os.path.join(HERE, 'fake_relay.py')
HOSTID = '3130373031334717003D002E'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Emulator:
    """fake_relay.py на вільному порту; журнал запитів (stderr) — у тимчасовому файлі."""

    def __init__(self, version='1.1.3'):
        self.port = free_port()
        self.token = 'pf-%s' % secrets.token_hex(12)
        self.log = tempfile.NamedTemporaryFile(prefix='preflight_relay_', suffix='.log', delete=False)
        self.proc = subprocess.Popen(
            [sys.executable, FAKE_RELAY, '--port', str(self.port), '--token', self.token, '--snapshot-sec', '2',
             '--relay-version', version, '--no-noise'], stdout=self.log, stderr=self.log)
        self.url = 'http://127.0.0.1:%d/api/v1' % self.port
        deadline = time.time() + 20
        while time.time() < deadline:     # перший знімок — після першого пакета «модуля»
            try:
                devices = self._get('/status').get('devices') or []
                if devices and devices[0].get('last_reading'):
                    return
            except OSError:
                pass
            time.sleep(0.2)
        raise RuntimeError('емулятор не запустився')

    def _get(self, path):
        request = urllib.request.Request(self.url + path, headers={'Authorization': 'Bearer %s' % self.token})
        with _opener().open(request, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))

    def sim(self, **payload):
        data = json.dumps(payload).encode('utf-8')
        request = urllib.request.Request('http://127.0.0.1:%d/_sim' % self.port, data=data)
        with _opener().open(request, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))

    def requests_seen(self):
        with open(self.log.name, encoding='utf-8', errors='replace') as handle:
            return re.findall(r'"(GET|POST|PUT|DELETE|PATCH) (/api/v1/[^ ]*)', handle.read())

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)
        self.log.close()
        os.unlink(self.log.name)


def run_preflight(*args, url=None, token=None):
    env = dict(os.environ)
    env.pop('TD_GENSET_RELAY_URL', None)
    env.pop('TD_GENSET_RELAY_TOKEN', None)
    env['NO_PROXY'] = env['no_proxy'] = '127.0.0.1,localhost'
    if url:
        env['TD_GENSET_RELAY_URL'] = url
    if token:
        env['TD_GENSET_RELAY_TOKEN'] = token
    result = subprocess.run([sys.executable, PREFLIGHT] + list(args), capture_output=True, text=True, env=env,
                            timeout=120, check=False)
    return result.returncode, result.stdout + result.stderr


class TestPreflightRelay(unittest.TestCase):

    def emulator(self, version='1.1.3'):
        emulator = Emulator(version)
        self.addCleanup(emulator.stop)
        return emulator

    def assertNoPost(self, emulator, output):
        methods = {method for method, _path in emulator.requests_seen()}
        self.assertEqual(methods, {'GET'}, 'лише GET, жодного POST')
        self.assertNotIn(emulator.token, output, 'токен не виводиться')

    def test_ready_113(self):
        emulator = self.emulator()
        code, output = run_preflight('--allow-http', '--hostid', HOSTID, url=emulator.url, token=emulator.token)
        self.assertEqual(code, 0, output)
        self.assertIn('ПІДСУМОК: ГОТОВО до етапу 1', output)
        self.assertIn('Оми датчиків у values (ретранслятор ≥ 1.1.3)', output)
        self.assertIn('(курсор коректний)', output)
        self.assertIn('Етап 2 (команди): з боку ретранслятора готово', output)
        seen = emulator.requests_seen()
        self.assertTrue(any(path.startswith('/api/v1/readings?') and 'raw=1' in path for _method, path in seen))
        self.assertNoPost(emulator, output)

    def test_ready_111_raw_and_stage2_blocked(self):
        emulator = self.emulator('1.1.1')
        emulator.sim(commands_enabled=False, remote_lock=True, snapshot=True)
        code, output = run_preflight('--allow-http', '--hostid', HOSTID, url=emulator.url, token=emulator.token)
        self.assertEqual(code, 0, output)
        self.assertIn('ретранслятор 1.1.1', output)
        self.assertIn('Ключів *_sensor_ohm немає (ретранслятор 1.1.1)', output)
        self.assertRegex(output, r'raw=1 — \d+ мс; оми з регістрів 18/20/22: паливо \d')
        self.assertIn('Етап 2 (команди): НЕ готово — relay.commands_enabled = false', output)
        self.assertIn('remote_lock = true', output)
        self.assertNoPost(emulator, output)

    def test_not_ready_reasons(self):
        emulator = self.emulator()
        code, output = run_preflight('--allow-http', '--hostid', HOSTID, url=emulator.url, token='wrong-token')
        self.assertEqual(code, 1, output)
        self.assertIn('401: токен не прийнято', output)
        self.assertNotIn('wrong-token', output)
        code, output = run_preflight('--allow-http', '--hostid', '3130373031334717003D0000', url=emulator.url,
                                     token=emulator.token)
        self.assertEqual(code, 1, output)
        self.assertIn('Модуля hostid 3130373031334717003D0000 на ретрансляторі немає; відомі: %s' % HOSTID, output)
        emulator.sim(link=False, seen_ago=600)
        code, output = run_preflight('--allow-http', '--hostid', HOSTID, url=emulator.url, token=emulator.token)
        self.assertEqual(code, 1, output)
        self.assertIn("НЕ на зв'язку", output)
        self.assertIn('ПІДСУМОК: НЕ ГОТОВО до етапу 1', output)
        self.assertNoPost(emulator, output)
        closed = 'http://127.0.0.1:%d/api/v1' % free_port()
        code, output = run_preflight('--allow-http', '--hostid', HOSTID, url=closed, token=emulator.token)
        self.assertEqual(code, 1, output)
        self.assertIn('ретранслятор недоступний', output)

    def test_usage(self):
        code, output = run_preflight('--allow-http', url='http://127.0.0.1:9/api/v1')
        self.assertEqual(code, 2)
        self.assertIn('не задано токен', output)
        code, output = run_preflight(url='http://127.0.0.1:9/api/v1', token='x')
        self.assertEqual(code, 2)
        self.assertIn('https://', output)

    def test_source_has_no_post_and_no_secrets(self):
        with open(PREFLIGHT, encoding='utf-8') as handle:
            source = handle.read()
        self.assertNotIn("'POST'", source)
        self.assertNotIn('data=', source)
        self.assertNotIn('gen-relay', source)
        self.assertIn("method='GET'", source)


if __name__ == '__main__':
    unittest.main()
