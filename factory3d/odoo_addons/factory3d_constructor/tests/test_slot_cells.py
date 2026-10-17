from odoo.tests import TransactionCase, tagged

from ..services import cells


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSlotCells(TransactionCase):
    """AC-11…AC-16 (сервісна частина): R-01."""

    RACK = {'bays': 18, 'levels': 4, 'bay_width': 2.7, 'depth': 1.1, 'level_height': 1.5,
            'positions_per_bay': 3, 'max_load_kg': 1000}

    def _rack(self, rot=0, overrides=None, elevation=0.0, **params):
        return cells.generate_cells('pallet_rack', 'FG-R1', 60.0, 5.0, rot, dict(self.RACK, **params), overrides, elevation)

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
        self.assertEqual(set(cells.SLOT_TEMPLATES), {
            'pallet_rack', 'cantilever', 'shelf', 'floor_stack', 'machine_spot', 'zone'})

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
