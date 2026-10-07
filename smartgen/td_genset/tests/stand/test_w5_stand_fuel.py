# Part of td_genset (ToDo). Власник файлу: W5 «Стенд і документація».
"""Стенд, етап 3 «Паливо» і оми датчиків: надходження і заправка зі звіркою за рівнем, падіння рівня без роботи,
низький рівень і активність «Долити паливо», калібрування датчика Ом → L і перерахунок історії, оми з ключів
(ретранслятор 1.1.3) і з сирого образу ``raw=1`` (1.1.1).

ТК-10, ТК-11, ТК-14.9, ТК-14.11 · AC-40, AC-48, AC-51, AC-53, AC-54, AC-63, AC-68, AC-69.
"""
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import html2plaintext

from .stand_common import TdGensetStandCase

OHM_FIELDS = ('fuel_sensor_ohm', 'water_temp_sensor_ohm', 'oil_pressure_sensor_ohm')
OHM_KEYS = {'fuel_sensor_ohm': 'fuel_level_sensor_ohm', 'water_temp_sensor_ohm': 'water_temp_sensor_ohm',
            'oil_pressure_sensor_ohm': 'oil_pressure_sensor_ohm'}
OHM_REGS = {'fuel_sensor_ohm': '22', 'water_temp_sensor_ohm': '18', 'oil_pressure_sensor_ohm': '20'}
CALIBRATION = [(10.0, 0.0), (100.0, 60.0), (190.0, 137.0), (240.0, 145.0)]          # точки AC-69


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandFuel(TdGensetStandCase):
    """Емулятор зі змінних оточення (1.1.3), бак 145 L, пороги 10 L."""

    def setUp(self):
        super().setUp()
        self.location = self.env['td.genset.storage.location'].create({'name': 'Щитова'})
        self.relay.sim(snapshot_sec=3600)

    def start_level(self, pct, **keys):
        """Рівень палива на стенді ДО підключення Odoo (курсор генератора — на останньому знімку): перший знімок
        в Odoo вже з цим рівнем, без «падіння рівня» від стартових 95 %."""
        self.relay.sim(fuel_level=pct, **keys)
        last_id = self.relay.snapshot()
        self.genset.sudo().write({'readings_cursor': last_id - 1})
        readings = self.pull()
        self.assertTrue(readings, 'знімки не забрано')
        return readings[-1]

    def set_fuel(self, pct, **keys):
        """Рівень палива на стенді (% бака) + знімок → забір; повертає знімок Odoo з цим рівнем."""
        self.relay.sim(fuel_level=pct, snapshot=True, **keys)
        last_id = self.relay.last_reading_id()
        return self.pull().filtered(lambda r: r.relay_id == last_id)

    def test_tk10_ac48_ac51_receipt_refuel_confirmed_by_level(self):
        """ТК-10.1–10.2 · AC-48, AC-51, AC-40: Адміністратор — «Надходження палива» 2 нові каністри по 10 L (2 каністри,
        рух +20 L); «Заправити генератор» з них 20 L → запис «Очікує показання», рух −20 L; на стенді рівень +14 %
        (≈ +20 L) → подія «Заправка» без тривоги → звірка «Підтверджено за рівнем» (різниця ≤ 2 % бака)."""
        self.start_level(50)                                      # вільно ≈ 72 L
        receipt = self.env['td.genset.fuel.receipt.wizard'].with_user(self.user_a).create({
            'mode': 'new', 'canister_qty': 2, 'canister_volume_l': 10.0, 'location_id': self.location.id,
            'price_unit': 54.9})
        receipt.action_confirm()
        canisters = self.env['td.genset.canister'].search([('location_id', '=', self.location.id)])
        self.assertEqual(len(canisters), 2)
        self.assertEqual(canisters.mapped('liters'), [10.0, 10.0])
        moves_in = self.env['td.genset.fuel.move'].search([('kind', '=', 'in'), ('canister_id', 'in', canisters.ids)])
        self.assertAlmostEqual(sum(moves_in.mapped('liters_delta')), 20.0)
        self.env['td.genset.refuel.wizard'].with_user(self.user_a).create({
            'genset_id': self.genset.id, 'source': 'cans', 'canister_ids': [(6, 0, canisters.ids)],
        }).action_confirm()
        refuel = self.env['td.genset.refuel'].search([('genset_id', '=', self.genset.id)])
        self.assertEqual(len(refuel), 1)
        self.assertEqual(refuel.sensor_state, 'waiting')
        self.assertAlmostEqual(refuel.liters, 20.0)
        self.assertAlmostEqual(sum(refuel.move_ids.mapped('liters_delta')), -20.0)
        before = self.genset.fuel_liters
        self.set_fuel(64)
        event = self.events('refuel')
        self.assertEqual(len(event), 1)
        self.assertAlmostEqual(event.fuel_delta_l, self.genset.fuel_liters - before, delta=0.5)
        self.assertFalse(self.alarms('drain'))
        self.run_scheduler()                                       # звірка заправок (_reconcile_pending)
        self.assertEqual(refuel.sensor_state, 'confirmed')
        self.assertEqual(refuel.event_id, event)

    def test_tk10_ac40_drain_alarm(self):
        """ТК-10.3 · AC-40: зміна на 1 % (≈ 1,45 L) подій не створює; падіння на 10 % (≈ −14 L ≥ порога 10 L) за ≤ 60 хв
        при зупиненому генераторі → подія «Падіння рівня» з ΔL і тривога критична «можливий злив»."""
        self.start_level(95)
        self.set_fuel(94)
        self.assertFalse(self.events('drain'))
        self.assertFalse(self.events('refuel'))
        self.set_fuel(84)
        drain = self.events('drain')
        self.assertEqual(len(drain), 1)
        self.assertLessEqual(drain.fuel_delta_l, -10)
        alarm = self.alarms('drain')
        self.assertEqual(len(alarm), 1)
        self.assertEqual(alarm.level, 'crit')

    def test_tk14_ac63_low_fuel_activity(self):
        """ТК-14.9 · AC-63: рівень нижче 20 % → попередження «Низький рівень палива» і активність «Долити паливо»
        відповідальному на картці генератора (21 % → 19 %: без «падіння рівня», ΔL < порога)."""
        self.start_level(21)
        self.assertFalse(self.alarms().filtered(lambda a: 'low_fuel' in (a.code or '')))
        self.set_fuel(19)
        low = self.alarms().filtered(lambda a: 'low_fuel' in (a.code or ''))
        self.assertTrue(low)
        self.assertIn('warn', low.mapped('level'))
        refuel_type = self.env.ref('td_genset.activity_refuel')
        activity = self.genset.activity_ids.filtered(lambda a: a.activity_type_id == refuel_type)
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.genset.user_id)

    def test_tk10_ac69_calibration_recompute(self):
        """ТК-10.5 · AC-69: без калібрування знімок ``fuel_level = 94``, 188,6 Ом → 136 L «за % контролера»;
        Адміністратор таблицю лише читає; немонотонні точки → помилка; Тех. адміністратор заповнює 4 точки і
        «Перерахувати літри» → той самий знімок 135,8 L «за датчиком (Ом)»; 300 Ом → 145 L (крайня точка);
        знімок без омів → за %."""
        self.config.raw_regs_mode = 'no'                          # оми — з ключів 1.1.3
        reading = self.start_level(94, set={'fuel_level_sensor_ohm': 188.6})
        self.assertAlmostEqual(reading.fuel_sensor_ohm, 188.6, places=1)
        self.assertEqual(reading.fuel_liters, 136)
        self.assertEqual(reading.fuel_source, 'pct')
        Calibration = self.env['td.genset.fuel.calibration']
        with self.assertRaises(AccessError):
            Calibration.with_user(self.user_a).create({'genset_id': self.genset.id, 'ohm': 10.0, 'liters': 0.0})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            Calibration.create([{'genset_id': self.genset.id, 'ohm': 100.0, 'liters': 137.0},
                                {'genset_id': self.genset.id, 'ohm': 190.0, 'liters': 130.0}])
        Calibration.with_user(self.user_t).create([
            {'genset_id': self.genset.id, 'ohm': ohm, 'liters': liters} for ohm, liters in CALIBRATION])
        self.env.invalidate_all()
        self.assertTrue(self.genset.fuel_calibrated)
        self.genset.with_user(self.user_t).action_recompute_liters()
        self.env.invalidate_all()
        self.assertAlmostEqual(reading.fuel_liters, 135.8, places=1)
        self.assertEqual(reading.fuel_source, 'ohm')
        edge = self.set_fuel(94, set={'fuel_level_sensor_ohm': 300.0})
        self.assertAlmostEqual(edge.fuel_liters, 145.0, places=1)
        self.assertEqual(edge.fuel_source, 'ohm')
        no_ohm = self.set_fuel(94, drop=['fuel_level_sensor_ohm'])
        self.assertTrue(self.column_is_null(no_ohm, 'fuel_sensor_ohm'))
        self.assertEqual(no_ohm.fuel_source, 'pct')
        self.assertEqual(no_ohm.fuel_liters, 136)

    def test_tk14_ac68_ohms_from_keys_v113(self):
        """ТК-14.11 · AC-68 (ТА): ретранслятор 1.1.3 віддає ``*_sensor_ohm`` → оми знімків з ключів
        (``fuel_level_sensor_ohm`` → ``fuel_sensor_ohm``), запити ``/readings`` без ``raw=1``; у шаблоні експорту
        «Усі значення» є колонки омів і ``fuel_source``."""
        self.pull()                       # перший забір (без «останнього знімка» в Odoo) — поза перевіркою raw
        self.relay.snapshot()
        self.relay.snapshot()
        with self.spy_requests() as calls:
            readings = self.pull()
        relay_values = {reading['id']: reading['values'] for reading in self.relay.readings()}
        new = readings[-2:]
        self.assertEqual(len(new), 2, 'знімки не забрано')
        for reading in new:
            values = relay_values[reading.relay_id]
            for field, key in OHM_KEYS.items():
                self.assertAlmostEqual(reading[field], values[key], places=1, msg=field)
        pages = [call for call in self.readings_calls(calls) if str(call['params'].get('limit')) != '1']
        self.assertTrue(pages)
        self.assertFalse([call for call in pages if self.is_raw(call)], 'при 1.1.3 з ключами — без raw=1')
        export_fields = self.env.ref('td_genset.export_reading_all').export_fields.mapped('name')
        for name in OHM_FIELDS + ('fuel_source',):
            self.assertIn(name, export_fields)


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandRelay111(TdGensetStandCase):
    """Другий екземпляр емулятора (власний процес) у режимі ретранслятора 1.1.1 — без ключів ``*_sensor_ohm``."""

    relay_mode = 'own'
    relay_version = '1.1.1'

    def test_tk14_ac68_ohms_from_raw_regs_v111(self):
        """ТК-14.11 · AC-68: ретранслятор 1.1.1 → забір з ``raw=1``, оми з ``regs["22"|"18"|"20"] ÷ 10`` (188,6 /
        515,4 / 9,5 Ом), інші ``regs``/``coils`` не зберігаються, у «Поточних даних» — «188,6»; стенд перемкнули на
        1.1.3 — оми з ключів, запити без ``raw=1``; «Читати сирі регістри» = ні і знову 1.1.1 → оми NULL («немає
        даних»), без помилок і без ``raw=1``."""
        self.relay.sim(set={'fuel_level_sensor_ohm': 188.6}, snapshot=True)       # regs["22"] = 1886
        with self.spy_requests() as calls:
            readings = self.pull()
        pages = [call for call in self.readings_calls(calls) if str(call['params'].get('limit')) != '1']
        self.assertTrue(pages)
        self.assertTrue(all(self.is_raw(call) for call in pages), 'при 1.1.1 — raw=1')
        self.assertTrue(readings, 'знімки не забрано')
        raw = {reading['id']: reading for reading in self.relay.readings(raw=True)}
        last = readings[-1]
        self.assertEqual(raw[last.relay_id]['regs']['22'], 1886)
        for field, reg in OHM_REGS.items():
            self.assertAlmostEqual(last[field], raw[last.relay_id]['regs'][reg] / 10.0, places=1, msg=field)
        self.assertAlmostEqual(last.fuel_sensor_ohm, 188.6, places=1)
        self.assertAlmostEqual(last.water_temp_sensor_ohm, 515.4, places=1)
        self.assertAlmostEqual(last.oil_pressure_sensor_ohm, 9.5, places=1)
        for reading in readings:
            self.assertFalse(set(reading.values_extra or {}) & {'regs', 'coils'})
        self.assertIn('188,6', html2plaintext(self.genset.current_data_html or ''))

        self.relay.sim(version='1.1.3', unset=['fuel_level_sensor_ohm'], snapshot=True)
        self.pull()                       # перший забір після перемикання ще може йти з raw=1 (останній знімок без ключів)
        self.relay.snapshot()
        with self.spy_requests() as calls:
            readings = self.pull()
        pages = [call for call in self.readings_calls(calls) if str(call['params'].get('limit')) != '1']
        self.assertTrue(pages)
        self.assertFalse([call for call in pages if self.is_raw(call)], 'при 1.1.3 з ключами — без raw=1')
        last = readings[-1]
        values = {reading['id']: reading['values'] for reading in self.relay.readings()}[last.relay_id]
        self.assertAlmostEqual(last.fuel_sensor_ohm, values['fuel_level_sensor_ohm'], places=1)

        self.config.raw_regs_mode = 'no'
        self.relay.sim(version='1.1.1', snapshot=True)
        with self.spy_requests() as calls:
            readings = self.pull()
        self.assertFalse([call for call in self.readings_calls(calls) if self.is_raw(call)])
        last = readings[-1]
        for field in OHM_FIELDS:
            self.assertTrue(self.column_is_null(last, field), field)


@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')
class TestStandMaintenance(TdGensetStandCase):
    """ТО за мотогодинами стенду (емулятор зі змінних оточення: 34 год 51 хв)."""

    def test_tk11_ac53_ac54_maintenance_by_run_hours(self):
        """ТК-11 · AC-53, AC-54: «Перше ТО» = 30 год при мотогодинах стенду 34,85 → обладнання «Генератор · Стенд»,
        превентивна заявка ТО (одна, друга не створюється), попередження «Термін ТО»; заявку закрито (стадія
        «виконано») → мотогодини при закритті зафіксовано, «До ТО: 250 год», попередження знято."""
        self.genset.write({'maint_first_hours': 30})
        self.pull()
        self.run_scheduler()
        equipment = self.genset.equipment_id
        self.assertTrue(equipment)
        self.assertIn('Стенд', equipment.name)
        Request = self.env['maintenance.request']
        request = Request.search([('equipment_id', '=', equipment.id)])
        self.assertEqual(len(request), 1)
        self.assertEqual(request.maintenance_type, 'preventive')
        self.assertEqual(len(self.alarms('maintenance_due')), 1)
        self.snapshot()
        self.pull()
        self.run_scheduler()
        self.assertEqual(Request.search_count([('equipment_id', '=', equipment.id)]), 1)
        request.stage_id = self.env['maintenance.stage'].search([('done', '=', True)], limit=1)
        self.env.invalidate_all()
        self.assertAlmostEqual(request.td_run_hours_at_close, self.genset.run_hours_total, places=1)
        self.assertAlmostEqual(self.genset.maint_hours_left, 250, delta=0.5)
        self.assertFalse(self.alarms('maintenance_due'))
