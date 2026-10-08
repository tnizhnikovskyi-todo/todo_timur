# Part of td_genset (ToDo). Власник файлу: W5 «Стенд і документація».
"""Каркас стендових тестів ``TdGensetStandCase`` (AC-65; ТР А.13, «Інструкція» ТК-01…ТК-14; SPEC 15).

Тести тегуються ``@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')`` і без змінних оточення
``TD_GENSET_STAND_URL`` / ``TD_GENSET_STAND_TOKEN`` пропускаються (``SkipTest`` у ``setUpClass``); стенд — лише
локальний емулятор ``smartgen/tools/fake_relay.py`` (адреса не loopback → пропуск). Запуск —
``smartgen/tools/odoo/run_stand_tests.sh <база>``.

Два режими емулятора (``relay_mode``):

* ``'env'`` — емулятор, який підняв ``run_stand_tests.sh`` (адреса/токен/``/_sim`` — зі змінних оточення); перед
  кожним тестом ``POST /_sim {"reset": true, "snapshot_sec": 10, "noise": false, "version": …}``; годинник Odoo
  за потреби зсувається ``advance_odoo()`` (лише Odoo, емулятор — у реальному часі);
* ``'own'`` — власний екземпляр емулятора на вільному порту (``relay_harness.spawn_relay``; гаситься в
  ``tearDown``) з керованим годинником: ``advance(хв)`` зсуває вперед і годинник емулятора
  (``/_sim {"clock_advance": …}``), і час Odoo (``freezegun``, ``tick=True``) — сценарії з повторами, втратою
  зв'язку, догоном, розкладом; ``clock_start_utc()`` задає момент старту (наприклад, понеділок 08:44 Kyiv);
  ``relay_version`` — версія ретранслятора (1.1.1 — без ключів ``*_sensor_ohm``, AC-68).

Cron-методи викликаються напряму: ``pull()`` → ``td.genset._cron_pull_readings`` (до вичерпання сторінок),
``run_commands()`` → ``td.genset.command._cron_process_commands``, ``run_scheduler()`` →
``td.genset._cron_scheduler``. Налаштування стенду (ТР «Інструкція», передумови; BUILD_PLAN W5): повтор
непідтвердженої команди 1/3 хв, тест 3 хв, зв'язок 3/10 хв, пороги палива 10 L, бак 145 L.
"""
import logging
import os
import secrets
import unittest
from contextlib import contextmanager
from datetime import datetime, time as dtime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import freezegun
import pytz
import requests

from odoo import fields
from odoo.tools import SQL, html2plaintext

from ...models.td_logging import reset_log_state
from ..common import TdGensetCase
from .relay_harness import SimClient, StandError, StandTimeout, is_loopback_url, spawn_relay, wait_until

KYIV = pytz.timezone('Europe/Kyiv')
STAND_URL_ENV = 'TD_GENSET_STAND_URL'
STAND_TOKEN_ENV = 'TD_GENSET_STAND_TOKEN'
STAND_SIM_ENV = 'TD_GENSET_STAND_SIM'
SCHEDULE_REQUESTED_BY = 'Odoo: розклад'
OPEN_COMMAND_STATES = ('queued_odoo', 'to_send', 'sent', 'awaiting', 'retry', 'waiting_link')
STAND_CONFIG = {
    'retry_every_min': 1,
    'retry_window_min': 3,
    'test_minutes': 3,
    'missed_transition_policy': 'until_next',
    'late_retry_every_min': 5,
    'link_lost_min': 3,
    'link_alarm_min': 10,
    'relay_unavailable_alarm_min': 10,
    'raw_regs_mode': 'auto',
    'refuel_threshold_l': 10.0,
    'drain_threshold_l': 10.0,
    'drain_window_min': 60,
    'low_fuel_pct': 20,
    'catchup_summary': True,
    # Стенд без каністр: мінімальний запас 0 L, щоб «Запас у каністрах нижчий за мінімальний» (fuel_stock_low) не
    # змішувався з тривогами сценаріїв; так само ТО (мотогодини емулятора 34+ > «Перше ТО 30») — див. setUpClass.
    'fuel_min_stock_l': 0.0,
}


def utc_naive(value):
    """aware ``datetime`` → naive UTC (як ``fields.Datetime`` у базі)."""
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def kyiv_to_utc(day, hour, minute=0):
    """Київський час ``day hour:minute`` → naive UTC (без неоднозначних годин — для сценаріїв поза DST)."""
    return utc_naive(KYIV.localize(datetime.combine(day, dtime(hour, minute)), is_dst=None))


def tomorrow_kyiv(hour, minute=0):
    """Завтра о ``hour:minute`` Kyiv → naive UTC (денний час стенду поза тихими годинами і межами діб)."""
    today = datetime.now(timezone.utc).astimezone(KYIV).date()
    return kyiv_to_utc(today + timedelta(days=1), hour, minute)


def next_weekday_kyiv(weekday, hour, minute):
    """Найближчий (з завтрашнього дня) ``weekday`` (0 — понеділок) о ``hour:minute`` Kyiv → naive UTC."""
    today = datetime.now(timezone.utc).astimezone(KYIV).date()
    days = (weekday - today.weekday()) % 7 or 7
    return kyiv_to_utc(today + timedelta(days=days), hour, minute)


def float_time(dt_utc):
    """naive UTC → ``float_time`` (години) за київським часом — для рядків розкладу."""
    local = pytz.utc.localize(dt_utc).astimezone(KYIV)
    return local.hour + local.minute / 60.0


def kyiv_weekday(dt_utc):
    """naive UTC → день тижня за київським часом як ``dayofweek`` розкладу ('0' — понеділок)."""
    return str(pytz.utc.localize(dt_utc).astimezone(KYIV).weekday())


class TdGensetStandCase(TdGensetCase):
    """База стендових тестів (успадковує користувачів, ланцюжок і генератор «Стенд» з ``TdGensetCase``,
    але БЕЗ ``RelayMock``: усі запити модуля йдуть на емулятор)."""

    relay_mode = 'env'
    relay_version = '1.1.3'
    snapshot_sec = 10
    time_scale = 20

    # ------------------------------------------------------------------ клас
    @classmethod
    def setUpClass(cls):
        url = os.environ.get(STAND_URL_ENV)
        token = os.environ.get(STAND_TOKEN_ENV)
        if not url or not token:
            raise unittest.SkipTest('Стендові тести: не задано %s / %s (запуск — smartgen/tools/odoo/'
                                    'run_stand_tests.sh <база>)' % (STAND_URL_ENV, STAND_TOKEN_ENV))
        if not is_loopback_url(url):
            raise unittest.SkipTest('Стендові тести працюють лише з локальним емулятором (127.0.0.1), не з %s' % url)
        super().setUpClass()
        cls.stand_url = url.rstrip('/')
        cls.stand_token = token
        cls.stand_sim_url = os.environ.get(STAND_SIM_ENV) or (cls.stand_url + '/_sim')
        cls.config.write(STAND_CONFIG)
        cls.genset.write({'maint_first_hours': 1000})

    def clock_start_utc(self):
        """Момент старту годинника для ``relay_mode = 'own'`` (naive UTC) або ``None`` — «зараз»."""
        return None

    # ------------------------------------------------------------------ тест
    def setUp(self):
        # TransactionCase.setUp — без RelayMock з TdGensetCase.setUp: модуль ходить на емулятор.
        super(TdGensetCase, self).setUp()
        reset_log_state()
        self.relay_process = None
        self._freezer = None
        self._clock = None
        if self.relay_mode == 'own':
            self._setup_own_relay()
        else:
            self._setup_env_relay()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('td_genset.relay_url', self.relay.api_url)
        icp.set_param('td_genset.relay_token', self.relay.token)
        icp.set_param('td_genset.http_timeout', '5')
        self.relay.wait_first_reading()
        hostid = self.relay.device()['hostid']
        if self.genset.relay_hostid != hostid:
            self.genset.relay_hostid = hostid

    def _setup_env_relay(self):
        self.relay = SimClient(self.stand_url, self.stand_token, sim_url=self.stand_sim_url)
        if not self.relay.has_sim():
            self.skipTest('Стенд без службового /_sim (потрібен smartgen/tools/fake_relay.py)')
        self.relay.sim(reset=True, snapshot_sec=self.snapshot_sec, time_scale=self.time_scale, noise=False,
                       version=self.relay_version)

    def _setup_own_relay(self):
        start = self.clock_start_utc()
        real_now = datetime.now(timezone.utc).replace(tzinfo=None)
        offset = (start - real_now).total_seconds() if start else 0.0
        try:
            self.relay_process = spawn_relay('stand-own-%s' % secrets.token_hex(8), version=self.relay_version,
                                             snapshot_sec=self.snapshot_sec, time_scale=self.time_scale,
                                             clock_offset=offset)
        except FileNotFoundError as exc:
            self.skipTest('Немає емулятора %s (власний екземпляр для керованого годинника)' % exc)
        self.addCleanup(self.relay_process.stop)
        self.relay = self.relay_process.client
        self._start_clock(real_now + timedelta(seconds=offset))

    def _start_clock(self, start_utc):
        self._freezer = freezegun.freeze_time(start_utc, tick=True)
        self._clock = self._freezer.start()
        self.addCleanup(self._stop_clock)

    def _stop_clock(self):
        if self._freezer:
            self._freezer.stop()
            self._freezer = self._clock = None

    # ------------------------------------------------------------------ час
    def now(self):
        return fields.Datetime.now()

    def advance(self, minutes=0, seconds=0):
        """Зсунути вперед обидва годинники — емулятора і Odoo (лише ``relay_mode = 'own'``)."""
        delta = minutes * 60 + seconds
        assert self.relay_mode == 'own', 'advance(): керований годинник є лише у власного емулятора'
        self._shift_clock(delta)
        self.relay.advance(delta)

    def advance_odoo(self, minutes=0, seconds=0):
        """Зсунути вперед лише час Odoo (емулятор — у реальному часі): недоступність/401 без нових знімків."""
        if not self._clock:
            self._start_clock(datetime.now(timezone.utc).replace(tzinfo=None))
        self._shift_clock(minutes * 60 + seconds)

    def _shift_clock(self, seconds):
        # freezegun 1.2: у «тікаючої» фабрики немає tick() — зсуваємо точку відліку (працює для обох фабрик).
        self._clock.time_to_freeze += timedelta(seconds=seconds)

    def advance_to(self, target_utc):
        """``advance()`` до моменту ``target_utc`` (naive UTC), якщо він ще не настав."""
        delta = (target_utc - fields.Datetime.now()).total_seconds()
        if delta > 0:
            self.advance(seconds=int(delta) + 1)

    # ------------------------------------------------------------------ cron
    def pull(self, max_runs=12):
        """``_cron_pull_readings`` до вичерпання (курсор і кількість знімків не змінюються) → знімки генератора."""
        Reading = self.env['td.genset.reading']
        last = None
        for _ in range(max_runs):
            self.env['td.genset']._cron_pull_readings()
            self.env.invalidate_all()
            state = (self.genset.readings_cursor, Reading.search_count([('genset_id', '=', self.genset.id)]))
            if state == last:
                break
            last = state
        return self.odoo_readings()

    def run_commands(self):
        self.env['td.genset.command']._cron_process_commands()
        self.env.invalidate_all()

    def run_scheduler(self):
        self.env['td.genset']._cron_scheduler()
        self.env.invalidate_all()

    def link_on(self):
        return self.relay.device_state()['link']

    def snapshot(self):
        """Знімок «зараз» на емуляторі (лише коли модуль на зв'язку) → id останнього знімка."""
        if self.link_on():
            return self.relay.snapshot()
        return self.relay.last_reading_id()

    def tick(self, minutes=1, snapshot=True, pull=True, scheduler=False, commands=True):
        """Хвилина стенду: годинники +N хв, знімок, забір, планувальник, команди (``relay_mode = 'own'``)."""
        self.advance(minutes=minutes)
        if snapshot:
            self.snapshot()
        if pull:
            self.pull()
        if scheduler:
            self.run_scheduler()
        if commands:
            self.run_commands()

    def drive(self, commands, final_states, max_steps=8, scheduler=False):
        """Крутити стан-машину команд (крок cron → хвилина стенду), доки всі ``commands`` не в ``final_states``."""
        for _ in range(max_steps):
            self.run_commands()
            if all(cmd.state in final_states for cmd in commands):
                return commands
            for cmd in commands.filtered('relay_cmd_id'):
                self.relay.wait_command_final(cmd.relay_cmd_id, timeout=3, raise_on_timeout=False)
            self.tick(scheduler=scheduler, commands=False)
        self.run_commands()
        return commands

    # ------------------------------------------------------------------ дані Odoo
    def odoo_readings(self):
        return self.env['td.genset.reading'].search([('genset_id', '=', self.genset.id)], order='relay_id')

    def genset_commands(self, **domain):
        dom = [('genset_id', '=', self.genset.id)] + [(key, '=', value) for key, value in domain.items()]
        return self.env['td.genset.command'].search(dom, order='id')

    def alarms(self, code=None, active=True):
        domain = [('genset_id', '=', self.genset.id)]
        if code:
            domain.append(('code', '=', code))
        if active:
            domain.append(('state', '!=', 'cleared'))
        return self.env['td.genset.alarm'].search(domain, order='id')

    def events(self, event_type=None):
        domain = [('genset_id', '=', self.genset.id)]
        if event_type:
            domain.append(('event_type', '=', event_type))
        return self.env['td.genset.event'].search(domain, order='date_start, id')

    def chatter_texts(self, record=None):
        record = record or self.genset
        return [html2plaintext(body or '') for body in record.message_ids.mapped('body')]

    def assertChatterContains(self, text, record=None):
        texts = self.chatter_texts(record)
        self.assertTrue(any(text in body for body in texts),
                        'У чатері немає «%s»; є: %s' % (text, ' | '.join(texts[:10])))

    def column_is_null(self, record, column):
        """Значення колонки в базі — NULL («немає даних», SPEC 4), а не 0/False."""
        self.env.flush_all()
        self.env.cr.execute(SQL('SELECT %s IS NULL FROM %s WHERE id = %s',
                                SQL.identifier(column), SQL.identifier(record._table), record.id))
        return self.env.cr.fetchone()[0]

    # ------------------------------------------------------------------ дії користувачів
    def press(self, command, user=None, test_mode=None):
        """Кнопка пульта через майстер підтвердження (як у формі) → нові команди генератора."""
        before = self.genset_commands()
        vals = {'genset_id': self.genset.id, 'command': command}
        if test_mode:
            vals['test_mode'] = test_mode
        wizard = self.env['td.genset.command.wizard'].with_user(user or self.user_t).create(vals)
        wizard.action_confirm()
        self.env.invalidate_all()
        return self.genset_commands() - before

    def enqueue(self, command, source='schedule', requested_by=SCHEDULE_REQUESTED_BY, **kwargs):
        """Команда через єдину точку створення ``_enqueue`` (як планувальник) → запис команди."""
        cmd = self.env['td.genset.command']._enqueue(self.genset, command, source, requested_by, **kwargs)
        self.env.invalidate_all()
        return cmd

    def start_timer(self, hours, minutes, user=None):
        wizard = self.env['td.genset.timer.wizard'].with_user(user or self.user_s).create({
            'genset_id': self.genset.id, 'hours': hours, 'minutes': minutes})
        result = wizard.action_confirm()
        self.env.invalidate_all()
        return result

    # ------------------------------------------------------------------ підготовка стенду
    def prepare_mode(self, mode):
        """Режим контролера до підключення Odoo (оператор стенду, в обхід Odoo) і курсор знімків генератора —
        на останньому знімку (історія підготовки не потрапляє в Odoo як «керування не з Odoo»)."""
        if self.relay.values().get('controller_mode') != mode:
            cmd = self.relay.post_command(mode)
            self.relay.wait_command_final(cmd['id'])
            self.relay.wait_mode(mode)
        last_id = self.relay.snapshot()
        self.genset.sudo().write({'readings_cursor': last_id - 1})

    def wait_relay(self, predicate, message, timeout=6.0):
        return self.relay.wait_values(predicate, timeout, message)

    def relay_commands(self, source_prefix='odoo:'):
        """Команди на ретрансляторі, надіслані Odoo (``source`` з префіксом ``odoo:``)."""
        return [cmd for cmd in self.relay.commands() if (cmd.get('source') or '').startswith(source_prefix)]

    # ------------------------------------------------------------------ спостереження за HTTP і логами
    @contextmanager
    def spy_requests(self, fail=None):
        """Записувати запити модуля до ретранслятора (метод, шлях, параметри — без заголовків); ``fail(call, n)``
        → ``True`` — підмінити відповідь мережевою помилкою (``requests.ConnectionError``)."""
        calls = []
        original = requests.Session.request

        def request(session, method, url, *args, **kwargs):
            params = dict(kwargs.get('params') or (args[0] if args and isinstance(args[0], dict) else {}) or {})
            for key, values in parse_qs(urlsplit(url).query).items():
                params.setdefault(key, values[-1])
            call = {'method': (method or 'GET').upper(), 'path': urlsplit(url).path, 'params': params}
            calls.append(call)
            if fail and fail(call, calls):
                raise requests.exceptions.ConnectionError('stand: штучна мережева помилка')
            return original(session, method, url, *args, **kwargs)

        with patch.object(requests.Session, 'request', request):
            yield calls

    @staticmethod
    def readings_calls(calls):
        return [call for call in calls if call['method'] == 'GET' and call['path'].endswith('/readings')]

    @staticmethod
    def is_raw(call):
        return str(call['params'].get('raw', '')).lower() in ('1', 'true', 'yes')

    @contextmanager
    def capture_logs(self, *names):
        """Усі записи логерів модуля (DEBUG) і HTTP-бібліотек — для перевірки, що токена в логах немає (AC-57)."""
        names = names or ('odoo.addons.td_genset', 'urllib3', 'requests')
        records = []

        class Collector(logging.Handler):
            def emit(self, record):
                try:
                    records.append(record.getMessage())
                except Exception:  # noqa: BLE001 — неформатований запис теж перевіряємо як є
                    records.append(str(record.msg))

        handler = Collector(level=logging.DEBUG)
        loggers = [logging.getLogger(name) for name in names]
        levels = [lg.level for lg in loggers]
        for lg in loggers:
            lg.addHandler(handler)
            lg.setLevel(logging.DEBUG)
        try:
            yield records
        finally:
            for lg, level in zip(loggers, levels):
                lg.removeHandler(handler)
                lg.setLevel(level)


__all__ = [
    'KYIV', 'OPEN_COMMAND_STATES', 'SCHEDULE_REQUESTED_BY', 'STAND_CONFIG', 'StandError', 'StandTimeout',
    'TdGensetStandCase', 'float_time', 'kyiv_to_utc', 'kyiv_weekday', 'next_weekday_kyiv', 'tomorrow_kyiv',
    'utc_naive', 'wait_until',
]
