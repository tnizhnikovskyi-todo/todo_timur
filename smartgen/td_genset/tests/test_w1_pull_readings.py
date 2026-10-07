# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""сторінки, курсор, дублі, відкат, догон, оми з raw/ключів (AC-03, AC-04, AC-45, AC-68).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TdGensetCase, snapshot

NOW = datetime(2026, 10, 7, 12, 0, 0)


@tagged('standard', 'at_install')
class TestW1PullReadings(TdGensetCase):

    def _readings(self):
        return self.env['td.genset.reading'].search([('genset_id', '=', self.genset.id)])

    def _push_series(self, count, start, step=timedelta(minutes=1), **values):
        for index in range(count):
            self.push_reading(snapshot(**values), ts=start + index * step)

    def _null(self, reading, column):
        self.env.flush_all()
        self.env.cr.execute('SELECT %s IS NULL FROM td_genset_reading WHERE id = %%s' % column, (reading.id,))
        return self.env.cr.fetchone()[0]

    def test_ac03_pages_cursor_no_duplicates(self):
        """AC-03: 1 200 знімків, курсор 0 → 1 200 записів з унікальними relay_id, курсор = max id;
        повторний запуск і повторення тієї самої сторінки (той самий since) дублів не створюють."""
        with freeze_time(NOW):
            self._push_series(1200, NOW - timedelta(minutes=1200))
            for _i in range(3):
                self.run_pull()
            readings = self._readings()
            self.assertEqual(len(readings), 1200)
            self.assertEqual(len(set(readings.mapped('relay_id'))), 1200)
            self.assertEqual(self.genset.readings_cursor, 1200)
            self.run_pull()
            self.assertEqual(len(self._readings()), 1200)
            self.genset.sudo().readings_cursor = 500
            self.run_pull()
            self.assertEqual(len(self._readings()), 1200)
            self.assertEqual(self.genset.readings_cursor, 1000)
            payloads = [self.relay.reading_json(reading) for reading in self.relay.readings[:10]]
            created = self.env['td.genset.reading']._create_from_payload(self.genset, payloads)
            self.assertFalse(created)
            self.assertEqual(self.genset.last_reading_id.relay_id, 1200)

    def test_ac04_page_is_one_transaction(self):
        """AC-04: помилка мережі на другій сторінці → збережено рівно 500 знімків, курсор = next_since першої;
        після відновлення забір продовжується без пропусків; збій посеред сторінки відкочує всю сторінку."""
        with freeze_time(NOW):
            self._push_series(1500, NOW - timedelta(minutes=1500))
            self.run_pull()
            self.assertEqual((len(self._readings()), self.genset.readings_cursor), (500, 500))
            self.relay.fail('connection', path='/readings')
            with mute_logger('odoo.addons.td_genset.models.genset_monitoring'):
                self.assertIsNone(self.run_pull())
            self.assertEqual((len(self._readings()), self.genset.readings_cursor), (500, 500))
            self.relay.fail(None)
            event_model = type(self.env['td.genset.event'])
            with patch.object(event_model, '_td_process', side_effect=ValueError('збій посеред сторінки')), \
                    self.assertLogs('odoo.addons.td_genset.models.genset_monitoring', level='WARNING') as logs:
                self.run_pull()
            self.assertIn('збій посеред сторінки', logs.output[0])
            self.assertEqual((len(self._readings()), self.genset.readings_cursor), (500, 500))
            self.run_pull()
            self.run_pull()
            readings = self._readings()
            self.assertEqual((len(readings), self.genset.readings_cursor), (1500, 1500))
            self.assertEqual(sorted(readings.mapped('relay_id')), list(range(1, 1501)))

    def test_ac45_catchup_without_alarm_avalanche(self):
        """AC-45: 5 днів історії з 2 відключеннями, 1 роботою і тривогою, що минула → події заднім числом,
        без активних тривог і сповіщень; один підсумок «Догнано історію»; одна сторінка — один крок
        (``_notify_progress``)."""
        start = NOW - timedelta(days=5)
        step = timedelta(minutes=3)
        count = 5 * 24 * 20
        outages = [(300, 340), (1500, 1530)]
        run = (1505, 1525)
        alarm = (2000, 2010)
        with freeze_time(NOW):
            for index in range(count):
                values = {}
                if any(begin <= index < end for begin, end in outages):
                    values['mains_normal'] = False
                if run[0] <= index < run[1]:
                    values.update(genset_status=9, gen_on_load=True, mains_on_load=False, energy_kwh=260)
                if alarm[0] <= index < alarm[1]:
                    values.update(low_oil_pressure_warning=True, common_warning=True)
                self.push_reading(snapshot(**values), ts=start + index * step)
            self.genset.sudo().catchup_from_date = (start - timedelta(days=1)).date()
            progress = []
            cron_model = type(self.env['ir.cron'])

            def notify(cron, **kwargs):
                progress.append((kwargs['done'], kwargs['remaining']))

            with patch.object(cron_model, '_notify_progress', notify):
                for _i in range(6):
                    self.run_pull()
            self.assertEqual(progress[:5], [(500, 1)] * 4 + [(400, 0)])
            events = self.env['td.genset.event'].search([('genset_id', '=', self.genset.id)])
            by_type = {kind: events.filtered(lambda event, kind=kind: event.event_type == kind)
                       for kind in ('outage', 'run', 'alarm')}
            self.assertEqual(len(by_type['outage']), 2)
            self.assertEqual(len(by_type['run']), 1)
            self.assertEqual(len(by_type['alarm']), 1)
            self.assertFalse(by_type['alarm'].is_open)
            self.assertEqual(by_type['alarm'].date_start, start + alarm[0] * step)
            self.assertEqual(by_type['alarm'].date_end, start + alarm[1] * step)
            self.assertEqual(sorted(by_type['outage'].mapped('date_start')),
                             [start + outages[0][0] * step, start + outages[1][0] * step])
            self.assertFalse(self.env['td.genset.alarm'].search([('genset_id', '=', self.genset.id)]))
            self.assertFalse(self.env['mail.message'].search([('message_type', '=', 'user_notification'),
                                                              ('model', '=', 'td.genset')]))
            summaries = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id),
                                                         ('body', 'ilike', 'Догнано історію')])
            self.assertEqual(len(summaries), 1)
            self.assertIn('5 днів, 2400 знімків', summaries.body)
            self.assertFalse(self.genset.catchup_mode)
            self.assertEqual(self.genset.readings_cursor, count)

    def test_ac45_first_pull_starts_from_catchup_date(self):
        """AC-45, А.7: перший забір (курсор 0) — бінарний пошук першого знімка не старшого за «Починати історію з»."""
        start = NOW - timedelta(days=10)
        with freeze_time(NOW):
            self._push_series(200, start, step=timedelta(hours=1))
            self.genset.sudo().catchup_from_date = (NOW - timedelta(days=3)).date()
            self.run_pull()
            readings = self._readings()
            limit = datetime(2026, 10, 3, 21, 0)    # 04.10 00:00 Europe/Kyiv
            self.assertTrue(readings)
            self.assertGreaterEqual(min(readings.mapped('ts')), limit)
            self.assertEqual(min(readings.mapped('ts')), limit)
            probes = [call for call in self.relay.calls if call['path'] == '/readings'
                      and call['params'].get('limit') == '1']
            self.assertLessEqual(len(probes), 10)

    def test_ac68_ohms_from_raw_image_v111(self):
        """AC-68: ретранслятор 1.1.1, режим «auto» → запити з raw=1; оми з regs 22/18/20 ÷ 10; решта regs/coils
        не зберігається; літри 136 за % (калібрування порожнє)."""
        self.relay.version = '1.1.1'
        with freeze_time(NOW):
            self.push_reading(snapshot(fuel_level=94, fuel_sensor_ohm=188.6, water_temp_sensor_ohm=515.4,
                                       oil_pressure_sensor_ohm=9.5), ts=NOW - timedelta(seconds=30))
            self.run_pull()
        # сторінки — з raw=1 (проби бінарного пошуку курсору limit=1 образу не потребують)
        calls = [call for call in self.relay.calls if call['path'] == '/readings' and call['params']['limit'] != '1']
        self.assertTrue(calls and all(call['params'].get('raw') == '1' for call in calls))
        reading = self._readings()
        self.assertEqual(len(reading), 1)
        self.assertAlmostEqual(reading.fuel_sensor_ohm, 188.6)
        self.assertAlmostEqual(reading.water_temp_sensor_ohm, 515.4)
        self.assertAlmostEqual(reading.oil_pressure_sensor_ohm, 9.5)
        self.assertFalse(reading.values_extra)
        self.assertEqual((reading.fuel_liters, reading.fuel_source), (136.0, 'pct'))
        self.assertAlmostEqual(self.genset.fuel_sensor_ohm, 188.6)
        self.assertEqual(self.genset.last_values_json['fuel_level_sensor_ohm'], 188.6)
        self.assertNotIn('regs', self.genset.last_values_json)

    def test_ac68_ohms_from_keys_v113(self):
        """AC-68: ретранслятор 1.1.3 з ключами *_sensor_ohm → запити без raw=1, оми з ключів."""
        with freeze_time(NOW):
            self.push_reading(snapshot(fuel_sensor_ohm=188.6), ts=NOW - timedelta(seconds=90))
            self.run_pull()
            self.push_reading(snapshot(fuel_sensor_ohm=188.4), ts=NOW - timedelta(seconds=30))
            self.run_pull()
        calls = [call for call in self.relay.calls if call['path'] == '/readings']
        self.assertTrue(calls and not any('raw' in call['params'] for call in calls))
        self.assertAlmostEqual(self.genset.fuel_sensor_ohm, 188.4)
        self.assertAlmostEqual(self.genset.water_temp_sensor_ohm, 515.4)
        # 1.1.3, але в останньому знімку ключів немає → наступний запит з raw=1
        self.genset.sudo().last_values_json = {'fuel_level': 90}
        self.assertTrue(self.genset._need_raw(self.relay.status_json()))

    def test_ac68_raw_mode_no_keeps_null(self):
        """AC-68: «Читати сирі регістри» = ні, 1.1.1 без ключів → без raw=1, оми NULL, помилок немає."""
        self.relay.version = '1.1.1'
        self.config.raw_regs_mode = 'no'
        with freeze_time(NOW):
            self.push_reading(snapshot(), ts=NOW - timedelta(seconds=30))
            self.run_pull()
        calls = [call for call in self.relay.calls if call['path'] == '/readings']
        self.assertTrue(calls and not any('raw' in call['params'] for call in calls))
        reading = self._readings()
        for column in ('fuel_sensor_ohm', 'water_temp_sensor_ohm', 'oil_pressure_sensor_ohm'):
            self.assertTrue(self._null(reading, column), column)
        self.assertNotIn('fuel_level_sensor_ohm', self.genset.last_values_json)
        self.config.raw_regs_mode = 'yes'
        self.relay.version = '1.1.3'
        self.assertTrue(self.genset._need_raw(self.relay.status_json()))
