# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""run/outage/refuel/drain/external/alarm/gap (AC-27, AC-38…AC-41, AC-46).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
from datetime import datetime, timedelta

from freezegun import freeze_time

from odoo.tests import tagged

from .common import TdGensetCase, snapshot

T = datetime(2026, 10, 7, 9, 0, 0)        # 12:00 за Києвом


@tagged('standard', 'at_install')
class TestW1Events(TdGensetCase):

    def _feed(self, steps, live=True):
        """Знімки ``(ts, values[, reason])``: ``live`` — забір після кожного (без догону), інакше один забір."""
        for step in steps:
            ts, values = step[0], step[1]
            reason = step[2] if len(step) > 2 else 'change'
            with freeze_time(ts):
                self.push_reading(values, reason=reason, ts=ts)
            if live:
                with freeze_time(ts + timedelta(seconds=5)):
                    self.run_pull()
        if not live:
            with freeze_time(steps[-1][0] + timedelta(seconds=5)):
                self.run_pull()

    def _events(self, kind):
        return self.env['td.genset.event'].search([('genset_id', '=', self.genset.id), ('event_type', '=', kind)],
                                                  order='date_start')

    def _alarm(self, code, states=('active', 'acked')):
        return self.env['td.genset.alarm'].search([('genset_id', '=', self.genset.id), ('code', '=', code),
                                                   ('state', 'in', list(states))])

    def test_ac38_run_event(self):
        """AC-38: 0→1→3→4→3→5…→9 (під навантаженням, АКБ при прокрутці 22,1 і 21,9) →10→15→0; kWh 251→261;
        пік 8,4 kW; паливо 61→57 % → подія з тривалістю, 10 kWh, 8,4 kW, −6 L, 2 спроби, 21,9 V."""
        def snap(status, energy=251, fuel=61, **values):
            return snapshot(genset_status=status, energy_kwh=energy, fuel_level=fuel, **values)

        load = {'gen_on_load': True, 'mains_on_load': False}
        steps = [
            (T, snap(0), 'interval'),
            (T + timedelta(seconds=30), snap(1)),
            (T + timedelta(seconds=40), snap(3, battery_v=22.1)),
            (T + timedelta(seconds=50), snap(4)),
            (T + timedelta(seconds=60), snap(3, battery_v=21.9)),
            (T + timedelta(seconds=70), snap(5)),
            (T + timedelta(seconds=80), snap(6)),
            (T + timedelta(seconds=90), snap(7)),
            (T + timedelta(seconds=100), snap(8)),
            (T + timedelta(seconds=110), snap(9, active_power=6.0, **load)),
            (T + timedelta(seconds=170), snap(9, energy=255, active_power=8.4, **load), 'interval'),
            (T + timedelta(seconds=230), snap(9, energy=261, fuel=57, active_power=7.0, **load), 'interval'),
            (T + timedelta(seconds=290), snap(10, energy=261, fuel=57)),
            (T + timedelta(seconds=350), snap(15, energy=261, fuel=57)),
            (T + timedelta(seconds=400), snap(0, energy=261, fuel=57)),
        ]
        self._feed(steps, live=False)
        run = self._events('run')
        self.assertEqual(len(run), 1)
        self.assertEqual((run.date_start, run.date_end), (T + timedelta(seconds=30), T + timedelta(seconds=350)))
        self.assertAlmostEqual(run.duration, 320 / 3600.0)
        self.assertEqual(run.energy_kwh, 10.0)
        self.assertAlmostEqual(run.peak_kw, 8.4)
        self.assertEqual(run.fuel_delta_l, -6.0)
        self.assertEqual(run.crank_attempts, 2)
        self.assertAlmostEqual(run.crank_min_battery_v, 21.9)
        self.assertEqual(run.reason, 'Пуск не з Odoo')
        self.assertEqual(run.summary, 'Пуск з 2-ї спроби, навантаження прийнято; зупинено не з Odoo')
        self.assertTrue(run.is_bad)
        self.assertFalse(self.genset.open_run_event_id)
        self.assertIn('Точність', self.env['td.genset.event']._fields['crank_min_battery_v'].help)

    def test_ac38_run_reason_from_odoo_command(self):
        """2.8.1: пуск після команди Odoo «Пуск» → причина «Кнопка «Пуск» · <хто>», зв'язок з командою."""
        command = self.env['td.genset.command'].create({
            'genset_id': self.genset.id, 'command': 'start', 'source': 'button', 'user_id': self.user_t.id,
            'state': 'awaiting', 'sent_at': T - timedelta(seconds=20)})
        self._feed([(T - timedelta(seconds=30), snapshot(), 'interval'),
                    (T, snapshot(genset_status=1))])
        run = self._events('run')
        self.assertEqual(run.reason, 'Кнопка «Пуск» · %s' % self.user_t.name)
        self.assertEqual(run.command_id, command)
        self.assertTrue(run.is_open)

    def test_d07_run_reasons_by_facts(self):
        """D-07 (ТК-09.1, ТК-13.5): причини «Роботи» за фактами. Тест з навантаженням → «Тест · хто», зупинка після
        команди «Авто» кінця тесту; через 9 хв зникла мережа в Авто → «Зникла мережа · режим Авто», а не «Тест»
        (команда тесту вже причина першої роботи; розклад вимкнено — без «за розкладом»); «Стоп» з пульта без
        мережі → «зупинено командою «Стоп» (кнопка · хто) — мережі ще не було», а не «за розкладом»."""
        Command = self.env['td.genset.command']

        def command(name, source, done):
            return Command.create({'genset_id': self.genset.id, 'command': name, 'source': source,
                                   'user_id': self.user_t.id, 'state': 'done', 'sent_at': done - timedelta(seconds=3),
                                   'done_at': done})

        lost = {'mains_normal': False, 'mains_on_load': False}
        test = command('test', 'test', T + timedelta(seconds=13))
        self._feed([(T, snapshot(), 'interval'),
                    (T + timedelta(seconds=20), snapshot(genset_status=1, controller_mode='test')),
                    (T + timedelta(minutes=1), snapshot(genset_status=9, controller_mode='test', gen_on_load=True,
                                                        mains_on_load=False))])
        command('auto', 'test', T + timedelta(minutes=3, seconds=3))
        self._feed([(T + timedelta(minutes=3, seconds=30), snapshot(genset_status=10)),
                    (T + timedelta(minutes=4), snapshot(genset_status=0)),
                    (T + timedelta(minutes=9), snapshot(**lost)),
                    (T + timedelta(minutes=9, seconds=20), snapshot(genset_status=3, **lost)),
                    (T + timedelta(minutes=10), snapshot(genset_status=9, gen_on_load=True, **lost))])
        command('stop', 'button', T + timedelta(minutes=12))
        self._feed([(T + timedelta(minutes=12, seconds=30), snapshot(genset_status=10, **lost)),
                    (T + timedelta(minutes=13), snapshot(genset_status=0, **lost))])
        first, second = self._events('run')
        self.assertEqual((first.reason, first.command_id), ('Тест · %s' % self.user_t.name, test))
        self.assertEqual(first.summary, 'Пуск з 1-ї спроби, навантаження прийнято; зупинено командою «Авто» (тест)')
        self.assertEqual(second.reason, 'Зникла мережа · режим Авто')
        self.assertFalse(second.command_id)
        self.assertEqual(second.summary, 'Пуск з 1-ї спроби, навантаження прийнято; зупинено командою «Стоп» '
                                         '(кнопка · %s) — мережі ще не було' % self.user_t.name)
        body = ' '.join(self.env['mail.message'].search([('model', '=', 'td.genset'),
                                                         ('res_id', '=', self.genset.id)]).mapped('body'))
        self.assertIn('Зникла мережа · режим Авто', body)
        self.assertNotIn('за розкладом', body)

    def test_ac39_outage_with_pickup(self):
        """AC-39: мережа зникла 11:51 і повернулась 13:47, генератор 11:51:25–13:50 → подія 1 год 56 хв,
        вид «Обрив фази», «Генератор підхопив за 25 с»."""
        start = datetime(2026, 10, 7, 8, 51, 0)          # 11:51 за Києвом
        back = datetime(2026, 10, 7, 10, 47, 0)          # 13:47
        lost = {'mains_normal': False, 'mains_loss_phase': True, 'mains_blackout': False, 'mains_fault': False,
                'mains_on_load': False}
        running = dict(lost, genset_status=9, gen_on_load=True)
        steps = [(start - timedelta(minutes=1), snapshot(), 'interval'),
                 (start, snapshot(**lost)),
                 (start + timedelta(seconds=10), snapshot(genset_status=3, **lost)),
                 (start + timedelta(seconds=25), snapshot(**running))]
        stamp = start + timedelta(minutes=2)
        while stamp < back:
            steps.append((stamp, snapshot(**running), 'interval'))
            stamp += timedelta(minutes=2)
        steps.append((back, snapshot(genset_status=9, gen_on_load=True, mains_on_load=False)))
        # той самий момент: навантаження вже повернулося на мережу (кілька change-знімків в одну секунду)
        steps.append((back, snapshot(genset_status=10, mains_on_load=True)))
        steps.append((back + timedelta(minutes=3), snapshot()))
        self._feed(steps, live=False)
        outage = self._events('outage')
        self.assertEqual(len(outage), 1)
        self.assertEqual((outage.date_start, outage.date_end), (start, back))
        self.assertAlmostEqual(outage.duration, 116 / 60.0)
        self.assertEqual(outage.outage_kind, 'loss_phase')
        self.assertEqual(outage.time_to_pickup_s, 25)
        self.assertEqual(outage.summary, 'Генератор підхопив за 25 с')
        self.assertFalse(outage.is_bad)
        run = self._events('run')
        self.assertEqual(run.reason, 'Зникла мережа · режим Авто')
        self.assertEqual(run.summary, 'Пуск з 1-ї спроби, навантаження прийнято; мережа повернулася')
        self.assertEqual(run.date_end, back + timedelta(minutes=3))

    def test_ac39_outage_without_run(self):
        """AC-39: без роботи генератора в режимі Ручний → «Генератор не запускався — поза розкладом (режим Ручний)»."""
        manual = {'controller_mode': 'manual'}
        self._feed([(T, snapshot(**manual), 'interval'),
                    (T + timedelta(minutes=1), snapshot(mains_normal=False, **manual)),
                    (T + timedelta(minutes=3), snapshot(mains_normal=False, **manual), 'interval'),
                    (T + timedelta(minutes=5), snapshot(**manual))])
        outage = self._events('outage')
        self.assertEqual(outage.summary, 'Генератор не запускався — поза розкладом (режим Ручний)')
        self.assertEqual(outage.outage_kind, 'blackout')
        self.assertTrue(outage.is_bad)
        self.assertFalse(self._events('run'))

    def test_ac40_refuel_and_drain(self):
        """AC-40: 35 % → 95 % за 2 хв (стоїть) → «Заправка +87 L (51 → 138 L)» без тривоги; іншої ночі
        46 % → 38 % за 25 хв (стоїть) → «Падіння рівня −12 L (67 → 55 L)» + критична тривога «можливий злив»;
        1 % (1,45 L) подій не створює; падіння під час роботи — не «падіння без роботи»."""
        self._feed([(T, snapshot(fuel_level=35), 'interval'),
                    (T + timedelta(minutes=1), snapshot(fuel_level=60), 'interval'),
                    (T + timedelta(minutes=2), snapshot(fuel_level=95), 'interval'),
                    (T + timedelta(minutes=3), snapshot(fuel_level=95), 'interval'),
                    (T + timedelta(minutes=4), snapshot(fuel_level=94), 'interval')])
        refuel = self._events('refuel')
        self.assertEqual(len(refuel), 1)
        self.assertEqual(refuel.fuel_delta_l, 87.0)
        self.assertEqual(refuel.summary, '51 → 138 L')
        self.assertEqual(refuel.display_name, 'Заправка +87 L (51 → 138 L)')
        self.assertFalse(self._events('drain'))
        self.assertFalse(self.env['td.genset.alarm'].search([('genset_id', '=', self.genset.id),
                                                             ('level', '=', 'crit')]))
        night = datetime(2026, 10, 8, 21, 0, 0)
        self._feed([(night + timedelta(minutes=minute), snapshot(fuel_level=level), 'interval')
                    for minute, level in ((0, 46), (5, 45), (10, 44), (15, 42), (20, 40), (25, 38))])
        drain = self._events('drain')
        self.assertEqual(len(drain), 1)
        self.assertEqual(drain.fuel_delta_l, -12.0)
        self.assertEqual(drain.summary, '67 → 55 L — можливий злив')
        self.assertEqual(drain.display_name, 'Падіння рівня палива −12 L (67 → 55 L)')
        self.assertTrue(drain.is_bad)
        alarm = self._alarm('drain')
        self.assertEqual(alarm.level, 'crit')
        self.assertIn('Можливий злив', alarm.description)
        self.assertEqual(alarm.source_ref, drain)
        # падіння під час роботи генератора — не злив
        later = datetime(2026, 10, 9, 9, 0, 0)
        self._feed([(later + timedelta(minutes=minute), snapshot(fuel_level=level, genset_status=9), 'interval')
                    for minute, level in ((0, 46), (5, 44), (10, 42), (15, 40), (20, 38))])
        self.assertEqual(len(self._events('drain')), 1)

    def test_ac41_controller_alarms(self):
        """AC-41: ``low_oil_pressure_warning`` true → тривога-попередження і подія «Тривога контролера»; false →
        «знято о HH:MM», подія закрита; ``common_shutdown`` + ``low_fuel_shutdown`` → критична «Аварійна зупинка:
        низький рівень палива»."""
        self._feed([(T, snapshot(), 'interval'),
                    (T + timedelta(seconds=30), snapshot(low_oil_pressure_warning=True))])
        alarm = self._alarm('low_oil_pressure_warning')
        self.assertEqual((alarm.level, alarm.state), ('warn', 'active'))
        self.assertEqual(alarm.name, 'Попередження: низький тиск оливи')
        event = self._events('alarm')
        self.assertTrue(event.is_open)
        self.assertEqual(event.alarm_id, alarm)
        self.assertEqual(event.display_name, 'Тривога контролера: Попередження: низький тиск оливи')
        self._feed([(T + timedelta(seconds=90), snapshot(low_oil_pressure_warning=False))])
        self.assertEqual(alarm.state, 'cleared')
        self.assertEqual(alarm.date_cleared, T + timedelta(seconds=95))
        self.assertFalse(event.is_open)
        self.assertEqual(event.date_end, T + timedelta(seconds=90))
        cleared = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id),
                                                   ('body', 'ilike', 'знято о 12:01')])
        self.assertTrue(cleared)
        self._feed([(T + timedelta(seconds=120), snapshot(common_shutdown=True, low_fuel_shutdown=True,
                                                          common_alarm=True))])
        crit = self._alarm('low_fuel_shutdown')
        self.assertEqual((crit.level, crit.name), ('crit', 'Аварійна зупинка: низький рівень палива'))
        self.assertFalse(self._alarm('common_shutdown'))
        self.assertFalse(self.genset.open_alarm_codes.get('low_oil_pressure_warning'))
        self.assertIn('low_fuel_shutdown', self.genset.open_alarm_codes)

    def test_ac46_gap_is_not_interpolated(self):
        """AC-46: пропуск 40 хв між знімками → подія «Немає даних 40 хв», у журналі за цей час записів немає."""
        self._feed([(T, snapshot(), 'interval'),
                    (T + timedelta(minutes=1), snapshot(), 'interval'),
                    (T + timedelta(minutes=41), snapshot(), 'interval'),
                    (T + timedelta(minutes=42), snapshot(), 'interval')])
        gap = self._events('gap')
        self.assertEqual(len(gap), 1)
        self.assertEqual((gap.date_start, gap.date_end), (T + timedelta(minutes=1), T + timedelta(minutes=41)))
        self.assertEqual(gap.summary, 'Немає даних 40 хв')
        readings = self.env['td.genset.reading'].search([
            ('genset_id', '=', self.genset.id), ('ts', '>', T + timedelta(minutes=1)),
            ('ts', '<', T + timedelta(minutes=41))])
        self.assertFalse(readings)

    def test_ac27_external_control_events(self):
        """AC-27 (подія): новий запис ``cloud_commands_seen`` і знімок ``change`` з ``manual`` → одна подія
        «Керування не з Odoo: Авто → Ручний (застосунок SmartGen)», «Керує: не з Odoo», попередження в чатер;
        зміна на панелі — «(панель контролера)»; зміна за командою Odoo — не подія."""
        self._feed([(T, snapshot(), 'interval')])
        self.assertTrue(self.genset.cloud_cmd_last_utc)
        with freeze_time(T + timedelta(seconds=60)):
            self.relay.cloud_press('manual', ts=T + timedelta(seconds=60))
        with freeze_time(T + timedelta(seconds=70)):
            self.run_pull()
        events = self._events('external_control')
        self.assertEqual(len(events), 1)
        self.assertEqual(events.display_name, 'Керування не з Odoo: Авто → Ручний (застосунок SmartGen)')
        self.assertEqual((events.mode_from, events.mode_to, events.reason), ('auto', 'manual', 'застосунок SmartGen'))
        self.assertEqual(self.genset.control_source, 'external')
        alarm = self._alarm('external_control')
        self.assertEqual(alarm.level, 'warn')
        self.assertIn('Режим не повертається до наступного переходу', alarm.description)
        posted = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id),
                                                  ('subtype_id', '=', self.env.ref('td_genset.mt_alarm').id)])
        self.assertTrue(posted.filtered(lambda message: 'Керування не з Odoo' in message.body))
        # панель контролера: Ручний → Стоп без команди Odoo
        self._feed([(T + timedelta(seconds=200), snapshot(controller_mode='stop'))])
        events = self._events('external_control')
        self.assertEqual(len(events), 2)
        self.assertEqual(events[-1].summary, 'Ручний → Стоп (панель контролера)')
        # команда Odoo «Авто» → зміна режиму не є «керуванням не з Odoo»
        self.env['td.genset.command'].create({
            'genset_id': self.genset.id, 'command': 'auto', 'source': 'button', 'state': 'awaiting',
            'sent_at': T + timedelta(seconds=290)})
        self._feed([(T + timedelta(seconds=300), snapshot(controller_mode='auto'))])
        self.assertEqual(len(self._events('external_control')), 2)

    def test_ac27_external_breaker_in_manual(self):
        """2.8.1: у режимі Ручний автомат змінився без команди Odoo → «Автомат мережі: розімкнено (панель
        контролера)»; з командою Odoo «Автомат мережі» — події немає."""
        manual = {'controller_mode': 'manual'}
        self._feed([(T, snapshot(**manual), 'interval'),
                    (T + timedelta(seconds=30), snapshot(mains_on_load=False, **manual))])
        event = self._events('external_control')
        self.assertEqual(event.summary, 'Автомат мережі: розімкнено (панель контролера)')
        self.assertFalse(event.mode_to)
        self.env['td.genset.command'].create({
            'genset_id': self.genset.id, 'command': 'mains_close_open', 'source': 'button', 'state': 'done',
            'sent_at': T + timedelta(minutes=19)})
        self._feed([(T + timedelta(minutes=20), snapshot(mains_on_load=True, **manual))])
        self.assertEqual(len(self._events('external_control')), 1)
