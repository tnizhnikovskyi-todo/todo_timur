import json

from odoo import Command
from odoo.tests import tagged

from ..services import addr as addr_mod, snapshot
from .common import PASSWORD, F3DConstructorCase, F3DConstructorHttpCase


class NewFieldsMixin:
    @classmethod
    def _new_fields_setup(cls):
        env = cls.env
        cls.stype = env['td.slot.type'].create({'code': 'R01', 'name': "Фронтальний", 'template': 'pallet_rack'})
        cls.func = env['td.term'].create({'term_type': 'zone_function', 'key': 'receiving', 'name': "Приймання"})
        cls.attr_cold = env['td.term'].create({'term_type': 'zone_attr', 'key': 'cold', 'name': "Холод"})
        cls.attr_long = env['td.term'].create({'term_type': 'zone_attr', 'key': 'long', 'name': "Довгомір"})
        cls.category = env['stock.storage.category'].create({'name': "Паллети", 'max_weight': 1000})
        cls.removal = env['product.removal'].search([('method', '=', 'fifo')], limit=1) or env[
            'product.removal'
        ].create({'name': "FIFO", 'method': 'fifo'})
        cls.product = env['product.product'].create({'name': "Тестовий товар W0B"})
        cls.warehouse = env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.slot_vals = {
            'type_id': cls.stype.id,
            'function_id': cls.func.id,
            'attr_ids': [cls.attr_cold.id, cls.attr_long.id],
            'storage_category_id': cls.category.id,
            'removal_strategy_id': cls.removal.id,
            'temp_min_c': 2.0,
            'temp_max_c': 8.0,
            'tech': 'reach_truck',
            'addr': {'tpl': '{row}-{bay}'},
            'depth_mode': 'cell',
        }
        cls.items = [
            {'kind': 'column', 'x': 6.0, 'y': 6.0},
            {'kind': 'wall', 'x1': 0, 'y1': 0, 'x2': 10, 'y2': 0, 't': 0.3},
        ]


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestNewFieldsApi(NewFieldsMixin, F3DConstructorHttpCase):
    """W0-B: API-03 `load` віддає й API-04 `save` приймає нові поля MERGE.md §3.3–3.4 (round-trip)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._new_fields_setup()

    def test_load_without_data_has_empty_extensions(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        slot = self.make_slot(prefix='NF-0')
        data = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertTrue(data['ok'], data)
        self.assertEqual(data['rules'], {'putaway': [], 'replenish': []})
        self.assertEqual(data['presets'], [])
        codes = [t['code'] for t in data['types']]
        self.assertIn('R01', codes)  # тип із фікстури
        self.assertEqual(len(codes), 51)  # + 50 типів каталогу S1
        self.assertEqual((data['site']['loc_tree'], data['site']['depth_mode']), ('flat', 'level'))
        self.assertEqual(
            (data['site']['addr'], data['site']['warehouse'], data['site']['sprinkler_height']), ({}, None, 0.0)
        )
        self.assertTrue(all(layer['items'] == [] for layer in data['layers']))
        item = next(s for s in data['slots'] if s['id'] == slot.id)
        self.assertEqual(
            (item['type_id'], item['function_id'], item['attr_ids'], item['tech'], item['addr'], item['depth_mode']),
            (None, None, [], None, {}, None),
        )

    def test_save_load_roundtrip_of_new_fields(self):
        self.authenticate(self.u_manager.login, PASSWORD)
        layer = self.layers['storage']
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'td.layer',
                    'op': 'write',
                    'id': layer.id,
                    'etag': layer._f3d_etag(),
                    'vals': {'items': self.items},
                },
                {
                    'model': 'td.slot',
                    'op': 'create',
                    'tmp': 's1',
                    'vals': dict(
                        self.slot_vals,
                        uid='a' * 32,
                        layer_id=layer.id,
                        template='pallet_rack',
                        code_prefix='NF-R1',
                        params={
                            'bays': 2,
                            'levels': 2,
                            'bay_width': 2.7,
                            'depth': 1.1,
                            'level_height': 1.5,
                            'positions_per_bay': 2,
                            'max_load_kg': 800,
                        },
                    ),
                },
                {
                    'model': 'td.putaway.rule',
                    'op': 'create',
                    'tmp': 'p1',
                    'vals': {
                        'uid': 'b' * 32,
                        'product_id': self.product.id,
                        'out_code': 'NF-R1-B01-L1',
                        'in_location_id': self.wh_stock.id,
                        'package_type_ids': [],
                        'sublocation': 'last_used',
                    },
                },
                {
                    'model': 'td.replenish.rule',
                    'op': 'create',
                    'tmp': 'r1',
                    'vals': {'product_id': self.product.id, 'cell_code': 'NF-R1-B01-L1', 'min_qty': 2, 'max_qty': 9},
                },
            ],
        )
        self.assertTrue(res['ok'], res)
        self.assertEqual(set(res['id_map']), {'s1', 'p1', 'r1'})
        self.assertIn('td.putaway.rule:%d' % res['id_map']['p1'], res['etags'])
        self.site.write(
            {'addr': {'tpl': '{row}'}, 'loc_tree': 'row', 'sprinkler_height_m': 6.0, 'warehouse_id': self.warehouse.id}
        )
        data = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        loaded_layer = next(item for item in data['layers'] if item['id'] == layer.id)
        self.assertEqual(loaded_layer['items'], self.items)
        slot = next(item for item in data['slots'] if item['id'] == res['id_map']['s1'])
        expected = dict(
            self.slot_vals,
            attr_ids=sorted(self.slot_vals['attr_ids']),
            addr=addr_mod.normalize_addr(self.slot_vals['addr']),  # R-22 (S1): addr нормалізується
        )
        self.assertEqual({key: (sorted(slot[key]) if key == 'attr_ids' else slot[key]) for key in expected}, expected)
        putaway = data['rules']['putaway']
        self.assertEqual(len(putaway), 1)
        self.assertEqual(
            (putaway[0]['uid'], putaway[0]['product_id'], putaway[0]['out_code'], putaway[0]['sublocation']),
            ('b' * 32, self.product.id, 'NF-R1-B01-L1', 'last_used'),
        )
        self.assertEqual((putaway[0]['deleted'], putaway[0]['odoo_rule_id']), (False, None))
        replenish = data['rules']['replenish']
        self.assertEqual(
            [(r['cell_code'], r['min_qty'], r['max_qty']) for r in replenish], [('NF-R1-B01-L1', 2.0, 9.0)]
        )
        self.assertEqual(data['site']['loc_tree'], 'row')
        self.assertEqual(data['site']['warehouse']['id'], self.warehouse.id)
        self.assertEqual(
            (data['site']['addr'], data['site']['sprinkler_height']), (addr_mod.normalize_addr({'tpl': '{row}'}), 6.0)
        )
        # правило: write з etag, конфлікт, видалення
        rule = self.env['td.putaway.rule'].browse(res['id_map']['p1'])
        ok = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'td.putaway.rule',
                    'op': 'write',
                    'id': rule.id,
                    'etag': rule._f3d_etag(),
                    'vals': {'deleted': True},
                }
            ],
        )
        self.assertTrue(ok['ok'], ok)
        self.advance_clock()
        stale = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'td.putaway.rule',
                    'op': 'write',
                    'id': rule.id,
                    'etag': '2000-01-01 00:00:00.000000',
                    'vals': {'deleted': False},
                }
            ],
        )
        self.assertEqual((stale['ok'], stale['code']), (False, 'conflict'))
        self.assertEqual(stale['current']['deleted'], True)
        self.assertTrue(rule.exists() and self.site.draft_rev > 0)

    def test_save_validates_references_and_fields(self):
        self.authenticate(self.u_manager.login, PASSWORD)
        slot = self.make_slot(prefix='NF-V1')

        def write(vals, model='td.slot', record=slot):
            return self.rpc(
                '/f3d/constructor/save',
                site_id=self.site.id,
                ops=[{'model': model, 'op': 'write', 'id': record.id, 'etag': record._f3d_etag(), 'vals': vals}],
            )

        self.assertEqual(write({'type_id': 999999})['code'], 'validation')
        self.assertEqual(write({'type_id': 'x'})['code'], 'validation')
        self.assertEqual(write({'function_id': self.attr_cold.id})['code'], 'validation')  # не той довідник
        self.assertEqual(write({'attr_ids': [self.func.id]})['code'], 'validation')
        self.assertEqual(write({'attr_ids': 'cold'})['code'], 'validation')
        self.assertEqual(
            write({'odoo_rule_id': 1}, 'td.putaway.rule', self._rule())['code'], 'validation'
        )  # лише публікація
        self.assertTrue(write({'type_id': self.stype.id, 'attr_ids': []})['ok'])
        self.assertTrue(write({'type_id': None, 'function_id': False})['ok'])
        slot.invalidate_recordset()
        self.assertFalse(slot.type_id or slot.function_id)

    def _rule(self):
        return self.env['td.putaway.rule'].create({'site_id': self.site.id, 'product_id': self.product.id})

    def test_designer_writes_layer_items_but_not_layer_settings(self):
        """R-11: `items` — вміст шару: його пишуть ролі з edit_group_ids; налаштування шару — лише менеджер."""
        self.authenticate(self.u_tech.login, PASSWORD)
        layer = self.layers['production']  # edit_group_ids = технолог (R-23)
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'td.layer',
                    'op': 'write',
                    'id': layer.id,
                    'etag': layer._f3d_etag(),
                    'vals': {'items': self.items},
                }
            ],
        )
        self.assertTrue(res['ok'], res)
        layer.invalidate_recordset()
        self.assertEqual(layer.items, self.items)
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'td.layer',
                    'op': 'write',
                    'id': layer.id,
                    'etag': layer._f3d_etag(),
                    'vals': {'name': "Інше"},
                }
            ],
        )
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))
        foreign = self.layers['storage']  # шар комірника
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'td.layer',
                    'op': 'write',
                    'id': foreign.id,
                    'etag': foreign._f3d_etag(),
                    'vals': {'items': []},
                }
            ],
        )
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestNewFieldsSnapshot(NewFieldsMixin, F3DConstructorCase):
    """W0-B: знімок версії (schema 2) містить нові поля, відкат повертає їх, порожні поля знімок не змінюють."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._new_fields_setup()

    def fill(self):
        slot = self.make_slot(prefix='NF-S1')
        slot.write(dict(self.slot_vals, attr_ids=[Command.set([self.attr_cold.id, self.attr_long.id])]))
        self.layers['storage'].items = self.items
        self.site.write(
            {
                'addr': {'tpl': '{row}'},
                'loc_tree': 'section',
                'depth_mode': 'cell',
                'sprinkler_height_m': 6.5,
                'aisle_tech': 'reach_truck',
                'parse_rules': {'sep': '-'},
                'wizard_state': {'step': 3},
                'warehouse_id': self.warehouse.id,
            }
        )
        return slot

    def test_defaults_do_not_change_snapshot_shape(self):
        slot = self.make_slot(prefix='NF-D1')
        snap = snapshot.build_snapshot(self.site)
        self.assertEqual(snap['schema'], 2)
        item = next(s for s in snap['slots'] if s['uid'] == slot.uid)
        self.assertEqual(
            set(item),
            {
                'uid',
                'layer_uid',
                'template',
                'code_prefix',
                'x_m',
                'y_m',
                'rotation',
                'params',
                'overrides',
                'parent_location',
                'active',
            },
        )
        self.assertFalse({'items'} & set(snap['layers'][0]))
        self.assertEqual(
            set(snap['site']),
            {'name', 'code', 'building', 'column_grid', 'default_parent_location_id', 'default_parent_location'},
        )
        self.assertNotIn('sections', snap)

    def test_snapshot_contains_and_restores_new_fields(self):
        slot = self.fill()
        version = snapshot.create_version(self.site, "з новими полями")
        snap = json.loads(version.snapshot_id.raw.decode())
        item = next(s for s in snap['slots'] if s['uid'] == slot.uid)
        self.assertEqual(item['type'], {'id': self.stype.id, 'code': 'R01'})
        self.assertEqual((item['function'], item['attrs']), ('receiving', ['cold', 'long']))
        self.assertEqual(item['storage_category'], {'id': self.category.id, 'name': "Паллети"})
        self.assertEqual(
            (item['temp_min_c'], item['temp_max_c'], item['tech'], item['depth_mode']),
            (2.0, 8.0, 'reach_truck', 'cell'),
        )
        self.assertEqual(snap['site']['loc_tree'], 'section')
        self.assertEqual(snap['site']['warehouse'], {'id': self.warehouse.id, 'code': self.warehouse.code})
        self.assertEqual(
            next(layer for layer in snap['layers'] if layer['uid'] == self.layers['storage'].uid)['items'], self.items
        )
        self.assertEqual(snapshot.count_differences(snapshot.build_snapshot(self.site), snap), 0)
        # змінюємо все й відкочуємо до версії
        slot.write(
            {
                'type_id': False,
                'function_id': False,
                'attr_ids': [Command.clear()],
                'temp_min_c': 0,
                'temp_max_c': 0,
                'tech': False,
                'addr': False,
                'depth_mode': False,
                'storage_category_id': False,
                'removal_strategy_id': False,
            }
        )
        self.layers['storage'].items = []
        self.site.write(
            {
                'loc_tree': 'flat',
                'depth_mode': 'level',
                'sprinkler_height_m': 0,
                'warehouse_id': False,
                'addr': False,
                'parse_rules': False,
                'wizard_state': False,
                'aisle_tech': False,
            }
        )
        self.assertGreater(snapshot.count_differences(snapshot.build_snapshot(self.site), snap), 0)
        snapshot.restore_draft(version)
        slot.invalidate_recordset()
        self.assertEqual(
            (slot.type_id, slot.function_id, slot.storage_category_id, slot.removal_strategy_id),
            (self.stype, self.func, self.category, self.removal),
        )
        self.assertEqual(slot.attr_ids, self.attr_cold | self.attr_long)
        self.assertEqual(
            (slot.temp_min_c, slot.temp_max_c, slot.tech, slot.depth_mode, slot.addr),
            (2.0, 8.0, 'reach_truck', 'cell', addr_mod.normalize_addr({'tpl': '{row}-{bay}'})),
        )
        self.assertEqual(self.layers['storage'].items, self.items)
        site = self.site
        self.assertEqual(
            (site.loc_tree, site.depth_mode, site.sprinkler_height_m, site.aisle_tech),
            ('section', 'cell', 6.5, 'reach_truck'),
        )
        self.assertEqual(
            (site.addr, site.parse_rules, site.wizard_state, site.warehouse_id),
            (addr_mod.normalize_addr({'tpl': '{row}'}), {'sep': '-'}, {'step': 3}, self.warehouse),
        )
        self.assertEqual(snapshot.count_differences(snapshot.build_snapshot(site), snap), 0)
        self.assertEqual(site.draft_changes, 0)

    def test_restore_old_snapshot_resets_new_fields_to_defaults(self):
        """Знімок без розширень (schema 1) читається; відсутні ключі = типові значення (повна заміна)."""
        slot = self.make_slot(prefix='NF-O1')
        old = snapshot.build_snapshot(self.site)
        old['schema'] = 1
        self.fill()
        snapshot.apply_snapshot(self.site, old)
        slot.invalidate_recordset()
        self.assertFalse(slot.type_id or slot.function_id or slot.attr_ids or slot.tech or slot.addr or slot.depth_mode)
        self.assertEqual((slot.temp_min_c, slot.temp_max_c), (0.0, 0.0))
        self.assertFalse(self.layers['storage'].items)
        self.assertEqual(
            (self.site.loc_tree, self.site.depth_mode, self.site.warehouse_id),
            ('flat', 'level', self.env['stock.warehouse']),
        )

    def test_missing_references_are_ignored_on_restore(self):
        slot = self.fill()
        snap = snapshot.build_snapshot(self.site)
        item = next(s for s in snap['slots'] if s['uid'] == slot.uid)
        item['type'] = {'id': 0, 'code': 'NO_SUCH'}
        item['storage_category'] = {'id': 0, 'name': 'немає такої'}
        item['attrs'] = ['cold', 'ghost']
        snapshot.apply_snapshot(self.site, snap)
        slot.invalidate_recordset()
        self.assertFalse(slot.type_id or slot.storage_category_id)
        self.assertEqual(slot.attr_ids, self.attr_cold)
