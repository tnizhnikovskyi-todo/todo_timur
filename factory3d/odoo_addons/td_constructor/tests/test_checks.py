import json
import os

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from ..services import checks, geometry as geo
from . import golden_scenes
from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestChecks(TransactionCase):
    """AC-22…AC-32 (сервісна частина): R-02, R-03, R-04…R-10 і паритет із золотими фікстурами (AC-31)."""

    def _issues(self, scene_name):
        scene = next(s for s in golden_scenes.check_scenes() if s['name'] == scene_name)
        return checks.run_checks(scene['state'], scene['configs'], 0.001)

    def _keys(self, scene_name):
        return sorted((i['check'], i['severity'], tuple(i['codes'])) for i in self._issues(scene_name))

    # --- AC-22: SAT (R-03) ---
    def test_sat_examples(self):
        obb = geo.make_obb
        self.assertAlmostEqual(geo.sat_penetration(obb(0, 0, 1, 0.5), obb(1.5, 0, 1, 0.5)), 0.5, places=3)
        self.assertAlmostEqual(geo.sat_penetration(obb(0, 0, 1, 0.5), obb(2, 0, 1, 0.5)), 0.0, places=6)
        self.assertAlmostEqual(geo.sat_penetration(obb(0, 0, 1, 1), obb(2.2, 0, 1, 1, 45)), 0.214, places=3)
        self.assertLess(geo.sat_penetration(obb(0, 0, 1, 0.5), obb(3, 0, 1, 0.5)), 0)

    def test_geometry_r02_example(self):
        variant = {
            'length': 4000,
            'width': 1200,
            'front_side': 's',
            'anchor': 'front',
            'service': {'front': 1000, 'back': 0, 'left': 0, 'right': 0},
        }
        body = geo.placement_obb(variant, 10, 5, 0)
        self.assertAlmostEqual(body['cy'], 5.6)
        service = geo.service_obb(variant, 10, 5, 0)
        self.assertAlmostEqual(service['cy'], 5.1)
        self.assertAlmostEqual(service['a'], 2.0)
        self.assertAlmostEqual(service['b'], 1.1)

    def test_polygon(self):
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(geo.polygon_contains(square, (5, 5)))
        self.assertTrue(geo.polygon_contains(square, (10, 5)))
        self.assertFalse(geo.polygon_contains(square, (11, 5)))
        self.assertTrue(geo.obb_inside_polygon(geo.make_obb(5, 5, 1, 1, 45), square))
        self.assertFalse(geo.obb_inside_polygon(geo.make_obb(9.5, 5, 1, 1, 0), square))

    # --- AC-23…AC-29: кожна перевірка ---
    def test_fits(self):
        self.assertEqual(self._keys('fits_inside_bounds_ok'), [])
        self.assertEqual(self._keys('fits_outside_bounds'), [('fits', 'block', ('M-1',))])
        self.assertEqual(self._keys('fits_rotation_45_mode_q'), [('fits', 'block', ('M-1',))])
        self.assertIn('поворот', self._issues('fits_rotation_45_mode_q')[0]['message'])
        self.assertEqual(self._keys('fits_layer_kind_not_allowed'), [('fits', 'block', ('M-1',))])
        self.assertEqual(self._keys('fits_cell_ok'), [])
        self.assertEqual(self._keys('fits_cell_overflow_rot90'), [('fits', 'block', ('PAL-1',))])
        self.assertEqual(self._keys('fits_slot_outside_building'), [('fits', 'block', ('RK-9',))])

    def test_collide(self):
        self.assertEqual(self._keys('collide_overlap_0_3'), [('collide', 'block', ('A-1', 'A-2'))])
        self.assertEqual(self._keys('collide_touching_no_issue'), [])
        self.assertEqual(self._keys('collide_different_layers_no_issue'), [])
        # місце під верстат не конфліктує з розміщенням, що в нього поставлено (slot_id)
        keys = self._keys('collide_slot_inside_own_spot_ignored')
        self.assertNotIn(('collide', 'block', ('M-1', 'SP-1')), keys)
        self.assertEqual(len(keys), 2)

    def test_service_free(self):
        self.assertEqual(self._keys('service_free_neighbor_in_front'), [('service_free', 'warn', ('M-1', 'A-1'))])
        # поворот на 90° міняє бік зони (R-02)
        self.assertEqual(self._keys('service_free_rotated_90_no_issue'), [])
        self.assertEqual(self._keys('service_free_rotated_90_zone_east'), [('service_free', 'warn', ('M-1', 'A-1'))])

    def test_aisles_and_fire(self):
        issues = self._issues('aisles_free_blocked')
        self.assertEqual([i['check'] for i in issues], ['aisles_free'])
        self.assertIn('Прохід перекрито', issues[0]['message'])
        self.assertEqual(self._keys('aisles_free_clear'), [])
        self.assertEqual(self._keys('fire_exit_blocked'), [('fire', 'block', ('M-1',))])
        self.assertIn('Вихід перекрито', self._issues('fire_exit_blocked')[0]['message'])
        self.assertIn('Пожежний прохід перекрито', self._issues('fire_path_blocked')[0]['message'])

    def test_load(self):
        self.assertEqual(self._keys('load_floor_exceeded'), [('load', 'warn', ('M-1',))])
        self.assertEqual(self._keys('load_floor_unlimited_ok'), [])
        issues = self._issues('load_cell_exceeded')
        self.assertEqual(len(issues), 1)
        self.assertIn('комірки RK-1-B01-L1', issues[0]['message'])

    def test_utility_reach(self):
        self.assertEqual(self._keys('utility_reach_far'), [('utility_reach', 'warn', ('M-1',))])
        self.assertEqual(self._keys('utility_reach_near_ok'), [])
        self.assertIn('немає точки', self._issues('utility_reach_missing_kind')[0]['message'])
        self.assertEqual(self._keys('utility_reach_custom_limit'), [('utility_reach', 'warn', ('M-1',))])

    # --- AC-30: режими ---
    def test_modes(self):
        self.assertEqual(self._issues('collide_warn_mode')[0]['severity'], 'warn')
        self.assertEqual(self._issues('collide_disabled'), [])

    def test_default_configs_r04(self):
        modes = {key: mode for key, _enabled, mode, _params in checks.CHECK_DEFAULTS}
        self.assertEqual({k for k, m in modes.items() if m == 'block'}, {'fits', 'collide', 'aisles_free', 'fire'})
        self.assertEqual(len(modes), 7)

    # --- AC-31: золоті фікстури ---
    def test_golden_parity(self):
        """Файли `static/tests/fixtures/*_golden.json` збігаються з тим, що дають services/*.

        `F3D_UPDATE_GOLDEN=1` — оновити файли."""
        if os.environ.get('F3D_UPDATE_GOLDEN') == '1':
            golden_scenes.write_all()
        scenes = json.loads(
            open(os.path.join(golden_scenes.FIXTURES_DIR, 'checks_golden.json'), encoding='utf-8').read()
        )
        self.assertGreaterEqual(len(scenes['scenes']), 12)
        covered = {i['check'] for sc in scenes['scenes'] for i in sc['expected']}
        self.assertEqual(covered, set(checks.CHECK_KEYS))
        for name, text in golden_scenes.build_all().items():
            path = os.path.join(golden_scenes.FIXTURES_DIR, name)
            with open(path, encoding='utf-8') as handle:
                self.assertEqual(handle.read(), text, "%s застарілий: запустіть тест із F3D_UPDATE_GOLDEN=1" % name)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestCheckConfigs(F3DConstructorCase):
    """AC-32: налаштування перевірок площадки (R-04) і їх схема (R-22)."""

    def test_ac32_default_configs_and_uniqueness(self):
        site = self.env['f3d.site'].create({'name': "Нова", 'code': 'NEW'})
        configs = {c.check_key: c for c in site.check_config_ids}
        self.assertEqual(set(configs), set(checks.CHECK_KEYS))
        self.assertEqual(
            {k for k, c in configs.items() if c.mode == 'block'}, {'fits', 'collide', 'aisles_free', 'fire'}
        )
        self.assertEqual(configs['utility_reach'].params, {'max_m': 15.0})
        self.assertEqual(site.check_config_ids.sorted('sequence').mapped('check_key'), checks.CHECK_KEYS)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.env['f3d.check.config'].create({'site_id': site.id, 'check_key': 'fits', 'mode': 'warn'})

    def test_params_validation(self):
        config = self.site.check_config_ids.filtered(lambda c: c.check_key == 'utility_reach')
        config.params = {'max_m': 20}
        self.assertEqual(config.params['max_m'], 20.0)
        for bad in ({'max_m': 0}, {'max_m': 'x'}, {'tolerance_mm': -1}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                config.params = bad
