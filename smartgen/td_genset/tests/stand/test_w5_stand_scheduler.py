# Part of td_genset (ToDo). Власник файлу: W5 «Стенд і документація».
"""Стенд, етап 2 «Розклад, таймер, тест»: переходи розкладу, таймер (межі, подовження, зупинка, пріоритет над
кінцем вікна), тест без навантаження з поверненням, пропущений перехід після простою Odoo.

ТК-07, ТК-08, ТК-13.8 · AC-28…AC-34.

Власний емулятор з керованим годинником: старт — найближчий понеділок 08:44 Kyiv (рядок «Пн 08:45–08:50» —
скорочене «Пн 08:45–18:30» з AC-28); перед підключенням Odoo контролер переведено в «Ручний» (оператор стенду).
"""
from datetime import timedelta

import pytz

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .stand_common import KYIV, SCHEDULE_REQUESTED_BY, TdGensetStandCase, kyiv_to_utc, next_weekday_kyiv

FINAL = ('done', 'done_late', 'not_needed', 'skipped', 'failed', 'blocked', 'disabled_relay', 'disabled_odoo',
         'auth_error', 'cancelled')


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandScheduler(TdGensetStandCase):

    relay_mode = 'own'

    def clock_start_utc(self):
        return next_weekday_kyiv(0, 8, 44)

    def setUp(self):
        super().setUp()
        self.monday = pytz.utc.localize(self.now()).astimezone(KYIV).date()
        self.prepare_mode('manual')
        self.pull()
        self.assertEqual(self.genset.controller_mode, 'manual')

    def at(self, hour, minute, second=0):
        return kyiv_to_utc(self.monday, hour, minute) + timedelta(seconds=second)

    def add_window(self, start, end, day='0'):
        return self.env['td.genset.schedule'].create({
            'genset_id': self.genset.id, 'dayofweek': day, 'time_start': start, 'time_end': end})

    def minute(self, hour, minute, second=30):
        """Стенд у момент ``hour:minute:second`` Kyiv: знімок, забір, планувальник, команди."""
        self.advance_to(self.at(hour, minute, second))
        self.snapshot()
        self.pull()
        self.run_scheduler()
        self.run_commands()

    def window_start_auto(self):
        """08:44 — перша оцінка без команд; 08:45 — команда ``auto`` розкладу → підтверджено."""
        self.run_scheduler()
        self.assertFalse(self.genset_commands(), 'перший запуск планувальника не «зрушує» генератор')
        self.minute(8, 45)
        auto = self.genset_commands(source='schedule')
        self.assertEqual(auto.mapped('command'), ['auto'])
        self.drive(auto, FINAL, scheduler=True)
        self.assertEqual(auto.state, 'done')
        return auto

    def test_tk07_ac28_schedule_transitions(self):
        """ТК-07.1 · AC-28: рядок «Пн 08:45–08:50», понеділок, режим Ручний → протягом 1 хв після 08:45 команда
        ``auto`` (джерело «Розклад», ``source`` ``odoo:schedule``, ``requested_by`` «Odoo: розклад»), «Керує: Розклад»;
        між переходами жодних команд, навіть якщо режим змінено ззовні; о 08:50 — пакет ``manual`` + ``stop``."""
        self.add_window(8.75, 8 + 50 / 60.0)
        auto = self.window_start_auto()
        post = [cmd for cmd in self.relay_commands() if cmd['command'] == 'auto']
        self.assertEqual(len(post), 1)
        self.assertEqual(post[0]['source'], 'odoo:schedule')
        self.assertEqual(post[0]['requested_by'], SCHEDULE_REQUESTED_BY)
        self.assertEqual(self.genset.control_source, 'schedule')
        self.relay.sim(cloud_press='manual')                    # зовні в межах вікна
        self.relay.wait_mode('manual')
        for minute in (47, 48, 49):
            self.minute(8, minute)
        self.assertEqual(self.genset_commands(), auto)
        self.minute(8, 50)
        batch = self.genset_commands() - auto
        self.assertEqual(batch.mapped('command'), ['manual', 'stop'])
        self.assertEqual(set(batch.mapped('source')), {'schedule'})
        self.assertTrue(batch[0].batch_key)
        self.assertEqual(batch[0].batch_key, batch[1].batch_key)

    def test_tk07_ac31_timer_start_extend_stop(self):
        """ТК-07.2 · AC-31: Співробітник поза вікном: 25 год або 0 хв → «Вкажіть тривалість від 1 хв до 24 год»;
        таймер 0 год 5 хв → ``auto`` (джерело «Таймер»), «Керує: Таймер», хто запустив; +15 хв подовжує;
        «Зупинити таймер» поза вікном → ``manual`` + ``stop``, «Керує: Розклад»."""
        self.run_scheduler()
        for hours, minutes in ((25, 0), (0, 0)):
            with self.assertRaises((UserError, ValidationError)):
                self.start_timer(hours, minutes)
        self.start_timer(0, 5)
        genset = self.genset
        self.assertEqual(genset.control_source, 'timer')
        self.assertEqual(genset.timer_user_id, self.user_s)
        self.assertAlmostEqual((genset.timer_end - self.now()).total_seconds(), 300, delta=60)
        auto = self.genset_commands(source='timer')
        self.assertEqual(auto.mapped('command'), ['auto'])
        self.drive(auto, FINAL)
        self.assertEqual(auto.state, 'done')
        self.assertEqual(genset.controller_mode, 'auto')
        end = genset.timer_end
        genset.with_user(self.user_s).action_timer_extend_15()
        self.env.invalidate_all()
        self.assertEqual(genset.timer_end, end + timedelta(minutes=15))
        genset.with_user(self.user_s).action_timer_stop()
        self.env.invalidate_all()
        self.assertFalse(genset.timer_end)
        self.assertEqual(genset.control_source, 'schedule')
        back = self.genset_commands() - auto
        self.assertEqual(back.mapped('command'), ['manual', 'stop'])
        self.drive(back, FINAL)
        self.assertEqual(back[0].state, 'done')
        self.assertEqual(genset.controller_mode, 'manual')

    def test_tk07_ac32_timer_overrides_window_end(self):
        """ТК-07.3 · AC-32: таймер діє на кінці вікна → команд немає, запис «Пропущено: діє таймер до HH:MM»; кінець
        таймера поза вікном → ``manual`` + ``stop``."""
        self.add_window(8.75, 8.8)                              # Пн 08:45–08:48
        auto = self.window_start_auto()
        self.start_timer(0, 10)
        timer_cmds = self.genset_commands() - auto
        self.minute(8, 48)
        skipped = (self.genset_commands() - auto - timer_cmds).filtered(lambda c: c.state == 'skipped')
        self.assertTrue(skipped, 'кінець вікна під час таймера — запис «Пропущено: діє таймер»')
        self.assertIn('таймер', skipped[0].result_note or '')
        self.assertFalse([cmd for cmd in self.relay_commands() if cmd['command'] in ('manual', 'stop')])
        before = self.genset_commands()
        self.advance_to(self.genset.timer_end + timedelta(seconds=30))
        self.snapshot()
        self.pull()
        self.run_scheduler()
        back = self.genset_commands() - before
        self.assertEqual(back.mapped('command'), ['manual', 'stop'])
        self.assertFalse(self.genset.timer_end)

    def test_tk07_ac33_test_idle_returns_to_schedule(self):
        """ТК-07.4 · AC-33: Корист. Т → «Тест» → «Без навантаження» → ``manual`` + ``start`` (джерело «Тест»), «Керує:
        Тест», кінець тесту через 3 хв; пуск підтверджено; через 3 хв поза вікном — повернення ``manual`` + ``stop``
        («Керує: Розклад»), ``stop`` підтверджено."""
        self.run_scheduler()
        cmds = self.press('test', test_mode='idle')
        self.assertEqual(cmds.mapped('command'), ['manual', 'start'])
        genset = self.genset
        self.assertEqual(genset.control_source, 'test')
        self.assertEqual(genset.test_mode, 'idle')
        self.assertAlmostEqual((genset.test_end - self.now()).total_seconds(), 180, delta=60)
        self.drive(cmds, FINAL)
        start = cmds.filtered(lambda c: c.command == 'start')
        self.assertEqual(start.state, 'done')
        self.wait_relay(lambda v: v['genset_status'] in (8, 9), 'генератор працює')
        test_end = genset.test_end
        self.advance_to(test_end + timedelta(seconds=30))
        self.snapshot()
        self.pull()
        self.run_scheduler()
        self.assertFalse(genset.test_end)
        self.assertEqual(genset.control_source, 'schedule')
        back = self.genset_commands() - cmds
        self.assertEqual(back.mapped('command'), ['manual', 'stop'])
        self.drive(back, FINAL)
        self.assertEqual(back.filtered(lambda c: c.command == 'stop').state, 'done')

    def test_tk08_ac34_missed_transition_after_downtime(self):
        """ТК-08.1 · AC-34: Odoo «стоїть» 08:47–08:55 (стенд живе, знімки є), кінець вікна 08:50 → при першому
        запуску планувальника — ``manual`` + ``stop`` з позначкою «із запізненням (перехід 08:50)»
        (``late_transition_at`` = 08:50 Kyiv)."""
        self.add_window(8.75, 8 + 50 / 60.0)
        auto = self.window_start_auto()
        for minute in (48, 50, 52, 54):
            self.advance_to(self.at(8, minute))
            self.snapshot()
        self.minute(8, 55)
        late = self.genset_commands() - auto
        self.assertEqual(late.mapped('command'), ['manual', 'stop'])
        for cmd in late:
            self.assertEqual(cmd.late_transition_at, self.at(8, 50))
        texts = [cmd.result_note or '' for cmd in late] + self.chatter_texts()
        self.assertTrue(any('запізненням' in text for text in texts), 'позначка «із запізненням (перехід 08:50)»')

    def test_tk08_ac34_missed_transition_skipped_after_external_control(self):
        """ТК-08.1 · AC-34 (ТА): під час простою Odoo, після переходу 08:50, режим змінили із застосунку SmartGen →
        запізніла команда «Пропущено: керування не з Odoo після переходу», POST не виконується."""
        self.add_window(8.75, 8 + 50 / 60.0)
        auto = self.window_start_auto()
        posted = len(self.relay_commands())
        self.advance_to(self.at(8, 50))
        self.snapshot()
        self.advance_to(self.at(8, 52))
        self.relay.sim(cloud_press='manual')
        self.relay.wait_mode('manual')
        self.snapshot()
        self.advance_to(self.at(8, 54))
        self.snapshot()
        self.minute(8, 55)
        self.run_commands()
        late = self.genset_commands() - auto
        manual = late.filtered(lambda c: c.command == 'manual')
        self.assertEqual(len(manual), 1)
        self.assertEqual(manual.state, 'skipped')
        self.assertIn('не з Odoo', manual.result_note or '')
        self.assertEqual(len(self.relay_commands()), posted)

    def test_tk13_ac29_ac30_schedule_validation_and_exception(self):
        """ТК-13.8 · AC-29, AC-30: Адміністратор додає «Вт 18:00–09:00» → «Кінець має бути пізніше за початок»;
        рядок, що перетинає «Вт 08:45–18:30» → «Вікна одного дня не можуть перетинатися»; другий виняток на ту саму
        дату → «На цю дату виняток уже є»; виняток «Інший час» (сьогодні 08:46–08:48 замість вікна 09:00–10:00)
        виконує переходи у вказаний час."""
        Schedule = self.env['td.genset.schedule'].with_user(self.user_a)
        Schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': 8.75, 'time_end': 18.5})
        for start, end, text in ((18.0, 9.0, 'пізніше за початок'), (9.0, 10.0, 'не можуть перетинатися')):
            with self.assertRaises(ValidationError) as error, self.env.cr.savepoint():
                Schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': start, 'time_end': end})
            self.assertIn(text, str(error.exception))
        Exception_ = self.env['td.genset.schedule.exception'].with_user(self.user_a)
        Exception_.create({'genset_id': self.genset.id, 'date': self.monday, 'action': 'custom',
                           'time_start': 8 + 46 / 60.0, 'time_end': 8.8})
        with self.assertRaises(Exception), self.env.cr.savepoint(), mute_logger('odoo.sql_db'):
            Exception_.create({'genset_id': self.genset.id, 'date': self.monday, 'action': 'skip'})
            self.env.flush_all()
        self.add_window(9.0, 10.0)
        self.run_scheduler()                                     # 08:44 — перша оцінка
        self.minute(8, 45)
        self.assertFalse(self.genset_commands(), 'звичайне вікно цього дня не діє — лише «Інший час»')
        self.minute(8, 46)
        auto = self.genset_commands(source='exception') | self.genset_commands(source='schedule')
        self.assertEqual(auto.mapped('command'), ['auto'])
        self.drive(auto, FINAL, scheduler=True)
        self.minute(8, 48)
        batch = self.genset_commands() - auto
        self.assertEqual(batch.mapped('command'), ['manual', 'stop'])
