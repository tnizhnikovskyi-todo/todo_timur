# Part of td_genset (ToDo). Власник файлу: W5 «Стенд і документація».
"""Стенд, етап 2 «Керування»: команда з пульта 201 → done → підтвердження за знімком, «Не потрібно», повтори і
тривога, 409, 403, перезапуск ретранслятора, «no reply», «Дозволити команди», блокування, невдалий пуск,
керування не з Odoo, «Ручний + Стоп» і ліміт черги, автомати, «Стоп» без мережі, зв'язок зник до підтвердження.

ТК-05, ТК-06, ТК-12.4, ТК-13, ТК-14.3 · AC-12…AC-23, AC-24 (доступ до майстра), AC-26, AC-27, AC-65…AC-67.

Власний емулятор з керованим годинником (команда — крок cron щохвилини); старт — завтра 11:00 Kyiv (поза тихими
годинами); налаштування стенду — повтор 1/3 хв (``STAND_CONFIG``).
"""
from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .stand_common import TdGensetStandCase, float_time, kyiv_weekday, tomorrow_kyiv, wait_until

FINAL = ('done', 'done_late', 'not_needed', 'skipped', 'failed', 'blocked', 'disabled_relay', 'disabled_odoo',
         'auth_error', 'cancelled')
STOP_CONFIRM_STATUSES = ('10', '11', '12', '13', '15', '0')


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandCommands(TdGensetStandCase):

    relay_mode = 'own'

    def clock_start_utc(self):
        return tomorrow_kyiv(11)

    def setUp(self):
        super().setUp()
        self.pull()                       # стан, зв'язок і commands_ready до команд

    def relay_posts(self, command=None):
        return [cmd for cmd in self.relay_commands() if command is None or cmd['command'] == command]

    def confirm_manual(self):
        """Підготовка через Odoo: «Ручний» з пульта → підтверджено (режим Ручний на контролері)."""
        manual = self.press('manual')
        self.drive(manual, FINAL)
        self.assertEqual(manual.state, 'done')
        return manual

    def run_without_mains(self):
        """Авто + зникла мережа → генератор запустився і взяв навантаження (стенд), Odoo забрав знімки."""
        self.relay.sim(mains_normal=False)
        self.wait_relay(lambda v: v['genset_status'] == 9 and v['gen_on_load'], 'автопуск без мережі', timeout=8)
        self.snapshot()
        self.pull()

    # ------------------------------------------------------------------ ТК-05
    def test_tk05_ac12_ac13_button_command_confirmed(self):
        """ТК-05 · AC-12, AC-13, AC-65: Корист. Т → «Ручний» → запис журналу (хто, «Кнопка», «Ручний»), POST 201 зі
        ``requested_by`` «<Ім'я> (res.users <id>)» і ``source`` ``odoo:button`` → ``done`` → «Підтверджено» за знімком з
        ``ts ≥ done_utc`` і ``controller_mode = manual``, повідомлення в чатері; повторний «Ручний» — «Не потрібно: уже
        Ручний», POST не виконується."""
        self.assertEqual(self.genset.controller_mode, 'auto')
        cmd = self.press('manual')
        self.assertEqual(len(cmd), 1)
        self.assertEqual((cmd.command, cmd.source, cmd.user_id), ('manual', 'button', self.user_t))
        self.run_commands()
        self.assertEqual(cmd.state, 'sent')
        self.assertTrue(cmd.relay_cmd_id)
        relay_cmd = self.relay.wait_command_final(cmd.relay_cmd_id)
        self.assertEqual(relay_cmd['status'], 'done')
        self.assertEqual(relay_cmd['source'], 'odoo:button')
        self.assertEqual(relay_cmd['requested_by'], '%s (res.users %d)' % (self.user_t.name, self.user_t.id))
        self.drive(cmd, FINAL)
        self.assertEqual(cmd.state, 'done')
        self.assertTrue(cmd.done_at and cmd.confirmed_at)
        self.assertTrue(cmd.confirm_reading_id)
        self.assertGreaterEqual(cmd.confirm_reading_id.ts, cmd.done_at)
        self.assertEqual(cmd.confirm_reading_id.controller_mode, 'manual')
        self.assertEqual(self.genset.controller_mode, 'manual')
        self.assertChatterContains('Підтверджено')
        posted = len(self.relay_posts())
        again = self.press('manual')
        self.run_commands()
        self.assertEqual(again.state, 'not_needed')
        self.assertIn('Не потрібно', again.result_note or '')
        self.assertEqual(len(self.relay_posts()), posted)

    # ------------------------------------------------------------------ ТК-06
    def test_tk06_ac14_no_exec_retries_then_alarm(self):
        """ТК-06.1 · AC-14: «контролер не виконує» (``done``, режим не змінюється), повтор 1/3 хв → POST повторюється
        (``source`` ``odoo:retry``, не більше «Спроба N з 3»), після вікна — «Не підтверджено — тривога» і тривога
        критична з причиною «…Перевірте на об'єкті…»; дедлайн = перша спроба + 3 хв."""
        self.relay.sim(no_exec=True)
        cmd = self.press('manual')
        self.assertEqual(cmd.max_attempts, 3)
        self.drive(cmd, FINAL, max_steps=10)
        self.assertEqual(cmd.state, 'failed')
        self.assertEqual(cmd.deadline_at, cmd.first_sent_at + timedelta(minutes=3))
        posts = self.relay_posts('manual')
        self.assertGreaterEqual(len(posts), 2)
        self.assertLessEqual(len(posts), cmd.max_attempts + 1)
        self.assertEqual(posts[0]['source'], 'odoo:button')
        self.assertEqual({post['source'] for post in posts[1:]}, {'odoo:retry'})
        self.assertEqual({post['status'] for post in posts}, {'done'})
        self.assertEqual(self.relay.values()['controller_mode'], 'auto')
        alarm = self.alarms('cmd_unconfirmed')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'crit')
        self.assertIn('Перевірте на об', alarm.description or '')
        self.assertEqual(cmd.alarm_id, alarm)

    def test_tk06_ac15_409_then_201(self):
        """ТК-06.2 · AC-15, AC-65: модуль не на зв'язку в момент команди → POST 409 «modem is not connected» →
        «Повтор: модуль не на зв'язку (спроба 1)», наступна спроба через 1 хв, перша спроба зафіксована; модуль
        повернувся → 201 і «Підтверджено»."""
        self.relay.sim(link=False)        # /status ще не перечитано — для Odoo модуль онлайн, POST дає 409
        cmd = self.press('manual')
        self.run_commands()
        self.assertEqual(cmd.state, 'retry')
        self.assertEqual(cmd.transport_attempt, 1)
        self.assertIn('не на зв', cmd.result_note or '')
        self.assertTrue(cmd.first_sent_at)
        self.assertFalse(cmd.relay_cmd_id)
        self.assertAlmostEqual((cmd.next_attempt_at - self.now()).total_seconds(), 60, delta=10)
        self.assertFalse(self.relay_posts())
        self.relay.sim(link=True)
        self.relay.wait_tick()
        self.drive(cmd, FINAL)
        self.assertEqual(cmd.state, 'done')
        self.assertEqual(len(self.relay_posts('manual')), 1)

    def test_tk06_ac16_403_commands_disabled(self):
        """ТК-06.3 · AC-16, AC-65: ретранслятор без ``RELAY_COMMANDS_ENABLED`` (403) → «Керування вимкнено на
        ретрансляторі», без повторів (і через 2 хв POST немає), тривога тех.; пульт неактивний."""
        self.relay.sim(commands_enabled=False)
        cmd = self.press('manual')
        self.run_commands()
        self.assertEqual(cmd.state, 'disabled_relay')
        self.tick(minutes=2)
        self.assertEqual(cmd.state, 'disabled_relay')
        self.assertFalse(self.relay.commands())
        self.assertEqual(len(self.alarms('relay_cmd_disabled')), 1)
        self.assertFalse(self.genset.relay_commands_enabled)
        self.assertFalse(self.genset.with_user(self.user_t).get_pult_state()['can_control'])

    def test_tk06_ac17_relay_restart_between_sent_and_done(self):
        """ТК-06.4 · AC-17, AC-65: ретранслятор перезапущено між ``sent`` і ``done`` → ``failed`` «relay restarted» →
        причина «ретранслятор перезапущено», повтор у межах вікна (нова спроба, новий id) → «Підтверджено»."""
        self.relay.sim(no_reply=True, time_scale=1)      # команда «висить» у sent (30 с реального часу)
        cmd = self.press('manual')
        self.run_commands()
        first_id = cmd.relay_cmd_id
        self.assertTrue(first_id)
        wait_until(lambda: self.relay.command(first_id)['status'] == 'sent', 3, 'команда в sent')
        self.relay.sim(restart=True, no_reply=False, time_scale=self.time_scale)
        self.assertEqual(self.relay.command(first_id)['error'], 'relay restarted')
        self.tick()
        self.assertEqual(cmd.relay_error, 'relay restarted')
        self.assertIn('перезапущено', cmd.result_note or '')
        self.drive(cmd, FINAL)
        self.assertEqual(cmd.state, 'done')
        self.assertNotEqual(cmd.relay_cmd_id, first_id)

    def test_tk06_ac17_no_reply_timeout(self):
        """AC-17 (ТК-06): модуль не відповів 30 с → ретранслятор ``timeout`` «no reply in 30 s» → повтор у межах
        вікна → «Підтверджено»."""
        self.relay.sim(no_reply=True)
        cmd = self.press('manual')
        self.run_commands()
        first_id = cmd.relay_cmd_id
        self.assertTrue(first_id)
        self.advance(seconds=40)
        self.assertEqual(self.relay.wait_command_final(first_id)['status'], 'timeout')
        self.relay.sim(no_reply=False)
        self.tick()
        self.assertIn('no reply', cmd.relay_error or '')
        self.drive(cmd, FINAL)
        self.assertEqual(cmd.state, 'done')
        self.assertGreaterEqual(len(self.relay_posts('manual')), 2)

    # ------------------------------------------------------------------ ТК-12.4
    def test_tk12_ac66_commands_not_allowed(self):
        """ТК-12.4 · AC-66: «Дозволити команди» вимкнено → «Не надіслано: команди вимкнено в Odoo», POST не
        виконується; забір показань працює."""
        self.genset.commands_allowed = False
        cmd = self.enqueue('manual')
        self.run_commands()
        self.assertEqual(cmd.state, 'disabled_odoo')
        self.assertFalse(self.relay.commands())
        count = len(self.odoo_readings())
        self.snapshot()
        self.assertGreater(len(self.pull()), count)

    # ------------------------------------------------------------------ ТК-13
    def test_tk13_ac19_ac20_batch_manual_stop_and_queue(self):
        """ТК-13.1 · AC-19, AC-20: кінець вікна розкладу в Авто (генератор працює — мережі немає) → два POST поспіль
        ``manual`` і ``stop`` з одним ключем пакета, обидва «Підтверджено» (``stop`` — охолодження/зупинка і
        ``gen_on_load = false``); третя команда під час їх виконання — «У черзі Odoo» і надсилається лише після
        завершення пакета (на ретрансляторі ≤ 2 команд Odoo одночасно)."""
        start = self.now()
        end = start + timedelta(minutes=3)
        self.env['td.genset.schedule'].create({
            'genset_id': self.genset.id, 'dayofweek': kyiv_weekday(start),
            'time_start': float_time(start - timedelta(hours=1)), 'time_end': float_time(end)})
        self.run_scheduler()                                   # перша оцінка: у вікні, без команд
        self.assertFalse(self.genset_commands())
        self.run_without_mains()
        self.advance_to(end.replace(second=0, microsecond=0) + timedelta(minutes=1, seconds=20))
        self.snapshot()
        self.pull()
        self.run_scheduler()
        batch = self.genset_commands(source='schedule')
        self.assertEqual(batch.mapped('command'), ['manual', 'stop'])
        self.assertTrue(batch[0].batch_key)
        self.assertEqual(batch[0].batch_key, batch[1].batch_key)
        self.assertEqual(batch.mapped('sequence'), [1, 2])
        self.run_commands()
        self.assertEqual(batch.mapped('state'), ['sent', 'sent'])
        self.assertEqual([post['command'] for post in self.relay_posts()], ['manual', 'stop'])
        third = self.press('auto')
        self.assertEqual(third.state, 'queued_odoo')
        self.drive(batch | third, FINAL, max_steps=10)
        self.assertEqual(batch.mapped('state'), ['done', 'done'])
        stop = batch[1]
        self.assertIn(stop.confirm_reading_id.genset_status, STOP_CONFIRM_STATUSES)
        self.assertFalse(stop.confirm_reading_id.gen_on_load)
        posts = self.relay_posts()
        third_posts = [post for post in posts if post['command'] == 'auto']
        self.assertTrue(third_posts)
        first_two_done = max(post['done'] for post in posts[:2])
        self.assertGreaterEqual(third_posts[0]['created'], first_two_done)

    def test_tk13_ac21_mains_breaker_toggle(self):
        """ТК-13.2 · AC-21: Ручний режим, ``mains_on_load = true``, свіжий знімок → «Автомат мережі: Розімкнути» →
        ``mains_close_open`` (цільове положення «розімкнено»), підтвердження за ``mains_on_load = false``; команда з
        уже досягнутим цільовим положенням — «Не потрібно», POST немає."""
        self.confirm_manual()
        self.assertTrue(self.genset.mains_on_load)
        cmd = self.press('mains_close_open')
        self.assertEqual(cmd.command, 'mains_close_open')
        self.assertFalse(cmd.target_breaker_closed)
        self.drive(cmd, FINAL)
        self.assertEqual(cmd.state, 'done')
        self.assertFalse(cmd.confirm_reading_id.mains_on_load)
        self.assertFalse(self.genset.mains_on_load)
        posted = len(self.relay_posts())
        again = self.enqueue('mains_close_open', source='button', requested_by=self.user_t,
                             target_breaker_closed=False)
        self.run_commands()
        self.assertEqual(again.state, 'not_needed')
        self.assertEqual(len(self.relay_posts()), posted)

    def test_tk13_ac22_gen_breaker_needs_running(self):
        """ТК-13.3 · AC-22: генератор стоїть (``genset_status = 0``) → «Автомат генератора: Замкнути» — «Генератор ще
        не в режимі роботи. Спочатку «Пуск».», команда не створюється."""
        self.assertEqual(self.genset.genset_status, '0')
        with self.assertRaises(UserError) as error:
            self.press('gen_close_open')
        self.assertIn('Спочатку', str(error.exception))
        self.assertFalse(self.genset_commands())
        self.assertFalse(self.relay.commands())

    def test_tk13_ac23_remote_lock(self):
        """ТК-13.4 · AC-23, AC-24: ``remote_lock`` на контролері → бейдж (``remote_lock``), попередження
        «Дистанційне керування заблоковано на контролері»; команда розкладу — «Не надіслано: блокування» без POST,
        повідомлення в чатер; майстер команд від Адміністратора → помилка доступу."""
        self.relay.sim(remote_lock=True, snapshot=True)
        self.pull()
        self.assertTrue(self.genset.remote_lock)
        alarm = self.alarms('remote_lock')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'warn')
        cmd = self.enqueue('manual')
        self.run_commands()
        self.assertEqual(cmd.state, 'blocked')
        self.assertIn('блокування', cmd.result_note or '')
        self.assertFalse(self.relay.commands())
        self.assertChatterContains('блокування')
        with self.assertRaises(AccessError):
            self.press('manual', user=self.user_a)

    def test_tk13_ac26_crank_failure(self):
        """ТК-13.6 · AC-26: Ручний → «Пуск», на стенді невдалий пуск (``crank_failure``) → коли cron перевіряє
        підтвердження, знімки вже показують ``crank_failure = true`` → «Не виконано: невдалий пуск» без повторів
        (один POST ``start``), тривога критична «Невдалий пуск». Оберти прокрутки стартером (250 об/хв у стані 3) не є
        підтвердженням пуску, якщо далі в знімках ``crank_failure``."""
        self.confirm_manual()
        self.relay.sim(crank_failure=True)
        start = self.press('start')
        self.run_commands()
        self.assertTrue(start.relay_cmd_id)
        self.relay.wait_command_final(start.relay_cmd_id)
        self.wait_relay(lambda v: v['crank_failure'] and v['genset_status'] == 0, 'невдалий пуск', timeout=10)
        self.snapshot()
        self.drive(start, FINAL)
        self.assertEqual(start.state, 'failed')
        self.assertIn('невдалий пуск', (start.result_note or '').lower())
        self.assertEqual(len(self.relay_posts('start')), 1)
        alarm = self.alarms('crank_failure_cmd')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'crit')

    def test_tk13_ac27_cloud_press_external_control(self):
        """ТК-13.7 · AC-27: у вікні розкладу в Авто «натиснули» Ручний у застосунку SmartGen (``cloud_press``) →
        подія «Керування не з Odoo: Авто → Ручний (застосунок SmartGen)», «Керує: не з Odoo», попередження;
        Odoo не повертає Авто до наступного переходу (жодної команди за кілька хвилин)."""
        now = self.now()
        self.env['td.genset.schedule'].create({
            'genset_id': self.genset.id, 'dayofweek': kyiv_weekday(now),
            'time_start': float_time(now - timedelta(hours=1)), 'time_end': float_time(now + timedelta(hours=1))})
        self.run_scheduler()                                   # перша оцінка: у вікні, режим уже Авто
        self.relay.sim(cloud_press='manual')
        self.relay.wait_mode('manual')
        self.snapshot()
        self.pull()
        event = self.events('external_control')
        self.assertEqual(len(event), 1)
        self.assertEqual((event.mode_from, event.mode_to), ('auto', 'manual'))
        self.assertIn('SmartGen', event.reason or '')
        self.assertEqual(self.genset.control_source, 'external')
        self.assertEqual(self.alarms('external_control').level, 'warn')
        for _ in range(3):
            self.tick(scheduler=True)
        self.assertFalse(self.genset_commands())
        self.assertFalse(self.relay_posts())
        self.assertEqual(self.genset.controller_mode, 'manual')

    def test_tk13_ac67_stop_without_mains(self):
        """ТК-13.5 · AC-67: генератор працює під навантаженням, мережі немає → у діалозі «Стоп» попередження «Мережі
        немає: після зупинки офіс залишиться без живлення»; після підтвердження ``stop`` «Підтверджено», щойно знімок
        після ``done_utc`` показує охолодження/зупинку і ``gen_on_load = false``."""
        self.run_without_mains()
        self.assertTrue(self.genset.gen_on_load)
        self.assertFalse(self.genset.mains_ok)
        wizard = self.env['td.genset.command.wizard'].with_user(self.user_t).create({
            'genset_id': self.genset.id, 'command': 'stop'})
        self.assertIn('Мережі немає', wizard.warning_text or '')
        stop = self.press('stop')
        self.drive(stop, FINAL)
        self.assertEqual(stop.state, 'done')
        self.assertIn(stop.confirm_reading_id.genset_status, STOP_CONFIRM_STATUSES)
        self.assertFalse(stop.confirm_reading_id.gen_on_load)

    # ------------------------------------------------------------------ ТК-14.3
    def test_tk14_ac18_link_lost_before_confirmation(self):
        """ТК-14.3 · AC-18: ``done`` отримано, а модуль зник до знімка-підтвердження → «Очікує: немає зв'язку», навіть
        після вікна повторів тривоги «не підтверджено» немає; модуль повернувся, перший знімок показує цільовий режим
        → «Підтверджено після відновлення зв'язку». Налаштування сценарію: повтор кожні 5 хв (довше за «зв'язок
        втрачено через 3 хв»), щоб втрата зв'язку настала раніше за повтор."""
        self.config.write({'retry_every_min': 5, 'retry_window_min': 10})
        self.relay.sim(time_scale=1, snapshot_sec=3600)          # 0,5 с між done і зміною режиму на контролері
        cmd = self.press('manual')
        self.run_commands()
        self.assertTrue(cmd.relay_cmd_id)
        self.assertEqual(self.relay.wait_command_final(cmd.relay_cmd_id)['status'], 'done')
        self.relay.sim(link=False)                               # знімка з новим режимом ретранслятор не зробить
        self.relay.sim(time_scale=self.time_scale)
        self.advance(minutes=1)
        self.pull()
        self.run_commands()                                      # sent → awaiting (done_at), знімка ще немає
        self.advance(minutes=3)
        self.pull()                                              # «Немає зв'язку»
        self.assertEqual(self.genset.link_state, 'offline')
        self.run_commands()
        self.assertEqual(cmd.state, 'waiting_link')
        self.assertTrue(cmd.link_lost_during)
        self.advance(minutes=8)                                  # вікно повторів (10 хв від першої спроби) минуло
        self.pull()
        self.run_commands()
        self.assertEqual(cmd.state, 'waiting_link')
        self.assertFalse(self.alarms('cmd_unconfirmed'))
        self.relay.sim(link=True)
        self.relay.wait_tick()
        self.snapshot()
        self.drive(cmd, FINAL)
        self.assertEqual(cmd.state, 'done_late')
        self.assertEqual(cmd.confirm_reading_id.controller_mode, 'manual')
        self.assertEqual(len(self.relay_posts('manual')), 1)
