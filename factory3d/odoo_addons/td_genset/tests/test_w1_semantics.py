# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""null/відсутні ключі/mains_normal/is_running (AC-05, AC-06, AC-07).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
from datetime import datetime, timedelta

from freezegun import freeze_time

from odoo.tests import tagged

from .common import TdGensetCase, snapshot

NOW = datetime(2026, 10, 7, 12, 0, 0)


@tagged('standard', 'at_install')
class TestW1Semantics(TdGensetCase):

    def _pull(self, values, ts=None, reason='interval'):
        stamp = ts or NOW - timedelta(seconds=20)
        with freeze_time(stamp + timedelta(seconds=20)):
            self.push_reading(values, reason=reason, ts=stamp)
            self.run_pull()
        return self.genset.last_reading_id

    def _is_null(self, reading, column):
        self.env.flush_all()
        self.env.cr.execute('SELECT %s IS NULL FROM td_genset_reading WHERE id = %%s' % column, (reading.id,))
        return self.env.cr.fetchone()[0]

    def _alarm(self, code):
        return self.env['td.genset.alarm'].search([('genset_id', '=', self.genset.id), ('code', '=', code),
                                                   ('state', '!=', 'cleared')])

    def test_ac05_current_state_on_card(self):
        """AC-05: Авто, мережа в нормі і під навантаженням, стан 0, паливо 95 % × 145 L → «Авто», «Мережа»,
        «Очікування», 138 L, «Онлайн»."""
        reading = self._pull(snapshot(controller_mode='auto', mains_normal=True, mains_on_load=True, genset_status=0,
                                      fuel_level=95))
        genset = self.genset
        self.assertEqual(genset.controller_mode, 'auto')
        self.assertEqual(genset.feed_source, 'mains')
        self.assertEqual((genset.genset_status, genset.genset_stage), ('0', 'standby'))
        self.assertTrue(genset.mains_ok)
        self.assertFalse(genset.is_running)
        self.assertEqual((genset.fuel_liters, genset.fuel_source), (138.0, 'pct'))
        self.assertEqual(genset.link_state, 'online')
        self.assertEqual(genset.last_reading_at, reading.ts)
        self.assertEqual((genset.energy_kwh, genset.run_hours, genset.start_count), (253.0, 34, 39))
        self.assertAlmostEqual(genset.run_hours_total, 34 + 51 / 60.0)
        self.assertEqual(reading.reason, 'first')

    def test_ac06_null_and_missing_keys(self):
        """AC-06: ``oil_pressure = null`` → у базі NULL, «немає даних» (last_values_json), у графік точка не
        потрапляє; ключа ``water_temp_sensor_ohm`` немає → у «Поточних даних» рядка немає (ключа немає)."""
        first = self._pull(snapshot(oil_pressure=300), ts=NOW - timedelta(minutes=2))
        values = snapshot(oil_pressure=None)
        del values['water_temp_sensor_ohm']
        reading = self._pull(values)
        self.assertTrue(self._is_null(reading, 'oil_pressure'))
        self.assertTrue(self._is_null(reading, 'water_temp_sensor_ohm'))
        self.assertFalse(self._is_null(reading, 'water_temp'))
        last_values = self.genset.last_values_json
        self.assertIn('oil_pressure', last_values)
        self.assertIsNone(last_values['oil_pressure'])
        self.assertNotIn('water_temp_sensor_ohm', last_values)
        # графік/pivot: NULL не входить в агрегат (avg лише по знімку з даними)
        groups = self.env['td.genset.reading']._read_group(
            [('id', 'in', (first | reading).ids)], [], ['oil_pressure:avg'])
        self.assertEqual(groups[0][0], 300.0)
        alarm = self._alarm('sensor_oil_pressure')
        self.assertEqual(alarm.level, 'warn')
        self.assertEqual(alarm.name, 'Немає даних з датчика тиску оливи')
        # дані повернулися → тривога знята
        self._pull(snapshot(oil_pressure=310), ts=NOW + timedelta(minutes=1))
        self.assertFalse(self._alarm('sensor_oil_pressure'))

    def test_ac06_unknown_keys_to_values_extra(self):
        """AC-06, ФВ-40: невідомі ключі нової версії ретранслятора → values_extra; *_text не зберігаються."""
        reading = self._pull(snapshot(new_register_99=42))
        self.assertEqual(reading.values_extra, {'new_register_99': 42})
        self.assertIn('new_register_99', reading.values_extra_text)
        self.assertEqual(reading.genset_status, '0')

    def test_ac07_mains_and_generator_semantics(self):
        """AC-07: ``mains_status=2`` + ``mains_normal=true`` → «Є мережа»; стоїть з ``gen_undervoltage`` — не аварія;
        стан 9 з ``gen_undervoltage`` → попередження «Низька напруга генератора»; у станах 1–7 (пуск, розгін,
        прогрів) сигнали «генератор не в нормі» — теж не аварія (лише стани 8–9)."""
        reading = self._pull(snapshot(mains_status=2, mains_normal=True, genset_status=0, gen_undervoltage=True),
                             ts=NOW - timedelta(minutes=3))
        self.assertTrue(reading.mains_ok)
        self.assertTrue(self.genset.mains_ok)
        self.assertFalse(reading.alarm_flags and 'gen_undervoltage' in reading.alarm_flags)
        self.assertFalse(self._alarm('gen_undervoltage'))
        for minute, status in ((-2.5, 3), (-2.0, 5), (-1.5, 7)):
            reading = self._pull(snapshot(genset_status=status, gen_undervoltage=True, gen_underfrequency=True,
                                          gen_overvoltage=True), ts=NOW + timedelta(minutes=minute), reason='change')
            self.assertTrue(reading.is_running)
            self.assertFalse(reading.alarm_flags and 'gen_' in reading.alarm_flags, status)
            for code in ('gen_undervoltage', 'gen_underfrequency', 'gen_overvoltage'):
                self.assertFalse(self._alarm(code), (status, code))
        reading = self._pull(snapshot(genset_status=9, gen_undervoltage=True, gen_on_load=True, mains_on_load=False),
                             ts=NOW + timedelta(minutes=1), reason='change')
        self.assertTrue(reading.is_running)
        self.assertEqual(reading.feed_source, 'genset')
        self.assertIn('gen_undervoltage', reading.alarm_flags)
        alarm = self._alarm('gen_undervoltage')
        self.assertEqual((alarm.level, alarm.name), ('warn', 'Низька напруга генератора'))
        reading = self._pull(snapshot(mains_normal=False), ts=NOW + timedelta(minutes=2), reason='change')
        self.assertFalse(reading.mains_ok)
        self.assertEqual(reading.feed_source, 'none')
        self.assertFalse(self._alarm('gen_undervoltage'))

    def test_ac07_running_rule_and_unknown_mode(self):
        """1.2: «працює» = стан ∉ {0, 15} або оберти > 0 (14 — теж працює); ``controller_mode=null`` → «Невідомо»."""
        derive = self.env['td.genset.reading']._derive
        self.assertTrue(derive(snapshot(genset_status=14), self.genset)['is_running'])
        self.assertTrue(derive(snapshot(genset_status=0, speed=300), self.genset)['is_running'])
        self.assertFalse(derive(snapshot(genset_status=15), self.genset)['is_running'])
        self.assertNotIn('is_running', derive({'controller_mode': 'auto'}, self.genset))
        self.assertEqual(derive(snapshot(controller_mode=None), self.genset)['controller_mode'], 'unknown')
        self.assertNotIn('fuel_liters', derive({'fuel_level': None}, self.genset))
        reading = self._pull(snapshot(controller_mode=None, fuel_level=None))
        self.assertEqual(self.genset.controller_mode, 'unknown')
        self.assertTrue(self._is_null(reading, 'fuel_liters'))
        self.assertTrue(self._is_null(reading, 'fuel_source'))
