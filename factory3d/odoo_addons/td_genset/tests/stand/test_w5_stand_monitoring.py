# Part of td_genset (ToDo). Власник файлу: W5 «Стенд і документація».
"""Стенд, етап 1 «Моніторинг»: підключення і перший знімок, «немає даних», журнал 15 хв, зв'язок, здоров'я
ретранслятора, 401/недоступність, відновлення курсору, догон після простою, події і тривоги контролера, генератор
без hostid.

ТК-01…ТК-04, ТК-09, ТК-12.1, ТК-14.1, ТК-14.2, ТК-14.8 · AC-01…AC-11, AC-38, AC-39, AC-41, AC-45, AC-46, AC-57,
AC-60, AC-65.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .relay_harness import free_port
from .stand_common import TdGensetStandCase, tomorrow_kyiv

WRONG_TOKEN = 'stand-wrong-token-0123456789'
# Тривоги «поточного стану», які можуть законно бути активними після догону (не «минулі стани»).
CURRENT_STATE_CODES = {'maintenance_due', 'fuel_stock_low'}


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandMonitoring(TdGensetStandCase):
    """Емулятор зі змінних оточення (``run_stand_tests.sh``), ретранслятор 1.1.3, реальний час."""

    def _check_relay_message(self):
        """«Перевірити зв'язок» від Корист. Т → текст повідомлення (сповіщення або помилка користувачу)."""
        try:
            action = self.genset.with_user(self.user_t).action_check_relay()
        except UserError as exc:
            return str(exc)
        params = (action or {}).get('params') or {}
        return '%s %s' % (params.get('title') or '', params.get('message') or '')

    def _readings_cursor_ids(self):
        cursor = self.genset.readings_cursor
        return [reading['id'] for reading in self.relay.readings() if reading['id'] <= cursor]

    def test_tk01_ac02_check_relay(self):
        """ТК-01.1 · AC-01, AC-02, AC-57: «Перевірити зв'язок» (Корист. Т) показує версію ретранслятора (1.1.3) і стан
        модуля; токена у відповіді немає; інший токен (401) — «Ретранслятор відхилив токен»; ретранслятор
        недоступний — «Ретранслятор недоступний», без трасування у відповіді."""
        message = self._check_relay_message()
        self.assertIn('1.1.3', message)
        self.assertNotIn(self.relay.token, message)
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('td_genset.relay_token', WRONG_TOKEN)
        message = self._check_relay_message()
        self.assertIn('відхилив токен', message)
        self.assertNotIn(WRONG_TOKEN, message)
        self.assertNotIn('Traceback', message)
        icp.set_param('td_genset.relay_token', self.relay.token)
        icp.set_param('td_genset.relay_url', 'http://127.0.0.1:%d/api/v1' % free_port())
        message = self._check_relay_message()
        self.assertIn('недоступний', message)
        self.assertNotIn(self.relay.token, message)
        self.assertNotIn('Traceback', message)

    def test_tk01_ac03_ac05_first_snapshot_no_duplicates(self):
        """ТК-01.2 · AC-03, AC-05, AC-65: перший забір створює кожен знімок ретранслятора один раз (унікальні
        ``relay_id``, курсор = найбільший id); повторний запуск без нових знімків — 0 нових записів; штучне
        повторення сторінки (той самий ``since``) не падає і не дублює. Картка: Режим «Авто», живлення «Мережа»,
        агрегат «Очікування», паливо 138 L (95 % × 145), зв'язок «Онлайн»."""
        self.relay.sim(snapshot_sec=3600)          # без планових знімків під час тесту — лише явні
        for _ in range(3):
            last_id = self.relay.snapshot()
        readings = self.pull()
        ids = readings.mapped('relay_id')
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.genset.readings_cursor, last_id)
        self.assertEqual(ids, self._readings_cursor_ids())
        self.env['td.genset']._cron_pull_readings()
        self.env.invalidate_all()
        self.assertEqual(len(self.odoo_readings()), len(ids))
        self.genset.sudo().write({'readings_cursor': 0})           # та сама сторінка ще раз
        self.env['td.genset']._cron_pull_readings()
        self.env.invalidate_all()
        self.assertEqual(self.odoo_readings().mapped('relay_id'), ids)
        genset = self.genset
        self.assertEqual(genset.controller_mode, 'auto')
        self.assertEqual(genset.feed_source, 'mains')
        self.assertTrue(genset.mains_ok)
        self.assertEqual(genset.genset_status, '0')
        self.assertEqual(genset.genset_stage, 'standby')
        self.assertFalse(genset.is_running)
        self.assertEqual(genset.fuel_liters, 138)
        self.assertEqual(genset.fuel_source, 'pct')
        self.assertEqual(genset.link_state, 'online')
        self.assertEqual(genset.last_reading_id.relay_id, last_id)
        self.assertEqual(genset.relay_version, '1.1.3')
        self.assertTrue(genset.relay_commands_ready)

    def test_tk02_ac06_ac07_no_data_and_semantics(self):
        """ТК-02 · AC-06, AC-07: ``oil_pressure = null`` і ключа ``water_temp_sensor_ohm`` немає → у базі NULL
        («немає даних», не 0), в «Усі значення» — null / ключа немає; ``mains_status = 2`` і ``mains_normal`` →
        «Є мережа»; ``gen_undervoltage`` при зупиненому генераторі — не тривога; при ``genset_status = 9`` —
        попередження «Низька напруга генератора»."""
        self.pull()
        self.relay.sim(set={'oil_pressure': None}, drop=['water_temp_sensor_ohm'], snapshot=True)
        last_id = self.relay.last_reading_id()
        reading = self.pull().filtered(lambda r: r.relay_id == last_id)
        self.assertEqual(len(reading), 1)
        self.assertTrue(self.column_is_null(reading, 'oil_pressure'))
        self.assertTrue(self.column_is_null(reading, 'water_temp_sensor_ohm'))
        values = self.genset.last_values_json or {}
        self.assertIn('oil_pressure', values)
        self.assertIsNone(values['oil_pressure'])
        self.assertNotIn('water_temp_sensor_ohm', values)
        self.assertEqual(reading.mains_status, 2)
        self.assertTrue(reading.mains_ok)
        self.assertTrue(self.genset.mains_ok)
        self.assertTrue(reading.gen_undervoltage)
        self.assertFalse(reading.is_running)
        self.assertFalse(self.alarms('gen_undervoltage'))
        self.relay.sim(set={'genset_status': 9, 'gen_undervoltage': True}, snapshot=True)
        self.pull()
        alarm = self.alarms('gen_undervoltage')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'warn')

    def test_tk03_ac08_journal_last_snapshot_per_slot(self):
        """ТК-03.1 · AC-08: журнал 15 хв — у кожному 15-хвилинному інтервалі за Europe/Kyiv рівно один журнальний
        знімок, і це останній за часом (після кожного нового забору перераховується); ``slot_15`` — початок
        інтервалу (Kyiv, збережений в UTC; зсув Kyiv цілий у годинах, тому межі збігаються з UTC); ``is_hour`` —
        інтервали, що починаються о :00 (фільтр «Погодинно»)."""
        self.relay.sim(snapshot_sec=3600)
        for _ in range(2):
            self.relay.snapshot()
        self.pull()
        for _ in range(2):
            self.relay.snapshot()
        readings = self.pull()
        self.assertGreaterEqual(len(readings), 4)
        by_slot = defaultdict(list)
        for reading in readings:
            slot = reading.ts.replace(minute=reading.ts.minute - reading.ts.minute % 15, second=0, microsecond=0)
            self.assertEqual(reading.slot_15, slot, reading.relay_id)
            self.assertEqual(reading.is_hour, slot.minute == 0, reading.relay_id)
            by_slot[slot].append(reading)
        for slot, items in by_slot.items():
            journal = [reading for reading in items if reading.is_journal]
            self.assertEqual(len(journal), 1, slot)
            self.assertEqual(journal[0], max(items, key=lambda r: (r.ts, r.relay_id)), slot)

    def test_tk14_ac11_relay_health(self):
        """ТК-14.2 · AC-11: ``registers_known = 0`` → тривога-попередження тех. «Ретранслятор не розбирає дані»;
        ``commands_enabled = false`` → бейдж «Керування вимкнено на ретрансляторі», пульт неактивний; умова
        зникла → тривога знята."""
        self.relay.sim(registers_known=0, commands_enabled=False)
        self.pull()
        alarm = self.alarms('relay_health')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'warn')
        self.assertEqual(self.genset.relay_registers_known, 0)
        self.assertFalse(self.genset.relay_commands_enabled)
        self.assertFalse(self.genset.with_user(self.user_t).get_pult_state()['can_control'])
        self.relay.sim(registers_known=55, commands_enabled=True, snapshot=True)
        self.pull()
        self.assertFalse(self.alarms('relay_health'))
        self.assertTrue(self.genset.relay_commands_enabled)

    def test_ac65_cursor_continues_after_relay_restart(self):
        """AC-65 (ТК-06.4, relay_api.md §10): перезапуск ретранслятора з тими самими даними — id знімків
        продовжуються, курсор Odoo продовжується без дублів і пропусків; перший знімок після перезапуску —
        ``reason = first``."""
        self.relay.sim(snapshot_sec=3600)
        self.relay.snapshot()
        self.pull()
        cursor = self.genset.readings_cursor
        self.assertTrue(cursor)
        self.relay.sim(restart=True)
        self.relay.wait_tick()
        self.relay.snapshot()
        readings = self.pull()
        ids = readings.mapped('relay_id')
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(self.genset.readings_cursor, cursor)
        self.assertEqual(ids, self._readings_cursor_ids())
        self.assertIn('first', readings.filtered(lambda r: r.relay_id > cursor).mapped('reason'))

    def _assert_no_token(self, logs, *records):
        secrets = (self.relay.token, WRONG_TOKEN)
        for secret in secrets:
            self.assertFalse([line for line in logs if secret in line], 'токен у логах (AC-57)')
            for record in records:
                for text in (record.name or '', record.description or ''):
                    self.assertNotIn(secret, text, 'токен у тексті тривоги (AC-57)')
            for text in self.chatter_texts():
                self.assertNotIn(secret, text, 'токен у чатері (AC-57)')

    def test_tk14_ac10_ac57_wrong_token(self):
        """ТК-14.2 · AC-10, AC-57: токен змінено (401) — cron не падає, курсор не змінюється, тривога тех.
        «Ретранслятор відхилив токен (401)» (не пізніше ніж за 10 хв); токена немає в логах (DEBUG), тексті
        тривоги і чатері."""
        self.pull()
        cursor = self.genset.readings_cursor
        self.relay.snapshot()
        self.env['ir.config_parameter'].sudo().set_param('td_genset.relay_token', WRONG_TOKEN)
        with self.capture_logs() as logs:
            self.env['td.genset']._cron_pull_readings()
            self.advance_odoo(minutes=11)
            self.env['td.genset']._cron_pull_readings()
        self.env.invalidate_all()
        self.assertEqual(self.genset.readings_cursor, cursor)
        alarm = self.alarms('relay_auth')
        self.assertEqual(len(alarm), 1)
        self.assertIn('401', '%s %s' % (alarm.name, alarm.description or ''))
        self._assert_no_token(logs, alarm)

    def test_tk12_ac10_ac57_relay_unavailable(self):
        """ТК-12.1, ТК-14.2 · AC-10, AC-57: ретранслятор недоступний (порт закрито) — cron не падає, курсор не
        змінюється; через 5 хв тривоги ще немає, через 10 хв — тривога тех. «Ретранслятор недоступний»; токена
        немає в логах (DEBUG) і тексті тривоги."""
        self.pull()
        cursor = self.genset.readings_cursor
        self.env['ir.config_parameter'].sudo().set_param(
            'td_genset.relay_url', 'http://127.0.0.1:%d/api/v1' % free_port())
        with self.capture_logs() as logs:
            self.env['td.genset']._cron_pull_readings()
            self.advance_odoo(minutes=5)
            self.env['td.genset']._cron_pull_readings()
            self.env.invalidate_all()
            self.assertFalse(self.alarms('relay_unavailable'))
            self.advance_odoo(minutes=6)
            self.env['td.genset']._cron_pull_readings()
        self.env.invalidate_all()
        self.assertEqual(self.genset.readings_cursor, cursor)
        alarm = self.alarms('relay_unavailable')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'warn')
        self._assert_no_token(logs, alarm)


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandLink(TdGensetStandCase):
    """Власний емулятор з керованим годинником (зв'язок, пропуски); старт — завтра 10:00 Kyiv."""

    relay_mode = 'own'

    def clock_start_utc(self):
        return tomorrow_kyiv(10)

    def test_tk04_ac09_link_lost_and_restored(self):
        """ТК-04 · AC-09: модуль зупинено → через 3 хв «Немає зв'язку», пульт недоступний, тривоги ще немає (до 10 хв);
        після 10 хв без зв'язку — тривога критична «Немає зв'язку з модулем», рівень 1 (Співробітник) сповіщено;
        модуль запущено → «Онлайн», тривога знята, повідомлення «Зв'язок відновлено…», подія «Зв'язок» закрита."""
        self.pull()
        self.assertEqual(self.genset.link_state, 'online')
        self.relay.sim(link=False)
        self.advance(minutes=3, seconds=30)
        self.relay.sim(seen_ago=210)
        self.pull()
        self.assertEqual(self.genset.link_state, 'offline')
        self.assertTrue(self.events('link').filtered('is_open'))
        self.assertFalse(self.genset.with_user(self.user_t).get_pult_state()['can_control'])
        self.advance(minutes=5)
        self.pull()
        self.run_scheduler()
        self.assertFalse(self.alarms('link_lost'), 'тривога раніше ніж через 10 хв без зв\'язку')
        self.advance(minutes=5)              # 13,5 хв без даних: ≥ 10 хв і від втрати даних, і від «Немає зв'язку»
        self.pull()
        self.run_scheduler()                 # ескалація: рівень 1 — одразу
        alarm = self.alarms('link_lost')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'crit')
        self.assertIn(self.user_s, alarm.notified_user_ids)
        self.relay.sim(link=True)
        self.relay.wait_tick()
        self.snapshot()
        self.pull()
        self.assertEqual(self.genset.link_state, 'online')
        self.assertFalse(self.alarms('link_lost'))
        self.assertFalse(self.events('link').filtered('is_open'))
        self.assertChatterContains('відновлено')

    def test_tk03_ac46_gap_no_data(self):
        """ТК-03.2 · AC-46: модуль 10 хв без зв'язку (знімків немає) → подія «Немає даних» ≈ 10 хв, закрита;
        знімків за пропуск немає (значення не інтерполюються), у журналі 15 хв за цей час записів немає."""
        self.assertTrue(self.pull(), 'знімки не забрано')
        before = self.odoo_readings()[-1]
        self.relay.sim(link=False)
        self.advance(minutes=10)
        self.relay.sim(link=True)
        self.relay.wait_tick()
        self.snapshot()
        readings = self.pull()
        gap = self.events('gap')
        self.assertEqual(len(gap), 1)
        self.assertFalse(gap.is_open)
        self.assertGreaterEqual(gap.date_end - gap.date_start, timedelta(minutes=9))
        self.assertLessEqual(gap.date_end - gap.date_start, timedelta(minutes=11))
        inside = readings.filtered(lambda r: before.ts < r.ts < gap.date_end)
        self.assertFalse(inside)


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandCatchup(TdGensetStandCase):
    """Догон після простою Odoo і помилка посеред сторінок; власний емулятор з годинником (завтра 09:00 Kyiv)."""

    relay_mode = 'own'
    time_scale = 50

    def clock_start_utc(self):
        return tomorrow_kyiv(9)

    def _relay_now(self):
        return datetime.strptime(self.relay.status()['relay']['time_utc'], '%Y-%m-%dT%H:%M:%SZ')

    def test_tk14_ac45_catchup_without_alarm_avalanche(self):
        """ТК-14.1 · AC-45: Odoo не забирав показання ~40 хв, а на стенді були 2 відключення мережі (одне з пуском
        у Авто, одне без пуску в Ручному), 1 робота генератора і тривога контролера, що минула. Після запуску cron
        події створено заднім числом із правильними часами (відключення, робота, тривога — закриті), активних тривог
        і сповіщень за минулі стани немає, у чатері — підсумок «Догнано історію…»; курсор = останній знімок."""
        self.advance(minutes=2)
        outage1_start = self._relay_now()
        self.relay.sim(mains_normal=False)
        self.wait_relay(lambda v: v['genset_status'] == 9 and v['gen_on_load'], 'автопуск без мережі', timeout=8)
        self.advance(minutes=2)
        outage1_end = self._relay_now()
        self.relay.sim(mains_normal=True)
        self.wait_relay(lambda v: v['genset_status'] == 0 and v['mains_on_load'], 'зупинка після мережі', timeout=8)
        self.advance(minutes=2)
        self.relay.sim(set={'low_oil_pressure_warning': True}, snapshot=True)
        self.advance(minutes=2)
        self.relay.sim(set={'low_oil_pressure_warning': False}, snapshot=True)
        self.advance(minutes=2)
        command = self.relay.post_command('manual')
        self.relay.wait_command_final(command['id'])
        self.relay.wait_mode('manual')
        self.relay.sim(mains_normal=False, snapshot=True)
        self.advance(minutes=2)
        self.relay.sim(mains_normal=True, snapshot=True)
        for _ in range(13):                  # 26 хв «тиші»: знімки щохвилини-дві, без пропусків > 3 хв
            self.advance(minutes=2)
        self.relay.snapshot()
        last_id = self.relay.last_reading_id()
        self.pull()
        genset = self.genset
        self.assertEqual(genset.readings_cursor, last_id)
        self.assertFalse(genset.catchup_mode)
        outages = self.events('outage')
        self.assertEqual(len(outages), 2)
        self.assertFalse(outages.filtered('is_open'))
        self.assertLessEqual(abs((outages[0].date_start - outage1_start).total_seconds()), 15)
        self.assertLessEqual(abs((outages[0].date_end - outage1_end).total_seconds()), 15)
        runs = self.events('run')
        self.assertEqual(len(runs), 1)
        self.assertFalse(runs.is_open)
        self.assertGreaterEqual(runs.date_start, outages[0].date_start)
        alarm_events = self.events('alarm')
        self.assertFalse(alarm_events.filtered('is_open'))
        oil = alarm_events.filtered(lambda e: any(
            word in ('%s %s' % (e.reason or '', e.summary or '')).lower() for word in ('oil', 'олив')))
        self.assertEqual(len(oil), 1, 'подія «Тривога контролера: низький тиск оливи» (сигнал — у причині)')
        past = self.alarms().filtered(lambda a: a.code not in CURRENT_STATE_CODES)
        self.assertFalse(past, 'активні тривоги за минулі стани: %s' % past.mapped('code'))
        self.assertFalse(self.alarms(active=False).mapped('notified_user_ids'))
        self.assertChatterContains('Догнано історію')

    def test_tk14_ac04_ac03_page_error_keeps_cursor(self):
        """ТК-14.1 · AC-04, AC-03: на стенді 1 001 знімок (3 сторінки по 500); мережева помилка (стенд «зупинено»)
        з 2-ї сторінки → збережено рівно 500 знімків першої сторінки, курсор = ``next_since`` першої; після
        відновлення наступні запуски продовжують з курсору: усі 1 001 знімок, без пропусків і дублів."""
        self.relay.sim(snapshot_sec=3600)
        while self.relay.last_reading_id() < 1001:
            self.relay.sim(snapshot=True)
        relay_ids = [reading['id'] for reading in self.relay.readings()]

        def page_fails(call, calls):
            pages = [c for c in self.readings_calls(calls) if str(c['params'].get('limit')) != '1']
            return call in pages and pages.index(call) >= 1

        with self.spy_requests(fail=page_fails):
            for _ in range(3):
                self.env['td.genset']._cron_pull_readings()
        self.env.invalidate_all()
        self.assertEqual(self.odoo_readings().mapped('relay_id'), relay_ids[:500])
        self.assertEqual(self.genset.readings_cursor, relay_ids[499])
        readings = self.pull(max_runs=20)
        self.assertEqual(readings.mapped('relay_id'), relay_ids[:len(readings)])
        self.assertEqual(readings.mapped('relay_id'), [rid for rid in relay_ids if rid <= self.genset.readings_cursor])
        self.assertGreaterEqual(len(readings), 1001)
        self.assertEqual(len(set(readings.mapped('relay_id'))), len(readings))


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandEvents(TdGensetStandCase):
    """Події і тривоги контролера в реальному режимі (не догон); власний емулятор, завтра 10:00 Kyiv."""

    relay_mode = 'own'

    def clock_start_utc(self):
        return tomorrow_kyiv(10)

    def test_tk09_ac38_ac39_ac41_outage_run_and_controller_alarm(self):
        """ТК-09.1–09.2 · AC-38, AC-39, AC-41: відключення мережі з пуском у Авто → події «Відключення мережі»
        (вид «Відсутність мережі», «Генератор підхопив за N с») і «Робота генератора» (kWh, пік 12 kW, ΔL < 0, пуск з
        1-ї спроби, причина — зникла мережа), обидві закриваються після повернення мережі; ``low_oil_pressure_warning``
        → попередження і відкрита подія «Тривога контролера»; сигнал зник → тривога «знято», подія закрита."""
        self.pull()
        self.relay.sim(mains_normal=False)
        self.wait_relay(lambda v: v['genset_status'] == 9 and v['gen_on_load'], 'автопуск без мережі', timeout=8)
        self.snapshot()
        self.pull()
        outage, run = self.events('outage'), self.events('run')
        self.assertEqual((len(outage), len(run)), (1, 1))
        self.assertTrue(outage.is_open and run.is_open)
        self.advance(minutes=5)                                  # робота під навантаженням: kWh, паливо
        self.relay.sim(mains_normal=True)
        self.wait_relay(lambda v: v['genset_status'] == 0 and v['mains_on_load'], 'зупинка після мережі', timeout=8)
        self.snapshot()
        self.pull()
        self.assertFalse(outage.is_open)
        self.assertEqual(outage.outage_kind, 'blackout')
        self.assertGreater(outage.time_to_pickup_s, 0)
        self.assertIn('підхопив', outage.summary or '')
        self.assertFalse(run.is_open)
        self.assertGreater(run.energy_kwh, 0)
        self.assertEqual(run.peak_kw, 12)
        self.assertLess(run.fuel_delta_l, 0)
        self.assertEqual(run.crank_attempts, 1)
        self.assertIn('мереж', (run.reason or '').lower())
        self.relay.sim(set={'low_oil_pressure_warning': True}, snapshot=True)
        self.pull()
        alarm = self.alarms('low_oil_pressure_warning')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'warn')
        event = self.events('alarm').filtered(lambda e: e.alarm_id == alarm)
        self.assertEqual(len(event), 1)
        self.assertTrue(event.is_open)
        self.relay.sim(set={'low_oil_pressure_warning': False}, snapshot=True)
        self.pull()
        self.assertEqual(alarm.state, 'cleared')
        self.assertTrue(alarm.date_cleared)
        self.assertFalse(event.is_open)

    def test_tk14_ac60_genset_without_hostid_skipped(self):
        """ТК-14.8 · AC-60: генератор без hostid (опитування увімкнено) — cron пропускає його без винятків і без
        помилок у логах; генератор «Стенд» забирається як звичайно."""
        other = self.env['td.genset'].create({
            'name': 'Без модуля', 'controller_model_id': self.controller_model.id, 'power_kw': 10.0,
            'relay_enabled': True})
        with self.assertNoLogs('odoo.addons.td_genset', level='ERROR'):
            self.pull()
            self.run_scheduler()
        self.assertTrue(self.odoo_readings())
        self.assertFalse(self.env['td.genset.reading'].search_count([('genset_id', '=', other.id)]))
