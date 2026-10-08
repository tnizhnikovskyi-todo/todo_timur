# Part of td_genset (ToDo). Власник файлу: W2 «Керування».
"""Стан-машина команд (ТР 2.6.3, А.5; SPEC 5.5, 5.14): AC-12…AC-27, AC-66, AC-67.

``TdGensetW2Case`` — база тестів W2 (її імпортують ``test_w2_scheduler`` і ``test_w2_timer_test``):

* ретранслятор — ``RelayMock`` (``tests/common.py``); поки клієнт W1 — заглушка без HTTP, його методи
  ``post_command/command/latest/status`` на час тесту ходять у ``RelayMock`` через ``requests`` за контрактом
  ``relay_client.py`` (коди → винятки ``Relay*``); щойно клієнт W1 сам ходить у HTTP — тести йдуть через нього;
* забір показань W1 імітує ``sync()``: останній знімок мока → ``td.genset.reading`` + поля стану генератора;
* ``_raise``/``_clear`` тривог і ``_notify_bus`` обгорнуті ``patch.object`` (виклики → ``self.raised``,
  ``self.cleared``, ``self.bus``), оригінали (заглушки або реалізація W1) теж викликаються;
* час — ``freezegun.freeze_time``.
"""
import html
import re
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import requests
from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models.genset_schedule import kyiv_localize
from ..models.relay_client import (RelayAuthError, RelayBadRequest, RelayBusy, RelayCommandsDisabled,
                                   RelayNotFound, RelayUnavailable)
from .common import TdGensetCase, snapshot


def kyiv(year, month, day, hour=0, minute=0):
    """Київський час → UTC naive (як у базі)."""
    return kyiv_localize(date(year, month, day), hour + minute / 60.0)


def _relay_request(client, method, path, params=None, json=None):
    """Контракт ``td.genset.relay.client._request`` (ТР 2.6.1, А.11) поверх ``requests`` — для тестів, поки
    клієнт W1 — заглушка. ``RelayMock`` патчить ``requests.Session.request``."""
    try:
        response = requests.Session().request(method, client._base_url() + path, params=params, json=json,
                                              headers=client._headers(), timeout=(5, client._timeout()), verify=True)
    except requests.exceptions.RequestException as exc:
        raise RelayUnavailable(None, exc.__class__.__name__, method, path) from None
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get('error', '') if isinstance(body, dict) else ''
    status = response.status_code
    if status in (200, 201):
        return body
    if status == 401:
        raise RelayAuthError(status, error, method, path)
    if status == 403:
        raise RelayCommandsDisabled(status, error, method, path)
    if status == 409:
        raise RelayBusy(status, error, method, path)
    if status == 404:
        if error == 'no readings yet':
            return None
        raise RelayNotFound(status, error, method, path)
    if status == 400:
        raise RelayBadRequest(status, error, method, path)
    raise RelayUnavailable(status, error, method, path)


class TdGensetW2Case(TdGensetCase):
    """База тестів W2 «Керування» (див. докстринг модуля)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Command = cls.env['td.genset.command']
        cls.config.write({'retry_every_min': 2, 'retry_window_min': 10, 'test_minutes': 3,
                          'missed_transition_policy': 'until_next', 'late_retry_every_min': 5})

    def setUp(self):
        super().setUp()
        self._install_client_shim()
        self._patch_alarms()
        self._patch_bus()
        self.set_genset(link_state='online', relay_commands_enabled=True, relay_commands_ready=True,
                        remote_lock=False, controller_mode='auto', genset_status='0', is_running=False,
                        mains_ok=True, mains_on_load=True, gen_on_load=False, speed=0.0, control_source='schedule',
                        sched_in_window=False, sched_last_eval_at=False, timer_end=False, test_end=False)

    # ------------------------------------------------------------------ оточення
    def _install_client_shim(self):
        client = self.env['td.genset.relay.client']
        before = len(self.relay.calls)
        try:
            client._request('GET', '/status')
        except Exception:  # noqa: BLE001 — реалізація W1 могла відповісти винятком; важливо, чи був HTTP
            pass
        if len(self.relay.calls) > before:
            del self.relay.calls[before:]
            return
        client_cls = type(client)
        shims = {
            '_request': _relay_request,
            'status': lambda model: _relay_request(model, 'GET', '/status'),
            'latest': lambda model, hostid: _relay_request(model, 'GET', '/latest', params={'hostid': hostid}),
            'post_command': lambda model, hostid, command, requested_by, source: _relay_request(
                model, 'POST', '/commands', json={'command': command, 'hostid': hostid,
                                                  'requested_by': (requested_by or '')[:120],
                                                  'source': (source or '')[:60]}),
            'command': lambda model, relay_cmd_id: _relay_request(model, 'GET', '/commands/%s' % relay_cmd_id),
        }
        for name, func in shims.items():
            patcher = patch.object(client_cls, name, func)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _patch_alarms(self):
        alarm_cls = type(self.env['td.genset.alarm'])
        original_raise, original_clear = alarm_cls._raise, alarm_cls._clear
        self.raised, self.cleared = [], []

        def fake_raise(model, genset, code, level, name, description='', source=None, tech=False):
            self.raised.append({'genset': genset, 'code': code, 'level': level, 'name': name,
                                'description': description, 'source': source, 'tech': tech})
            return original_raise(model, genset, code, level, name, description=description, source=source, tech=tech)

        def fake_clear(model, genset, code, note=''):
            self.cleared.append({'genset': genset, 'code': code, 'note': note})
            return original_clear(model, genset, code, note=note)

        for name, func in (('_raise', fake_raise), ('_clear', fake_clear)):
            patcher = patch.object(alarm_cls, name, func)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _patch_bus(self):
        genset_cls = type(self.env['td.genset'])
        original = genset_cls._notify_bus
        self.bus = []

        def fake_notify(records, kind, payload=None):
            self.bus.append((kind, dict(payload or {})))
            return original(records, kind, payload)

        patcher = patch.object(genset_cls, '_notify_bus', fake_notify)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ------------------------------------------------------------------ помічники
    def set_genset(self, **vals):
        self.genset.sudo().write(vals)

    def sync(self, store=True):
        """Як забір W1: нові знімки мока → ``td.genset.reading`` (якщо ``store``), стан генератора — з останнього."""
        Reading = self.env['td.genset.reading']
        record = Reading.browse()
        for reading in self.relay.readings if store else []:
            record = Reading.search([('genset_id', '=', self.genset.id), ('relay_id', '=', reading['id'])], limit=1)
            if not record:
                record = Reading.create(dict(self._reading_vals(reading['values']), genset_id=self.genset.id,
                                             relay_id=reading['id'], reason=reading['reason'],
                                             ts=datetime.fromtimestamp(reading['ts'], tz=timezone.utc).replace(
                                                 tzinfo=None, microsecond=0)))
        values = self.relay.readings[-1]['values'] if self.relay.readings else self.relay.values
        vals = self._reading_vals(values)
        status = values.get('genset_status')
        vals = {
            'controller_mode': vals['controller_mode'],
            'genset_status': vals['genset_status'],
            'is_running': (isinstance(status, int) and status not in (0, 15)) or vals['speed'] > 0,
            'speed': vals['speed'],
            'gen_on_load': vals['gen_on_load'],
            'mains_on_load': vals['mains_on_load'],
            'remote_lock': vals['remote_lock'],
            'mains_ok': vals['mains_normal'],
        }
        if record:
            vals['last_reading_id'] = record.id
        self.set_genset(**vals)
        return self.relay.readings[-1] if self.relay.readings else None

    @staticmethod
    def _reading_vals(values):
        status = values.get('genset_status')
        return {
            'controller_mode': values.get('controller_mode') or 'unknown',
            'genset_status': str(status) if isinstance(status, int) else False,
            'speed': values.get('speed') or 0,
            'gen_on_load': bool(values.get('gen_on_load')),
            'mains_on_load': bool(values.get('mains_on_load')),
            'remote_lock': bool(values.get('remote_lock')),
            'mains_normal': bool(values.get('mains_normal')),
            'crank_failure': bool(values.get('crank_failure')),
        }

    def push_state(self, ts=None, store=True, **values):
        """Знімок контролера (``snapshot(**values)``) у мок + ``sync()``."""
        reading = self.relay.push(snapshot(**values), reason='change', ts=ts)
        self.sync(store=store)
        return reading

    def commands(self, **domain):
        return self.Command.search([('genset_id', '=', self.genset.id)]
                                   + [(key, '=', value) for key, value in domain.items()], order='id')

    def posts(self, command=None):
        """``POST /commands`` у журналі мока."""
        return [call for call in self.relay.calls if call['method'] == 'POST' and call['path'] == '/commands'
                and (command is None or call['json'].get('command') == command)]

    def chatter(self):
        return self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id)])

    def chatter_text(self):
        """Тексти повідомлень чатера генератора без HTML-розмітки і сутностей."""
        return '\n'.join(html.unescape(re.sub(r'<[^>]+>', ' ', str(message.body or '')))
                         for message in self.chatter())

    def raised_codes(self):
        return [alarm['code'] for alarm in self.raised]

    def confirm_wizard(self, command, user=None, **vals):
        wizard = self.env['td.genset.command.wizard'].with_user(user or self.user_t).create(
            dict({'genset_id': self.genset.id, 'command': command}, **vals))
        return wizard, wizard.action_confirm()


@tagged('standard', 'at_install')
class TestW2Commands(TdGensetW2Case):

    def test_ac12_button_command_confirmed_by_snapshot(self):
        """AC-12: «Авто» з пульта → журнал (хто, «Кнопка», «Надіслано», id ретранслятора, requested_by, source
        ``odoo:button``) → знімок з ``controller_mode=auto`` і ``ts ≥ done_utc`` → «Підтверджено», чатер, bus."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            wizard, action = self.confirm_wizard('auto')
            self.assertIn('Перевести в режим Авто?', wizard.warning_text)
            self.assertIn('Генератор запуститься сам, якщо зникне мережа.', wizard.warning_text)
            self.assertEqual(action['tag'], 'display_notification')
            command = self.commands()
            self.assertEqual(len(command), 1)
            self.assertEqual((command.command, command.source, command.user_id, command.state),
                             ('auto', 'button', self.user_t, 'to_send'))
            self.assertEqual(command.requested_by, '%s (res.users %s)' % (self.user_t.name, self.user_t.id))
            self.assertEqual(self.genset.control_source, 'manual')
            self.assertTrue(self.env['ir.cron.trigger'].search_count(
                [('cron_id', '=', self.env.ref('td_genset.cron_commands').id)]))
            self.run_commands()
            self.assertEqual(command.state, 'sent')
            self.assertEqual(command.result_note, 'Надіслано')
            self.assertEqual(command.relay_cmd_id, self.relay.commands[-1]['id'])
            self.assertEqual(command.first_sent_at, start)
            self.assertEqual(command.deadline_at, start + timedelta(minutes=10))
            post = self.posts()[-1]['json']
            self.assertEqual((post['command'], post['source'], post['requested_by']),
                             ('auto', 'odoo:button', command.requested_by))
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'done')
            self.assertEqual(command.done_at, start + timedelta(minutes=1))
            self.assertEqual(command.confirmed_at, start + timedelta(minutes=1))
            self.assertIn('Команда Авто. Підтверджено контролером', self.chatter_text())
            states = [payload.get('state') for kind, payload in self.bus if kind == 'command']
            self.assertEqual(states[-1], 'done')
            self.assertIn('sent', states)

    def test_ac12_confirmation_needs_snapshot_after_done(self):
        """AC-12 / ФВ-9: знімок до ``done_utc`` не підтверджує; ``unknown`` не підтверджує; збережений знімок
        після ``done`` — ``confirm_reading_id``."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            command = self.Command._enqueue(self.genset, 'auto', 'button', self.user_t)
            self.relay.auto_effect_reading = False
            self.run_commands()
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'awaiting')
            self.assertFalse(command._check_confirmation(self.genset.last_reading_id))
            self.push_state(ts=start + timedelta(minutes=1, seconds=20), controller_mode=None)
            self.assertFalse(command._check_confirmation(self.genset.last_reading_id))
            frozen.move_to(start + timedelta(minutes=1, seconds=40))
            self.push_state(ts=start + timedelta(minutes=1, seconds=40), controller_mode='auto')
            self.run_commands()
            self.assertEqual(command.state, 'done')
            self.assertEqual(command.confirm_reading_id, self.genset.last_reading_id)

    def test_ac13_not_needed_when_mode_already_target(self):
        """AC-13: ``controller_mode=auto`` → ``auto`` з пульта чи розкладу не надсилається, «Не потрібно: уже Авто»."""
        with freeze_time(datetime(2026, 10, 7, 11, 0)):
            self.push_state(controller_mode='auto')
            self.confirm_wizard('auto')
            schedule = self.Command._enqueue(self.genset, 'auto', 'schedule', 'Odoo: розклад')
            self.run_commands()
            for command in self.commands():
                self.assertEqual(command.state, 'not_needed')
                self.assertEqual(command.result_note, 'Не потрібно: уже Авто')
            self.assertEqual(schedule.user_id, self.env.ref('base.user_root'))
            self.assertFalse(self.posts())
            self.assertIn('Не потрібно: уже Авто', self.chatter_text())

    def _run_minutes(self, frozen, start, minutes, command, quick_done=True):
        """Крок cron щохвилини; знімок ``interval`` щохвилини (``snapshot_sec = 60``); ``quick_done`` — ретранслятор
        виконує POST за 3 с (як справжній, ~3 с)."""
        post_minutes = []
        for minute in range(minutes + 1):
            now = start + timedelta(minutes=minute)
            frozen.move_to(now)
            self.relay.push(None, reason='interval', ts=now)
            before = len(self.relay.commands)
            self.run_commands()
            if len(self.relay.commands) > before:
                post_minutes.append(minute)
                if quick_done:
                    self.relay.complete_command(status='done', ts=now + timedelta(seconds=3))
            if command.state in ('failed', 'done', 'done_late'):
                break
        return post_minutes

    def test_ac14_confirmation_retries_then_alarm(self):
        """AC-14: контролер не виконує → POST на 0/2/4/6/8 хв, «Спроба N з 5 · без підтвердження», на 10-й хв —
        «Не підтверджено — тривога», тривога критична з текстом 2.8.4 (Кнопка, HH:MM, спроб 5)."""
        start = datetime(2026, 10, 7, 11, 0)   # 14:00 за Києвом
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto')
            self.relay.controller_executes = False
            command = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            notes = []
            original_set_state = type(command)._set_state

            def spy(record, state, note=None, chatter=None, **vals):
                original_set_state(record, state, note=note, chatter=chatter, **vals)
                notes.append(record.result_note)

            with patch.object(type(command), '_set_state', spy):
                post_minutes = self._run_minutes(frozen, start, 12, command)
            self.assertEqual(post_minutes, [0, 2, 4, 6, 8])
            self.assertEqual(command.state, 'failed')
            self.assertEqual(frozen.time_to_freeze, start + timedelta(minutes=10))
            for attempt in range(1, 6):
                self.assertIn('Спроба %s з 5 · без підтвердження' % attempt, notes)
            self.assertEqual(command.max_attempts, 5)
            self.assertEqual(self.raised_codes(), ['cmd_unconfirmed'])
            alarm = self.raised[0]
            self.assertEqual(alarm['level'], 'crit')
            self.assertFalse(alarm['tech'])
            self.assertEqual(alarm['name'], 'Команда «Ручний» не підтверджена за 10 хв')
            self.assertEqual(alarm['description'],
                             "Кнопка, 14:00. Спроб: 5, режим контролера не змінився. Перевірте на об'єкті: режим "
                             "панелі, блокування, зв'язок модуля з контролером.")
            self.assertEqual(alarm['source'], command)
            self.assertIn('Команда «Ручний» не виконана за 10 хв (спроб: 5). Створено тривогу.', self.chatter_text())
            frozen.move_to(start + timedelta(minutes=20))
            self.run_commands()
            self.assertEqual(len(self.posts()), 5)

    def test_ac15_transport_retry_on_409(self):
        """AC-15: 409 «modem is not connected» → «Повтор: модуль не на зв'язку (спроба 1)», через 1 хв — POST 201,
        далі звичайний хід (Підтверджено, не «після відновлення»)."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto')
            self.relay.fail(409, path='/commands', method='POST', times=1)
            command = self.Command._enqueue(self.genset, 'manual', 'timer', self.user_s)
            self.run_commands()
            self.assertEqual(command.state, 'retry')
            self.assertEqual(command.result_note, "Повтор: модуль не на зв'язку (спроба 1)")
            self.assertEqual(command.first_sent_at, start)
            self.assertEqual(command.next_attempt_at, start + timedelta(minutes=1))
            frozen.move_to(start + timedelta(seconds=20))
            self.run_commands()
            self.assertEqual(len(self.posts()), 1)
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'sent')
            self.assertEqual(self.posts()[-1]['json']['source'], 'odoo:retry')
            frozen.move_to(start + timedelta(minutes=2))
            self.run_commands()
            self.assertEqual(command.state, 'done')
            self.assertFalse(self.raised)

    def test_ac15_transport_failure_whole_window_alarm(self):
        """AC-15: 409/5xx триває все вікно → тривога як в AC-14 з причиною «модуль не на зв'язку»."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto')
            self.relay.fail(409, path='/commands', method='POST')
            command = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            self._run_minutes(frozen, start, 12, command)
            self.assertEqual(command.state, 'failed')
            self.assertEqual(len(self.posts()), 10)
            alarm = self.raised[-1]
            self.assertEqual(alarm['name'], "Команда «Ручний» не підтверджена за 10 хв (модуль не на зв'язку)")
            self.assertIn("режим контролера не змінився, модуль не на зв'язку.", alarm['description'])
            # 5xx — так само транспортний повтор
            self.relay.fail(503, path='/commands', method='POST', times=1)
            other = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            self.run_commands()
            self.assertEqual(other.result_note, 'Повтор: ретранслятор недоступний (спроба 1)')

    def test_ac16_commands_disabled_on_relay(self):
        """AC-16: 403 → «Керування вимкнено на ретрансляторі» без повторів, тривога тех. адміністратору;
        ``relay_commands_enabled=False`` — без POST."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto')
            self.relay.commands_enabled = False
            command = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            self.run_commands()
            self.assertEqual(command.state, 'disabled_relay')
            self.assertEqual(command.result_note, 'Керування вимкнено на ретрансляторі')
            self.assertEqual(self.raised[-1]['code'], 'relay_cmd_disabled')
            self.assertTrue(self.raised[-1]['tech'])
            self.assertEqual(self.raised[-1]['name'], 'Команди вимкнено на ретрансляторі (RELAY_COMMANDS_ENABLED=0).')
            frozen.move_to(start + timedelta(minutes=5))
            self.run_commands()
            self.assertEqual(len(self.posts()), 1)
            self.set_genset(relay_commands_enabled=False)
            second = self.Command._enqueue(self.genset, 'manual', 'schedule', 'Odoo: розклад')
            self.run_commands()
            self.assertEqual(second.state, 'disabled_relay')
            self.assertEqual(len(self.posts()), 1)

    def test_ac16_auth_error_and_bad_request(self):
        """401 → «Помилка доступу» + тривога ``relay_auth``; 400 → ``failed`` + тривога тех. (2.6.3)."""
        with freeze_time(datetime(2026, 10, 7, 11, 0)):
            self.push_state(controller_mode='auto')
            self.relay.fail(401, path='/commands', method='POST', times=1)
            command = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            self.run_commands()
            self.assertEqual(command.state, 'auth_error')
            self.assertEqual(self.raised[-1]['code'], 'relay_auth')
            self.assertTrue(self.raised[-1]['tech'])
            self.relay.fail(400, path='/commands', method='POST', times=1)
            bad = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            self.run_commands()
            self.assertEqual(bad.state, 'failed')
            self.assertTrue(bad.result_note.startswith('Не виконано: ретранслятор не прийняв команду (400'))
            self.assertEqual(self.raised[-1]['code'], 'relay_cmd_rejected')
            self.assertTrue(self.raised[-1]['tech'])

    def test_ac17_relay_restarted_retry_new_id(self):
        """AC-17: ретранслятор перезапущено між ``sent`` і ``done`` → ``failed`` «relay restarted» → повтор у межах
        вікна з новим id, причина «ретранслятор перезапущено»."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto')
            self.relay.command_flow = 'queued'
            command = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            self.run_commands()
            first_id = command.relay_cmd_id
            self.relay.relay_restart()
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'retry')
            self.assertEqual(command.relay_error, 'relay restarted')
            self.assertEqual(command.result_note, 'Спроба 1 з 5 · ретранслятор перезапущено')
            self.relay.command_flow = 'done'
            frozen.move_to(start + timedelta(minutes=3))
            self.run_commands()
            self.assertEqual(command.state, 'sent')
            self.assertNotEqual(command.relay_cmd_id, first_id)
            self.assertEqual(len(self.posts()), 2)
            frozen.move_to(start + timedelta(minutes=4))
            self.run_commands()
            self.assertEqual(command.state, 'done')
            self.assertIn('зі спроби 2', command.result_note)

    def test_ac17_sent_without_final_status_is_timeout(self):
        """А.5: ``sent`` довше 2 хв без фінального статусу ретранслятора — як ``timeout`` (повтор)."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto')
            self.relay.command_flow = 'queued'
            command = self.Command._enqueue(self.genset, 'manual', 'button', self.user_t)
            self.run_commands()
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'sent')
            frozen.move_to(start + timedelta(minutes=2))
            self.run_commands()
            self.assertEqual(command.state, 'retry')
            self.assertEqual(command.relay_status, 'timeout')
            self.assertEqual(command.attempt, 1)

    def test_ac18_link_lost_before_confirmation(self):
        """AC-18: ``done``, далі немає зв'язку → «Очікує: немає зв'язку» без тривоги; після відновлення перший
        знімок з цільовим режимом → «Підтверджено після відновлення зв'язку»."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.relay.controller_executes = False
            command = self.Command._enqueue(self.genset, 'auto', 'button', self.user_t)
            self.run_commands()
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'awaiting')
            self.set_genset(link_state='offline')
            frozen.move_to(start + timedelta(minutes=2))
            self.run_commands()
            self.assertEqual(command.state, 'waiting_link')
            self.assertEqual(command.result_note, "Очікує: немає зв'язку")
            self.assertTrue(command.link_lost_during)
            deadline = command.deadline_at
            for minute in range(3, 27):
                frozen.move_to(start + timedelta(minutes=minute))
                self.run_commands()
            self.assertEqual(command.state, 'waiting_link')
            self.assertFalse(self.raised)
            self.assertEqual(len(self.posts()), 1)
            # зв'язок відновлено: перший знімок — Авто (змінили на об'єкті, поки не було зв'язку)
            frozen.move_to(start + timedelta(minutes=27))
            self.set_genset(link_state='online')
            self.push_state(ts=start + timedelta(minutes=27), controller_mode='auto')
            self.run_commands()
            self.assertEqual(command.state, 'done_late')
            self.assertEqual(command.result_note, "Підтверджено після відновлення зв'язку")
            self.assertGreaterEqual(command.deadline_at, deadline + timedelta(minutes=25))
            self.assertIn("Підтверджено після відновлення зв'язку", self.chatter_text())

    def test_ac18_link_restored_not_confirmed_retries_new_window(self):
        """AC-18: після відновлення перший знімок не цільовий → повтори з новим вікном."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.relay.controller_executes = False
            command = self.Command._enqueue(self.genset, 'auto', 'button', self.user_t)
            self.run_commands()
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.set_genset(link_state='offline')
            frozen.move_to(start + timedelta(minutes=2))
            self.run_commands()
            self.assertEqual(command.state, 'waiting_link')
            frozen.move_to(start + timedelta(minutes=30))
            self.set_genset(link_state='online')
            self.push_state(ts=start + timedelta(minutes=30), controller_mode='manual')
            self.run_commands()
            self.assertEqual(command.state, 'sent')
            self.assertEqual(len(self.posts()), 2)
            self.assertGreaterEqual(command.deadline_at, start + timedelta(minutes=40))
            self.assertFalse(self.raised)

    def test_ac19_manual_stop_batch(self):
        """AC-19: «Ручний + Стоп» — два POST в одному кроці (manual, потім stop), один ключ пакета;
        manual — за ``controller_mode``, stop — за зупинкою/охолодженням і ``gen_on_load=false``."""
        start = datetime(2026, 10, 7, 15, 30)   # 18:30 за Києвом
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto', genset_status=9,
                            mains_normal=False, gen_on_load=True)
            self.assertTrue(self.genset.is_running)
            batch = self.Command._enqueue_batch(self.genset, ['manual', 'stop'], 'schedule', 'Odoo: розклад')
            self.assertEqual(batch.mapped('command'), ['manual', 'stop'])
            self.assertEqual(batch.mapped('sequence'), [1, 2])
            self.assertEqual(len(set(batch.mapped('batch_key'))), 1)
            self.assertTrue(batch[0].batch_key.startswith('%s-' % self.genset.id))
            self.run_commands()
            self.assertEqual([call['json']['command'] for call in self.posts()], ['manual', 'stop'])
            self.assertEqual(batch.mapped('state'), ['sent', 'sent'])
            self.assertEqual([call['json']['requested_by'] for call in self.posts()], ['Odoo: розклад'] * 2)
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(batch.mapped('state'), ['done', 'done'])
            self.assertIn('Розклад: Ручний. Підтверджено контролером.', self.chatter_text())
            self.assertIn('Розклад: Стоп. Підтверджено контролером.', self.chatter_text())
        stop = batch[1]
        stop.done_at = start
        cooling = {'ts': start + timedelta(seconds=5), 'controller_mode': 'manual', 'genset_status': 10, 'speed': 1500,
                   'gen_on_load': False, 'mains_on_load': False, 'crank_failure': False, 'relay_id': 1, 'record': None}
        self.assertTrue(stop._check_confirmation(cooling))
        self.assertFalse(stop._check_confirmation(dict(cooling, gen_on_load=True)))
        self.assertFalse(stop._check_confirmation(dict(cooling, genset_status=9)))
        self.assertFalse(stop._check_confirmation(dict(cooling, ts=start - timedelta(seconds=1))))

    def test_ac19_batch_goal_is_stop_mode(self):
        """AC-19 (рішення 07.10): мета пакета «Ручний + Стоп» — режим Stop. Контролер уже в Stop → обидві команди
        «Не потрібно: уже Стоп»; Ручний і генератор стоїть → надсилаються обидві, ``manual`` підтверджує знімок
        з режимом ``manual`` або ``stop``, ``stop`` — перший знімок зі станом 0/15."""
        start = datetime(2026, 10, 7, 15, 30)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='stop')
            batch = self.Command._enqueue_batch(self.genset, ['manual', 'stop'], 'schedule', 'Odoo: розклад')
            self.run_commands()
            self.assertEqual(batch.mapped('state'), ['not_needed', 'not_needed'])
            self.assertEqual(set(batch.mapped('result_note')), {'Не потрібно: уже Стоп'})
            self.assertFalse(self.posts())
            self.assertTrue(batch[0]._is_manual_stop_batch())
            self.push_state(ts=start, controller_mode='manual')
            self.assertFalse(self.genset.is_running)
            batch = self.Command._enqueue_batch(self.genset, ['manual', 'stop'], 'timer', 'Odoo: таймер')
            self.relay.command_flow = 'queued'
            self.run_commands()
            self.assertEqual([call['json']['command'] for call in self.posts()], ['manual', 'stop'])
            for cmd in self.relay.commands:
                self.relay.complete_command(cmd['id'], status='done', ts=start + timedelta(seconds=3))
            self.assertEqual(self.relay.readings[-1]['values']['controller_mode'], 'stop')
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(batch.mapped('state'), ['done', 'done'])
            # одиночні команди пульта — правила «лише на переходах» без змін
            self.sync()
            single = self.Command._enqueue(self.genset, 'stop', 'button', self.user_t)
            self.assertFalse(single._is_manual_stop_batch())
            self.run_commands()
            self.assertEqual(single.state, 'not_needed')
            self.assertEqual(single.result_note, 'Не потрібно: генератор уже зупинено')

    def test_ac20_queue_limit_two_inflight(self):
        """AC-20: 2 незавершені на ретрансляторі → третя «У черзі Odoo», надсилається після завершення попередніх;
        одночасно від Odoo — не більше 2."""
        start = datetime(2026, 10, 7, 15, 30)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='auto', genset_status=9,
                            mains_normal=False, gen_on_load=True)
            self.relay.command_flow = 'queued'
            batch = self.Command._enqueue_batch(self.genset, ['manual', 'stop'], 'schedule', 'Odoo: розклад')
            self.run_commands()
            self.assertEqual(batch.mapped('state'), ['sent', 'sent'])
            third = self.Command._enqueue(self.genset, 'auto', 'button', self.user_t)
            self.assertEqual(third.state, 'queued_odoo')
            self.assertEqual(third._label('state'), 'У черзі Odoo')
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(third.state, 'queued_odoo')
            self.assertEqual(len(self.posts()), 2)
            for cmd in self.relay.commands:
                self.relay.complete_command(cmd['id'], status='done', ts=start + timedelta(minutes=1, seconds=3))
            self.sync()
            frozen.move_to(start + timedelta(minutes=2))
            self.run_commands()
            self.assertEqual(batch.mapped('state'), ['done', 'done'])
            self.assertEqual(third.state, 'sent')
            self.assertEqual(len(self.posts()), 3)
        # навіть якщо три команди «До надсилання» створено одночасно — у роботі не більше 2
        with freeze_time(start + timedelta(hours=1)):
            self.push_state(controller_mode='manual')
            self.relay.command_flow = 'queued'
            for command in ('auto', 'start', 'test'):
                self.Command._enqueue(self.genset, command, 'button', self.user_t)
            self.run_commands()
            self.assertEqual(self.Command._count_inflight(self.genset), 2)

    def test_ac21_breaker_toggle(self):
        """AC-21: «Розімкнути» автомат мережі (знімок 40 с тому) → ``mains_close_open``, підтвердження
        ``mains_on_load=false``; положення вже цільове → «Не потрібно»; знімок > 2 хв → чекаємо показання."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(seconds=40), controller_mode='auto')
            wizard, action = self.confirm_wizard('mains_close_open')
            self.assertFalse(wizard.target_breaker_closed)
            self.assertIn("Генератор не живить об'єкт: живлення зникне повністю.", wizard.warning_text)
            self.assertTrue(wizard.confirm_required)
            command = self.commands()
            self.assertFalse(command.target_breaker_closed)
            self.run_commands()
            self.assertEqual(self.posts()[-1]['json']['command'], 'mains_close_open')
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'done')
            # положення вже цільове
            self.sync()
            self.assertFalse(self.genset.mains_on_load)
            again = self.Command._enqueue(self.genset, 'mains_close_open', 'button', self.user_t,
                                          target_breaker_closed=False)
            self.run_commands()
            self.assertEqual(again.state, 'not_needed')
            self.assertEqual(again.result_note, 'Не потрібно: автомат мережі уже розімкнено')
            self.assertEqual(len(self.posts()), 1)
            # знімок старший за 2 хв — команда чекає свіжого знімка
            frozen.move_to(start + timedelta(minutes=5))
            close = self.Command._enqueue(self.genset, 'mains_close_open', 'button', self.user_t,
                                          target_breaker_closed=True)
            self.run_commands()
            self.assertEqual(close.state, 'to_send')
            self.assertIn('Очікуємо показання', close.result_note)
            self.assertEqual(len(self.posts()), 1)
            self.push_state(ts=start + timedelta(minutes=5, seconds=30), controller_mode='auto', mains_on_load=False)
            frozen.move_to(start + timedelta(minutes=6))
            self.run_commands()
            self.assertEqual(close.state, 'sent')
            self.assertEqual(len(self.posts()), 2)
        stale_text = self.env['td.genset.command.wizard'].with_user(self.user_t).create(
            {'genset_id': self.genset.id, 'command': 'gen_close_open'})
        self.assertIn("на мить залишиться без живлення", stale_text.warning_text)

    def test_ac22_gen_breaker_close_only_when_running(self):
        """AC-22: ``genset_status=0`` → «Замкнути» автомат генератора — «Генератор ще не в режимі роботи.
        Спочатку «Пуск».», команда не створюється."""
        with freeze_time(datetime(2026, 10, 7, 11, 0)):
            self.push_state(controller_mode='manual', genset_status=0)
            with self.assertRaisesRegex(UserError, 'Генератор ще не в режимі роботи. Спочатку «Пуск».'):
                self.confirm_wizard('gen_close_open')
            self.assertFalse(self.commands())
            self.push_state(controller_mode='manual', genset_status=9)
            wizard, _action = self.confirm_wizard('gen_close_open')
            self.assertTrue(self.commands().target_breaker_closed)
            self.assertIn("Під час перемикання об'єкт на мить залишиться без живлення.", wizard.warning_text)

    def test_ac23_remote_lock_blocks(self):
        """AC-23: ``remote_lock`` → пульт, розклад і таймер (кінець) не надсилають: «Не надіслано: блокування»,
        повідомлення в чатер."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start):
            self.push_state(controller_mode='manual', remote_lock=True)
            self.confirm_wizard('auto')
            self.Command._enqueue(self.genset, 'auto', 'schedule', 'Odoo: розклад')
            self.Command._enqueue_batch(self.genset, ['manual', 'stop'], 'timer', 'Odoo: таймер')
            self.run_commands()
            self.assertEqual(set(self.commands().mapped('state')), {'blocked'})
            self.assertEqual(set(self.commands().mapped('result_note')), {'Не надіслано: блокування'})
            self.assertFalse(self.posts())
            self.assertIn('Не надіслано: блокування', self.chatter_text())
            with self.assertRaisesRegex(UserError, 'Дистанційне керування заблоковано на контролері'):
                self.genset.with_user(self.user_s)._timer_start(30, self.user_s)

    def test_ac24_pult_requires_tech_and_link(self):
        """AC-24: RPC команди від Співробітника/Адміністратора → помилка доступу, запис не створюється; без зв'язку
        пульт недоступний."""
        for user in (self.user_s, self.user_a):
            with self.assertRaises(AccessError):
                self.genset.with_user(user).with_context(default_command='start').action_open_command_wizard()
            with self.assertRaises(AccessError):
                self.env['td.genset.command.wizard'].with_user(user).create(
                    {'genset_id': self.genset.id, 'command': 'start'})
            with self.assertRaises(AccessError):
                self.genset.with_user(user)._test_start('load', user)
            with self.assertRaises(AccessError):
                self.env['td.genset.command'].with_user(user).create({'genset_id': self.genset.id, 'command': 'stop'})
        self.assertFalse(self.commands())
        self.set_genset(link_state='offline')
        with self.assertRaisesRegex(UserError, "Немає зв'язку з модулем — команди неможливо доставити"):
            self.confirm_wizard('stop')
        self.assertFalse(self.commands())

    def test_ac25_start_cancels_timer(self):
        """AC-25: діє таймер, «Пуск» → діалог з «Переконайтеся, що біля генератора немає людей…» і «Запущений
        таймер роботи поза графіком буде скасовано»; таймер скасовано (чатер «Таймер скасовано командою Пуск»),
        ``start`` підтверджено за ``speed>0`` / ``genset_status`` 8–9."""
        start = datetime(2026, 10, 10, 7, 0)   # субота, поза розкладом
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.genset.with_user(self.user_s)._timer_start(120, self.user_s)
            timer_command = self.commands()
            self.assertTrue(self.genset.timer_end)
            wizard = self.env['td.genset.command.wizard'].with_user(self.user_t).create(
                {'genset_id': self.genset.id, 'command': 'start'})
            self.assertIn('Переконайтеся, що біля генератора немає людей', wizard.warning_text)
            self.assertIn('Запущений таймер роботи поза графіком буде скасовано', wizard.warning_text)
            wizard.action_confirm()
            self.assertFalse(self.genset.timer_end)
            self.assertIn('Таймер скасовано командою Пуск', self.chatter_text())
            self.assertEqual(timer_command.state, 'cancelled')
            start_command = self.commands(command='start')
            self.run_commands()
            self.assertEqual(start_command.state, 'sent')
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(start_command.state, 'done')
            self.assertEqual(self.genset.control_source, 'manual')

    def test_ac26_crank_failure(self):
        """AC-26: після ``start`` знімки з ``crank_failure=true`` → «Не виконано: невдалий пуск» без повторів,
        тривога критична «Невдалий пуск»."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.relay.crank_failure = True
            self.confirm_wizard('start')
            command = self.commands()
            self.run_commands()
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'failed')
            self.assertEqual(command.result_note, 'Не виконано: невдалий пуск')
            self.assertEqual(self.raised[-1]['code'], 'crank_failure_cmd')
            self.assertEqual(self.raised[-1]['level'], 'crit')
            self.assertEqual(self.raised[-1]['name'], 'Невдалий пуск')
            self.assertEqual(self.raised[-1]['description'], 'Невдалий пуск після команди «Пуск».')
            for minute in range(2, 15):
                frozen.move_to(start + timedelta(minutes=minute))
                self.run_commands()
            self.assertEqual(len(self.posts()), 1)

    def test_ac26_start_confirmed_only_when_engine_runs(self):
        """ФВ-9 (рішення 07.10): ``start`` підтверджується знімком після ``done_at`` з ``genset_status ∈ {5…9}`` (оберти
        не обов'язкові: NULL/0 не заважає); прокрутка (стан 3, оберти ~250) і самі ``speed > 0`` — ще ні; поки
        триває пуск (1–4), повторного POST немає; ``crank_failure`` у будь-якому знімку після ``done_at`` →
        ``failed`` без повторів."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.relay.controller_executes = False
            command = self.Command._enqueue(self.genset, 'start', 'button', self.user_t)
            self.run_commands()
            self.relay.complete_command(status='done', ts=start + timedelta(seconds=3))
            cranking = self.relay.push(snapshot(controller_mode='manual', genset_status=3), reason='change',
                                       ts=start + timedelta(seconds=5))
            self.assertEqual(cranking['values']['speed'], 250)
            for minute in range(1, 5):
                frozen.move_to(start + timedelta(minutes=minute))
                self.relay.push(snapshot(controller_mode='manual', genset_status=3 if minute % 2 else 4),
                                reason='interval', ts=start + timedelta(minutes=minute))
                self.run_commands()
                self.assertEqual(command.state, 'awaiting')
            self.assertIn('триває пуск', command.result_note)
            self.assertEqual(len(self.posts()), 1)
            frozen.move_to(start + timedelta(minutes=5))
            self.relay.push(snapshot(controller_mode='manual', genset_status=6), reason='change',
                            ts=start + timedelta(minutes=5))
            self.run_commands()
            self.assertEqual(command.state, 'done')
        facts = {'ts': start + timedelta(minutes=1), 'controller_mode': 'manual', 'genset_status': 9, 'speed': 0,
                 'gen_on_load': False, 'mains_on_load': True, 'crank_failure': False, 'relay_id': 1, 'record': None}
        self.assertTrue(command._check_confirmation(facts))
        self.assertTrue(command._check_confirmation(dict(facts, speed=None)))
        self.assertTrue(command._check_confirmation(dict(facts, genset_status=5, speed=1500)))
        self.assertFalse(command._check_confirmation(dict(facts, genset_status=3, speed=250)))
        self.assertFalse(command._check_confirmation(dict(facts, genset_status=None, speed=1500)))
        self.assertFalse(command._check_confirmation(dict(facts, genset_status=0, speed=0)))
        # crank_failure у будь-якому знімку після done_at — відмова, навіть якщо пізніший знімок «працює»
        with freeze_time(start + timedelta(hours=1)) as frozen:
            later = start + timedelta(hours=1)
            other = self.Command._enqueue(self.genset, 'start', 'button', self.user_t)
            self.run_commands()
            self.relay.complete_command(status='done', ts=later + timedelta(seconds=3))
            self.relay.push(snapshot(controller_mode='manual', genset_status=4, crank_failure=True), reason='change',
                            ts=later + timedelta(seconds=40))
            self.sync()
            self.relay.push(snapshot(controller_mode='manual', genset_status=9), reason='change',
                            ts=later + timedelta(seconds=50))
            frozen.move_to(later + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(other.state, 'failed')
            self.assertEqual(other.result_note, 'Не виконано: невдалий пуск')

    def test_ac18_awaiting_without_snapshots_does_not_resend(self):
        """AC-18 (уточнення 07.10): без знімка після ``done_at`` повтору немає — чекаємо; зв'язок пропав →
        ``waiting_link``; зв'язок є, але знімка немає довше ``retry_every_min`` + 1 хв → повтор."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.relay.controller_executes = False
            command = self.Command._enqueue(self.genset, 'auto', 'button', self.user_t)
            self.run_commands()
            self.relay.complete_command(status='done', ts=start + timedelta(seconds=3))
            for minute in (1, 2, 3):
                frozen.move_to(start + timedelta(minutes=minute))
                self.run_commands()
                self.assertEqual(command.state, 'awaiting')
            self.assertEqual(len(self.posts()), 1)
            frozen.move_to(start + timedelta(minutes=4))   # 3 хв 57 с без знімка при живому зв'язку
            self.run_commands()
            self.assertEqual(command.state, 'sent')
            self.assertEqual(command.attempt, 1)
            self.assertEqual(len(self.posts()), 2)
            # друга спроба: знімків немає, а зв'язок пропав (link_lost_min = 3 хв) → waiting_link, без POST
            self.relay.complete_command(status='done', ts=start + timedelta(minutes=4, seconds=3))
            frozen.move_to(start + timedelta(minutes=5))
            self.run_commands()
            self.assertEqual(command.state, 'awaiting')
            self.set_genset(link_state='offline')
            frozen.move_to(start + timedelta(minutes=7))
            self.run_commands()
            self.assertEqual(command.state, 'waiting_link')
            self.assertEqual(len(self.posts()), 2)

    def test_ac27_external_control_not_reverted(self):
        """AC-27: у вікні (Авто) режим змінили не з Odoo → Odoo не надсилає ``auto`` до наступного переходу;
        на кінці вікна ``manual`` — «Не потрібно», ``stop`` — за станом генератора."""
        self.env['td.genset.schedule'].create({'genset_id': self.genset.id, 'dayofweek': '2',
                                              'time_start': 8.75, 'time_end': 18.5})
        start = kyiv(2026, 10, 7, 10, 0)
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            self.assertTrue(self.genset.sched_in_window)
            frozen.move_to(start + timedelta(minutes=5))
            self.relay.cloud_press('manual', ts=start + timedelta(minutes=5))
            self.sync()
            self.env['td.genset.event'].create({'genset_id': self.genset.id, 'event_type': 'external_control',
                                                'date_start': start + timedelta(minutes=5),
                                                'date_end': start + timedelta(minutes=5),
                                                'mode_from': 'auto', 'mode_to': 'manual'})
            self.set_genset(control_source='external')
            for minute in range(6, 300, 7):
                frozen.move_to(start + timedelta(minutes=minute))
                self.run_scheduler()
                self.run_commands()
            self.assertFalse(self.commands())
            self.assertEqual(self.genset.control_source, 'external')
            frozen.move_to(kyiv(2026, 10, 7, 18, 30))
            self.run_scheduler()
            self.run_commands()
            # рішення 07.10: «Ручний + Стоп» надсилається повністю (мета — режим Stop); Ручний підтвердиться одразу
            self.assertEqual([call['json']['command'] for call in self.posts()], ['manual', 'stop'])
            self.assertEqual(self.genset.control_source, 'schedule')
            frozen.move_to(kyiv(2026, 10, 7, 18, 31))
            self.run_commands()
            self.assertEqual(self.commands().mapped('state'), ['done', 'done'])

    def test_ac66_commands_disabled_in_odoo(self):
        """AC-66: «Дозволити команди» вимкнено → POST не виконується, «Не надіслано: команди вимкнено в Odoo»
        (пульт і планувальник); таймер не запускається."""
        with freeze_time(datetime(2026, 10, 7, 11, 0)):
            self.push_state(controller_mode='manual')
            self.set_genset(commands_allowed=False)
            self.confirm_wizard('auto')
            self.Command._enqueue(self.genset, 'auto', 'schedule', 'Odoo: розклад')
            self.run_commands()
            self.assertEqual(set(self.commands().mapped('state')), {'disabled_odoo'})
            self.assertEqual(set(self.commands().mapped('result_note')), {'Не надіслано: команди вимкнено в Odoo'})
            self.assertFalse(self.posts())
            with self.assertRaisesRegex(UserError, 'Команди вимкнено в Odoo'):
                self.genset.with_user(self.user_s)._timer_start(30, self.user_s)

    def test_ac67_stop_without_mains_warning_and_cooling(self):
        """AC-67: працює під навантаженням без мережі → «Стоп»: попередження «Мережі немає: після зупинки офіс
        залишиться без живлення», підтвердження обов'язкове; ``stop`` підтверджується охолодженням (10–13) і
        ``gen_on_load=false``; з мережею — «навантаження повернеться на мережу»."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual', genset_status=9,
                            mains_normal=False, gen_on_load=True)
            wizard = self.env['td.genset.command.wizard'].with_user(self.user_t).create(
                {'genset_id': self.genset.id, 'command': 'stop'})
            self.assertIn('Мережі немає: після зупинки офіс залишиться без живлення', wizard.warning_text)
            self.assertNotIn('Навантаження повернеться на мережу', wizard.warning_text)
            self.assertTrue(wizard.confirm_required)
            self.assertFalse(self.commands())   # без «Підтвердити» команда не створюється
            wizard.action_confirm()
            command = self.commands()
            self.relay.controller_executes = False
            self.run_commands()
            self.assertEqual(command.state, 'sent')
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.assertEqual(command.state, 'awaiting')
            self.push_state(ts=start + timedelta(minutes=1, seconds=5), controller_mode='manual', genset_status=10,
                            mains_normal=False, gen_on_load=False)
            frozen.move_to(start + timedelta(minutes=2))
            self.run_commands()
            self.assertEqual(command.state, 'done')
            self.assertEqual(command.confirm_reading_id.genset_status, '10')
        self.push_state(controller_mode='manual', genset_status=9, gen_on_load=True)
        with_mains = self.env['td.genset.command.wizard'].with_user(self.user_t).create(
            {'genset_id': self.genset.id, 'command': 'stop'})
        self.assertIn('Навантаження повернеться на мережу', with_mains.warning_text)
        self.assertFalse(with_mains.confirm_required)

    def test_cancel_pending_and_cron_robustness(self):
        """А.5: ``_cancel_pending`` скасовує лише незавершені до надсилання (``sent``/``awaiting`` — без повторів);
        помилка кроку однієї команди не зупиняє cron."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.relay.controller_executes = False
            sent = self.Command._enqueue(self.genset, 'auto', 'schedule', 'Odoo: розклад')
            self.run_commands()
            self.relay.complete_command(status='done', ts=start + timedelta(seconds=3))
            pending = self.Command._enqueue(self.genset, 'start', 'timer', 'Odoo: таймер')
            button = self.Command._enqueue(self.genset, 'stop', 'button', self.user_t)
            cancelled = self.Command._cancel_pending(self.genset, 'новий перехід')
            self.assertEqual(cancelled, pending)
            self.assertEqual(pending.state, 'cancelled')
            self.assertEqual(pending.result_note, 'Скасовано: новий перехід')
            self.assertEqual(sent.state, 'sent')
            self.assertTrue(sent.cancel_requested)
            self.assertEqual(button.state, 'to_send')
            self.relay.push(None, reason='interval', ts=start + timedelta(minutes=2))
            frozen.move_to(start + timedelta(minutes=3))
            command_cls = type(self.Command)
            original_step = command_cls._step_send

            def broken(record, now):
                if record == button:
                    raise ValueError('boom')
                return original_step(record, now)

            with patch.object(command_cls, '_step_send', broken), mute_logger('odoo.addons.td_genset.models.genset_command'):
                self.run_commands()
            self.assertEqual(sent.state, 'cancelled')   # не підтверджено → повтору не буде
            self.assertEqual(button.state, 'to_send')
            self.assertEqual(button.next_attempt_at, start + timedelta(minutes=4))

    # ------------------------------------------------------------------ ревю коду (ЗВІТ_РЕВЮ, п. 1, 4, 5, 8)
    def test_ac18_after_link_restore_next_retry_waits_interval(self):
        """AC-18, AC-14 (ревю коду, п. 1): після відновлення зв'язку перший знімок вирішує лише перше рішення —
        після нового POST знову діє ``done_at + retry_every_min``: наступна спроба не раніше ніж через 2 хв."""
        start = datetime(2026, 10, 7, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(ts=start - timedelta(minutes=1), controller_mode='manual')
            self.relay.controller_executes = False
            command = self.Command._enqueue(self.genset, 'auto', 'button', self.user_t)
            self.run_commands()
            frozen.move_to(start + timedelta(minutes=1))
            self.run_commands()
            self.set_genset(link_state='offline')
            frozen.move_to(start + timedelta(minutes=2))
            self.run_commands()
            self.assertEqual(command.state, 'waiting_link')
            restored = start + timedelta(minutes=30)
            frozen.move_to(restored)
            self.set_genset(link_state='online')
            self.push_state(ts=restored, controller_mode='manual')
            self.run_commands()
            self.assertEqual((command.state, len(self.posts())), ('sent', 2))   # перший знімок вирішив: повтор
            self.assertFalse(command.link_restored_at)
            for minute in (1, 2):   # done о 11:31; знімки з тим самим режимом — ще не час повтору
                frozen.move_to(restored + timedelta(minutes=minute))
                self.push_state(ts=restored + timedelta(minutes=minute), controller_mode='manual')
                self.run_commands()
                self.assertEqual(command.state, 'awaiting')
                self.assertEqual(len(self.posts()), 2)
            frozen.move_to(restored + timedelta(minutes=3))
            self.push_state(ts=restored + timedelta(minutes=3), controller_mode='manual')
            self.run_commands()
            self.assertEqual(len(self.posts()), 3)   # done_at (11:31) + retry_every_min (2 хв)
            self.assertFalse(self.raised)
