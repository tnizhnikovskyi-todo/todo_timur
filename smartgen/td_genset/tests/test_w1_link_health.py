# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""зв'язок, здоров'я, 401/5xx (AC-02, AC-09, AC-10, AC-11).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
from datetime import datetime, timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TdGensetCase, snapshot

T0 = datetime(2026, 10, 7, 9, 0, 0)       # 12:00 за Києвом
MONITORING_LOGGER = 'odoo.addons.td_genset.models.genset_monitoring'


@tagged('standard', 'at_install')
class TestW1LinkHealth(TdGensetCase):

    def _alarms(self, code=None, states=('active', 'acked')):
        domain = [('genset_id', '=', self.genset.id), ('state', 'in', list(states))]
        if code:
            domain.append(('code', '=', code))
        return self.env['td.genset.alarm'].search(domain)

    def _pull_at(self, moment):
        with freeze_time(moment):
            self.run_pull()

    def test_ac02_check_relay_button(self):
        """AC-02: «Перевірити зв'язок» (Т) показує версію, online, seconds_since_seen, commands_enabled,
        commands_ready, registers/coils; 401 і недоступність — зрозумілим текстом без трасування; А — AccessError."""
        self.push_reading(snapshot())
        result = self.genset.with_user(self.user_t).action_check_relay()
        message = result['params']['message']
        for text in ('1.1.3', 'онлайн', '7 с тому', 'команди на ретрансляторі: так', 'готовий до команд: так',
                     'регістрів: 55', 'сигналів: 80'):
            self.assertIn(text, message)
        self.assertEqual(result['params']['type'], 'success')
        self.assertEqual(self.genset.relay_version, '1.1.3')
        self.relay.fail(401)
        message = self.genset.with_user(self.user_t).action_check_relay()['params']['message']
        self.assertIn('Ретранслятор відхилив токен', message)
        self.relay.fail('timeout')
        message = self.genset.with_user(self.user_t).action_check_relay()['params']['message']
        self.assertEqual(message, 'Ретранслятор недоступний (таймаут 20 с).')
        with self.assertRaises(AccessError):
            self.genset.with_user(self.user_a).action_check_relay()
        refresh = self.genset.with_user(self.user_s).action_refresh()
        self.assertEqual(refresh['tag'], 'display_notification')

    def test_ac09_link_lost_and_restored(self):
        """AC-09: 3 хв без знімків і ``online=false`` → «Немає зв'язку з HH:MM» (момент переходу = останні дані
        + 3 хв); через 10 хв від переходу — критична тривога «Немає зв'язку з модулем» рівню 1; відновлення →
        «Онлайн», тривога знята, «Зв'язок відновлено після N хв без даних», подія «Зв'язок» закрита."""
        with freeze_time(T0):
            self.push_reading(snapshot(), ts=T0 - timedelta(seconds=10))
        self._pull_at(T0)
        self.assertEqual(self.genset.link_state, 'online')
        last_data = T0 - timedelta(seconds=10)
        lost_at = last_data + timedelta(minutes=3)          # 12:02:50 за Києвом
        self.set_status(online=False, seconds_since_seen=100)
        self._pull_at(T0 + timedelta(minutes=2))
        self.assertEqual(self.genset.link_state, 'online')
        self.set_status(online=False, seconds_since_seen=250)
        self._pull_at(T0 + timedelta(minutes=4))
        self.assertEqual(self.genset.link_state, 'offline')
        self.assertEqual(self.genset.link_changed_at, lost_at)
        event = self.env['td.genset.event'].search([('genset_id', '=', self.genset.id), ('event_type', '=', 'link')])
        self.assertEqual((len(event), event.date_start, event.is_open), (1, last_data, True))
        self.assertFalse(self._alarms('link_lost'))
        # 10 хв рахуються від переходу в «Немає зв'язку», а не від останніх даних
        self.set_status(seconds_since_seen=720)
        self._pull_at(T0 + timedelta(minutes=12))
        self.assertFalse(self._alarms('link_lost'))
        self.set_status(seconds_since_seen=780)
        self._pull_at(T0 + timedelta(minutes=13))
        alarm = self._alarms('link_lost')
        self.assertEqual((alarm.level, alarm.name), ('crit', "Немає зв'язку з модулем"))
        self.assertEqual(alarm.description, "Немає зв'язку з модулем з 12:02 (10 хв). Пульт недоступний.")
        with freeze_time(T0 + timedelta(minutes=13)):
            self.env['td.genset.alarm']._cron_escalate()
        self.assertEqual(alarm.notified_user_ids, self.user_s)
        # модуль повернувся
        self.set_status(online=True, seconds_since_seen=3)
        with freeze_time(T0 + timedelta(minutes=15)):
            self.push_reading(snapshot(), ts=T0 + timedelta(minutes=15) - timedelta(seconds=5))
            self.run_pull()
        self.assertEqual(self.genset.link_state, 'online')
        self.assertEqual(alarm.state, 'cleared')
        self.assertFalse(event.is_open)
        self.assertIn("Зв'язок відновлено після 15 хв без даних.", event.summary)
        log = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id),
                                               ('body', 'ilike', 'відновлено після 15 хв без даних')])
        self.assertEqual(len(log), 1)

    def test_ac09_catchup_is_not_link_loss(self):
        """2.8.6: під час догону історії свіжий знімок є на ретрансляторі — зв'язок не втрачено."""
        with freeze_time(T0):
            for minute in range(600):
                self.push_reading(snapshot(), ts=T0 - timedelta(minutes=600 - minute))
            self.run_pull()
            self.assertEqual(self.genset.link_state, 'online')
            self.assertTrue(self.genset.catchup_mode)
            self.run_pull()
            self.assertFalse(self.genset.catchup_mode)
        self.assertFalse(self.env['td.genset.event'].search([('genset_id', '=', self.genset.id),
                                                             ('event_type', '=', 'link')]))

    def test_ac10_relay_unavailable_and_auth(self):
        """AC-10: ретранслятор недоступний (5xx/таймаут) 10 хв → тривога тех. «Ретранслятор недоступний 10 хв»;
        401 → «Ретранслятор відхилив токен (401)»; cron не падає, курсор не змінюється; відновлення знімає."""
        with freeze_time(T0):
            self.push_reading(snapshot(), ts=T0 - timedelta(seconds=10))
        self._pull_at(T0)
        cursor = self.genset.readings_cursor
        self.relay.fail(500)
        with mute_logger(MONITORING_LOGGER):
            for minute in (1, 5, 10):
                self._pull_at(T0 + timedelta(minutes=minute))
                self.assertEqual(self.genset.readings_cursor, cursor)
            self.assertFalse(self._alarms('relay_unavailable'))
            self.relay.fail('timeout')
            with freeze_time(T0 + timedelta(minutes=11)):
                self.assertTrue(self.env.ref('td_genset.cron_pull_readings').method_direct_trigger())
        alarm = self._alarms('relay_unavailable')
        self.assertEqual(alarm.name, 'Ретранслятор недоступний 10 хв')
        self.assertTrue(alarm.tech_only)
        self.assertEqual(self.genset.readings_cursor, cursor)
        self.relay.fail(401)
        with mute_logger(MONITORING_LOGGER):
            self._pull_at(T0 + timedelta(minutes=12))
        auth = self._alarms('relay_auth')
        self.assertEqual((auth.name, auth.level, auth.tech_only), ('Ретранслятор відхилив токен (401)', 'warn', True))
        with freeze_time(T0 + timedelta(minutes=12)):
            self.env['td.genset.alarm']._cron_escalate()
        self.assertIn(self.user_t, auth.notified_user_ids)
        self.assertNotIn(self.user_s, auth.notified_user_ids)
        self.relay.fail(None)
        self._pull_at(T0 + timedelta(minutes=13))
        self.assertFalse(self._alarms('relay_unavailable') | self._alarms('relay_auth'))
        self.assertFalse(self.config.relay_unavailable_since)

    def test_ac09_relay_unavailable_link_goes_offline(self):
        """AC-09, AC-10 (ревю коду, п. 3): недоступний сам ретранслятор (таймаут/5xx) — знімків немає ≥ 3 хв →
        «Немає зв'язку» (пульт недоступний), подія «Зв'язок» відкрита; ретранслятор відповів зі свіжими знімками →
        «Онлайн», подія закрита."""
        with freeze_time(T0):
            self.push_reading(snapshot(), ts=T0 - timedelta(seconds=10))
        self._pull_at(T0)
        self.assertEqual(self.genset.link_state, 'online')
        self.relay.fail('timeout')
        with mute_logger(MONITORING_LOGGER):
            self._pull_at(T0 + timedelta(minutes=2))
            self.assertEqual(self.genset.link_state, 'online')
            self._pull_at(T0 + timedelta(minutes=4))
        self.assertEqual(self.genset.link_state, 'offline')
        link = self.env['td.genset.event'].search([('genset_id', '=', self.genset.id), ('event_type', '=', 'link')])
        self.assertTrue(link.filtered('is_open'))
        self.relay.fail(None)
        with freeze_time(T0 + timedelta(minutes=5)):
            self.push_reading(snapshot(), ts=T0 + timedelta(minutes=5) - timedelta(seconds=5))
        self._pull_at(T0 + timedelta(minutes=5))
        self.assertEqual(self.genset.link_state, 'online')
        self.assertFalse(link.filtered('is_open'))

    def test_ac10_readings_5xx_counts_even_if_status_ok(self):
        """AC-10 (ревю коду, п. 7): ``/status`` відповідає, а ``/readings`` стабільно 5xx → лічильник недоступності
        не скидається, через 10 хв — тривога тех. «Ретранслятор недоступний 10 хв»; успішна сторінка знімків її
        знімає і скидає лічильник."""
        with freeze_time(T0):
            self.push_reading(snapshot(), ts=T0 - timedelta(seconds=10))
        self._pull_at(T0)
        self.relay.fail(500, path='/readings')
        with mute_logger(MONITORING_LOGGER):
            for minute in (1, 5, 11):
                self._pull_at(T0 + timedelta(minutes=minute))
        alarm = self._alarms('relay_unavailable')
        self.assertEqual(alarm.name, 'Ретранслятор недоступний 10 хв')
        self.relay.fail(None)
        with freeze_time(T0 + timedelta(minutes=12)):
            self.push_reading(snapshot(), ts=T0 + timedelta(minutes=12) - timedelta(seconds=5))
        self._pull_at(T0 + timedelta(minutes=12))
        self.assertFalse(self._alarms('relay_unavailable'))
        self.assertFalse(self.config.relay_unavailable_since)

    def test_ac11_relay_health(self):
        """AC-11: ``registers_known=0`` → тривога-попередження тех. «Ретранслятор не розбирає дані
        (registers_known=0)»; ``commands_enabled=false`` → бейдж «Керування вимкнено на ретрансляторі»."""
        self.set_status(registers_known=0)
        self._pull_at(T0)
        alarm = self._alarms('relay_health')
        self.assertEqual(alarm.name, 'Ретранслятор не розбирає дані (registers_known=0)')
        self.assertEqual((alarm.level, alarm.tech_only), ('warn', True))
        self.set_status(registers_known=55, commands_enabled=False)
        self._pull_at(T0 + timedelta(minutes=1))
        self.assertFalse(self._alarms('relay_health'))
        self.assertFalse(self.genset.relay_commands_enabled)
        self.assertFalse(self.genset.relay_commands_ready)
        self.set_status(commands_enabled=True, format_learned=False)
        self._pull_at(T0 + timedelta(minutes=2))
        self.assertEqual(self._alarms('relay_cmd_format').name, 'Ретранслятор ще не вивчив формат команд')
        self.set_status(format_learned=True)
        self._pull_at(T0 + timedelta(minutes=3))
        self.assertFalse(self._alarms('relay_cmd_format'))
