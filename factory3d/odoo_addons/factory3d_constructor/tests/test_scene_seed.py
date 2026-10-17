import json

from odoo.tests import tagged
from odoo.tools import file_open

from ..hooks import baseline_poses
from ..services import checks, snapshot, state
from .common import F3DConstructorCase

# каркаси стелажів у 3D-моделі мають власні коди; у конструкторі це самі місця-шаблони
FRAME_ALIAS = {'FG-RACK-R%d' % i: 'FG-R%d' % i for i in range(1, 6)}
FRAME_ALIAS.update({'RACK-R%d' % i: 'FUR-R%d' % i for i in range(1, 7)})


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSceneSeed(F3DConstructorCase):
    """Сід = усі 31 шар і всі кодовані об'єкти 3D-моделі переглядача; v1 зберігає запечені положення (CD-28)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with file_open('factory3d_constructor/data/scene_inventory.json', 'rb') as handle:
            cls.inventory = json.loads(handle.read().decode('utf-8'))
        cls.site = cls.env['f3d.site'].search([('seed_key', '=', 'main_demo')], limit=1)

    def test_all_layers_with_groups(self):
        self.assertTrue(self.site, "Сід «Меблеве підприємство» не завантажено")
        layers = self.site.layer_ids.sorted('sequence')
        self.assertEqual(len(layers), len(self.inventory['layers']))
        self.assertEqual(len(layers), 31)
        self.assertEqual(
            [(layer.name, layer.group_name) for layer in layers],
            [(item['label'], item['group']) for item in self.inventory['layers']],
        )
        self.assertEqual(len({layer.group_name for layer in layers}), 8)

    def test_layer_visibility_follows_seed(self):
        """Дах, інженерні мережі й територія вимкнені за замовчуванням: їхні зони на весь цех закривають верстати."""
        with file_open('factory3d_constructor/data/seed_site.json', 'rb') as handle:
            seed = json.loads(handle.read().decode('utf-8'))
        want = {item['name']: bool(item.get('visible', True)) for item in seed['layers']}
        got = {layer.name: layer.visible for layer in self.site.layer_ids}
        self.assertEqual(got, want)
        self.assertTrue(got['Виробничі лінії'])
        self.assertFalse(got['Пожежна сигналізація'])

    def test_every_inventory_code_is_in_the_seed(self):
        slots = self.env['f3d.slot'].search([('site_id', '=', self.site.id)])
        covered = set(self.env['f3d.placement'].search([('site_id', '=', self.site.id)]).mapped('code'))
        covered |= set(slots.mapped('code_prefix'))
        for slot in slots:
            covered |= {cell['code'] for cell in slot._f3d_cells()}
        missing = [
            code for code in self.inventory['objects'] if code not in covered and FRAME_ALIAS.get(code) not in covered
        ]
        self.assertEqual(missing, [], "Об'єкти 3D-моделі без запису в сіді")
        self.assertEqual(len(self.inventory['objects']), 1078)

    def test_placement_poses_agree_with_inventory(self):
        """Етап 2 рахує зсув від інвентаря: x, y — центр AABB, rotation — yaw; без правок зсувів немає."""
        poses = self.inventory['objects']
        checked = 0
        for placement in self.env['f3d.placement'].search([('site_id', '=', self.site.id)]):
            obj = poses.get(placement.code)
            self.assertTrue(obj, placement.code)
            self.assertAlmostEqual(placement.x_m, obj['x'], places=6, msg=placement.code)
            self.assertAlmostEqual(placement.y_m, obj['y'], places=6, msg=placement.code)
            self.assertAlmostEqual(placement.rotation, obj.get('yaw') or 0.0, places=6, msg=placement.code)
            checked += 1
        self.assertGreater(checked, 150)
        for slot in self.env['f3d.slot'].search([('site_id', '=', self.site.id), ('params', '!=', False)]):
            obj = poses.get(slot.code_prefix)
            if obj and slot.template != 'zone':
                self.assertAlmostEqual(slot.x_m, obj['x'], places=6, msg=slot.code_prefix)
                self.assertAlmostEqual(slot.y_m, obj['y'], places=6, msg=slot.code_prefix)

    def test_v1_snapshot_stores_baseline_poses(self):
        seed_version = self.site.version_ids.filtered('is_seed')
        self.assertEqual(len(seed_version), 1)
        snap = snapshot.load_snapshot(seed_version)
        poses = (snap.get('baseline') or {}).get('poses') or {}
        self.assertEqual(len(poses), len(self.inventory['objects']))
        self.assertEqual(poses['SAW-1'], baseline_poses()['poses']['SAW-1'])
        self.assertEqual(set(poses['SAW-1']), {'x', 'y', 'z', 'L', 'W', 'H', 'yaw'})
        self.assertEqual(seed_version.report['baseline_poses'], len(poses))

    def test_seed_has_no_issues(self):
        """Сід відкривається без блокувань (collide/fits/fire/aisles у режимі block не заважають публікації)."""
        blocks = [i for i in state.run_site_checks(self.site) if i['severity'] == 'block']
        self.assertEqual(blocks, [], [i['message'] for i in blocks[:5]])

    def test_exact_cells_have_the_object_code(self):
        slot = self.env['f3d.slot'].search([('site_id', '=', self.site.id), ('code_prefix', '=', 'UNLOAD-3')])
        self.assertTrue(slot, "UNLOAD-3 має бути в сіді (етап 2 його ховає)")
        self.assertEqual([cell['code'] for cell in slot._f3d_cells()], ['UNLOAD-3'])

    def test_people_and_vehicles_are_dynamic(self):
        expected = {c for c, o in self.inventory['objects'].items() if o['kind'] in ('person', 'vehicle')}
        dynamic = set(
            self.env['f3d.placement'].search([('site_id', '=', self.site.id), ('dynamic', '=', True)]).mapped('code')
        )
        self.assertEqual(dynamic, expected)
        self.assertEqual(len(expected), 50)

    def test_dynamic_placements_skip_collide_service_aisles_fire(self):
        variant = {
            'id': 1,
            'length': 2000,
            'width': 1000,
            'height': 1500,
            'service': {'front': 500, 'back': 0, 'left': 0, 'right': 0},
            'rotations': 'any',
            'layer_kinds': ['production'],
            'slot_types': [],
            'anchor': 'center',
            'front_side': 's',
        }
        layer = {'id': 10, 'name': "L", 'kind': 'production', 'elevation': 0.0, 'max_floor_load': 0.0, 'bounds': None}
        layer['aisles'] = [{'x0': 0, 'y0': 0, 'x1': 10, 'y1': 10, 'name': 'A'}]
        layer['fire_paths'] = []
        layer['slot_types'] = []
        layer['utilities'] = []

        def placement(pid, code, dynamic):
            return {
                'id': pid, 'layer_id': 10, 'variant_id': 1, 'slot_id': None, 'cell_code': None, 'code': code,
                'name': code, 'x': 5.0, 'y': 5.0, 'rotation': 0.0, 'dynamic': dynamic,
            }  # fmt: skip

        base = {
            'site': {'building': {'length': 50, 'width': 50, 'height': 9}},
            'layers': [layer],
            'slots': [],
            'variants': [variant],
        }
        configs = [{'check': k, 'enabled': True, 'mode': 'block', 'params': {}} for k in checks.CHECK_KEYS]
        solid = checks.run_checks(dict(base, placements=[placement(1, 'A', False), placement(2, 'B', False)]), configs)
        self.assertTrue({i['check'] for i in solid} >= {'collide', 'aisles_free'})
        moving = checks.run_checks(dict(base, placements=[placement(1, 'A', True), placement(2, 'B', True)]), configs)
        self.assertEqual([i for i in moving if i['check'] != 'fits'], [])
