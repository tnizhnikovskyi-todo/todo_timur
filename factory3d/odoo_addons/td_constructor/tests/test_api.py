import json

from odoo.tests import tagged

from ..hooks import seed as seed_hook
from .common import F3DConstructorHttpCase, PASSWORD


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestApi(F3DConstructorHttpCase):
    """AC-04 (API-02), AC-07 (API-01/03), AC-30 (API-06/07), AC-47, AC-48, AC-61, AC-62: HTTP/JSON API §7."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('factory3d.constructor.publish_enabled', 'True')

    def login(self, user):
        self.authenticate(user.login, PASSWORD)

    def bump_write_date(self, model, record_id):
        """Імітація того, що запис змінив інший користувач у пізнішій транзакції (write_date = час транзакції, R-21)."""
        self.env.flush_all()
        table = self.env[model]._table
        self.env.cr.execute(
            "UPDATE %s SET write_date = write_date + interval '1 second' WHERE id = %%s" % table, (record_id,)
        )
        self.env.invalidate_all()

    # --- AC-04 -------------------------------------------------------------------------------------
    def test_ac04_create_site(self):
        self.login(self.u_manager)
        res = self.rpc('/f3d/constructor/site/create', name="Склад 2", code='S2')
        self.assertTrue(res['ok'], res)
        site = self.env['f3d.site'].browse(res['site_id'])
        self.assertEqual((site.building_length_m, site.building_width_m, site.building_height_m), (60, 30, 8))
        self.assertEqual(site.layer_ids.sorted('sequence').mapped('elevation_m'), [0.0, 0.0, 0.0, 6.0, 0.0])
        self.assertEqual(len(site.check_config_ids), 7)
        self.assertEqual(site.slot_count, 0)
        catalog = self.rpc('/f3d/constructor/load', site_id=site.id)['catalog']
        self.assertGreaterEqual(sum(len(p['variants']) for p in catalog), 4)
        # валідація
        self.assertEqual(self.rpc('/f3d/constructor/site/create', name="X", code='bad code')['code'], 'validation')
        self.assertEqual(self.rpc('/f3d/constructor/site/create', name="Дубль", code='S2')['code'], 'validation')
        self.login(self.u_tech)
        res = self.rpc('/f3d/constructor/site/create', name="Склад 3", code='S3')
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))

    # --- AC-07 -------------------------------------------------------------------------------------
    def test_ac07_companies(self):
        company2 = self.env['res.company'].create({'name': "Друга компанія"})
        site2 = (
            self.env['f3d.site']
            .with_context(f3d_blank=True)
            .create({'name': "Чужа", 'code': 'OTH', 'company_id': company2.id})
        )
        self.login(self.u_manager)
        ids = [s['id'] for s in self.rpc('/f3d/constructor/sites')['sites']]
        self.assertIn(self.site.id, ids)
        self.assertNotIn(site2.id, ids)
        res = self.rpc('/f3d/constructor/load', site_id=site2.id)
        self.assertEqual((res['ok'], res['code']), (False, 'not_found'))
        res = self.rpc('/f3d/constructor/save', site_id=site2.id, ops=[])
        self.assertEqual(res['code'], 'not_found')

    # --- AC-62: структура load, коди помилок, ліміти ------------------------------------------------
    def test_ac62_load_structure_and_errors(self):
        slot = self.make_slot(prefix='LD-R1', bays=3, levels=2)
        placement = self.make_placement(code='LD-M1')
        self.login(self.u_manager)
        res = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertTrue(res['ok'])
        for key in ('site', 'layers', 'slots', 'placements', 'catalog', 'checks', 'versions', 'rights'):
            self.assertIn(key, res)
        site = res['site']
        self.assertEqual(site['building'], {'length': 60.0, 'width': 30.0, 'height': 8.0})
        self.assertEqual(
            set(site['settings']),
            {'autosave_ms', 'max_model_mb', 'max_triangles', 'eps_mm', 'reach_default_m', 'publish_enabled'},
        )
        layer = next(layer for layer in res['layers'] if layer['kind'] == 'storage')
        for key in (
            'id',
            'uid',
            'name',
            'kind',
            'sequence',
            'elevation',
            'grid_step',
            'aisle_width',
            'max_floor_load',
            'bounds',
            'slot_types',
            'edit_groups',
            'color',
            'opacity',
            'style',
            'visible',
            'aisles',
            'fire_paths',
            'utilities',
            'underlay',
            'etag',
        ):
            self.assertIn(key, layer)
        self.assertEqual(layer['edit_groups'][0]['role'], 'storekeeper')
        s = next(s for s in res['slots'] if s['id'] == slot.id)
        self.assertEqual((s['code_prefix'], s['cell_count'], s['x'], s['template']), ('LD-R1', 6, 30.0, 'pallet_rack'))
        p = next(p for p in res['placements'] if p['id'] == placement.id)
        self.assertEqual((p['code'], p['variant_id'], p['equipment']), ('LD-M1', self.variant.id, None))
        variant = next(v for e in res['catalog'] for v in e['variants'] if v['id'] == self.variant.id)
        for key in (
            'id',
            'name',
            'length',
            'width',
            'height',
            'service',
            'rotations',
            'layer_kinds',
            'slot_types',
            'utilities',
            'power_kw',
            'panel',
            'weight_kg',
            'floor_load',
            'anchor',
            'front_side',
            'create_workcenter',
            'model',
            'etag',
        ):
            self.assertIn(key, variant)
        self.assertEqual(res['rights']['is_manager'], True)
        self.assertEqual(len(res['checks']), 7)
        # коди помилок
        self.assertEqual(self.rpc('/f3d/constructor/load', site_id=0)['code'], 'not_found')
        self.assertEqual(self.rpc('/f3d/constructor/save', site_id=self.site.id, ops="x")['code'], 'validation')
        too_many = [{'model': 'f3d.slot', 'op': 'unlink', 'id': 1}] * 501
        self.assertEqual(self.rpc('/f3d/constructor/save', site_id=self.site.id, ops=too_many)['code'], 'too_many')
        self.assertEqual(self.rpc('/f3d/constructor/version/restore', version_id=0)['code'], 'not_found')
        self.assertEqual(
            self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=False)['code'], 'validation'
        )

    def test_ac62_unauthenticated(self):
        self.authenticate(None, None)
        resp = self.opener.post(
            self.base_url() + '/f3d/constructor/sites', json={'jsonrpc': '2.0', 'method': 'call', 'params': {}}
        )
        data = resp.json()
        self.assertIn('error', data)  # auth='user': сесія потрібна

    # --- AC-47 -------------------------------------------------------------------------------------
    def test_ac47_plain_user_rights_code(self):
        self.login(self.u_plain)
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'f3d.slot',
                    'op': 'create',
                    'tmp': 't1',
                    'vals': {
                        'layer_id': self.layers['storage'].id,
                        'template': 'pallet_rack',
                        'code_prefix': 'PL-1',
                        'x_m': 5.0,
                        'y_m': 5.0,
                        'params': {'bays': 2, 'levels': 1},
                    },
                }
            ],
        )
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))
        self.assertTrue(self.rpc('/f3d/constructor/load', site_id=self.site.id)['ok'])  # читання дозволене
        self.assertFalse(self.env['f3d.slot'].search([('code_prefix', '=', 'PL-1')]))

    # --- AC-48 / AC-61: save, id_map, etag ----------------------------------------------------------
    def test_ac48_form_and_api_write_same_value(self):
        slot = self.make_slot(prefix='EQ-R1', bays=2, levels=1)
        self.login(self.u_store)
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[{'model': 'f3d.slot', 'op': 'write', 'id': slot.id, 'etag': slot._f3d_etag(), 'vals': {'x_m': 12.5}}],
        )
        self.assertTrue(res['ok'], res)
        self.assertEqual(slot.x_m, 12.5)
        loaded = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertEqual(next(s for s in loaded['slots'] if s['id'] == slot.id)['x'], 12.5)
        slot.write({'x_m': 13.25})  # «форма Odoo»
        loaded = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertEqual(next(s for s in loaded['slots'] if s['id'] == slot.id)['x'], 13.25)

    def test_ac61_save_id_map_conflict_atomic(self):
        self.login(self.u_manager)
        rev0 = self.site.draft_rev
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'f3d.slot',
                    'op': 'create',
                    'tmp': 't1',
                    'vals': {
                        'layer_id': self.layers['storage'].id,
                        'template': 'pallet_rack',
                        'code_prefix': 'SV-R1',
                        'x_m': 30.0,
                        'y_m': 10.0,
                        'params': {'bays': 2, 'levels': 2},
                    },
                },
                {
                    'model': 'f3d.placement',
                    'op': 'create',
                    'tmp': 't2',
                    'vals': {
                        'layer_id': self.layers['production'].id,
                        'variant_id': self.variant.id,
                        'code': 'SV-M1',
                        'name': "Станок",
                        'x_m': 20.0,
                        'y_m': 10.0,
                        'slot_id': None,
                    },
                },
            ],
        )
        self.assertTrue(res['ok'], res)
        slot = self.env['f3d.slot'].browse(res['id_map']['t1'])
        self.assertEqual(slot.code_prefix, 'SV-R1')
        self.assertGreater(res['rev'], rev0)
        self.assertTrue(res['has_changes'])
        self.assertIn('f3d.slot:%d' % slot.id, res['etags'])
        # «@tmp» у посиланнях на нові записи
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'f3d.slot',
                    'op': 'create',
                    'tmp': 'a',
                    'vals': {
                        'layer_id': self.layers['production'].id,
                        'template': 'machine_spot',
                        'code_prefix': 'SV-S1',
                        'x_m': 40.0,
                        'y_m': 20.0,
                        'params': {'length': 5.0, 'width': 2.0},
                    },
                },
                {
                    'model': 'f3d.placement',
                    'op': 'create',
                    'tmp': 'b',
                    'vals': {
                        'layer_id': self.layers['production'].id,
                        'variant_id': self.variant.id,
                        'code': 'SV-M2',
                        'name': "Станок 2",
                        'x_m': 40.0,
                        'y_m': 20.0,
                        'slot_id': '@a',
                    },
                },
            ],
        )
        self.assertTrue(res['ok'], res)
        self.assertEqual(self.env['f3d.placement'].browse(res['id_map']['b']).slot_id.id, res['id_map']['a'])
        # конфлікт: другий клієнт шле write зі старим etag
        old_etag = slot._f3d_etag()
        self.bump_write_date('f3d.slot', slot.id)  # «перший клієнт уже зберіг»
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[{'model': 'f3d.slot', 'op': 'write', 'id': slot.id, 'etag': old_etag, 'vals': {'x_m': 55.0}}],
        )
        self.assertEqual((res['ok'], res['code']), (False, 'conflict'))
        self.assertEqual(res['current']['id'], slot.id)
        self.assertEqual(slot.x_m, 30.0)  # нічого не застосовано
        # атомарність: друга операція падає → перша скасована
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {'model': 'f3d.slot', 'op': 'write', 'id': slot.id, 'vals': {'x_m': 44.0}},
                {
                    'model': 'f3d.slot',
                    'op': 'create',
                    'tmp': 'x',
                    'vals': {
                        'layer_id': self.layers['storage'].id,
                        'template': 'pallet_rack',
                        'code_prefix': 'bad prefix!',
                        'x_m': 1.0,
                        'y_m': 1.0,
                    },
                },
            ],
        )
        self.assertEqual((res['ok'], res['code'], res['op_index']), (False, 'validation', 1))
        slot.invalidate_recordset()
        self.assertEqual(slot.x_m, 30.0)
        # правильний etag проходить
        fresh = self.env['f3d.slot'].browse(slot.id)
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[{'model': 'f3d.slot', 'op': 'write', 'id': slot.id, 'etag': fresh._f3d_etag(), 'vals': {'x_m': 31.0}}],
        )
        self.assertTrue(res['ok'], res)

    def test_save_whitelist_and_rights_message(self):
        self.login(self.u_store)
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'f3d.placement',
                    'op': 'create',
                    'vals': {
                        'layer_id': self.layers['production'].id,
                        'variant_id': self.variant.id,
                        'code': 'WL-1',
                        'name': "X",
                    },
                }
            ],
        )
        self.assertEqual((res['code'], res['op_index']), ('rights', 0))
        self.assertIn("Шар «Виробництво» редагує", res['message'])
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[{'model': 'f3d.slot', 'op': 'create', 'vals': {'equipment_id': 1}}],
        )
        self.assertEqual(res['code'], 'validation')

    # --- AC-30 / API-05/06/07 -----------------------------------------------------------------------
    def test_validate_preview_publish_flow(self):
        generic = self.env.ref('factory3d_constructor.variant_generic_panel')
        self.make_placement(kind='production', code='PB-1', x=10.0, y=10.0, variant=generic)
        self.make_placement(kind='production', code='PB-2', x=10.3, y=10.0, variant=generic)
        self.login(self.u_manager)
        res = self.rpc('/f3d/constructor/validate', site_id=self.site.id)
        self.assertTrue(any(i['check'] == 'collide' for i in res['issues']))
        self.assertGreaterEqual(res['summary']['block'], 1)
        res = self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True)
        self.assertEqual((res['ok'], res['code']), (False, 'blocked'))
        self.assertTrue(res['issues'])
        self.assertFalse(self.site.version_ids)
        # переводимо collide в warn: публікація проходить, зауваження в report
        self.site.check_config_ids.filtered(lambda c: c.check_key == 'collide').mode = 'warn'
        preview = self.rpc('/f3d/constructor/publish/preview', site_id=self.site.id)
        self.assertTrue(preview['ok'], preview)
        self.assertEqual(preview['action']['res_model'], 'f3d.publish.wizard')
        self.assertGreaterEqual(preview['summary']['create'], 2)
        res = self.rpc('/f3d/constructor/publish', site_id=self.site.id, note="через API", confirm=True)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['version']['n'], 1)
        self.assertTrue(any(w['check'] == 'collide' for w in res['warnings']))
        self.assertEqual(res['counts']['created'], len(res['created']))
        # повтор без змін
        res = self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True)
        self.assertEqual((res['ok'], res['code']), (False, 'no_changes'))
        self.assertEqual(self.rpc('/f3d/constructor/publish/preview', site_id=self.site.id)['code'], 'no_changes')
        # стоп-кран
        self.env['ir.config_parameter'].sudo().set_param('factory3d.constructor.publish_enabled', 'False')
        self.assertEqual(self.rpc('/f3d/constructor/publish/preview', site_id=self.site.id)['code'], 'disabled')
        # права
        self.login(self.u_tech)
        self.assertEqual(self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True)['code'], 'rights')
        self.assertEqual(self.rpc('/f3d/constructor/publish/preview', site_id=self.site.id)['code'], 'rights')

    def test_version_restore_api(self):
        self.env['ir.config_parameter'].sudo().set_param('factory3d.constructor.publish_enabled', 'True')
        self.make_slot(prefix='RS-R1', bays=2, levels=1)
        self.login(self.u_manager)
        self.assertTrue(self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True)['ok'])
        self.make_slot(kind='yard', prefix='RS-Z1', template='zone', polygon=[[0, 0], [4, 0], [4, 4]])
        version = self.site.version_ids
        res = self.rpc('/f3d/constructor/version/restore', version_id=version.id)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['draft_changes'], 0)
        self.assertEqual(self.env['f3d.slot'].search_count([('site_id', '=', self.site.id)]), 1)
        self.login(self.u_tech)
        self.assertEqual(self.rpc('/f3d/constructor/version/restore', version_id=version.id)['code'], 'rights')

    def test_ac17_underlay_in_load(self):
        layer = self.layers['storage']
        att = self.env['ir.attachment'].create(
            {'name': 'plan.dxf', 'raw': b'0\nEOF\n', 'res_model': 'f3d.layer', 'res_id': layer.id}
        )
        layer.underlay_attachment_id = att
        self.login(self.u_manager)
        loaded = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        underlay = next(layer_ for layer_ in loaded['layers'] if layer_['id'] == layer.id)['underlay']
        self.assertEqual((underlay['format'], underlay['status']), ('dxf', 'ready'))
        self.assertEqual(underlay['url'], '/web/content/%d' % att.id)
        self.assertEqual(underlay['params']['unit'], 'mm')

    def test_perf_load_and_validate_seed(self):
        """§13.4: API-03 для seed ≤ 1,5 с; API-05 ≤ 1 с."""
        import time

        seed_site = self.env['f3d.site'].search([('seed_key', '=', 'main_demo')])
        if not seed_site:
            self.skipTest("seed-площадки немає")
        self.login(self.u_manager)
        started = time.time()
        res = self.rpc('/f3d/constructor/load', site_id=seed_site.id)
        self.assertLess(time.time() - started, 1.5)
        self.assertEqual(len(res['slots']), len(seed_hook.read_seed()['slots']))
        self.assertLess(len(json.dumps(res)), 2 * 1024 * 1024)
        started = time.time()
        self.assertTrue(self.rpc('/f3d/constructor/validate', site_id=seed_site.id)['ok'])
        self.assertLess(time.time() - started, 1.0)
