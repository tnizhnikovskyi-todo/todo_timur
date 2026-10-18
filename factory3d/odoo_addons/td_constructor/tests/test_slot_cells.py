from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from ..services import cells
from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSlotCells(TransactionCase):
    """AC-11…AC-16 (сервісна частина): R-01."""

    RACK = {
        'bays': 18,
        'levels': 4,
        'bay_width': 2.7,
        'depth': 1.1,
        'level_height': 1.5,
        'positions_per_bay': 3,
        'max_load_kg': 1000,
    }

    def _rack(self, rot=0, overrides=None, elevation=0.0, **params):
        return cells.generate_cells(
            'pallet_rack', 'FG-R1', 60.0, 5.0, rot, dict(self.RACK, **params), overrides, elevation
        )

    def test_ac11_pallet_rack(self):
        out = self._rack()
        self.assertEqual(len(out), 72)
        self.assertEqual(out[0]['code'], 'FG-R1-B01-L1')
        self.assertEqual(out[-1]['code'], 'FG-R1-B18-L4')
        self.assertAlmostEqual(out[0]['x'], 37.05)
        self.assertAlmostEqual(out[0]['y'], 5.0)
        self.assertAlmostEqual(out[-1]['x'], 82.95)
        by_code = {c['code']: c for c in out}
        self.assertAlmostEqual(by_code['FG-R1-B01-L4']['z0'], 4.5)
        self.assertEqual(by_code['FG-R1-B01-L1']['kind'], 'pallet_cell')
        self.assertEqual(by_code['FG-R1-B01-L1']['capacity'], 3)
        self.assertAlmostEqual(cells.footprint('pallet_rack', self.RACK)[0], 48.6)

    def test_rotation_90(self):
        first = self._rack(rot=90)[0]
        self.assertAlmostEqual(first['x'], 60.0)
        self.assertAlmostEqual(first['y'], -17.95)

    def test_ac12_templates(self):
        self.assertEqual(
            set(cells.SLOT_TEMPLATES), {'pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'machine_spot', 'zone'}
        )

    def test_ac13_overrides(self):
        out = self._rack(overrides={'FG-R1-B02-L1': {'disabled': True}, 'FG-R1-B03-L1': {'max_load_kg': 1500}})
        self.assertEqual(len(out), 71)
        by_code = {c['code']: c for c in out}
        self.assertNotIn('FG-R1-B02-L1', by_code)
        self.assertEqual(by_code['FG-R1-B03-L1']['max_load_kg'], 1500)

    def test_ac14_levels(self):
        self.assertEqual(len(self._rack(levels=5)), 90)

    def test_elevation_ac09(self):
        shelf = {'sections': 2, 'shelves': 3, 'cell_w': 0.9, 'cell_d': 0.4, 'cell_h': 0.4}
        out = cells.generate_cells('shelf', 'ANT-S1', 10, 10, 0, shelf, {}, 3.6)
        self.assertEqual(len(out), 6)
        by_code = {c['code']: c for c in out}
        self.assertAlmostEqual(by_code['ANT-S1-S01-L3']['z0'], 3.6 + 2 * 0.4)

    def test_floor_stack_codes(self):
        out = cells.generate_cells('floor_stack', 'PLT', 0, 0, 0, {'rows': 4, 'cols': 3}, {}, 0)
        self.assertEqual(len(out), 12)
        self.assertIn('PLT-04C', {c['code'] for c in out})

    def test_no_cells_templates(self):
        spot = {'length': 4, 'width': 1.5}
        self.assertEqual(cells.generate_cells('machine_spot', 'SP', 0, 0, 0, spot, {}, 0), [])
        zone = {'polygon': [[0, 0], [10, 0], [10, 5]]}
        self.assertEqual(cells.generate_cells('zone', 'ZN', 0, 0, 0, zone, {}, 0), [])
        self.assertEqual(cells.footprint('zone', zone), (10, 5))

    def test_param_validation(self):
        with self.assertRaises(cells.CellsError):
            cells.normalize_params('pallet_rack', {'bays': 0})
        with self.assertRaises(cells.CellsError):
            cells.normalize_params('pallet_rack', {'levels': 13})
        with self.assertRaises(cells.CellsError):
            cells.normalize_params('pallet_rack', {'bays': 'x'})
        with self.assertRaises(cells.CellsError):
            cells.normalize_params('zone', {'polygon': [[0, 0], [1, 1]]})
        self.assertEqual(cells.normalize_params('pallet_rack', {})['bays'], 6)  # умовчання

    def test_code_too_long(self):
        with self.assertRaises(cells.CellsError):
            cells.generate_cells('pallet_rack', 'A' * 26, 0, 0, 0, self.RACK, {}, 0)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSlotCellsOrm(F3DConstructorCase):
    """AC-13, AC-14, AC-15, AC-16 на записах ORM."""

    def test_ac13_overrides_and_validation(self):
        slot = self.make_slot(bays=18, levels=4)
        self.assertEqual(slot.cell_count, 72)
        slot.write({'overrides': {'TQ-R1-B02-L1': {'disabled': True}, 'TQ-R1-B03-L1': {'max_load_kg': 1500}}})
        self.assertEqual(slot.cell_count, 71)
        cells = {c['code']: c for c in slot._f3d_cells()}
        self.assertNotIn('TQ-R1-B02-L1', cells)
        self.assertEqual(cells['TQ-R1-B03-L1']['max_load_kg'], 1500)
        with self.assertRaises(ValidationError) as ctx:
            slot.write({'overrides': {'TQ-R1-B99-L1': {'disabled': True}}})
        self.assertIn("Комірки TQ-R1-B99-L1 немає в шаблоні.", str(ctx.exception))
        # зміна параметрів без overrides: недійсні ключі мовчки відкидаються
        slot.write({'params': dict(slot.params, bays=2)})
        self.assertEqual(slot.cell_count, 7)  # 2 прольоти × 4 яруси − B02-L1 (вимкнена)
        self.assertEqual(list(slot.overrides), ['TQ-R1-B02-L1'])  # B03 більше не існує → відкинуто

    def test_ac14_levels(self):
        slot = self.make_slot(bays=18, levels=4)
        slot.params = dict(slot.params, levels=5)
        self.assertEqual(slot.cell_count, 90)
        self.assertAlmostEqual(slot.footprint_l_m, 48.6)

    def test_ac15_layer_allowed_types(self):
        with self.assertRaises(ValidationError) as ctx:
            self.make_slot(kind='storage', prefix='SP-1', template='machine_spot', length=3.0, width=1.5)
        self.assertIn("не допускає тип", str(ctx.exception))
        self.layers['storage'].allowed_slot_type_ids = False
        slot = self.make_slot(kind='storage', prefix='SP-1', template='machine_spot', length=3.0, width=1.5)
        self.assertEqual(slot.cell_count, 0)

    def test_ac16_no_gate_dock(self):
        keys = set(self.env['td.term'].search([('term_type', '=', 'slot_type')]).mapped('key'))
        self.assertEqual(keys, set(cells.SLOT_TEMPLATES))
        self.assertFalse(keys & {'gate', 'dock'})
        selection = dict(self.env['td.slot']._fields['template'].selection)
        self.assertEqual(set(selection), set(cells.SLOT_TEMPLATES))

    def test_slot_rotation_and_cells_html(self):
        slot = self.make_slot(bays=2, levels=1)
        slot.rotation = 450
        self.assertEqual(slot.rotation, 90)
        with self.assertRaises(ValidationError):
            slot.write({'params': {'bays': 0}})
        self.assertIn("Усього 2", slot.cells_html)

    def test_prefix_unique_per_site(self):
        self.make_slot(prefix='AA')
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.make_slot(kind='yard', prefix='AA', template='zone', polygon=[[0, 0], [1, 0], [1, 1]])
