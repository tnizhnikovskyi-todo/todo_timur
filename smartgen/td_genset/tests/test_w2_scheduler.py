# Part of td_genset (ToDo). Власник файлу: W2 «Керування».
"""Планувальник (ТР 2.7, А.6): переходи розкладу, валідація, дні-винятки, пропущені переходи, DST —
AC-28, AC-29, AC-30, AC-34, AC-35, AC-37."""
from datetime import date, datetime, timedelta

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models.genset_schedule import kyiv_hhmm, to_kyiv
from .test_w2_commands import TdGensetW2Case, kyiv


@tagged('standard', 'at_install')
class TestW2Scheduler(TdGensetW2Case):

    def add_line(self, day, start, end, enabled=True):
        return self.env['td.genset.schedule'].create({
            'genset_id': self.genset.id, 'dayofweek': str(day), 'time_start': start, 'time_end': end,
            'enabled': enabled})

    def run_until(self, frozen, start, end, step=5, commands=False):
        """Планувальник (і за потреби cron команд) кожні ``step`` хв від ``start`` до ``end`` включно (UTC);
        повертає ``[(київський HH:MM, команда, джерело, стан)]`` нових записів журналу."""
        created = []
        moment = start
        while moment <= end:
            frozen.move_to(moment)
            before = set(self.commands().ids)
            self.run_scheduler()
            if commands:
                self.run_commands()
            for command in self.commands().filtered(lambda record: record.id not in before):
                created.append((kyiv_hhmm(moment), command.command, command.source, command.state))
            moment += timedelta(minutes=step)
        return created

    # ------------------------------------------------------------------ AC-28
    def test_ac28_schedule_transitions(self):
        """AC-28: «Пн 08:45–18:30»: о 08:45 — ``auto`` (Розклад, ``odoo:schedule``); о 18:30 — ``manual`` +
        ``stop``; між 08:46 і 18:29 команд немає, навіть якщо режим змінено ззовні."""
        self.add_line(0, 8.75, 18.5)
        monday = (2026, 10, 5)
        with freeze_time(kyiv(*monday, 8, 30)) as frozen:
            self.push_state(controller_mode='manual')
            self.run_scheduler()   # перший запуск — лише стан, без команд (А.6 п. 2)
            self.assertFalse(self.genset.sched_in_window)
            self.assertFalse(self.commands())
            created = self.run_until(frozen, kyiv(*monday, 8, 35), kyiv(*monday, 8, 45), step=1, commands=True)
            self.assertEqual([item[:3] for item in created], [('08:45', 'auto', 'schedule')])
            auto = self.commands()
            self.assertEqual(auto.user_id, self.env.ref('base.user_root'))
            self.assertEqual(auto.requested_by, 'Odoo: розклад')
            self.assertEqual(auto.state, 'sent')
            self.assertEqual(self.posts()[-1]['json']['source'], 'odoo:schedule')
            self.assertEqual(self.genset.control_source, 'schedule')
            self.assertTrue(self.genset.sched_in_window)
            frozen.move_to(kyiv(*monday, 8, 46))
            self.run_commands()
            self.assertEqual(auto.state, 'done')
            self.sync()
            # режим змінили ззовні й повернули — розклад не втручається до кінця вікна
            frozen.move_to(kyiv(*monday, 12, 0))
            self.relay.cloud_press('manual')
            self.sync()
            created = self.run_until(frozen, kyiv(*monday, 12, 1), kyiv(*monday, 14, 59), step=7, commands=True)
            frozen.move_to(kyiv(*monday, 15, 0))
            self.relay.cloud_press('auto')
            self.sync()
            created += self.run_until(frozen, kyiv(*monday, 15, 1), kyiv(*monday, 18, 29), step=4, commands=True)
            self.assertEqual(created, [])
            self.assertEqual(len(self.posts()), 1)
            created = self.run_until(frozen, kyiv(*monday, 18, 30), kyiv(*monday, 18, 31), step=1, commands=True)
            self.assertEqual([item[:3] for item in created],
                             [('18:30', 'manual', 'schedule'), ('18:30', 'stop', 'schedule')])
            manual, stop = self.commands()[-2:]
            self.assertEqual(manual.batch_key, stop.batch_key)
            self.assertEqual(manual.state, 'done')
            self.assertEqual(stop.state, 'not_needed')   # генератор стоїть — Стоп не надсилається (ФВ-9)
            self.assertEqual(stop.result_note, 'Не потрібно: генератор уже зупинено')
            self.assertFalse(self.genset.sched_in_window)

    def test_ac28_window_helpers(self):
        """AC-28/AC-36: межі вікон — UTC через ``kyiv_localize``; суміжні вікна (і через північ) — одне вікно."""
        self.add_line(0, 8.0, 12.0)
        self.add_line(0, 12.0, 24.0)
        self.add_line(1, 0.0, 6.0)
        self.add_line(1, 9.0, 10.0, enabled=False)
        self.assertEqual(self.genset._window_bounds(date(2026, 10, 5)), [(8.0, 24.0)])
        self.assertEqual(self.genset._window_bounds(date(2026, 10, 6)), [(0.0, 6.0)])
        self.assertTrue(self.genset._in_window(to_kyiv(kyiv(2026, 10, 5, 23, 59))))
        self.assertTrue(self.genset._in_window(to_kyiv(kyiv(2026, 10, 6, 0, 0))))
        self.assertFalse(self.genset._in_window(to_kyiv(kyiv(2026, 10, 6, 6, 0))))
        self.assertEqual(self.genset._next_transition(to_kyiv(kyiv(2026, 10, 5, 7, 0))),
                         (kyiv(2026, 10, 5, 8, 0), 'start'))
        self.assertEqual(self.genset._next_transition(to_kyiv(kyiv(2026, 10, 5, 13, 0))),
                         (kyiv(2026, 10, 6, 6, 0), 'end'))
        self.env['td.genset.schedule'].search([('genset_id', '=', self.genset.id)]).unlink()
        self.assertIsNone(self.genset._next_transition(to_kyiv(kyiv(2026, 10, 5, 13, 0))))

    # ------------------------------------------------------------------ AC-29
    def test_ac29_schedule_validation(self):
        """AC-29: «Вт 18:00–09:00» → «Кінець має бути пізніше за початок.»; перетин з «Вт 08:45–18:30» →
        «Вікна одного дня не можуть перетинатися.»; Співробітник розклад не змінює."""
        schedule = self.env['td.genset.schedule'].with_user(self.user_a)
        schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': 8.75, 'time_end': 18.5})
        with self.assertRaisesRegex(ValidationError, 'Кінець має бути пізніше за початок.'), self.env.cr.savepoint():
            schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': 18.0, 'time_end': 9.0})
        with self.assertRaisesRegex(ValidationError, 'Вікна одного дня не можуть перетинатися.'), \
                self.env.cr.savepoint():
            schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': 18.0, 'time_end': 20.0})
        schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': 18.5, 'time_end': 20.0})
        schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': 10.0, 'time_end': 11.0,
                         'enabled': False})
        with self.assertRaises(AccessError):
            self.env['td.genset.schedule'].with_user(self.user_s).create(
                {'genset_id': self.genset.id, 'dayofweek': '2', 'time_start': 8.0, 'time_end': 9.0})

    # ------------------------------------------------------------------ AC-30
    def test_ac30_exception_days(self):
        """AC-30: «31.12.2026 — Інший час 08:45–14:00» і «01.01.2027 — Не запускати»: 31.12 переходи о 08:45 і
        14:00 (звичайне вікно не діє), 01.01 — жодного; другий виняток на 31.12 → «На цю дату виняток уже є.»"""
        self.add_line(3, 9.0, 18.0)     # четвер — 31.12.2026
        self.add_line(4, 8.75, 18.5)    # п'ятниця — 01.01.2027
        exceptions = self.env['td.genset.schedule.exception'].with_user(self.user_a)
        exceptions.create({'genset_id': self.genset.id, 'date': date(2026, 12, 31), 'action': 'custom',
                           'time_start': 8.75, 'time_end': 14.0, 'note': 'Передсвятковий день'})
        exceptions.create({'genset_id': self.genset.id, 'date': date(2027, 1, 1), 'action': 'skip'})
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            exceptions.create({'genset_id': self.genset.id, 'date': date(2026, 12, 31), 'action': 'skip'})
        constraint = dict((name, message) for name, _definition, message
                          in type(self.env['td.genset.schedule.exception'])._sql_constraints)
        self.assertEqual(constraint['date_uniq'], 'На цю дату виняток уже є.')
        with self.assertRaisesRegex(ValidationError, 'Кінець має бути пізніше за початок.'), self.env.cr.savepoint():
            exceptions.create({'genset_id': self.genset.id, 'date': date(2027, 1, 2), 'action': 'custom',
                               'time_start': 14.0, 'time_end': 9.0})
        self.assertEqual(self.genset._window_bounds(date(2026, 12, 31)), [(8.75, 14.0)])
        self.assertEqual(self.genset._window_bounds(date(2027, 1, 1)), [])
        with freeze_time(kyiv(2026, 12, 31, 7, 0)) as frozen:
            self.push_state(controller_mode='manual')
            self.run_scheduler()
            created = self.run_until(frozen, kyiv(2026, 12, 31, 7, 5), kyiv(2027, 1, 1, 20, 0), step=5)
        self.assertEqual(created, [('08:45', 'auto', 'exception', 'to_send'),
                                   ('14:00', 'manual', 'exception', 'to_send'),
                                   ('14:00', 'stop', 'exception', 'to_send')])

    # ------------------------------------------------------------------ AC-34
    def test_ac34_missed_transition_during_downtime(self):
        """AC-34: Odoo стоїть 18:00–19:00, кінець вікна 18:30 → о 19:00 «Ручний + Стоп» з позначкою «із запізненням
        (перехід 18:30)»."""
        self.add_line(2, 8.75, 18.5)    # середа
        with freeze_time(kyiv(2026, 10, 7, 17, 59)) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            self.assertTrue(self.genset.sched_in_window)
            frozen.move_to(kyiv(2026, 10, 7, 19, 0))
            self.run_scheduler()
            manual, stop = self.commands()
            self.assertEqual((manual.command, stop.command), ('manual', 'stop'))
            self.assertEqual(manual.late_transition_at, kyiv(2026, 10, 7, 18, 30))
            self.assertIn('із запізненням (перехід 18:30)', manual.result_note)
            self.run_commands()
            self.assertEqual(manual.state, 'sent')
            self.assertIn('із запізненням (перехід 18:30)', manual.result_note)
            self.assertIn('із запізненням (перехід 18:30)', self.chatter_text())

    def test_ac34_missed_transition_skipped_after_external_control(self):
        """AC-34: між 18:30 і 19:00 зафіксовано «Керування не з Odoo» → «Пропущено: керування не з Odoo після
        переходу» + повідомлення."""
        self.add_line(2, 8.75, 18.5)
        with freeze_time(kyiv(2026, 10, 7, 17, 59)) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            self.env['td.genset.event'].create({
                'genset_id': self.genset.id, 'event_type': 'external_control',
                'date_start': kyiv(2026, 10, 7, 18, 40), 'date_end': kyiv(2026, 10, 7, 18, 40),
                'mode_from': 'auto', 'mode_to': 'stop'})
            frozen.move_to(kyiv(2026, 10, 7, 19, 0))
            self.run_scheduler()
            self.run_commands()
            self.assertEqual(self.commands().mapped('state'), ['skipped', 'skipped'])
            self.assertTrue(self.commands()[0].result_note.startswith(
                'Пропущено: керування не з Odoo після переходу'))
            self.assertFalse(self.posts())
            self.assertIn('Пропущено: керування не з Odoo після переходу', self.chatter_text())

    # ------------------------------------------------------------------ AC-35
    def test_ac35_missed_transition_without_link_until_next(self):
        """AC-35: модуль не на зв'язку 18:20–19:40, перехід 18:30 → через 10 хв тривога «Команда «Ручний» не
        підтверджена за 10 хв (модуль не на зв'язку)», далі спроби кожні 5 хв; після відновлення — 201, done,
        «Підтверджено після відновлення зв'язку»."""
        self.add_line(2, 8.75, 18.5)
        with freeze_time(kyiv(2026, 10, 7, 18, 0)) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            frozen.move_to(kyiv(2026, 10, 7, 18, 23))
            self.set_genset(link_state='offline')
            attempts, alarm_at = [], None
            moment = kyiv(2026, 10, 7, 18, 24)
            while moment <= kyiv(2026, 10, 7, 19, 50):
                frozen.move_to(moment)
                if moment == kyiv(2026, 10, 7, 19, 40):
                    self.set_genset(link_state='online')
                manual = self.commands(command='manual')
                before = manual.transport_attempt if manual else 0
                self.run_scheduler()
                self.run_commands()
                manual = self.commands(command='manual')
                if manual and manual.transport_attempt > before:
                    attempts.append(kyiv_hhmm(moment))
                if manual and manual.alarm_raised_at and not alarm_at:
                    alarm_at = kyiv_hhmm(moment)
                moment += timedelta(minutes=1)
            self.assertEqual(alarm_at, '18:40')
            self.assertEqual(self.raised[0]['code'], 'cmd_unconfirmed')
            self.assertEqual(self.raised[0]['name'],
                             "Команда «Ручний» не підтверджена за 10 хв (модуль не на зв'язку)")
            self.assertEqual(attempts[:10], ['18:30', '18:31', '18:32', '18:33', '18:34', '18:35', '18:36',
                                             '18:37', '18:38', '18:39'])
            self.assertEqual(attempts[10:13], ['18:44', '18:49', '18:54'])
            self.assertEqual(len(self.posts('manual')), 1)
            self.assertEqual(manual.state, 'done_late')
            self.assertEqual(manual.result_note.split(' · ')[0], "Підтверджено після відновлення зв'язку")
            self.assertEqual(self.commands(command='stop').state, 'not_needed')
            self.assertIn('cmd_unconfirmed', [item['code'] for item in self.cleared])

    def test_ac35_missed_transition_window_only(self):
        """AC-35: політика «Лише вікно повторів» — після тривоги спроб немає."""
        self.config.missed_transition_policy = 'window_only'
        self.add_line(2, 8.75, 18.5)
        with freeze_time(kyiv(2026, 10, 7, 18, 0)) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            self.set_genset(link_state='offline')
            moment = kyiv(2026, 10, 7, 18, 25)
            while moment <= kyiv(2026, 10, 7, 19, 30):
                frozen.move_to(moment)
                self.run_scheduler()
                self.run_commands()
                moment += timedelta(minutes=1)
            manual = self.commands(command='manual')
            self.assertEqual(manual.state, 'failed')
            self.assertEqual(manual.transport_attempt, 10)
            self.assertEqual(self.raised[0]['name'],
                             "Команда «Ручний» не підтверджена за 10 хв (модуль не на зв'язку)")
            self.set_genset(link_state='online')
            frozen.move_to(kyiv(2026, 10, 7, 19, 45))
            self.run_commands()
            self.assertFalse(self.posts())

    # ------------------------------------------------------------------ AC-37
    def test_ac37_dst_spring_forward(self):
        """AC-37: «Нд 03:30–04:30», ніч 29.03.2026 (03:00→04:00): ``auto`` о 04:00 (перша дійсна хвилина),
        ``manual`` + ``stop`` о 04:30."""
        self.add_line(6, 3.5, 4.5)
        with freeze_time(datetime(2026, 3, 29, 0, 30)) as frozen:   # 02:30 EET
            self.push_state(controller_mode='manual')
            self.run_scheduler()
            created = self.run_until(frozen, datetime(2026, 3, 29, 0, 31), datetime(2026, 3, 29, 2, 0), step=1)
        self.assertEqual([item[:3] for item in created], [('04:00', 'auto', 'schedule'),
                                                          ('04:30', 'manual', 'schedule'),
                                                          ('04:30', 'stop', 'schedule')])
        self.assertEqual(self.genset._next_transition(to_kyiv(datetime(2026, 3, 29, 0, 0))),
                         (datetime(2026, 3, 29, 1, 0), 'start'))

    def test_ac37_dst_fall_back(self):
        """AC-37: ніч 25.10.2026 (04:00→03:00): кожен перехід один раз, повторна година не породжує других команд."""
        self.add_line(6, 3.5, 4.5)
        with freeze_time(datetime(2026, 10, 24, 23, 50)) as frozen:   # 02:50 EEST
            self.push_state(controller_mode='manual')
            self.run_scheduler()
            created = self.run_until(frozen, datetime(2026, 10, 24, 23, 51), datetime(2026, 10, 25, 3, 0), step=1)
        self.assertEqual([item[:3] for item in created], [('03:30', 'auto', 'schedule'),
                                                          ('04:30', 'manual', 'schedule'),
                                                          ('04:30', 'stop', 'schedule')])
        # 03:30 EEST = 00:30 UTC; повторна 03:30 EET (01:30 UTC) — без команд; 04:30 EET = 02:30 UTC
        self.assertEqual(self.genset._window_moments(date(2026, 10, 25)),
                         [(datetime(2026, 10, 25, 0, 30), datetime(2026, 10, 25, 2, 30))])
