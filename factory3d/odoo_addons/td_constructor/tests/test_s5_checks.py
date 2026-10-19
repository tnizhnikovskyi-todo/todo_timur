import json

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from ..services import building, rack_spec, state as state_mod
from ..services.schemas import SchemaError
from . import golden_s5
from .common import F3DConstructorCase

L_CONTOUR = golden_s5.L_CONTOUR


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s5")
class TestS5Building(F3DConstructorCase):
    """S5: об'єкти будівлі (R-22), права на `items`, перевірки `inside` / `aisle_width` / `height` на даних БД, N-06."""

    def item(self, iid, kind, x, y, **kw):
        return dict({'id': iid, 'kind': kind, 'name': '', 'x': x, 'y': y, 'w': 1.0, 'd': 1.0, 'rot': 0}, **kw)

    def enable(self, *keys, mode='warn'):
        Config = self.env['td.check.config']
        for key in keys:
            rows = Config.search([('site_id', '=', self.site.id), ('check_key', '=', key)])
            if rows:
                rows.write({'enabled': True, 'mode': mode})
            else:
                Config.create({'site_id': self.site.id, 'check_key': key, 'enabled': True, 'mode': mode})

    def issues(self, check):
        return sorted(
            (tuple(i['codes']), i['severity']) for i in state_mod.run_site_checks(self.site) if i['check'] == check
        )

    # --- золоті фікстури та R-22 ---------------------------------------------------------------------
    def test_fixtures_match_code(self):
        path = golden_s5.FIXTURES / (golden_s5.NAME + '.json')
        self.assertTrue(path.is_file(), "немає фікстури %s" % path)
        for name, data in golden_s5.build().items():
            self.assertEqual(
                json.loads(path.read_text(encoding='utf-8')),
                json.loads(golden_s5.dump(data)),
                "%s.json застарів: python3 odoo_addons/td_constructor/tests/golden_s5.py --write" % name,
            )

    def test_items_normalization_and_errors(self):
        cases = golden_s5.item_cases()
        self.assertEqual(building.normalize_items(cases['good']), cases['normalized'])
        wall = next(it for it in cases['normalized'] if it['kind'] == 'wall')
        self.assertEqual((wall['d'], wall['th']), (0.3, 0.3), "товщина стіни дублюється в d")
        office = next(it for it in cases['normalized'] if it['kind'] == 'office')
        self.assertIsNone(office['location_uid'], "зв'язок із локацією — лише ворота й док")
        for case in cases['bad']:
            with self.assertRaises(SchemaError, msg=case['label']) as ctx:
                building.normalize_items(case['value'])
            self.assertEqual(str(ctx.exception), case['error'])
        self.assertEqual(building.normalize_items(None), [])
        with self.assertRaises(SchemaError):
            building.normalize_items([{'id': 'a', 'kind': 'column', 'x': 0, 'y': 0, 'w': 1, 'd': 1}] * 2)
        self.assertEqual(len(building.normalize_items([self.item('i%d' % n, 'column', n, 0) for n in range(300)])), 300)

    def test_layer_items_validation_and_load(self):
        layer = self.layers['building']
        layer.items = [self.item('c1', 'column', 5, 5, w=0.4, d=0.4), self.item('g1', 'gate', 0, 5, location_uid='L-1')]
        self.assertEqual([it['id'] for it in layer.items], ['c1', 'g1'])
        self.assertEqual(state_mod.layer_dict(layer)['items'][1]['location_uid'], 'L-1')
        with self.assertRaises(ValidationError):
            layer.items = [self.item('c1', 'column', 5, 5, w=0)]
        with self.assertRaises(ValidationError):
            layer.items = [self.item('c1', 'tree', 5, 5)]
        with self.assertRaises(ValidationError):
            layer.items = {'id': 'x'}
        layer.items = []
        self.assertEqual(state_mod.layer_dict(layer)['items'], [])

    def test_layer_items_rights(self):
        layer = self.layers['building']
        items = [self.item('c1', 'column', 5, 5, w=0.4, d=0.4)]
        with self.assertRaises(AccessError):
            layer.with_user(self.u_store).write({'items': items})
        layer.edit_group_ids = [Command.set([self.env.ref('td_constructor.group_td_constructor_storekeeper').id])]
        layer.with_user(self.u_store).write({'items': items})
        self.assertEqual(layer.items[0]['id'], 'c1')
        with self.assertRaises(AccessError, msg="контур (bounds) — лише менеджер"):
            layer.with_user(self.u_store).write({'bounds': L_CONTOUR})
        layer.with_user(self.u_manager).write({'bounds': L_CONTOUR})
        self.assertEqual(len(layer.bounds), 6)
        with self.assertRaises(ValidationError, msg="контур не може перетинати сам себе"):
            layer.bounds = [[0, 0], [10, 10], [10, 0], [0, 10]]

    # --- перевірки на даних БД -----------------------------------------------------------------------
    def test_inside_with_contour_and_items(self):
        building_layer = self.layers['building']
        building_layer.bounds = L_CONTOUR
        building_layer.items = [
            self.item('col', 'column', 30.0, 10.0, w=0.4, d=0.4, name='К-1'),
            self.item('gt', 'gate', 10.0, 1.5),
        ]
        self.make_slot(prefix='IN', x=10.0, y=8.0, bays=2)
        self.make_slot(prefix='OUT', x=30.0, y=22.0, bays=2)
        self.make_slot(prefix='COL', x=30.0, y=10.0, bays=2)
        self.make_slot(prefix='GATE', x=10.0, y=1.5, bays=2)
        self.enable('inside', mode='block')
        got = self.issues('inside')
        self.assertEqual(got, [(('COL',), 'block'), (('OUT',), 'block')])
        self.enable('inside', mode='warn')
        self.assertTrue(all(sev == 'warn' for _codes, sev in self.issues('inside')))
        row = self.env['td.check.config'].search([('site_id', '=', self.site.id), ('check_key', '=', 'inside')])
        row.enabled = False
        self.assertEqual(self.issues('inside'), [])

    def test_aisle_width_by_site_and_zone_tech(self):
        self.layers['building'].aisles = [
            {'id': 'a1', 'name': "Вузький", 'x0': 0, 'y0': 0, 'x1': 30, 'y1': 2.0},
            {'id': 'a2', 'name': "Достатній", 'x0': 0, 'y0': 4, 'x1': 30, 'y1': 7.0},
            {'id': 'a3', 'name': "У зоні візків", 'x0': 40, 'y0': 2, 'x1': 41.0, 'y1': 12},
        ]
        self.make_slot(prefix='A1', x=10.0, y=15.0, bays=4)
        self.make_slot(prefix='A2', x=10.0, y=17.5, bays=4)  # зазор 1.4 м
        zone = self.make_slot(
            prefix='ZV', template='zone', x=0.0, y=0.0, polygon=[[38, 0], [46, 0], [46, 14], [38, 14]]
        )
        self.enable('aisle_width')
        self.assertEqual(self.issues('aisle_width'), [], "техніку складу не задано — перевірка мовчить")
        self.site.aisle_tech = 'reach'
        self.assertEqual(
            [codes for codes, _sev in self.issues('aisle_width')], [('A1', 'A2'), ('У зоні візків',), ("Вузький",)]
        )
        zone.tech = 'hand'  # візки: мінімум 1.2 м → прохід 1.0 м усе ще вузький
        self.assertIn((("У зоні візків",), 'warn'), self.issues('aisle_width'))
        zone.tech = 'custom:0.9'
        self.assertNotIn((("У зоні візків",), 'warn'), self.issues('aisle_width'))
        self.site.aisle_tech = 'custom:1.2'  # свій мінімум складу: проїзд 1.4 м достатній
        self.assertEqual([codes for codes, _sev in self.issues('aisle_width')], [])
        self.site.aisle_tech = 'none'
        self.assertEqual(self.issues('aisle_width'), [])

    def test_height_against_ceiling_and_sprinklers(self):
        self.site.sprinkler_height_m = 4.5
        self.make_slot(prefix='LOW', x=10.0, y=10.0, bays=2, levels=2)  # 3.25 м
        self.make_slot(prefix='MID', x=20.0, y=10.0, bays=2, levels=3)  # 4.75 м: ближче 0.5 м до спринклерів
        self.make_slot(prefix='TALL', x=30.0, y=10.0, bays=2, levels=6, level_height=1.6)  # 9.85 м > стелі 8 м
        self.make_slot(kind='yard', prefix='YARD', x=40.0, y=10.0, bays=2, levels=6)  # двір не перевіряється
        self.enable('height')
        self.assertEqual(self.issues('height'), [(('MID',), 'warn'), (('TALL',), 'warn')])
        self.site.sprinkler_height_m = 0
        self.assertEqual(self.issues('height'), [(('TALL',), 'warn')])

    def test_tech_catalog_and_zone_resolution(self):
        self.assertEqual(
            (building.tech_min('reach'), building.tech_min('reach:2.5'), building.tech_min('none')), (2.8, 2.5, None)
        )
        self.assertEqual(building.parse_tech('custom:3,2'), ('custom', 3.2))
        self.assertEqual(building.parse_tech('xyz'), (None, None))
        self.assertEqual(building.tech_label('forklift'), "Навантажувач")
        self.assertAlmostEqual(building.polygon_area(L_CONTOUR), 40 * 15 + 20 * 15)
        self.assertAlmostEqual(building.polygon_perimeter([[0, 0], [4, 0], [0, 3]]), 12.0)
        self.assertEqual(building.slot_height('pallet_rack', {'levels': 4, 'level_height': 1.5}), 6.25)
        self.assertEqual(building.slot_height('shelf', {'shelves': 5, 'cell_h': 1.0}), 5.1)

    # --- специфікація на даних БД ------------------------------------------------------------------------
    def test_spec_from_db_state(self):
        self.make_slot(prefix='R1', x=10.0, y=5.0, bays=4, levels=3)
        self.make_slot(prefix='R2', x=10.0, y=12.0, bays=2, levels=5, double_sided=True, gap_y=0.2)
        self.make_slot(prefix='S1', template='shelf', x=30.0, y=5.0, sections=3, shelves=5)
        self.make_slot(prefix='F1', template='floor_stack', x=40.0, y=5.0, rows=1, cols=2)
        state = state_mod.checks_state(self.site)
        spec = rack_spec.build_spec(rack_spec.spec_slots(state))
        self.assertEqual(spec['summary']['racks'], 3)
        by_code = {r['code']: r for r in spec['racks']}
        self.assertEqual(
            [(ln['key'], ln['qty']) for ln in by_code['R1']['lines']], [('frame', 5), ('beam', 24), ('brace', 8)]
        )
        self.assertEqual(
            [(ln['key'], ln['qty']) for ln in by_code['R2']['lines']],
            [('frame', 6), ('beam', 20), ('brace', 8), ('tie', 3)],
        )
        shelf = next(ln for ln in by_code['S1']['lines'] if ln['key'] == 'shelf')
        self.assertEqual((shelf['qty'], shelf['area']), (15, round(15 * 0.9 * 0.4, 4)))
        self.assertNotIn('F1', by_code)
