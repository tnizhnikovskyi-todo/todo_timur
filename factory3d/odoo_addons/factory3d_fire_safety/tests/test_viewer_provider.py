"""AC-55…AC-57, AC-59 (+AC-22 ``totals.state``): payload `fire` і `evacuation` без переглядача (R-20, R-21)."""
import json

from odoo.tests import tagged

from odoo.addons.factory3d_fire_safety.tools.payload import build_evacuation, build_fire

from .common import FireCase

GROUP_KEYS = ['zone', 'zone_name', 'kind', 'kind_name', 'n', 'spacing', 'area', 'loop', 'state', 'alarm_state',
              'compliance', 'stale']
RULES = ['smoke_area_6_12m', 'smoke_spacing_6_12m', 'smoke_wall_6_12m', 'heat_area', 'heat_spacing', 'mcp_spacing',
         'mcp_height', 'sounder_level', 'spark_detection_required', 'flame_detector_note']
EVAC_KEYS = ['exits', 'routes', 'max_distance', 'worst_point', 'drill_origin', 'drill_zone', 'drill_detector',
             'norm_distance', 'norm_ref', 'norm_alt', 'norm_alt_ref', 'drill_steps', 'drill_active', 'compliance']
DUST = 'fire/groups/FA-FAC/dust'


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestPayload(FireCase):

    def fire(self, user=None):
        self.env.invalidate_all()  # поля без depends (`maintenance_request_name`) кешуються на час транзакції
        return build_fire((self.env(user=user) if user else self.env), {'now': self.T0})

    def test_fire_structure(self):
        data = self.fire(self.u)
        self.assertEqual(list(data), ['rules', 'loops', 'groups', 'totals', 'events', 'panel', 'systems'])
        self.assertEqual(list(data['rules']), RULES)
        self.assertEqual(data['rules']['smoke_spacing_6_12m'], 8.8)
        self.assertEqual(data['rules']['mcp_spacing'], 30)
        self.assertIsInstance(data['rules']['mcp_spacing'], int)
        self.assertIsNone(data['rules']['smoke_area_6_12m'])
        self.assertEqual(data['loops'], {
            '1': {'detectors': 64, 'mcp': 10, 'sounders': 11, 'flame': 0, 'modules': 0, 'state': 'ok'},
            '2': {'detectors': 68, 'mcp': 10, 'sounders': 13, 'flame': 3, 'modules': 4, 'state': 'ok'},
            '3': {'detectors': 44, 'mcp': 7, 'sounders': 7, 'flame': 0, 'modules': 0, 'state': 'ok'},
            '4': {'detectors': 46, 'mcp': 9, 'sounders': 10, 'flame': 0, 'modules': 0, 'state': 'ok'}})
        self.assertEqual(len(data['groups']), 35)
        for code, group in data['groups'].items():
            self.assertEqual([k for k in group if k in GROUP_KEYS], GROUP_KEYS, code)
        self.assertEqual(data['groups']['FA-BOILER']['zone'], 'BOILER')
        totals = data['totals']
        self.assertEqual((totals['detectors'], totals['mcp'], totals['sounders'], totals['flame'],
                          totals['spark_detectors'], totals['mcp_max_m']), (222, 36, 41, 3, 4, 26.9))
        self.assertEqual(list(data['panel']), ['code', 'state', 'state_text', 'comm', 'last_seen', 'alarms', 'faults',
                                              'disabled', 'sounders', 'brigade'])
        self.assertEqual(set(data['systems']), {'SPARK-1', 'SMOKE-CTRL', 'SPRINKLERS'})
        self.assertNotIn('devices', data)
        json.dumps(data)

    def test_group_states(self):
        groups = self.fire()['groups']
        self.assertEqual(groups['FA-CUT']['state'], 'ok')
        self.assertEqual(groups['FA-CUT']['alarm_state'], 'unknown')
        self.assertIn('stale', groups['FA-CUT'])
        self.push_text('fire/groups/FA-CUT/state', 'alarm', self.at(0))
        self.assertEqual(self.fire()['groups']['FA-CUT']['state'], 'alarm')
        self.push_value(DUST, 86.1, self.at(10))
        fac = self.fire()['groups']['FA-FAC']
        self.assertEqual((fac['state'], fac['dust']), ('warn', 0.861))
        self.assertIn('warning', fac)
        self.assertNotIn('maintenance_request', fac)
        self.push_value(DUST, 90.1, self.at(70))
        request = self.env['maintenance.request'].search([('f3d_fire_zone_id', '=', self.z_fac.id)])
        self.assertEqual(len(request), 1)
        self.assertEqual(self.fire()['groups']['FA-FAC']['maintenance_request'], request.name)

    def test_evacuation_structure(self):
        data = build_evacuation(self.env(user=self.u), {'now': self.T0})
        self.assertEqual(list(data), EVAC_KEYS)
        self.assertEqual(len(data['exits']), 12)
        self.assertEqual(list(data['exits'][0]), ['code', 'x', 'y', 'side', 'width', 'ok'])
        self.assertEqual(len(data['routes']), 32)
        self.assertEqual(data['routes']['Z-CNC']['exit'], 'EX-S3')
        self.assertEqual(data['max_distance'], 45.3)
        self.assertEqual(data['worst_point'], [32.25, 33.75])
        self.assertEqual((data['norm_distance'], data['norm_alt']), (240, 50))
        self.assertTrue(data['norm_ref'])
        self.assertTrue(data['norm_alt_ref'])
        self.assertEqual(len(data['drill_steps']), 8)
        self.assertIsNone(data['drill_active'])
        self.assertEqual((data['drill_origin'], data['drill_zone'], data['drill_detector']),
                         ('FA-CNC', 'Присадка', '2.CNC.05'))
        self.assertEqual(data['compliance'], {'routes_ok': 32, 'routes_total': 32, 'worst': 38.6, 'norm': 240,
                                              'exits_ok': True, 'smoke_ok': 8, 'smoke_total': 8})
        json.dumps(data)
        drill = self.new_drill(zone_id=self.z_cut.id, mode='tabletop')
        drill.action_start(ts=self.T0)
        data = build_evacuation(self.env(user=self.u), {'now': self.T0})
        self.assertEqual(data['drill_active']['zone_code'], 'FA-CUT')
        self.assertEqual(data['drill_active']['name'], drill.name)
        self.assertEqual(data['drill_origin'], 'FA-CUT')
        self.assertEqual(data['drill_active']['steps_total'], 8)
        self.assertEqual(data['drill_active']['started'], '2026-10-14 10:00')
        self.assertNotIn('person_ids', json.dumps(data))

    def test_devices_and_disabled(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('factory3d.fire_safety.viewer_devices', 'True')
        self.push_value(DUST, 86.1, self.at(0))
        data = self.fire(self.u)
        self.assertEqual(len(data['devices']), 353)
        self.assertEqual(data['devices']['2.FAC.07']['dust'], 0.861)
        self.assertEqual(data['devices']['2.FAC.07']['zone'], 'FA-FAC')
        self.assertEqual(list(data)[-1], 'devices')
        json.dumps(data)
        icp.set_param('factory3d.fire_safety.read_enabled', 'False')
        self.panel._cron_sync()
        self.assertEqual(self.panel.comm, 'off')
        self.assertEqual(self.fire()['totals']['state'], 'Обробка вимкнена')
