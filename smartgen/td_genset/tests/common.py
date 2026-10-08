# Part of td_genset (ToDo). Власник файлу: W0 «Каркас» (спільний для всіх потоків; зміни — через архітектора).
"""Каркас unit-тестів (ТР А.11, А.13; SPEC 15): ``TdGensetCase``, ``RelayMock``, ``snapshot()``.

``RelayMock`` патчить ``requests.Session.request`` і відповідає як ретранслятор (``relay_api.md`` 3–5, 7;
формати — 1:1 з ``smartgen/tools/fake_relay.py``): ``GET /status``, ``/latest``, ``/readings`` (+ ``raw=1``),
``POST /commands``, ``GET /commands/<id>``, ``GET /commands?since``. Жодних реальних HTTP-запитів: адреса
поза ``base_url`` → ``AssertionError``.

Режими:

* версія ретранслятора ``'1.1.3'`` (за замовчуванням) або ``'1.1.1'`` — без 5 ключів
  ``water_temp_sensor_ohm``, ``oil_pressure_sensor_ohm``, ``fuel_level_sensor_ohm``, ``controller_sw``,
  ``controller_hw`` у ``values`` (оми — лише з ``regs`` при ``raw=1``, AC-68);
* помилки: ``fail_with = 409 | 403 | 401 | 400 | 404 | 500 | 502 | 503 | 504 | 'timeout' | 'connection'``
  (+ ``fail_path`` — підрядок шляху, ``fail_method``, ``fail_times`` — скільки разів, ``fail_error`` — текст);
  або ``mock.fail(409, path='/commands', method='POST', times=1, error='command format not learned yet: …')``;
* ``controller_executes = False`` — ретранслятор каже ``done``, але режим контролера не змінюється;
* ``command_flow = 'done' | 'sent' | 'queued' | 'failed' | 'timeout'`` — що поверне перший
  ``GET /commands/<id>`` (``done`` → ефект на контролері + знімок ``change`` з ``ts = done + 1 с``);
* ``crank_failure = True`` — ``start``/``test`` закінчуються невдалим пуском (сигнал ``crank_failure``);
* ``start`` контролер виконує лише в режимі Ручний (``relay_api.md`` 7.1): в Авто/Стоп/Тест — ``done`` без пуску
  (``start_needs_manual = False`` — пуск у будь-якому режимі);
* ``relay_restart()`` — ``queued``/``sent`` → ``failed`` «relay restarted», наступний знімок ``first``.

Час — ``time.time()`` (``freezegun.freeze_time`` діє).
"""
import copy
import json as jsonlib
import re
import time
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import requests

from odoo.tests import TransactionCase

HOSTID = '3130373031334717003D002E'
BASE_URL = 'http://relay.test/api/v1'          # домен .test ніколи не резолвиться
TOKEN = 'test-token-0123456789abcdefghij'
QUEUE_MAX = 5
MAX_LIMIT = 2000
V113_KEYS = ('water_temp_sensor_ohm', 'oil_pressure_sensor_ohm', 'fuel_level_sensor_ohm',
             'controller_sw', 'controller_hw')
ALLOWED_COMMANDS = ['auto', 'gen_close_open', 'mains_close_open', 'manual', 'start', 'stop', 'test']
COMMAND_FRAMES = {   # кадри Modbus RTU 05H (як fake_relay.command_frame)
    'start': '00050000FF008DEB', 'stop': '00050001FF00DC2B', 'test': '00050002FF002C2B',
    'auto': '00050003FF007DEB', 'manual': '00050004FF00CC2A', 'gen_close_open': '00050005FF009DEA',
    'mains_close_open': '00050006FF006DEA',
}
GENSET_STATUS_TEXT = {
    0: 'Standby', 1: 'Preheat', 2: 'Fuel Output', 3: 'Crank', 4: 'Crank Rest', 5: 'Safety Run',
    6: 'Start Idle', 7: 'High Speed Warming Up', 8: 'Wait for Load', 9: 'Normal Running',
    10: 'High Speed Cooling', 11: 'Stop Idle', 12: 'ETS', 13: 'Wait for Stop', 14: 'Stop Failure',
    15: 'After Stop',
}
REMOTE_START_TEXT = {0: 'No Delay', 1: 'Start Delay', 2: 'Stop Delay'}
MAINS_STATUS_TEXT = {0: 'Normal', 1: 'Abnormal', 2: 'No Delay'}
AT_SPEED = {5, 6, 7, 8, 9, 10, 11}
# Сигнали 01H: адреса → ключ (relay_api.md 5.2; адрес 5, 54, 55, 62, 63, 70, 71, 79 немає)
COIL_KEYS = {
    0: 'common_alarm', 1: 'common_warning', 2: 'common_shutdown', 3: 'remote_mode', 4: 'remote_lock',
    6: 'mains_on_load', 7: 'gen_on_load', 8: 'emergency_stop', 9: 'overspeed_shutdown',
    10: 'underspeed_shutdown', 11: 'speed_signal_loss_shutdown', 12: 'overfrequency_shutdown',
    13: 'underfrequency_shutdown', 14: 'overvoltage_shutdown', 15: 'undervoltage_shutdown',
    16: 'gen_overcurrent_shutdown', 17: 'crank_failure', 18: 'high_temp_shutdown',
    19: 'low_oil_pressure_shutdown', 20: 'frequency_loss_alarm', 21: 'input_shutdown',
    22: 'low_fuel_shutdown', 23: 'low_coolant_shutdown', 24: 'high_temp_warning',
    25: 'low_oil_pressure_warning', 26: 'gen_overcurrent_warning', 27: 'stop_failure_warning',
    28: 'low_fuel_warning', 29: 'charging_failure_warning', 30: 'battery_undervoltage_warning',
    31: 'battery_overvoltage_warning', 32: 'input_warning', 33: 'speed_signal_loss_warning',
    34: 'low_coolant_warning', 35: 'temp_sensor_open_warning', 36: 'oil_pressure_sensor_open_warning',
    37: 'maintenance_due_warning', 38: 'charger_fail_warning', 39: 'overpower_warning',
    40: 'test_mode', 41: 'auto_mode', 42: 'manual_mode', 43: 'stop_mode',
    44: 'temp_sensor_open_shutdown', 45: 'oil_pressure_sensor_open_shutdown',
    46: 'maintenance_due_shutdown', 47: 'overpower_shutdown', 48: 'emergency_stop_input',
    49: 'aux_input_1', 50: 'aux_input_2', 51: 'aux_input_3', 52: 'aux_input_4', 53: 'aux_input_5',
    56: 'crank_relay', 57: 'fuel_relay', 58: 'aux_output_1', 59: 'aux_output_2', 60: 'aux_output_3',
    61: 'aux_output_4', 64: 'mains_fault', 65: 'mains_normal', 66: 'mains_overvoltage',
    67: 'mains_undervoltage', 68: 'mains_loss_phase', 69: 'mains_blackout', 72: 'gen_normal',
    73: 'gen_overvoltage', 74: 'gen_undervoltage', 75: 'gen_overfrequency', 76: 'gen_underfrequency',
    77: 'gen_overcurrent', 78: 'scheduled_not_run',
}
NO_DATA_RAW = 32766          # «###» на контролері → null у values
MODE_FLAGS = {'test': 'test_mode', 'auto': 'auto_mode', 'manual': 'manual_mode', 'stop': 'stop_mode'}
ERROR_TEXTS = {
    400: 'unknown command, allowed: %r' % (ALLOWED_COMMANDS,),
    401: 'missing or wrong token',
    403: 'commands are disabled on the relay (RELAY_COMMANDS_ENABLED=0)',
    404: 'not found',
    405: 'method not allowed',
    409: 'modem is not connected right now',
    500: 'internal error',
}


def utc_text(ts):
    """Секунди Unix → ``'2026-10-07T15:57:22Z'`` (або None)."""
    return None if ts is None else time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ts))


def to_ts(value):
    """``float`` / naive UTC ``datetime`` / aware ``datetime`` → секунди Unix."""
    if value is None:
        return time.time()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    return float(value)


def snapshot(**values):
    """Повний ``values`` знімка (relay_api.md 5.1–5.2) — «Садова» 07.10: стоїть, Авто, мережа в нормі, бак 95 %.

    Ключ зі значенням ``None`` = ``null`` («немає даних»); щоб прибрати ключ — ``del`` у результаті.
    Узгодження (лише для ключів, яких немає в аргументах): ``controller_mode`` → прапорці
    ``*_mode``; ``mains_normal=False`` → ``mains_blackout``/``mains_fault``, напруги мережі 0,
    ``mains_on_load=False``; ``genset_status`` 5–11 → оберти/напруги/частота генератора, ``gen_normal``;
    ``*_text`` — за кодами. Псевдонім: ``fuel_sensor_ohm`` → ``fuel_level_sensor_ohm``.
    """
    if 'fuel_sensor_ohm' in values:
        values['fuel_level_sensor_ohm'] = values.pop('fuel_sensor_ohm')
    data = {
        'mains_ua': 239, 'mains_ub': 234, 'mains_uc': 240, 'mains_uab': 409, 'mains_ubc': 410, 'mains_uca': 418,
        'mains_freq': 50.0, 'gen_ua': 0, 'gen_ub': 0, 'gen_uc': 0, 'gen_uab': 0, 'gen_ubc': 0, 'gen_uca': 0,
        'gen_freq': 0.0, 'current_a': 0.0, 'current_b': 0.0, 'current_c': 0.0, 'water_temp': 35,
        'water_temp_sensor_ohm': 515.4, 'oil_pressure': 0, 'oil_pressure_sensor_ohm': 9.5, 'fuel_level': 95,
        'fuel_level_sensor_ohm': 189.2, 'speed': 0, 'battery_v': 27.8, 'dplus_v': 0.0, 'active_power': 0,
        'reactive_power': 0, 'apparent_power': 0, 'power_factor': 1.0, 'maint_h': 0, 'maint_min': 0,
        'genset_status': 0, 'genset_status_text': 'Standby', 'genset_status_delay': 0,
        'remote_start_status': 2, 'remote_start_status_text': 'Stop Delay', 'remote_start_delay': 0,
        'ats_status': 2, 'ats_status_delay': 0, 'mains_status': 2, 'mains_status_text': 'No Delay',
        'mains_status_delay': 0, 'run_hours': 34, 'run_minutes': 51, 'start_count': 39, 'energy_kwh': 253,
        'controller_sw': 4.3, 'controller_hw': 3.4, 'power_a': 0, 'power_b': 0, 'power_c': 0, 'load_pct': 0,
        'controller_mode': 'auto',
    }
    for key in COIL_KEYS.values():
        data[key] = False
    data.update(auto_mode=True, mains_on_load=True, mains_normal=True, gen_undervoltage=True,
                gen_underfrequency=True, aux_input_2=True, aux_output_4=True)

    def soft(key, value):
        if key not in values:
            data[key] = value

    mode = values.get('controller_mode', data['controller_mode'])
    if 'controller_mode' in values and mode is not None:
        for name, flag in MODE_FLAGS.items():
            soft(flag, name == mode)
    if values.get('mains_normal') is False:
        soft('mains_blackout', True)
        soft('mains_fault', True)
        soft('mains_on_load', False)
        soft('mains_status', 1)
        for key in ('mains_ua', 'mains_ub', 'mains_uc', 'mains_uab', 'mains_ubc', 'mains_uca'):
            soft(key, 0)
        soft('mains_freq', 0.0)
    status = values.get('genset_status')
    if isinstance(status, int) and status in AT_SPEED:
        soft('speed', 1500)
        soft('oil_pressure', 350)
        soft('gen_ua', 230)
        soft('gen_ub', 231)
        soft('gen_uc', 229)
        soft('gen_uab', 398)
        soft('gen_ubc', 400)
        soft('gen_uca', 399)
        soft('gen_freq', 50.0)
        soft('dplus_v', 28.0)
        soft('battery_v', 28.4)
        soft('gen_normal', True)
        soft('gen_undervoltage', False)
        soft('gen_underfrequency', False)
        soft('fuel_relay', True)
    elif status == 3:
        soft('speed', 250)
        soft('crank_relay', True)
        soft('fuel_relay', True)
        soft('battery_v', 24.0)
    data.update(values)
    if isinstance(data.get('genset_status'), int):
        soft('genset_status_text', GENSET_STATUS_TEXT.get(data['genset_status']))
    if isinstance(data.get('mains_status'), int):
        soft('mains_status_text', MAINS_STATUS_TEXT.get(data['mains_status']))
    if isinstance(data.get('remote_start_status'), int):
        soft('remote_start_status_text', REMOTE_START_TEXT.get(data['remote_start_status']))
    return data


def raw_image(values):
    """Сирий образ ``regs``/``coils`` (``raw=1``) — як у ``fake_relay.raw_image``: регістри 0–44, 46–55
    (значення в одиницях протоколу; оми — ×10 у регістрах 18/20/22) і сигнали 0–79."""
    def num(key, scale=1, signed=False):
        val = values.get(key)
        if val is None:
            return NO_DATA_RAW
        raw = int(round(float(val) * scale))
        return raw & 0xFFFF if signed else max(0, min(raw, 0xFFFF))

    def u32(key):
        val = values.get(key)
        val = 0 if val is None else int(val)
        return (val >> 16) & 0xFFFF, val & 0xFFFF

    regs = {}
    simple = {0: 'mains_ua', 1: 'mains_ub', 2: 'mains_uc', 3: 'mains_uab', 4: 'mains_ubc', 5: 'mains_uca',
              7: 'gen_ua', 8: 'gen_ub', 9: 'gen_uc', 10: 'gen_uab', 11: 'gen_ubc', 12: 'gen_uca',
              17: 'water_temp', 19: 'oil_pressure', 21: 'fuel_level', 23: 'speed', 30: 'maint_h',
              31: 'maint_min', 34: 'genset_status', 35: 'genset_status_delay', 36: 'remote_start_status',
              37: 'remote_start_delay', 38: 'ats_status', 39: 'ats_status_delay', 40: 'mains_status',
              41: 'mains_status_delay', 44: 'run_minutes', 55: 'load_pct'}
    for addr, key in simple.items():
        regs[addr] = num(key)
    for addr, key, scale in ((6, 'mains_freq', 100), (13, 'gen_freq', 100), (14, 'current_a', 10),
                             (15, 'current_b', 10), (16, 'current_c', 10), (18, 'water_temp_sensor_ohm', 10),
                             (20, 'oil_pressure_sensor_ohm', 10), (22, 'fuel_level_sensor_ohm', 10),
                             (24, 'battery_v', 10), (25, 'dplus_v', 10), (50, 'controller_sw', 10),
                             (51, 'controller_hw', 10)):
        regs[addr] = num(key, scale)
    for addr, key, scale in ((26, 'active_power', 1), (27, 'reactive_power', 1), (28, 'apparent_power', 1),
                             (29, 'power_factor', 100), (52, 'power_a', 1), (53, 'power_b', 1), (54, 'power_c', 1)):
        regs[addr] = num(key, scale, signed=True)
    regs[32] = regs[33] = 0
    regs[42], regs[43] = u32('run_hours')
    regs[46], regs[47] = u32('start_count')
    regs[48], regs[49] = u32('energy_kwh')
    reg_addrs = [addr for addr in range(56) if addr != 45]
    coils = {addr: int(bool(values.get(COIL_KEYS[addr]))) if addr in COIL_KEYS else 0 for addr in range(80)}
    return {str(addr): regs[addr] for addr in reg_addrs}, {str(addr): coils[addr] for addr in range(80)}


class RelayMock:
    """Мок API ретранслятора для unit-тестів (див. докстринг модуля).

    Стан: ``readings`` (знімки, як їх зберігає ретранслятор — з ``regs``/``coils``), ``commands``,
    ``values`` (поточний образ контролера), ``device``/``relay`` (поля ``/status``), ``calls`` (журнал
    запитів без заголовків: ``{'method', 'path', 'params', 'json', 'timeout', 'verify'}``).
    """

    def __init__(self, base_url=BASE_URL, token=TOKEN, hostid=HOSTID, version='1.1.3'):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.hostid = hostid
        self.version = version
        self.commands_enabled = True
        self.format_learned = True
        self.controller_executes = True
        self.crank_failure = False
        self.start_needs_manual = True
        self.command_flow = 'done'
        self.auto_effect_reading = True
        self.fail_with = None
        self.fail_path = None
        self.fail_method = None
        self.fail_times = None
        self.fail_error = None
        self.values = snapshot()
        self.readings = []
        self.commands = []
        self.calls = []
        self.started = time.time()
        self.device = {
            'hostid': hostid, 'online': True, 'seconds_since_seen': 7, 'long_connection': True,
            'modem_ip': '127.0.0.1', 'command_slave': 0, 'command_format': 'rtu',
            'cloud_commands_seen': [], 'registers_known': 55, 'coils_known': 80,
            'cloud_routes': {'livedata': '127.0.0.1:21318', 'historic': '127.0.0.1:21318'},
        }
        self.relay = {'snapshot_sec': 60, 'public': '127.0.0.1:21318', 'upstream': 'cloud.test:21318'}
        self.overrides = {}
        self._reading_id = 0
        self._command_id = 0
        self._need_first = True
        self._patcher = None

    # ------------------------------------------------------------------ керування патчем
    def start(self):
        mock = self

        def fake_request(session, method, url, *args, **kwargs):
            return mock.handle(method, url, *args, **kwargs)

        self._patcher = patch.object(requests.Session, 'request', fake_request)
        self._patcher.start()
        return self

    def stop(self):
        if self._patcher:
            self._patcher.stop()
            self._patcher = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # ------------------------------------------------------------------ сценарій
    def push(self, values=None, reason='interval', ts=None):
        """Додати знімок (стає поточним образом контролера). Повертає повний запис знімка."""
        if values is not None:
            self.values = dict(values)
        stamp = to_ts(ts)
        if self._need_first and reason == 'interval':
            reason = 'first'
        self._need_first = False
        self._reading_id += 1
        full = copy.deepcopy(self.values)
        regs, coils = raw_image(full)
        reading = {'id': self._reading_id, 'ts': stamp, 'time_utc': utc_text(stamp), 'hostid': self.hostid,
                   'reason': reason, 'values': full, 'regs': regs, 'coils': coils}
        self.readings.append(reading)
        return reading

    def set_status(self, **kw):
        """Змінити поля ``/status``: ключі ``version``, ``commands_enabled``, ``snapshot_sec``, ``uptime_s``,
        ``time_utc`` — у ``relay``; решта (``online``, ``seconds_since_seen``, ``long_connection``,
        ``commands_ready``, ``controller_mode``, ``cloud_commands_seen``, ``registers_known``,
        ``coils_known``, ``last_reading`` …) — у ``devices[0]`` (явне значення перекриває обчислене)."""
        for key, value in kw.items():
            if key == 'version':
                self.version = value
            elif key == 'commands_enabled':
                self.commands_enabled = value
            elif key == 'format_learned':
                self.format_learned = value
            elif key in ('snapshot_sec', 'uptime_s', 'time_utc', 'public', 'upstream'):
                self.relay[key] = value
            else:
                self.overrides[key] = value

    def fail(self, status, path=None, method=None, times=None, error=None):
        """Режим помилок: ``status`` — код або ``'timeout'``/``'connection'``; ``path`` — підрядок шляху."""
        self.fail_with, self.fail_path, self.fail_method = status, path, method
        self.fail_times, self.fail_error = times, error

    def relay_restart(self):
        """Перезапуск ретранслятора: ``queued``/``sent`` → ``failed`` «relay restarted»; наступний знімок ``first``."""
        now = time.time()
        for cmd in self.commands:
            if cmd['status'] in ('queued', 'sent'):
                self._finish(cmd, 'failed', now, error='relay restarted')
        self._need_first = True
        self.started = now

    def complete_command(self, cmd_id=None, status='done', error=None, ts=None):
        """Завершити команду (остання, якщо ``cmd_id`` не задано) статусом ``done``/``failed``/``timeout``."""
        cmd = self._command(cmd_id) if cmd_id else self.commands[-1]
        self._finish(cmd, status, to_ts(ts), error=error)
        return cmd

    def cloud_press(self, command, ts=None):
        """Натискання в застосунку SmartGen: запис у ``cloud_commands_seen`` + ефект на контролері."""
        stamp = to_ts(ts)
        seen = list(self.overrides.get('cloud_commands_seen', self.device['cloud_commands_seen']))
        seen.append({'time_utc': utc_text(stamp), 'frame': COMMAND_FRAMES.get(command), 'format': 'rtu',
                     'slave': 0, 'command': command})
        self.device['cloud_commands_seen'] = seen[-10:]
        self.overrides.pop('cloud_commands_seen', None)
        self._apply_command(command)
        return self.push(reason='change', ts=stamp + 1)

    # ------------------------------------------------------------------ формати відповідей
    def status_json(self):
        now = time.time()
        device = dict(self.device)
        device.update({
            'last_seen_utc': utc_text(now - (device.get('seconds_since_seen') or 0)),
            'last_data_utc': utc_text(now - (device.get('seconds_since_seen') or 0)),
            'controller_mode': self.values.get('controller_mode'),
            'command_format': 'rtu' if self.format_learned else None,
            'commands_ready': bool(self.commands_enabled and device.get('long_connection') and self.format_learned),
            'last_reading': None if not self.readings else {
                'id': self.readings[-1]['id'], 'time_utc': self.readings[-1]['time_utc']},
        })
        device.update(self.overrides)
        return {
            'relay': dict({'version': self.version, 'uptime_s': int(now - self.started), 'time_utc': utc_text(now),
                           'commands_enabled': self.commands_enabled}, **self.relay),
            'config': {'allowed_hostids': [self.hostid], 'hist_port': 21318, 'cmd_format_setting': 'auto',
                       'wire_log': False, 'wire_log_until_utc': None, 'raw_days': 14.0, 'readings_days': 180.0},
            'devices': [device],
            'counts': {'raw': 0, 'readings': len(self.readings), 'commands': len(self.commands)},
        }

    def reading_json(self, reading, raw=False):
        out = {key: copy.deepcopy(reading[key]) for key in ('id', 'ts', 'time_utc', 'hostid', 'reason', 'values')}
        if self.version == '1.1.1':
            for key in V113_KEYS:
                out['values'].pop(key, None)
        if raw:
            out['regs'], out['coils'] = dict(reading['regs']), dict(reading['coils'])
        return out

    @staticmethod
    def command_json(cmd):
        keys = ['id', 'created', 'created_utc', 'hostid', 'command', 'requested_by', 'source', 'status', 'frame',
                'uid', 'sent', 'sent_utc', 'done', 'done_utc', 'response', 'error']
        return {key: cmd[key] for key in keys}

    # ------------------------------------------------------------------ обробка запиту
    def handle(self, method, url, params=None, data=None, headers=None, cookies=None, files=None, auth=None,
               timeout=None, allow_redirects=True, proxies=None, hooks=None, stream=None, verify=None, cert=None,
               json=None):
        """Сигнатура = ``requests.Session.request``; у ``calls`` пишуться метод, шлях, параметри, тіло,
        ``timeout`` і ``verify`` (заголовки — ніколи, AC-57)."""
        method = (method or 'GET').upper()
        if not url.startswith(self.base_url):
            raise AssertionError('RelayMock: unexpected HTTP request outside the relay mock: %s %s' % (method, url))
        parts = urlsplit(url)
        path = parts.path[len(urlsplit(self.base_url).path):] or '/'
        query = {key: values[-1] for key, values in parse_qs(parts.query).items()}
        query.update({key: str(value) for key, value in (params or {}).items() if value is not None})
        body = json
        if body is None and data:
            try:
                body = jsonlib.loads(data)
            except (TypeError, ValueError):
                body = data
        self.calls.append({'method': method, 'path': path, 'params': dict(query), 'json': copy.deepcopy(body),
                           'timeout': timeout, 'verify': verify})
        failure = self._maybe_fail(method, path)
        if failure is not None:
            return failure
        auth = dict(headers or {}).get('Authorization')
        if auth != 'Bearer %s' % self.token:
            return self._error(401)
        try:
            return self._route(method, path, query, body)
        except _ApiError as exc:
            return self._response(exc.status, exc.payload)

    def _maybe_fail(self, method, path):
        if self.fail_with is None:
            return None
        if self.fail_path and self.fail_path not in path:
            return None
        if self.fail_method and self.fail_method.upper() != method:
            return None
        if self.fail_times is not None:
            if self.fail_times <= 0:
                return None
            self.fail_times -= 1
        if self.fail_with == 'timeout':
            raise requests.exceptions.ReadTimeout('Read timed out. (read timeout=20)')
        if self.fail_with == 'connection':
            raise requests.exceptions.ConnectionError('Connection refused')
        status = int(self.fail_with)
        if status in (502, 503, 504):
            return self._response(status, '<html><body><h1>%s Bad Gateway</h1></body></html>' % status,
                                  content_type='text/html')
        return self._error(status, self.fail_error)

    def _route(self, method, path, query, body):
        routes = {'/status': ('GET',), '/latest': ('GET',), '/readings': ('GET',), '/commands': ('GET', 'POST')}
        is_command = bool(re.fullmatch(r'/commands/[^/]+', path))
        allowed = ('GET',) if is_command else routes.get(path)
        if not allowed:
            raise _ApiError(404, 'not found')
        if method not in allowed:
            raise _ApiError(405, 'method not allowed')
        if path == '/status':
            return self._response(200, self.status_json())
        if path == '/latest':
            self._check_hostid(query.get('hostid'))
            if not self.readings:
                raise _ApiError(404, 'no readings yet')
            return self._response(200, self.reading_json(self.readings[-1], _flag(query.get('raw'))))
        if path == '/readings':
            since, limit = _qint(query, 'since', 0), min(_qint(query, 'limit', 500), MAX_LIMIT)
            self._check_hostid(query.get('hostid'))
            page = [reading for reading in self.readings if reading['id'] > since][:limit]
            raw = _flag(query.get('raw'))
            return self._response(200, {'readings': [self.reading_json(reading, raw) for reading in page],
                                        'next_since': page[-1]['id'] if page else since})
        if is_command:
            try:
                cmd = self._command(int(path.rsplit('/', 1)[1]))
            except ValueError:
                raise _ApiError(404, 'no such command') from None
            self._progress(cmd)
            return self._response(200, self.command_json(cmd))
        if method == 'GET':
            since, limit = _qint(query, 'since', 0), min(_qint(query, 'limit', 200), MAX_LIMIT)
            page = [cmd for cmd in self.commands if cmd['id'] > since][:limit]
            return self._response(200, {'commands': [self.command_json(cmd) for cmd in page]})
        return self._post_command(body)

    def _post_command(self, body):
        if not isinstance(body, dict):
            raise _ApiError(400, 'body must be JSON')
        command = body.get('command')
        if command not in COMMAND_FRAMES:
            raise _ApiError(400, ERROR_TEXTS[400])
        self._check_hostid(body.get('hostid'))
        if not self.commands_enabled:
            raise _ApiError(403, ERROR_TEXTS[403])
        device = self.status_json()['devices'][0]
        if not device.get('long_connection') or not device.get('online'):
            raise _ApiError(409, ERROR_TEXTS[409])
        if not self.format_learned:
            raise _ApiError(409, 'command format not learned yet: waiting for a command from the SmartGen cloud '
                                 '(or set RELAY_CMD_FORMAT)')
        waiting = [cmd for cmd in self.commands if cmd['status'] in ('queued', 'sent')]
        if len(waiting) >= QUEUE_MAX:
            raise _ApiError(409, '%d commands already waiting for this modem' % len(waiting))
        now = time.time()
        self._command_id += 1

        def text(key, size):
            value = body.get(key)
            return None if value is None else str(value)[:size]

        cmd = {'id': self._command_id, 'created': now, 'created_utc': utc_text(now), 'hostid': self.hostid,
               'command': command, 'requested_by': text('requested_by', 120), 'source': text('source', 60),
               'status': 'queued', 'frame': None, 'uid': None, 'sent': None, 'sent_utc': None, 'done': None,
               'done_utc': None, 'response': None, 'error': None}
        self.commands.append(cmd)
        return self._response(201, self.command_json(cmd))

    def _progress(self, cmd):
        """Перший GET /commands/<id> переводить ``queued`` за ``command_flow``."""
        if cmd['status'] != 'queued':
            return
        now = time.time()
        flow = self.command_flow
        if flow == 'queued':
            return
        cmd.update(status='sent', frame=COMMAND_FRAMES[cmd['command']], uid='action', sent=now, sent_utc=utc_text(now))
        if flow == 'sent':
            return
        if flow == 'failed':
            self._finish(cmd, 'failed', now, error='controller rejected the command')
        elif flow == 'timeout':
            self._finish(cmd, 'timeout', now, error='no reply in 30 s')
        else:
            self._finish(cmd, 'done', now)

    def _finish(self, cmd, status, now, error=None):
        if cmd['frame'] is None:
            cmd.update(frame=COMMAND_FRAMES[cmd['command']], uid='action', sent=now, sent_utc=utc_text(now))
        cmd.update(status=status, done=now, done_utc=utc_text(now), error=error)
        cmd['response'] = {'method': 'writeConfig', 'hostid': self.hostid, 'uid': 'action',
                           'params': '%s,%d' % (cmd['frame'], 0 if status == 'failed' and error and 'rejected' in error
                                                else 1)}
        if status == 'done' and self.controller_executes and not self.values.get('remote_lock'):
            self._apply_command(cmd['command'])
            if self.auto_effect_reading:
                self.push(reason='change', ts=now + 1)

    def _apply_command(self, command):
        """Спрощений ефект команди на образі контролера (режими, пуск/зупинка, автомати)."""
        values = dict(self.values)
        if command in MODE_FLAGS:
            for name, flag in MODE_FLAGS.items():
                values[flag] = name == command
            values['controller_mode'] = command
        running = values.get('genset_status') not in (0, 15, None)
        if command == 'start' and self.start_needs_manual and values.get('controller_mode') != 'manual':
            pass   # «Пуск» працює лише в режимі Ручний (relay_api.md 7.1): контролер прийняв запис, але не пускає
        elif command in ('start', 'test') and self.crank_failure:
            values.update(genset_status=0, genset_status_text='Standby', speed=0, crank_failure=True,
                          common_shutdown=True, common_alarm=True)
        elif command == 'start' or (command == 'test' and not running):
            values.update(_running_values(values, on_load=command == 'test'))
        elif command == 'stop' and running:
            values.update(_stopped_values(values))
        elif command == 'gen_close_open' and values.get('genset_status') in AT_SPEED:
            closing = not values.get('gen_on_load')
            values['gen_on_load'] = closing
            if closing:
                values['mains_on_load'] = False
        elif command == 'mains_close_open' and values.get('mains_normal'):
            closing = not values.get('mains_on_load')
            values['mains_on_load'] = closing
            if closing:
                values['gen_on_load'] = False
        self.values = values

    def _command(self, cmd_id):
        for cmd in self.commands:
            if cmd['id'] == cmd_id:
                return cmd
        raise _ApiError(404, 'no such command')

    def _check_hostid(self, hostid):
        if hostid and hostid != self.hostid:
            raise _ApiError(404, 'unknown hostid', known=[self.hostid])

    def _error(self, status, error=None):
        return self._response(status, {'error': error or ERROR_TEXTS.get(status, 'error')})

    @staticmethod
    def _response(status, payload, content_type='application/json'):
        response = requests.Response()
        response.status_code = status
        if isinstance(payload, (dict, list)):
            response._content = jsonlib.dumps(payload).encode('utf-8')
        else:
            response._content = str(payload).encode('utf-8')
        response.headers['Content-Type'] = content_type
        response.headers['Cache-Control'] = 'no-store'
        response.encoding = 'utf-8'
        response.reason = {200: 'OK', 201: 'Created'}.get(status, 'Error')
        return response


class _ApiError(Exception):
    def __init__(self, status, error, **extra):
        super().__init__(error)
        self.status = status
        self.payload = dict({'error': error}, **extra)


def _flag(value):
    return str(value).lower() in ('1', 'true', 'yes')


def _qint(query, name, default):
    value = query.get(name)
    if value in (None, ''):
        return default
    try:
        number = int(value)
    except ValueError:
        raise _ApiError(400, 'bad request: ValueError') from None
    if number < 0:
        raise _ApiError(400, 'bad request: ValueError')
    return number


def _running_values(values, on_load=False):
    data = snapshot(genset_status=9 if on_load else 8, controller_mode=values.get('controller_mode'))
    keep = {key: values[key] for key in ('mains_normal', 'mains_ua', 'mains_ub', 'mains_uc', 'mains_uab',
                                         'mains_ubc', 'mains_uca', 'mains_freq', 'fuel_level', 'fuel_level_sensor_ohm',
                                         'run_hours', 'run_minutes', 'start_count', 'energy_kwh', 'remote_lock',
                                         'test_mode', 'auto_mode', 'manual_mode', 'stop_mode', 'controller_mode')
            if key in values}
    running = {key: data[key] for key in ('genset_status', 'genset_status_text', 'speed', 'oil_pressure', 'gen_ua',
                                          'gen_ub', 'gen_uc', 'gen_uab', 'gen_ubc', 'gen_uca', 'gen_freq', 'dplus_v',
                                          'battery_v', 'gen_normal', 'gen_undervoltage', 'gen_underfrequency',
                                          'fuel_relay')}
    running.update(keep)
    running['start_count'] = (values.get('start_count') or 0) + 1
    if on_load:
        running.update(gen_on_load=True, mains_on_load=False, active_power=8, load_pct=30)
    return running


def _stopped_values(values):
    data = snapshot()
    stopped = {key: data[key] for key in ('genset_status', 'genset_status_text', 'speed', 'oil_pressure', 'gen_ua',
                                          'gen_ub', 'gen_uc', 'gen_uab', 'gen_ubc', 'gen_uca', 'gen_freq', 'dplus_v',
                                          'gen_normal', 'gen_undervoltage', 'gen_underfrequency', 'fuel_relay',
                                          'active_power', 'load_pct', 'current_a', 'current_b', 'current_c')}
    stopped.update(gen_on_load=False, mains_on_load=bool(values.get('mains_normal')))
    return stopped


class TdGensetCase(TransactionCase):
    """База unit-тестів ``td_genset`` (теги ``standard``, ``at_install`` — за замовчуванням ``TransactionCase``).

    ``setUpClass``: параметри ретранслятора (адреса/токен мока), конфіг, модель контролера HGM6120N,
    генератор «Стенд» (``relay_enabled``, ``commands_allowed``, hostid мока), користувачі ``user_s``
    (Співробітник, у ланцюжку 0 хв), ``user_a`` (Адміністратор, 10 хв), ``user_t`` (Тех. адміністратор, 30 хв),
    ``user_x`` (Співробітник поза ланцюжком). ``setUp``: свіжий ``RelayMock`` (``self.relay``).
    """

    relay_version = '1.1.3'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_param('td_genset.relay_url', BASE_URL)
        icp.set_param('td_genset.relay_token', TOKEN)
        icp.set_param('td_genset.http_timeout', '20')
        cls.config = cls.env.ref('td_genset.config_main')
        cls.controller_model = cls.env.ref('td_genset.controller_hgm6120n')
        cls.group_user = cls.env.ref('td_genset.group_user')
        cls.group_admin = cls.env.ref('td_genset.group_admin')
        cls.group_tech = cls.env.ref('td_genset.group_tech')
        users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.user_s = users.create(cls._user_vals('td_user_s', 'Співробітник Стенд', cls.group_user))
        cls.user_a = users.create(cls._user_vals('td_user_a', 'Адміністратор Стенд', cls.group_admin))
        cls.user_t = users.create(cls._user_vals('td_user_t', 'Тех. адміністратор Стенд', cls.group_tech))
        cls.user_x = users.create(cls._user_vals('td_user_x', 'Співробітник поза ланцюжком', cls.group_user))
        levels = cls.config.level_ids.sorted(lambda level: (level.sequence, level.id))
        for level, user in zip(levels, (cls.user_s, cls.user_a, cls.user_t)):
            level.user_id = user
        cls.genset = cls.env['td.genset'].create({
            'name': 'Стенд',
            'address': 'Тестовий стенд',
            'controller_model_id': cls.controller_model.id,
            'power_kw': 12.0,
            'tank_volume_l': 145.0,
            'relay_hostid': HOSTID,
            'relay_enabled': True,
            'commands_allowed': True,
            'user_id': cls.user_t.id,
        })

    @classmethod
    def _user_vals(cls, login, name, group):
        return {
            'name': name,
            'login': login,
            'email': '%s@example.com' % login,
            'tz': 'Europe/Kyiv',
            'groups_id': [(6, 0, [group.id])],
        }

    def setUp(self):
        super().setUp()
        self.relay = RelayMock(version=self.relay_version)
        self.relay.start()
        self.addCleanup(self.relay.stop)

    # ------------------------------------------------------------------ помічники А.11
    snapshot = staticmethod(snapshot)

    def push_reading(self, values, reason='interval', ts=None):
        """Додати знімок у мок (``values`` — зазвичай ``snapshot(...)``; ``None`` — поточний образ контролера)."""
        return self.relay.push(values, reason=reason, ts=ts)

    def set_status(self, **kw):
        """Змінити ``/status`` мока (див. ``RelayMock.set_status``)."""
        self.relay.set_status(**kw)

    def run_pull(self):
        """Один запуск cron «забір показань і стан»."""
        return self.env['td.genset']._cron_pull_readings()

    def run_commands(self):
        """Один запуск cron «команди»."""
        return self.env['td.genset.command']._cron_process_commands()

    def run_scheduler(self):
        """Один запуск cron «розклад, таймер, тест, ескалація»."""
        return self.env['td.genset']._cron_scheduler()
