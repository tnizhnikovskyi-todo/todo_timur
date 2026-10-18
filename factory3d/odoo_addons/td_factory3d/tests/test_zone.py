from collections import Counter
from unittest import mock

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.td_factory3d.hooks import zones as zone_hooks

from .common import F3DCase

CMP = '[[110,60],[115.6,60],[115.6,71.4],[110,71.4]]'


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestZoneData(F3DCase):

    def setUp(self):
        super().setUp()
        self.zones = self.env['td.zone'].with_context(active_test=False).search([])

    def test_45_zones_loaded(self):
        data = self.zones.filtered(lambda z: z.get_external_id())
        self.assertEqual(len(data), 45)
        self.assertEqual(self.env.ref('td_factory3d.zone_z_sheets').td_code, 'Z-SHEETS')

    def test_types_distribution(self):
        counts = Counter(self.zones.mapped('zone_type'))
        expected = {'receiving': 7, 'storage': 7, 'production': 5, 'assembly': 1, 'packing': 1,
                    'shipping': 7, 'technical': 4, 'office': 2, 'outdoor': 11}
        for key, value in expected.items():
            self.assertEqual(counts[key], value, key)

    def test_polygons_inside_site(self):
        for zone in self.zones:
            self.assertTrue(zone.polygon, zone.td_code)
            self.assertGreaterEqual(zone.x_min, -32.0)
            self.assertLessEqual(zone.x_max, 182.0)
            self.assertGreaterEqual(zone.y_min, -30.0)
            self.assertLessEqual(zone.y_max, 100.0)

    def test_indoor_inside_building(self):
        indoor = self.zones.filtered(lambda z: z.zone_type != 'outdoor')
        self.assertEqual(len(indoor), 34)
        for zone in indoor:
            self.assertGreaterEqual(zone.x_min, 0.0, zone.td_code)
            self.assertLessEqual(zone.x_max, 150.0, zone.td_code)
            self.assertGreaterEqual(zone.y_min, 0.0, zone.td_code)
            self.assertLessEqual(zone.y_max, 72.0, zone.td_code)

    def test_roof_flag(self):
        self.assertEqual(self.zones.filtered('is_roof').mapped('td_code'), ['Z-ROOF'])
        self.assertAlmostEqual(self.env.ref('td_factory3d.zone_z_roof').area_m2, 10800.0, 1)
        self.assertAlmostEqual(self.env.ref('td_factory3d.zone_z_sheets').area_m2, 1200.6, 1)
        with self.assertRaises(ValidationError):
            self.make_zone('X-ROOF', zone_type='storage', is_roof=True)


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestGeometry(F3DCase):

    def test_area_bbox(self):
        zone = self.make_zone('Z-CMP-T', CMP, zone_type='technical')
        self.assertAlmostEqual(zone.area_m2, 63.8, 1)
        self.assertEqual(zone.x_min, 110)
        self.assertEqual(zone.y_max, 71.4)
        self.assertEqual(zone.polygon[1], [115.6, 60])

    def test_polygon_validation(self):
        for text in ('[[1,1],[2,2]]', '[[200,0],[10,0],[10,10]]', '[[1,1],[2,2],[3,3]]',
                     'не json'):
            with self.subTest(text=text), self.assertRaises(ValidationError):
                self.make_zone('X-BAD', text, zone_type='storage')

    def test_polygon_text_inverse(self):
        zone = self.make_zone('X-TXT', zone_type='storage')
        self.assertFalse(zone.polygon_text)
        zone.polygon_text = '[[0,0],[10,0],[10,10]]'
        self.assertEqual(zone.polygon, [[0, 0], [10, 0], [10, 10]])
        self.assertAlmostEqual(zone.area_m2, 50.0, 1)
        zone.polygon_text = ''
        self.assertFalse(zone.polygon)
        self.assertEqual(zone.area_m2, 0.0)

    def test_zone_at(self):
        Zone = self.env['td.zone']
        cases = [((45.5, 5.0), 'Z-CUT'), ((14.6, 0.6), 'Z-SHEETS'), ((140, 65), 'Z-OUT-7'),
                 ((-7.3, 5.0), 'Z-YARD-W'), ((172, -14), 'Z-GATE-E'),
                 ((128.5, 76.2), 'Z-ENERGY'), ((75, 36), 'Z-CNC')]
        for point, code in cases:
            self.assertEqual(Zone.zone_at(*point).td_code, code, point)
        self.assertFalse(Zone.zone_at(0.3, 5.0))
        self.assertEqual(Zone.zone_at(75, 36, roof=True).td_code, 'Z-ROOF')

    def test_zone_at_concave(self):
        poly = [(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)]
        inside = self.env['td.zone']._point_in_polygon
        self.assertTrue(inside(2, 8, poly))
        self.assertFalse(inside(8, 8, poly))
        self.assertTrue(inside(10, 2, poly))


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestCounters(F3DCase):

    def test_counts_and_docks(self):
        zone = self.make_zone('X-CNT', zone_type='storage')
        self.loc_in.td_zone_id = zone
        self.make_dock(self.dock_w1, 'west', 1, 0.0, 5.0)
        self.dock_w1.td_zone_id = zone
        self.wc.td_zone_id = zone
        self.eq.td_zone_id = zone
        self.assertEqual(zone.location_count, 2)
        self.assertEqual(zone.dock_count, 1)
        self.assertEqual(zone.dock_location_ids, self.dock_w1)
        self.assertEqual(zone.workcenter_count, 1)
        self.assertEqual(zone.equipment_count, 1)

    def test_archived_not_counted(self):
        zone = self.make_zone('X-ARC', zone_type='storage')
        self.loc_in.td_zone_id = zone
        self.dock_e1.td_zone_id = zone
        self.assertEqual(zone.location_count, 2)
        self.dock_e1.active = False
        zone.invalidate_recordset()
        self.assertEqual(zone.location_count, 1)

    def test_actions(self):
        zone = self.make_zone('X-ACT', zone_type='storage')
        action = zone.action_view_workcenters()
        self.assertEqual(action['res_model'], 'mrp.workcenter')
        self.assertEqual(action['domain'], [('td_zone_id', '=', zone.id)])
        self.assertEqual(action['context'], {'default_td_zone_id': zone.id})


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestZoneBind(F3DCase):

    def test_bind_workcenter_and_rerun(self):
        zone = self.env.ref('td_factory3d.zone_z_cut')
        self.wc.td_code = 'SAW-T'
        rows = [{'zone': 'Z-CUT', 'kind': 'workcenter', 'value': 'SAW-T'}]
        with self.with_data_file('scene_zone_links.csv', rows):
            res = zone_hooks.bind(self.env)
            self.assertEqual(self.wc.td_zone_id, zone)
            self.assertEqual(res['workcenters'], 1)
            res2 = zone_hooks.bind(self.env)
        self.assertEqual(res2['workcenters'], 1)
        self.assertEqual(self.wc.td_zone_id, zone)
        self.assertEqual(res['zones'], 45)

    def test_bind_root_and_prefix(self):
        zone = self.env.ref('td_factory3d.zone_z_hw')
        rows = [{'zone': 'Z-HW', 'kind': 'root', 'value': self.loc_in.complete_name},
                {'zone': 'Z-HW', 'kind': 'prefix', 'value': 'LOCT-'}]
        if 'td_code' in self.env['stock.location']._fields:
            self.loc_in.td_code = 'LOCT-1'
        with self.with_data_file('scene_zone_links.csv', rows):
            res = zone_hooks.bind(self.env)
        self.assertEqual(zone.root_location_id, self.loc_in)
        self.assertEqual(res['roots'], 1)
        if 'td_code' in self.env['stock.location']._fields:
            self.assertEqual(self.loc_in.td_zone_id, zone)

    def test_equipment_from_workcenter(self):
        zone = self.env.ref('td_factory3d.zone_z_cut')
        self.wc.write({'td_code': 'SAW-T', 'td_zone_id': zone.id})
        self.eq.td_code = 'SAW-T'
        with self.with_data_file('scene_zone_links.csv', []):
            res = zone_hooks.bind(self.env)
        self.assertEqual(self.eq.td_zone_id, zone)
        self.assertGreaterEqual(res['equipment'], 1)


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestEquipmentZoneFromWorkcenter(F3DCase):
    """B-2: поле workcenter_id існує (Enterprise), але порожнє — зв'язок за td_code (A-15)."""

    def setUp(self):
        super().setUp()
        model = self.env['ir.model']._get('maintenance.equipment')
        self.env['ir.model.fields'].create({
            'name': 'x_workcenter_id', 'field_description': 'Робочий центр (імітація mrp_maintenance)',
            'ttype': 'many2one', 'relation': 'mrp.workcenter', 'model_id': model.id, 'state': 'manual',
        })
        patcher = mock.patch.object(zone_hooks, 'WC_LINK', 'x_workcenter_id')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.zone = self.env.ref('td_factory3d.zone_z_cut')
        self.wc.write({'td_code': 'SAW-T', 'td_zone_id': self.zone.id})

    def test_empty_link_falls_back_to_code(self):
        self.assertIn('x_workcenter_id', self.env['maintenance.equipment']._fields)
        self.eq.td_code = 'SAW-T'
        self.assertFalse(self.eq.x_workcenter_id)
        with self.with_data_file('scene_zone_links.csv', []):
            res = zone_hooks.bind(self.env)
        self.assertEqual(self.eq.td_zone_id, self.zone)
        self.assertGreaterEqual(res['equipment'], 1)

    def test_filled_link_still_inherits(self):
        eq2 = self.env['maintenance.equipment'].create({'name': 'Eq with link'})
        eq2.x_workcenter_id = self.wc
        with self.with_data_file('scene_zone_links.csv', []):
            zone_hooks.bind(self.env)
        self.assertEqual(eq2.td_zone_id, self.zone)

    def test_link_to_other_workcenter_not_overridden_by_code(self):
        other = self.env['mrp.workcenter'].create({'name': 'Other WC'})
        self.eq.write({'td_code': 'SAW-T', 'x_workcenter_id': other.id})
        with self.with_data_file('scene_zone_links.csv', []):
            zone_hooks.bind(self.env)
        self.assertFalse(self.eq.td_zone_id)
