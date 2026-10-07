# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО».
"""KPI, надходження, каністри, місця, заправка/звірка, витрата, калібрування (AC-47…AC-52, AC-69).

Базовий клас — ``TdGensetCase`` (RelayMock, ``snapshot()``, ``push_reading``). Знімки: ``snapshot(...)`` →
``push_reading`` → запис ``td.genset.reading`` через ``_create_from_payload`` (W1) або, поки це заглушка,
напряму за ``READING_FIELD_MAP``. Події «Заправка»/«Робота» (W1) створюються напряму; ``_raise``/``_clear``
тривог (W1) перехоплюються ``patch.object`` (``AlarmSpyMixin``).
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from freezegun import freeze_time
from lxml import etree
from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models import genset_fuel
from ..models.genset_fuel import fmt_num, kyiv_hhmm
from ..models.genset_reading import READING_FIELD_MAP
from .common import TdGensetCase, snapshot

MINUS = '−'
AC69_POINTS = ((10.0, 0.0), (100.0, 60.0), (190.0, 137.0), (240.0, 145.0))


class AlarmSpyMixin:
    """Перехоплює ``td.genset.alarm._raise``/``_clear`` (W1): виклики — у ``self.raised``/``self.cleared``."""

    def _spy_alarms(self):
        self.raised, self.cleared = [], []
        raised, cleared = self.raised, self.cleared

        def fake_raise(model, genset, code, level, name, description='', source=None, tech=False):
            raised.append({'genset': genset, 'code': code, 'level': level, 'name': name,
                           'description': description, 'source': source, 'tech': tech})
            return model.browse()

        def fake_clear(model, genset, code, note=''):
            cleared.append({'genset': genset, 'code': code, 'note': note})

        alarm_class = type(self.env['td.genset.alarm'])
        for name, func in (('_raise', fake_raise), ('_clear', fake_clear)):
            patcher = patch.object(alarm_class, name, func)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _calls(self, calls, code):
        return [call for call in calls if call['code'] == code]


class TdFuelCase(AlarmSpyMixin, TdGensetCase):
    """Спільне для тестів палива: місця «Щитова»/«Склад», постачальник, помічники знімків, каністр, подій."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        locations = cls.env['td.genset.storage.location']
        cls.board = locations.create({'name': 'Щитова'})
        cls.store = locations.create({'name': 'Склад'})
        cls.supplier = cls.env['res.partner'].create({'name': 'АЗС WOG', 'is_company': True})

    def setUp(self):
        super().setUp()
        self._spy_alarms()

    def _reading(self, values, ts=None, genset=None):
        """Знімок ``values`` (``snapshot()``) → RelayMock (``push_reading``) → ``td.genset.reading``."""
        genset = genset or self.genset
        payload = self.push_reading(values, ts=ts)
        readings = self.env['td.genset.reading']
        if genset == self.genset:
            created = readings._create_from_payload(genset, [payload])
            if created:
                return created[-1]
        vals = {
            'genset_id': genset.id,
            'relay_id': payload['id'],
            'ts': datetime.fromtimestamp(payload['ts'], tz=timezone.utc).replace(tzinfo=None),
            'reason': payload['reason'],
        }
        for key, value in payload['values'].items():
            if key not in READING_FIELD_MAP or value is None:
                continue
            field_name, field_type = READING_FIELD_MAP[key]
            vals[field_name] = str(value) if field_type in ('selection', 'char') else value
        return readings.create(vals)

    def _set_tank(self, liters, genset=None):
        """Стан бака з останнього знімка (як ``_apply_reading`` W1)."""
        genset = genset or self.genset
        genset.sudo().write({'fuel_liters': liters, 'fuel_level': round(liters / genset.tank_volume_l * 100),
                             'fuel_source': 'pct'})

    def _canister(self, liters, volume=20.0, location=None, user=None):
        canisters = self.env['td.genset.canister'].with_user(user or self.user_a)
        return canisters.create({'volume_l': volume, 'liters': liters, 'location_id': (location or self.board).id})

    def _event(self, event_type, start, end=None, genset=None, **vals):
        return self.env['td.genset.event'].create(dict(
            genset_id=(genset or self.genset).id, event_type=event_type, date_start=start, date_end=end, **vals))

    def _calibrate(self, genset=None, points=AC69_POINTS):
        genset = genset or self.genset
        return self.env['td.genset.fuel.calibration'].with_user(self.user_t).create([
            {'genset_id': genset.id, 'ohm': ohm, 'liters': liters} for ohm, liters in points])

    def _refuel_wizard(self, user=None, **vals):
        return self.env['td.genset.refuel.wizard'].with_user(user or self.user_a).create(
            dict({'genset_id': self.genset.id}, **vals))

    def _last_refuel(self):
        return self.env['td.genset.refuel'].search([('genset_id', '=', self.genset.id)], order='id desc', limit=1)


@tagged('standard', 'at_install')
class TestW4Fuel(TdFuelCase):

    # ------------------------------------------------------------------ AC-47 KPI і мінімальний запас
    def test_ac47_fuel_kpi_and_min_stock(self):
        """AC-47: бак 95 % (138 L), каністри 127 L, витрата 3,4 L/год, мінімальний запас 100 L → «У баку 138 L»,
        «У каністрах 127 L (6 повних · 1 часткова · 5 порожніх)», «Разом 265 L · вистачить на ≈ 78 год»,
        «Мінімальний запас 100 L · запас у нормі»; при 90 L — «бракує 10 L» і попередження."""
        genset = self.genset
        self.assertEqual(self.config.fuel_min_stock_l, 100.0)
        self._set_tank(138.0)
        full = [self._canister(20.0) for _index in range(6)]
        partial = self._canister(7.0)
        for _index in range(5):
            self._canister(0.0)
        start = fields.Datetime.now() - timedelta(days=5)
        self._event('run', start, start + timedelta(hours=10), fuel_delta_l=-34.0, energy_kwh=60.0)
        self.raised.clear()

        genset.invalidate_recordset()
        self.assertEqual(genset.fuel_liters, 138.0)
        self.assertEqual(genset.fuel_in_canisters_l, 127.0)
        self.assertEqual(genset.canister_liters, 127.0)
        self.assertEqual(genset.fuel_canisters_summary, '6 повних · 1 часткова · 5 порожніх')
        self.assertEqual(genset.fuel_total_l, 265.0)
        self.assertEqual(genset.fuel_rate_lph_30d, 3.4)
        self.assertEqual(genset.fuel_hours_left, 78.0)
        self.assertEqual(genset.fuel_min_stock_l, 100.0)
        self.assertTrue(genset.fuel_min_stock_ok)
        self.assertEqual(genset.fuel_stock_lack_l, 0.0)

        # інвентаризація: 127 → 120 → 100 (ще в нормі) → 90 L — «бракує 10 L» і попередження
        partial.with_user(self.user_a).liters = 0.0
        full[0].with_user(self.user_a).liters = 0.0
        self.assertFalse(self._calls(self.raised, 'fuel_stock_low'))
        full[1].with_user(self.user_a).liters = 10.0
        genset.invalidate_recordset()
        self.assertEqual(genset.fuel_in_canisters_l, 90.0)
        self.assertFalse(genset.fuel_min_stock_ok)
        self.assertEqual(genset.fuel_stock_lack_l, 10.0)
        self.assertEqual(genset.fuel_canisters_summary, '4 повні · 1 часткова · 7 порожніх')
        warnings = self._calls(self.raised, 'fuel_stock_low')
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['level'], 'warn')
        self.assertEqual(warnings[0]['genset'], genset)
        self.assertEqual(warnings[0]['name'], 'Запас у каністрах 90 L нижчий за мінімальний 100 L.')

        # активну тривогу (її створює W1 _raise) знімає надходження: 90 + 20 = 110 L
        self.env['td.genset.alarm'].create({'genset_id': genset.id, 'code': 'fuel_stock_low', 'level': 'warn',
                                            'name': warnings[0]['name']})
        self.env['td.genset.fuel.receipt.wizard'].with_user(self.user_a).create({
            'mode': 'new', 'canister_qty': 1, 'canister_volume_l': 20.0, 'location_id': self.store.id,
        }).action_confirm()
        cleared = self._calls(self.cleared, 'fuel_stock_low')
        self.assertEqual(len(cleared), 1)
        self.assertEqual(cleared[0]['genset'], genset)
        genset.invalidate_recordset()
        self.assertTrue(genset.fuel_min_stock_ok)

    def test_ac47_stock_not_checked_before_canisters(self):
        """AC-47: поки каністр немає (облік не почато), попередження про мінімальний запас не створюється."""
        self.env['td.genset']._check_fuel_stock()
        self.genset._check_fuel_stock()
        self.assertFalse(self._calls(self.raised, 'fuel_stock_low'))
        self.genset.invalidate_recordset()
        self.assertEqual(self.genset.fuel_canisters_summary, '0 повних · 0 часткових · 0 порожніх')
        self.assertEqual(self.genset.fuel_stock_lack_l, 100.0)

    # ------------------------------------------------------------------ AC-48 надходження
    def test_ac48_fuel_receipt_new_canisters(self):
        """AC-48: «Нові каністри», 2 × 10 L, «Щитова», 54,90, постачальник → К-11, К-12 (10/10 L, Щитова), рух
        «+20 L · АЗС … · 54,90 грн/л · 1 098 грн», залишок оновлено; кількість 0 або об'єм 4 L → «Кількість 1–50,
        об'єм 5–60 L»; Корист. С — без доступу."""
        wizards = self.env['td.genset.fuel.receipt.wizard']
        before = self.env['td.genset.canister'].search([]).ids
        wizard = wizards.with_user(self.user_a).create({
            'mode': 'new', 'canister_qty': 2, 'canister_volume_l': 10.0, 'location_id': self.board.id,
            'price_unit': 54.90, 'partner_id': self.supplier.id,
        })
        self.assertEqual(wizard.summary, '+20 L · 2 каністри · 1 098 грн. У каністрах стане 20 L.')
        wizard.action_confirm()

        canisters = self.env['td.genset.canister'].search([('id', 'not in', before)], order='id')
        self.assertEqual(len(canisters), 2)
        numbers = [int(name.split('-')[1]) for name in canisters.mapped('name')]
        self.assertTrue(all(name.startswith('К-') and len(name) >= 4 for name in canisters.mapped('name')))
        self.assertEqual(numbers[1], numbers[0] + 1)
        for canister in canisters:
            self.assertEqual((canister.liters, canister.volume_l, canister.location_id, canister.state),
                             (10.0, 10.0, self.board, 'full'))
        moves = canisters.move_ids.sorted('id')
        self.assertEqual(moves.mapped('kind'), ['in', 'in'])
        self.assertEqual(len(set(moves.mapped('receipt_key'))), 1)
        self.assertTrue(moves[0].receipt_key)
        self.assertEqual(sum(moves.mapped('liters_delta')), 20.0)
        self.assertEqual(set(moves.mapped('note')), {'+20 L · АЗС WOG · 54,90 грн/л · 1 098 грн'})
        self.assertEqual(moves.mapped('price_unit'), [54.9, 54.9])
        self.assertEqual(moves.partner_id, self.supplier)
        self.assertEqual(moves.user_id, self.user_a)
        self.assertEqual(moves[-1].balance_after, 20.0)

        for qty, volume in ((0, 10.0), (2, 4.0), (51, 20.0), (1, 61.0)):
            bad = wizards.with_user(self.user_a).create({'mode': 'new', 'canister_qty': qty, 'canister_volume_l': volume,
                                                         'location_id': self.board.id})
            with self.assertRaises(UserError) as error:
                bad.action_confirm()
            self.assertIn("Кількість 1–50, об'єм 5–60 L", str(error.exception))

        self.assertTrue(wizards.with_user(self.user_a).has_access('create'))
        self.assertFalse(wizards.with_user(self.user_s).has_access('create'))
        with self.assertRaises(AccessError):
            wizards.with_user(self.user_s).create({'mode': 'new', 'location_id': self.board.id})
        with self.assertRaises(AccessError):
            wizard.with_user(self.user_s).action_confirm()

    def test_ac48_fuel_receipt_fill_existing(self):
        """AC-48: «Наповнити наявні» — неповні каністри доливаються доповна одним надходженням."""
        half = self._canister(5.0)
        empty = self._canister(0.0, volume=10.0)
        self._canister(20.0)
        wizard = self.env['td.genset.fuel.receipt.wizard'].with_user(self.user_a).create(
            {'price_unit': 55.40, 'partner_id': self.supplier.id})
        self.assertEqual(wizard.mode, 'fill')
        self.assertEqual(wizard.canister_ids, half | empty)
        self.assertEqual(wizard.summary, '+25 L · 2 каністри · 1 385 грн. У каністрах стане 50 L.')
        wizard.action_confirm()
        self.assertEqual((half.liters, empty.liters), (20.0, 10.0))
        receipt = (half | empty).move_ids.filtered(lambda move: move.kind == 'in')
        self.assertEqual(sorted(receipt.mapped('liters_delta')), [10.0, 15.0])
        self.assertEqual(set(receipt.mapped('note')), {'+25 L · АЗС WOG · 55,40 грн/л · 1 385 грн'})
        self.assertEqual(max(receipt.mapped('balance_after')), 50.0)

    # ------------------------------------------------------------------ AC-49 каністра
    def test_ac49_canister_fix_move_write_off(self):
        """AC-49: К-04 з 7 L → 5 L і «Склад» → рухи «Коригування К-04 7 → 5 L (−2 L)» і «Переміщення К-04
        Щитова → Склад»; поза 0–20 → помилка; «Списати» (друге підтвердження) → «Списано К-04 (разом із 5 L)»,
        каністра в архіві."""
        canister = self._canister(7.0)
        name = canister.name
        created = canister.move_ids
        self.assertEqual((created.kind, created.liters_delta), ('fix', 7.0))
        self.assertEqual(created.note, 'Коригування %s 0 → 7 L (+7 L)' % name)

        canister.with_user(self.user_a).write({'liters': 5.0, 'location_id': self.store.id})
        fix = canister.move_ids.filtered(lambda move: move.kind == 'fix') - created
        self.assertEqual(fix.note, 'Коригування %s 7 → 5 L (%s2 L)' % (name, MINUS))
        self.assertEqual((fix.liters_delta, fix.user_id), (-2.0, self.user_a))
        move = canister.move_ids.filtered(lambda move: move.kind == 'loc')
        self.assertEqual(move.note, 'Переміщення %s Щитова → Склад' % name)
        self.assertEqual((move.liters_delta, move.location_from_id, move.location_to_id),
                         (0.0, self.board, self.store))
        self.assertEqual(fix.balance_after, 5.0)

        for value in (21.0, -1.0):
            with self.assertRaises(ValidationError):
                canister.with_user(self.user_a).liters = value
        self.assertEqual(canister.liters, 5.0)
        with self.assertRaises(AccessError):
            canister.with_user(self.user_s).liters = 3.0

        arch = etree.fromstring(self.env['td.genset.canister'].get_view(view_type='form')['arch'])
        buttons = arch.xpath("//button[@name='action_write_off']")
        self.assertTrue(buttons and buttons[0].get('confirm'), '«Списати» — з другим підтвердженням (confirm)')
        with self.assertRaises(AccessError):
            canister.with_user(self.user_s).action_write_off()
        canister.with_user(self.user_a).action_write_off()
        self.assertFalse(canister.active)
        self.assertEqual(canister.liters, 0.0)
        off = canister.move_ids.filtered(lambda move: move.kind == 'off')
        self.assertEqual(off.note, 'Списано %s (разом із 5 L)' % name)
        self.assertEqual(off.liters_delta, -5.0)
        self.assertEqual(off.balance_after, 0.0)

    def test_ac49_archive_is_write_off(self):
        """AC-49: архівація каністри = списання (рух «Списання»); каністру з рухами не видаляють."""
        canister = self._canister(3.0)
        canister.with_user(self.user_a).action_archive()
        off = canister.move_ids.filtered(lambda move: move.kind == 'off')
        self.assertEqual(off.note, 'Списано %s (разом із 3 L)' % canister.name)
        self.assertEqual((canister.active, canister.liters), (False, 0.0))
        with self.assertRaises(UserError):
            canister.with_user(self.user_t).unlink()
        empty = self._canister(0.0)
        self.assertFalse(empty.move_ids)
        empty.with_user(self.user_t).unlink()
        self.assertFalse(empty.exists())

    # ------------------------------------------------------------------ AC-50 місце зберігання
    def test_ac50_location_with_canisters_not_deleted(self):
        """AC-50: у «Щитова» є каністри → Корист. Т видаляє місце → «У «Щитова» є каністри — спершу перемістіть їх.»"""
        canister = self._canister(10.0, location=self.board)
        with self.assertRaises(UserError) as error:
            self.board.with_user(self.user_t).unlink()
        self.assertEqual(str(error.exception), 'У «Щитова» є каністри — спершу перемістіть їх.')
        canister.with_user(self.user_a).location_id = self.store
        self.board.with_user(self.user_t).unlink()
        self.assertFalse(self.board.exists())
        # лише списані каністри — архівувати замість видалення
        canister.with_user(self.user_a).action_write_off()
        with self.assertRaises(UserError) as error:
            self.store.with_user(self.user_t).unlink()
        self.assertIn('списані каністри', str(error.exception))

    # ------------------------------------------------------------------ AC-51 заправка і звірка
    def test_ac51_refuel_from_canisters_and_reconcile(self):
        """AC-51: вільно 94 L, обрано каністри на 86 L → рух −86 L (часткові першими), запис «очікує показання»;
        стрибок +87 L у вікні 2 год → «підтверджено за рівнем: +87 L»; без стрибка 2 год → «не підтверджено» +
        попередження."""
        self._set_tank(51.0)
        canisters = [self._canister(20.0) for _index in range(4)]
        partial = self._canister(6.0)
        wizard = self._refuel_wizard(source='cans', canister_ids=[Command.set([can.id for can in canisters] + [partial.id])])
        self.assertEqual((wizard.free_l, wizard.will_fill_l), (94.0, 86.0))
        self.assertFalse(wizard.hint)
        self.assertEqual(wizard.summary, 'Заллється 86 L → у баку ≈ 137 L з 145 L.')
        wizard.action_confirm()

        refuel = self._last_refuel()
        self.assertEqual((refuel.liters, refuel.source, refuel.user_id), (86.0, 'cans', self.user_a))
        self.assertEqual((refuel.sensor_state, refuel.sensor_note), ('waiting', 'очікує показання'))
        moves = refuel.move_ids.sorted('id')
        self.assertEqual(set(moves.mapped('kind')), {'out'})
        self.assertEqual(sum(moves.mapped('liters_delta')), -86.0)
        self.assertEqual((moves[0].canister_id, moves[0].liters_delta), (partial, -6.0))
        self.assertEqual(moves.genset_id, self.genset)
        self.assertEqual(refuel.canister_ids, partial.browse([can.id for can in canisters] + [partial.id]))
        self.assertTrue(all(can.liters == 0.0 for can in canisters + [partial]))
        self.assertTrue(self.genset.message_ids.filtered(lambda message: 'Заправка: 86 L' in (message.body or '')))

        before = self._reading(snapshot(fuel_level=35), ts=refuel.date + timedelta(minutes=5))
        after = self._reading(snapshot(fuel_level=95), ts=refuel.date + timedelta(minutes=7))
        event = self._event('refuel', after.ts, after.ts, fuel_delta_l=87.0, reading_start_id=before.id,
                            reading_end_id=after.id)
        self.env['td.genset.refuel']._reconcile_pending()
        self.assertEqual((refuel.sensor_state, refuel.sensor_note), ('confirmed', 'підтверджено за рівнем: +87 L'))
        self.assertEqual((refuel.level_before_l, refuel.level_after_l), (51.0, 138.0))
        self.assertEqual((refuel.level_before_pct, refuel.level_after_pct), (35.0, 95.0))
        self.assertEqual((refuel.event_id, event.refuel_id), (event, refuel))

        # без стрибка рівня 2 год → «не підтверджено» + попередження
        self._refuel_wizard(source='other', source_note='Паливовоз', liters=20.0).action_confirm()
        other = self._last_refuel()
        self.assertEqual((other.liters, other.source_note, other.move_ids), (20.0, 'Паливовоз', self.env['td.genset.fuel.move']))
        self.env['td.genset.refuel']._reconcile_pending()
        self.assertEqual(other.sensor_state, 'waiting')
        self.assertFalse(self._calls(self.raised, 'refuel_unconfirmed'))
        with freeze_time(other.date + timedelta(hours=2, minutes=1)):
            self.env['td.genset.refuel']._reconcile_pending()
        self.assertEqual((other.sensor_state, other.sensor_note), ('unconfirmed', 'не підтверджено'))
        warnings = self._calls(self.raised, 'refuel_unconfirmed')
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['level'], 'warn')
        self.assertEqual(warnings[0]['name'],
                         'Заправку 20 L (%s) не підтверджено датчиком рівня.' % kyiv_hhmm(other.date))

        # подія, що прийшла із запізненням (догон), ще підтверджує запис і знімає тривогу
        self.env['td.genset.alarm'].create({'genset_id': self.genset.id, 'code': 'refuel_unconfirmed',
                                            'level': 'warn', 'name': warnings[0]['name']})
        self._event('refuel', other.date + timedelta(minutes=30), other.date + timedelta(minutes=30), fuel_delta_l=19.0)
        self.env['td.genset.refuel']._reconcile_pending()
        self.assertEqual(other.sensor_state, 'confirmed')
        self.assertEqual(len(self._calls(self.cleared, 'refuel_unconfirmed')), 1)

    def test_ac51_refuel_wizard_limits(self):
        """AC-51: каністри на 120 L при вільних 94 L → заливається 94 L, «Не вміститься 26 L — лишиться в каністрі»;
        бак повний → «Бак повний — заливати нікуди»; Корист. С заправку не записує."""
        self._set_tank(51.0)
        canisters = [self._canister(20.0) for _index in range(6)]
        wizard = self._refuel_wizard(source='cans', canister_ids=[Command.set([can.id for can in canisters])])
        self.assertEqual((wizard.free_l, wizard.will_fill_l), (94.0, 94.0))
        self.assertIn('Не вміститься 26 L — лишиться в каністрі', wizard.hint)
        wizard.action_confirm()
        refuel = self._last_refuel()
        self.assertEqual(refuel.liters, 94.0)
        self.assertEqual(sum(refuel.move_ids.mapped('liters_delta')), -94.0)
        self.assertEqual(sum(can.liters for can in canisters), 26.0)

        self._set_tank(145.0)
        full_tank = self._refuel_wizard(source='cans', canister_ids=[Command.set([can.id for can in canisters])])
        self.assertEqual(full_tank.free_l, 0.0)
        self.assertIn('Бак повний — заливати нікуди', full_tank.hint)
        with self.assertRaises(UserError) as error:
            full_tank.action_confirm()
        self.assertIn('Бак повний — заливати нікуди', str(error.exception))

        self._set_tank(51.0)
        with self.assertRaises(AccessError):
            self._refuel_wizard(user=self.user_s, source='other', liters=10.0)
        with self.assertRaises(AccessError):
            wizard.with_user(self.user_s).action_confirm()

    def test_ac51_refuel_by_level_difference(self):
        """AC-51: різниця з рівнем більша за 2 % бака → «за рівнем: +N L» (видно обидва значення)."""
        refuel = self.env['td.genset.refuel'].create({'genset_id': self.genset.id, 'source': 'other', 'liters': 86.0})
        self._event('refuel', refuel.date + timedelta(minutes=10), refuel.date + timedelta(minutes=10),
                    fuel_delta_l=80.0)
        self.env['td.genset.refuel']._reconcile_pending()
        self.assertEqual((refuel.sensor_state, refuel.sensor_note, refuel.liters), ('by_level', 'за рівнем: +80 L', 86.0))

    # ------------------------------------------------------------------ AC-52 витрата
    def test_ac52_fuel_consumption(self):
        """AC-52: за 30 днів події «Робота» з ΔL −53 L, 15,5 год, 96 kWh, остання ціна 55,40 → «Витрачено 53 L ·
        ≈ 2 936 грн», «3,4 L/год», «0,55 L/kWh», «1,8 L на добу»; період 7 днів перераховує."""
        now = fields.Datetime.now()
        canister = self._canister(0.0)
        moves = self.env['td.genset.fuel.move']
        moves._post('in', 10.0, canister=canister, price_unit=54.90, partner_id=self.supplier, date=now - timedelta(days=20))
        moves._post('in', 10.0, canister=canister, price_unit=55.40, date=now - timedelta(days=2))
        for days, hours, delta, kwh in ((20, 4.0, -15.0, 28.0), (5, 6.0, -20.0, 36.0), (2, 5.5, -18.0, 32.0)):
            start = now - timedelta(days=days)
            self._event('run', start, start + timedelta(hours=hours), fuel_delta_l=delta, energy_kwh=kwh)
        # не рахуються: інший тип, давніше 30 днів, інший генератор
        self._event('outage', now - timedelta(days=3), now - timedelta(days=3, hours=-1), fuel_delta_l=-99.0)
        self._event('run', now - timedelta(days=40), now - timedelta(days=40, hours=-2), fuel_delta_l=-99.0)
        other = self.env['td.genset'].create({'name': 'Другий', 'controller_model_id': self.controller_model.id,
                                              'power_kw': 10.0})
        self._event('run', now - timedelta(days=1), now - timedelta(days=1, hours=-1), genset=other, fuel_delta_l=-99.0)

        stats = self.genset._fuel_stats(30)
        self.assertEqual(stats, {'used_l': 53.0, 'hours': 15.5, 'kwh': 96.0, 'lph': 3.4, 'lpkwh': 0.55,
                                 'per_day': 1.8, 'cost': 2936.0})
        self.assertEqual('Витрачено %s L · ≈ %s грн' % (fmt_num(stats['used_l']), fmt_num(stats['cost'], 0)),
                         'Витрачено 53 L · ≈ 2 936 грн')
        self.assertEqual(self.genset._fuel_stats(7), {'used_l': 38.0, 'hours': 11.5, 'kwh': 68.0, 'lph': 3.3,
                                                      'lpkwh': 0.56, 'per_day': 5.4, 'cost': 2105.0})
        genset = self.genset
        genset.invalidate_recordset()
        self.assertEqual((genset.fuel_used_30d_l, genset.fuel_rate_lph_30d, genset.fuel_rate_lpkwh_30d,
                          genset.fuel_per_day_30d, genset.fuel_cost_30d), (53.0, 3.4, 0.55, 1.8, 2936.0))
        self.assertEqual((genset.fuel_used_7d_l, genset.fuel_rate_lph_7d, genset.fuel_rate_lpkwh_7d,
                          genset.fuel_per_day_7d, genset.fuel_cost_7d), (38.0, 3.3, 0.56, 5.4, 2105.0))
        self.assertEqual(self.env['td.genset']._fuel_stats(30)['used_l'], 0.0)

    # ------------------------------------------------------------------ AC-69 калібрування датчика
    def test_ac69_liters_by_calibration_and_recompute(self):
        """AC-69: бак 145 L без калібрування, знімок 94 % · 188,6 Ом → 136 L «за % контролера»; Корист. Т додає
        точки 10 → 0, 100 → 60, 190 → 137, 240 → 145 і «Перерахувати літри» → 135,8 L «за датчиком (Ом)»;
        300 Ом → 145 L (крайня точка); без опору — за %; Корист. С/А таблицю лише читають."""
        genset = self.genset
        reading = self._reading(snapshot(fuel_level=94, fuel_sensor_ohm=188.6))
        self.assertEqual(reading.fuel_sensor_ohm, 188.6)
        self.assertEqual((reading.fuel_liters, reading.fuel_source), (136.0, 'pct'))
        edge = self._reading(snapshot(fuel_level=99, fuel_sensor_ohm=300.0))
        values = snapshot(fuel_level=40)
        del values['fuel_level_sensor_ohm']
        no_ohm = self._reading(values)
        self.assertEqual((no_ohm.fuel_liters, no_ohm.fuel_source), (58.0, 'pct'))
        genset.sudo().last_reading_id = reading

        calibration = self.env['td.genset.fuel.calibration']
        for user in (self.user_s, self.user_a):
            with self.assertRaises(AccessError):
                calibration.with_user(user).create({'genset_id': genset.id, 'ohm': 10.0, 'liters': 0.0})
        self._calibrate()
        self.assertEqual(len(calibration.with_user(self.user_s).search([('genset_id', '=', genset.id)])), 4)
        with self.assertRaises(AccessError):
            genset.fuel_calibration_ids[:1].with_user(self.user_a).liters = 1.0
        self.assertTrue(genset.fuel_calibrated)
        self.assertEqual(genset._liters_from_ohm(188.6), 135.8)
        self.assertEqual(genset._liters_from_ohm(300.0), 145.0)
        self.assertEqual(genset._liters_from_ohm(5.0), 0.0)
        self.assertEqual(genset._liters_from_ohm(100.0), 60.0)
        self.assertIsNone(genset._liters_from_ohm(None))

        reading.invalidate_recordset()
        self.assertEqual(reading.fuel_source, 'pct', 'історія не перераховується без кнопки (ТР 2.16)')
        with self.assertRaises(AccessError):
            genset.with_user(self.user_a).action_recompute_liters()
        action = genset.with_user(self.user_t).action_recompute_liters()
        self.assertEqual((action['type'], action['tag']), ('ir.actions.client', 'display_notification'))
        self.assertIn('за калібруванням датчика', action['params']['message'])
        (reading | edge | no_ohm).invalidate_recordset()
        self.assertEqual((reading.fuel_liters, reading.fuel_source), (135.8, 'ohm'))
        self.assertEqual((edge.fuel_liters, edge.fuel_source), (145.0, 'ohm'))
        self.assertEqual((no_ohm.fuel_liters, no_ohm.fuel_source), (58.0, 'pct'))
        genset.invalidate_recordset()
        self.assertEqual((genset.fuel_liters, genset.fuel_source), (135.8, 'ohm'))
        self.assertEqual(genset.fuel_recompute_next_id, 0)

        fresh = self._reading(snapshot(fuel_level=94, fuel_sensor_ohm=188.6))
        self.assertEqual((fresh.fuel_liters, fresh.fuel_source), (135.8, 'ohm'))

    def test_ac69_calibration_validation(self):
        """AC-69: одна точка або немонотонна послідовність (190 Ом → 130 L після 100 Ом → 137 L) → помилка
        «Калібрування має бути монотонним…», літри далі за %; крива, що лише спадає, — допустима; Ом унікальні."""
        other = self.env['td.genset'].create({'name': 'Другий', 'controller_model_id': self.controller_model.id,
                                              'power_kw': 10.0, 'tank_volume_l': 145.0})
        reading = self._reading(snapshot(fuel_level=94, fuel_sensor_ohm=188.6), genset=other)
        self.assertEqual((reading.fuel_liters, reading.fuel_source), (136.0, 'pct'))

        with self.assertRaises(ValidationError) as error:
            other.with_user(self.user_t).write({'fuel_calibration_ids': [
                Command.create({'ohm': ohm, 'liters': liters})
                for ohm, liters in ((10.0, 0.0), (100.0, 137.0), (190.0, 130.0), (240.0, 145.0))]})
        self.assertIn('Калібрування має бути монотонним', str(error.exception))
        self.assertFalse(other.fuel_calibration_ids)
        self.assertFalse(other.fuel_calibrated)
        self.assertIsNone(other._liters_from_ohm(188.6))

        self._calibrate(other, points=((10.0, 0.0),))
        self.assertFalse(other.fuel_calibrated)
        self.assertIsNone(other._liters_from_ohm(188.6))
        with self.assertRaises(UserError) as error:
            other.with_user(self.user_t).action_recompute_liters()
        self.assertIn('Калібрування має бути монотонним', str(error.exception))
        reading.invalidate_recordset()
        self.assertEqual((reading.fuel_liters, reading.fuel_source), (136.0, 'pct'))
        with self.assertRaises(ValidationError):
            self._calibrate(other, points=((100.0, 137.0), (190.0, 130.0)))
        with self.assertRaises(ValidationError):
            self._calibrate(other, points=((100.0, 150.0),))
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self._calibrate(other, points=((10.0, 1.0),))

        # датчик зі спадною кривою (240 Ом — порожньо, 33 Ом — повно) — допустимо
        other.fuel_calibration_ids.unlink()
        self._calibrate(other, points=((33.0, 145.0), (240.0, 0.0)))
        self.assertTrue(other.fuel_calibrated)
        self.assertEqual(other._liters_from_ohm(136.5), 72.5)
        other.with_user(self.user_t).action_recompute_liters()
        reading.invalidate_recordset()
        self.assertEqual((reading.fuel_liters, reading.fuel_source), (36.0, 'ohm'))

    def test_ac69_recompute_in_batches(self):
        """AC-69 (ТР 2.9): «Перерахувати літри» — партіями: перша одразу, решта — cron ``cron_recompute_liters``
        (``_trigger()`` + ``_notify_progress``); події не перераховуються."""
        readings = [self._reading(snapshot(fuel_level=50 + index, fuel_sensor_ohm=100.0 + index))
                    for index in range(5)]
        event = self._event('refuel', fields.Datetime.now(), fields.Datetime.now(), fuel_delta_l=12.0)
        self._calibrate()
        cron = self.env.ref('td_genset.cron_recompute_liters')
        triggers = self.env['ir.cron.trigger']
        with patch.object(genset_fuel, 'RECOMPUTE_BATCH', 2):
            action = self.genset.with_user(self.user_t).action_recompute_liters()
            self.assertIn('решту (3)', action['params']['message'])
            self.assertTrue(self.genset.fuel_recompute_next_id)
            self.assertTrue(triggers.search([('cron_id', '=', cron.id)]))
            self.assertEqual(self.env['td.genset']._cron_recompute_liters(), 1)
            self.assertEqual(self.env['td.genset']._cron_recompute_liters(), 0)
        self.assertEqual(self.genset.fuel_recompute_next_id, 0)
        self.assertEqual(self.env['td.genset']._cron_recompute_liters(), 0)
        expected = [60.0, 60.9, 61.7, 62.6, 63.4]
        for reading, liters in zip(readings, expected):
            reading.invalidate_recordset()
            self.assertEqual((reading.fuel_liters, reading.fuel_source), (liters, 'ohm'))
        self.assertEqual(event.fuel_delta_l, 12.0)
        self.assertTrue(cron.method_direct_trigger())
