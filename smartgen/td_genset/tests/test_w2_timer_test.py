# Part of td_genset (ToDo). Власник файлу: W2 «Керування».
"""Таймер «Робота поза графіком», тест, «Наступна подія» (ТР 2.7, А.6; ФВ-20, ФВ-22, ФВ-23) —
AC-31, AC-32, AC-33, AC-36."""
from datetime import timedelta

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_w2_commands import TdGensetW2Case, kyiv


@tagged('standard', 'at_install')
class TestW2TimerTest(TdGensetW2Case):

    def add_line(self, day, start, end):
        return self.env['td.genset.schedule'].create({
            'genset_id': self.genset.id, 'dayofweek': str(day), 'time_start': start, 'time_end': end})

    def tick(self, frozen, moment, commands=True):
        frozen.move_to(moment)
        self.run_scheduler()
        if commands:
            self.run_commands()

    def next_event(self):
        self.genset.invalidate_recordset(['next_event_text'])
        return self.genset.next_event_text

    def start_timer(self, hours, minutes, user=None):
        wizard = self.env['td.genset.timer.wizard'].with_user(user or self.user_s).create(
            {'genset_id': self.genset.id, 'hours': hours, 'minutes': minutes})
        return wizard, wizard.action_confirm()

    # ------------------------------------------------------------------ AC-31
    def test_ac31_timer_start_limits_extend_stop(self):
        """AC-31: Співробітник поза вікном: 0 год 0 хв / 25 год → «Вкажіть тривалість від 1 хв до 24 год»;
        2 год 30 хв → ``auto``, «Керує: Таймер», до/хто/коли; «+60 хв» — не далі 24 год від зараз («Таймер уже на
        максимумі — 24 год»); «Зупинити таймер» поза вікном → ``manual`` + ``stop``, «Керує: Розклад»."""
        start = kyiv(2026, 10, 10, 10, 0)   # субота, розкладу немає, режим Ручний
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='manual')
            self.set_genset(control_source='schedule')
            for hours, minutes in ((0, 0), (25, 0), (24, 30), (1, 60)):
                with self.assertRaisesRegex(UserError, 'Вкажіть тривалість від 1 хв до 24 год'):
                    self.start_timer(hours, minutes)
            self.assertFalse(self.commands())
            wizard, action = self.start_timer(2, 30)
            self.assertEqual(wizard.confirm_text, 'Генератор перейде в режим Авто на 2 год 30 хв, потім у Ручний і Стоп.')
            self.assertEqual(action['params']['message'], 'Таймер запущено до 12:30.')
            self.assertEqual(self.genset.timer_end, start + timedelta(hours=2, minutes=30))
            self.assertEqual(self.genset.timer_started_at, start)
            self.assertEqual(self.genset.timer_user_id, self.user_s)
            self.assertEqual(self.genset.control_source, 'timer')
            auto = self.commands()
            self.assertEqual((auto.command, auto.source, auto.user_id), ('auto', 'timer', self.user_s))
            self.run_commands()
            self.assertEqual(self.posts()[-1]['json']['source'], 'odoo:timer')
            self.assertEqual(self.next_event(), '12:30 → кінець таймера · далі за розкладом')
            self.assertIn('запустив Співробітник Стенд', self.chatter_text())
            with self.assertRaisesRegex(UserError, 'Таймер уже запущено'):
                self.start_timer(1, 0)
            # +60 хв — будь-який Співробітник
            frozen.move_to(start + timedelta(minutes=110))   # 11:50
            self.genset.with_user(self.user_x).action_timer_extend_60()
            self.assertEqual(self.genset.timer_end, start + timedelta(hours=3, minutes=30))
            self.assertIn('Таймер подовжено на 60 хв, до 13:30.', self.chatter_text())
            # не далі 24 год від поточного моменту
            now = start + timedelta(minutes=110)
            self.set_genset(timer_end=now + timedelta(hours=23, minutes=50))
            self.genset.with_user(self.user_s).action_timer_extend_60()
            self.assertEqual(self.genset.timer_end, now + timedelta(hours=24))
            self.assertIn('Таймер подовжено на 10 хв', self.chatter_text())
            with self.assertRaisesRegex(UserError, 'Таймер уже на максимумі — 24 год.'):
                self.genset.with_user(self.user_s).action_timer_extend_15()
            # зупинка поза вікном → Ручний + Стоп
            self.sync()
            self.genset.with_user(self.user_x).action_timer_stop()
            self.assertFalse(self.genset.timer_end)
            self.assertEqual(self.genset.control_source, 'schedule')
            manual, stop = self.commands()[-2:]
            self.assertEqual((manual.command, stop.command), ('manual', 'stop'))
            self.assertEqual((manual.source, manual.user_id), ('timer', self.user_x))
            self.assertEqual(manual.batch_key, stop.batch_key)
            self.assertIn('Зупинив таймер роботи поза графіком.', self.chatter_text())
            with self.assertRaisesRegex(UserError, 'Таймер не запущено'):
                self.genset.with_user(self.user_s).action_timer_stop()

    def test_ac31_timer_stop_in_window_keeps_auto(self):
        """AC-31: «Зупинити таймер» у вікні — нічого не надсилається (режим лишається Авто), «Керує: Розклад»;
        права: таймер — Співробітник; без зв'язку таймер недоступний."""
        self.add_line(5, 14.0, 18.0)    # субота 14:00–18:00
        start = kyiv(2026, 10, 10, 15, 0)
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            self.assertTrue(self.genset.sched_in_window)
            self.start_timer(1, 0)
            self.run_commands()
            self.assertEqual(self.commands().state, 'not_needed')
            frozen.move_to(start + timedelta(minutes=10))
            before = len(self.commands())
            self.genset.with_user(self.user_s).action_timer_stop()
            self.assertEqual(len(self.commands()), before)
            self.assertEqual(self.genset.control_source, 'schedule')
            self.assertFalse(self.genset.timer_end)
            self.set_genset(link_state='offline')
            with self.assertRaisesRegex(UserError, "Немає зв'язку з модулем"):
                self.start_timer(0, 30)
        outsider = self.env['res.users'].with_context(no_reset_password=True).create(
            {'name': 'Без груп модуля', 'login': 'td_w2_outsider'})
        with self.assertRaises(AccessError):
            self.genset.with_user(outsider).action_timer_extend_15()

    # ------------------------------------------------------------------ AC-32
    def test_ac32_timer_over_window_end(self):
        """AC-32: таймер до 20:00, кінець вікна 18:30 → о 18:30 команд немає, запис «Пропущено: діє таймер до
        20:00»; о 20:00 — ``manual`` + ``stop``."""
        self.add_line(1, 8.75, 18.5)    # вівторок
        start = kyiv(2026, 10, 6, 17, 0)
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            self.start_timer(3, 0)
            self.run_commands()
            self.assertEqual(self.commands().state, 'not_needed')
            self.tick(frozen, kyiv(2026, 10, 6, 18, 29))
            self.tick(frozen, kyiv(2026, 10, 6, 18, 30))
            skipped = self.commands()[-1]
            self.assertEqual((skipped.command, skipped.state), ('manual', 'skipped'))
            self.assertEqual(skipped.result_note, 'Пропущено: діє таймер до 20:00')
            self.assertIn('Кінець вікна: команду пропущено — діє таймер до 20:00. Після таймера — Ручний + Стоп.',
                          self.chatter_text())
            self.assertFalse(self.posts())
            self.assertEqual(self.genset.control_source, 'timer')
            self.tick(frozen, kyiv(2026, 10, 6, 19, 59))
            self.assertEqual(len(self.commands()), 2)
            self.tick(frozen, kyiv(2026, 10, 6, 20, 0))
            manual, stop = self.commands()[-2:]
            self.assertEqual((manual.command, manual.source, stop.command), ('manual', 'timer', 'stop'))
            self.assertEqual(manual.state, 'sent')
            self.assertFalse(self.genset.timer_end)
            self.assertEqual(self.genset.control_source, 'schedule')
            self.assertIn('Таймер завершився.', self.chatter_text())

    def test_ac32_window_start_during_timer(self):
        """AC-32: таймер 07:00–10:00, початок вікна 08:45 → «Не потрібно: уже Авто за таймером»; о 10:00 — нічого
        (у вікні), «Керує: Розклад»."""
        self.add_line(2, 8.75, 18.5)    # середа
        start = kyiv(2026, 10, 7, 7, 0)
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='manual')
            self.run_scheduler()
            self.start_timer(3, 0)
            self.run_commands()
            self.tick(frozen, start + timedelta(minutes=1))
            self.assertEqual(self.commands().state, 'done')
            self.sync()
            self.tick(frozen, kyiv(2026, 10, 7, 8, 44))
            self.tick(frozen, kyiv(2026, 10, 7, 8, 45))
            window_start = self.commands()[-1]
            self.assertEqual((window_start.command, window_start.state), ('auto', 'not_needed'))
            self.assertEqual(window_start.result_note, 'Не потрібно: уже Авто за таймером')
            self.assertIn('Початок вікна: команда не потрібна — генератор уже в Авто за таймером.', self.chatter_text())
            self.tick(frozen, kyiv(2026, 10, 7, 10, 0))
            self.assertFalse(self.genset.timer_end)
            self.assertEqual(len(self.commands()), 2)
            self.assertEqual(self.genset.control_source, 'schedule')
            self.assertEqual(len(self.posts()), 1)

    # ------------------------------------------------------------------ AC-33
    def test_ac33_test_idle_returns_by_schedule(self):
        """AC-33: без вибору варіанта підтвердити не можна; «Без навантаження» → ``manual``, потім ``start``,
        «Керує: Тест»; перехід під час тесту — «Пропущено: іде тест»; через 3 хв у вікні → ``auto``."""
        self.add_line(2, 8.75, 18.5)
        start = kyiv(2026, 10, 7, 8, 43)
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='auto')
            self.run_scheduler()
            wizard = self.env['td.genset.command.wizard'].with_user(self.user_t).create(
                {'genset_id': self.genset.id, 'command': 'test'})
            self.assertIn('Переконайтеся, що біля генератора немає людей', wizard.warning_text)
            self.assertIn('Через 3 хв генератор сам повернеться в режим за розкладом або таймером.', wizard.warning_text)
            with self.assertRaisesRegex(UserError, 'Оберіть варіант тесту'):
                wizard.action_confirm()
            self.assertFalse(self.commands())
            wizard.test_mode = 'idle'
            wizard.action_confirm()
            manual, start_cmd = self.commands()
            self.assertEqual((manual.command, start_cmd.command), ('manual', 'start'))
            self.assertEqual((manual.source, manual.sequence, start_cmd.sequence), ('test', 1, 2))
            self.assertEqual(manual.batch_key, start_cmd.batch_key)
            self.assertEqual(self.genset.control_source, 'test')
            self.assertEqual(self.genset.test_mode, 'idle')
            self.assertEqual(self.genset.test_end, start + timedelta(minutes=3))
            self.assertEqual(self.next_event(), '08:46 → кінець тесту · далі Авто за розкладом')
            self.run_commands()
            self.assertEqual([call['json']['command'] for call in self.posts()], ['manual', 'start'])
            self.tick(frozen, start + timedelta(minutes=1))
            self.assertEqual([manual.state, start_cmd.state], ['done', 'done'])
            self.sync()
            self.tick(frozen, kyiv(2026, 10, 7, 8, 45))
            skipped = self.commands()[-1]
            self.assertEqual((skipped.command, skipped.state, skipped.result_note),
                             ('auto', 'skipped', 'Пропущено: іде тест'))
            self.tick(frozen, kyiv(2026, 10, 7, 8, 46))
            back = self.commands()[-1]
            self.assertEqual((back.command, back.source), ('auto', 'test'))
            self.assertFalse(self.genset.test_end)
            self.assertEqual(self.genset.control_source, 'schedule')
            self.assertIn('Тест завершено через 3 хв: повернення в режим Авто за розкладом.', self.chatter_text())

    def test_ac33_test_load_out_of_window(self):
        """AC-33: тест «З навантаженням» поза вікном → ``test``; через 3 хв — ``manual`` + ``stop``."""
        start = kyiv(2026, 10, 10, 11, 0)   # субота без розкладу
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='manual')
            self.run_scheduler()
            self.genset.with_user(self.user_t)._test_start('load', self.user_t)
            test_command = self.commands()
            self.assertEqual((test_command.command, test_command.source), ('test', 'test'))
            self.assertEqual(self.next_event(), '11:03 → кінець тесту · далі Ручний + Стоп')
            self.run_commands()
            self.tick(frozen, start + timedelta(minutes=1))
            self.assertEqual(test_command.state, 'done')
            self.sync()
            self.assertEqual(self.genset.controller_mode, 'test')
            self.tick(frozen, start + timedelta(minutes=3))
            manual, stop = self.commands()[-2:]
            self.assertEqual((manual.command, stop.command, manual.source), ('manual', 'stop', 'test'))
            self.assertEqual([call['json']['command'] for call in self.posts()], ['test', 'manual', 'stop'])
            self.assertIn('Тест завершено через 3 хв: повернення в режим Ручний + Стоп.', self.chatter_text())

    def test_ac33_test_pauses_timer(self):
        """AC-33/ФВ-22: тест призупиняє таймер (після тесту — знову Авто за таймером); кінець таймера, що настав би
        під час тесту, переноситься на кінець тесту."""
        start = kyiv(2026, 10, 10, 11, 0)
        with freeze_time(start) as frozen:
            self.push_state(controller_mode='manual')
            self.run_scheduler()
            self.start_timer(1, 0)
            self.run_commands()
            self.tick(frozen, start + timedelta(minutes=1))
            self.sync()
            self.genset.with_user(self.user_t)._test_start('load', self.user_t)
            self.assertFalse(self.genset.timer_end)
            self.assertEqual(self.genset.test_timer_paused_left, 59 * 60)
            self.assertEqual(self.next_event(), '11:04 → кінець тесту · далі Авто за таймером')
            self.run_commands()
            self.tick(frozen, start + timedelta(minutes=2))
            self.sync()
            self.assertEqual(self.genset.controller_mode, 'test')
            self.tick(frozen, start + timedelta(minutes=4))
            self.assertEqual(self.genset.timer_end, start + timedelta(minutes=63))
            self.assertEqual(self.genset.control_source, 'timer')
            back = self.commands()[-1]
            self.assertEqual((back.command, back.source), ('auto', 'test'))
            self.assertIn('Тест завершено через 3 хв: повернення в режим Авто за таймером.', self.chatter_text())
        # таймер мав закінчитися під час тесту → кінець переноситься на кінець тесту, далі — за розкладом
        later = kyiv(2026, 10, 10, 13, 0)
        with freeze_time(later) as frozen:
            self.set_genset(timer_end=later + timedelta(minutes=1), timer_started_at=later - timedelta(hours=1),
                            timer_user_id=self.user_s.id, control_source='timer')
            self.genset.with_user(self.user_t)._test_start('idle', self.user_t)
            self.assertEqual(self.genset.test_timer_paused_left, 0)
            self.assertEqual(self.next_event(), '13:03 → кінець тесту · далі Ручний + Стоп')
            self.tick(frozen, later + timedelta(minutes=1))
            self.assertFalse(self.genset.timer_end)
            self.tick(frozen, later + timedelta(minutes=3))
            manual, stop = self.commands()[-2:]
            self.assertEqual((manual.command, stop.command), ('manual', 'stop'))
            self.assertEqual(self.genset.control_source, 'schedule')

    def test_ac33_auto_ends_test_early(self):
        """ФВ-22: «Авто» з пульта під час тесту завершує тест раніше і повертає таймер з паузи."""
        start = kyiv(2026, 10, 10, 11, 0)
        with freeze_time(start):
            self.push_state(controller_mode='manual')
            self.set_genset(timer_end=start + timedelta(minutes=30), timer_started_at=start,
                            timer_user_id=self.user_s.id)
            self.genset.with_user(self.user_t)._test_start('load', self.user_t)
            self.assertEqual(self.genset.test_timer_paused_left, 30 * 60)
            self.confirm_wizard('auto')
            self.assertFalse(self.genset.test_end)
            self.assertEqual(self.genset.timer_end, start + timedelta(minutes=30))
            self.assertEqual(self.genset.control_source, 'timer')
            self.assertIn('Тест завершено раніше командою Авто.', self.chatter_text())
            self.assertEqual(self.commands()[0].state, 'cancelled')

    # ------------------------------------------------------------------ AC-36
    def test_ac36_next_event_text(self):
        """AC-36: «сьогодні, 18:30 → Ручний + Стоп» / «21:00 → кінець таймера · далі за розкладом» /
        «10:05 → кінець тесту · далі Авто за розкладом» / «Розклад вимкнено»."""
        self.assertEqual(self.next_event(), 'Розклад вимкнено')
        self.add_line(2, 8.75, 18.5)    # середа
        self.add_line(3, 8.75, 18.5)    # четвер
        with freeze_time(kyiv(2026, 10, 7, 14, 3)):
            self.assertEqual(self.next_event(), 'сьогодні, 18:30 → Ручний + Стоп')
        with freeze_time(kyiv(2026, 10, 7, 19, 0)):
            self.assertEqual(self.next_event(), 'завтра, 08:45 → Авто')
        with freeze_time(kyiv(2026, 10, 8, 19, 0)):
            self.assertEqual(self.next_event(), 'середа, 08:45 → Авто')
        with freeze_time(kyiv(2026, 10, 7, 19, 0)):
            self.set_genset(timer_end=kyiv(2026, 10, 7, 21, 0))
            self.assertEqual(self.next_event(), '21:00 → кінець таймера · далі за розкладом')
            self.set_genset(timer_end=False, test_end=kyiv(2026, 10, 8, 10, 5), test_mode='load')
            self.assertEqual(self.next_event(), '10:05 → кінець тесту · далі Авто за розкладом')
            self.set_genset(test_end=False, test_mode=False)
        self.env['td.genset.schedule'].search([('genset_id', '=', self.genset.id)]).write({'enabled': False})
        self.assertEqual(self.next_event(), 'Розклад вимкнено')
