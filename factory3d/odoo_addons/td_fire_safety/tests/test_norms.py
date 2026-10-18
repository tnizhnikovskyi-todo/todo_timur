"""AC-05…AC-11, AC-70 (R-01…R-04, R-08, R-23): норми, розстановка, покриття, адреси."""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import FireCase

# Додаток A.1: код зони → (n_required, розрив R-02 у м, точка)
A1 = {
    'FA-RCV-1': (4, 3.95, '(0.6, 0.6)'),
    'FA-RCV-2': (4, 4.02, '(0.6, 10.15)'),
    'FA-RCV-3': (4, 4.02, '(0.6, 20.15)'),
    'FA-RCV-4': (4, 4.02, '(0.6, 30.15)'),
    'FA-RCV-5': (4, 4.02, '(0.6, 40.15)'),
    'FA-RCV-6': (4, 4.02, '(0.6, 50.15)'),
    'FA-RCV-7': (4, 4.26, '(0.6, 60.15)'),
    'FA-SHEETS': (24, 5.02, '(14.6, 0.6)'),
    'FA-HW': (6, 5.46, '(14.6, 46.0)'),
    'FA-EDGE': (3, 5.37, '(28.8, 46.0)'),
    'FA-PKS': (3, 5.08, '(35.8, 46.0)'),
    'FA-CUT': (12, 5.05, '(41.8, 0.6)'),
    'FA-EB': (12, 4.88, '(55.8, 0.6)'),
    'FA-CNC': (12, 5.44, '(68.8, 0.6)'),
    'FA-SORT': (12, 4.95, '(81.8, 0.6)'),
    'FA-FAC': (18, 5.86, '(42.2, 71.4)'),
    'FA-ASM': (8, 5.62, '(92.4, 15.1)'),
    'FA-PRE': (4, 5.81, '(92.4, 30.0)'),
    'FA-MAINT': (4, 3.96, '(92.4, 46.4)'),
    'FA-PACK': (8, 5.04, '(110.0, 0.6)'),
    'FA-POST': (6, 5.16, '(110.0, 34.0)'),
    'FA-CMP': (2, 4.0, '(110.0, 60.0)'),
    'FA-CHG': (2, 4.0, '(116.0, 60.0)'),
    'FA-FG': (14, 6.26, '(122.0, 54.1)'),
    'FA-ELEC': (4, 4.33, '(129.4, 62.4)'),
    'FA-OUT-1': (4, 4.07, '(136.0, 0.6)'),
    'FA-OUT-2': (4, 4.14, '(136.0, 10.15)'),
    'FA-OUT-3': (4, 4.14, '(136.0, 20.15)'),
    'FA-OUT-4': (4, 4.14, '(136.0, 30.15)'),
    'FA-OUT-5': (4, 4.14, '(136.0, 40.15)'),
    'FA-OUT-6': (4, 4.14, '(136.0, 50.15)'),
    'FA-OUT-7': (4, 4.37, '(136.0, 60.15)'),
    'FA-BOILER': (2, 4.24, '(67.6, 75.0)'),
    'FA-SOC': (2, 3.75, '(104.2, 46.6)'),
    'FA-OFFICE': (8, 4.94, '(92.6, 58.4)'),
}

# AC-07 і R-02 п. 6: точки, що перевіряються дослівно
EXACT_POINTS = {'FA-FG', 'FA-SHEETS', 'FA-OFFICE', 'FA-BOILER', 'FA-CUT', 'FA-RCV-1'}

NORM_KEYS = {
    'smoke_spacing_6_12m', 'smoke_wall_6_12m', 'smoke_area_6_12m', 'heat_spacing', 'heat_wall', 'heat_area',
    'mcp_spacing', 'mcp_height', 'sounder_level', 'sounder_bg_production', 'sounder_bg_storage',
    'sounder_bg_office', 'spark_detection_required', 'flame_detector_note', 'evac_distance_prod_B',
    'evac_distance_polymer', 'evac_exits_min', 'exit_width_min', 'door_width_min', 'smoke_zone_max_area',
    'smoke_vent_area', 'smoke_vent_aa', 'exit_dispersal_k', 'smoke_exhaust_required', 'lightning_class',
    'eyewash_required', 'pv_roof_fire',
}


class NormCase(FireCase):

    def zone(self, code):
        return self.env['td.fire.zone'].search([('code', '=', code)])

    def device(self, address):
        return self.env['td.fire.device'].search([('address', '=', address)])

    def norm(self, key):
        return self.env['td.fire.norm'].search([('key', '=', key)])

    def set_param(self, key, value):
        self.env['ir.config_parameter'].sudo().set_param('td.fire_safety.' + key, value)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestRequired(NormCase):

    def test_table(self):
        self.panel.action_recompute_compliance()
        zones = self.env['td.fire.zone'].search([])
        self.assertEqual(len(zones), 35)
        for code, (n, _gap, _pt) in A1.items():
            zone = self.zone(code)
            self.assertEqual(zone.n_required, n, code)
            self.assertTrue(zone.n_ok, code)
        self.assertEqual(self.zone('FA-OFFICE').area_m2, 383)
        self.assertEqual(self.zone('FA-SHEETS').n_required, 24)

    def test_change_spacing(self):
        self.panel.action_recompute_compliance()
        self.assertFalse(self.panel.compliance_dirty)
        norm = self.norm('smoke_spacing_6_12m')
        norm.value = 6.0
        self.assertTrue(self.panel.compliance_dirty)
        self.panel.action_recompute_compliance()
        cut = self.zone('FA-CUT')
        self.assertEqual(cut.n_required, 24)
        self.assertFalse(cut.n_ok)
        self.assertEqual(cut.compliance, 'fail')
        norm.value = 8.8
        self.assertTrue(self.panel.compliance_dirty)
        self.panel.action_recompute_compliance()
        self.assertEqual(cut.compliance, 'ok')

    def test_norm_not_set(self):
        self.norm('smoke_wall_6_12m').value_set = False
        self.panel.action_recompute_compliance()
        cut = self.zone('FA-CUT')
        self.assertEqual((cut.n_required, cut.n_ok, cut.compliance), (0, False, 'na'))
        self.assertIn('smoke_wall_6_12m', cut.compliance_note)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestCoverage(NormCase):

    def test_gaps(self):
        self.panel.action_recompute_compliance()
        for code, (_n, gap, point) in A1.items():
            zone = self.zone(code)
            # координати в data округлені до 0,01 м, тож розрив може відрізнятися від A.1 на 0,01
            self.assertAlmostEqual(zone.cover_max_gap_m, gap, delta=0.011, msg=code)
            if code in EXACT_POINTS:  # у FA-FAC/FA-PACK точка — майже-нічия: залежить від округлення координат у data
                self.assertEqual(zone.cover_point, point, code)
            self.assertTrue(zone.cover_point, code)
            self.assertEqual(zone.compliance, 'ok', code)
        self.assertTrue(self.zone('FA-FG').cover_ok)

    def test_tolerance_warn(self):
        self.set_param('cover_tol_m', '0.03')
        self.panel.action_recompute_compliance()
        fg = self.zone('FA-FG')
        self.assertFalse(fg.cover_ok)
        self.assertEqual(fg.compliance, 'warn')
        others = self.env['td.fire.zone'].search([('code', '!=', 'FA-FG')])
        self.assertEqual(set(others.mapped('compliance')), {'ok'})
        office = self.zone('FA-OFFICE')
        self.assertAlmostEqual(office.cover_max_gap_m, 4.94, 2)
        self.assertEqual(office.cover_point, '(92.6, 58.4)')

    def test_no_detectors(self):
        zone = self.zone('FA-RCV-1')
        zone.device_ids.write({'active': False})
        self.panel.action_recompute_compliance()
        self.assertEqual(zone.compliance, 'fail')
        self.assertFalse(zone.n_ok)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestMcpSounder(NormCase):

    def test_mcp(self):
        self.panel.action_recompute_compliance()
        self.assertAlmostEqual(self.panel.compliance_mcp_max_m, 26.9, 1)
        self.assertEqual(self.panel.compliance_mcp_point, '(60.0, 72.0)')
        self.assertTrue(self.panel.compliance_mcp_ok)

    def test_mcp_archived(self):
        self.device('1.MCP.08').active = False
        self.panel.action_recompute_compliance()
        self.assertAlmostEqual(self.panel.compliance_mcp_max_m, 32.0, 1)
        self.assertEqual(self.panel.compliance_mcp_point, '(32.0, 72.0)')
        self.assertFalse(self.panel.compliance_mcp_ok)

    def test_mcp_archived_no_change(self):
        self.device('2.MCP.09').active = False
        self.panel.action_recompute_compliance()
        self.assertAlmostEqual(self.panel.compliance_mcp_max_m, 26.9, 1)

    def test_sounder_informative(self):
        self.panel.action_recompute_compliance()
        self.assertAlmostEqual(self.panel.compliance_sounder_max_m, 45.2, 1)
        self.assertTrue(self.panel.compliance_mcp_ok)
        self.assertEqual(self.env['td.fire.zone'].search([('compliance', '!=', 'ok')]).mapped('code'), [])


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestMissingZones(NormCase):

    def test_missing(self):
        self.panel.action_recompute_compliance()
        self.assertFalse(self.panel.compliance_missing_zones)
        self.zone('FA-SOC').active = False
        self.panel.action_recompute_compliance()
        self.assertEqual(self.panel.compliance_missing_zones, 'Z-SOC')
        self.zone('FA-OFFICE').active = False
        self.panel.action_recompute_compliance()
        self.assertEqual(self.panel.compliance_missing_zones, 'Z-OFFICE, Z-SOC')


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestNormModel(NormCase):

    def test_get(self):
        Norm = self.env['td.fire.norm']
        self.assertEqual(Norm.get('smoke_spacing_6_12m'), 8.8)
        self.assertIsNone(Norm.get('smoke_area_6_12m'))
        self.assertEqual(Norm.get('smoke_area_6_12m', 5.0), 5.0)
        self.assertEqual(Norm.get('mcp_spacing'), 30.0)
        self.assertEqual(Norm.get('exit_dispersal_k'), 1.5)
        self.assertIsNone(Norm.get('no_such_key'))
        self.assertTrue(Norm.get_ref('mcp_spacing'))
        self.assertEqual(Norm.get_ref('no_such_key'), '')

    def test_key_regex(self):
        with self.assertRaises(ValidationError):
            self.env['td.fire.norm'].create({'key': 'Bad-Key', 'name': 'x', 'ref': 'y'})

    def test_json_keys_present(self):
        keys = set(self.env['td.fire.norm'].with_context(active_test=False).search([]).mapped('key'))
        self.assertEqual(keys, NORM_KEYS)
        self.assertEqual(len(keys), 27)

    def test_cache_invalidation(self):
        Norm = self.env['td.fire.norm']
        self.assertEqual(Norm.get('mcp_spacing'), 30.0)
        self.norm('mcp_spacing').value = 25.0
        self.assertEqual(Norm.get('mcp_spacing'), 25.0)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestAddresses(NormCase):

    def test_lsp_id(self):
        Device = self.env['td.fire.device']
        self.assertEqual(Device.lsp_id(2, 16, 7), 21607)
        self.assertEqual(Device.lsp_id(1, 90, 1), 19001)
        with self.assertRaises(ValueError):
            Device.lsp_id(9, 1, 1)

    def test_unique_lsp(self):
        devices = self.env['td.fire.device'].with_context(active_test=False).search([])
        with_lsp = devices.filtered(lambda d: d.lsp_instance > 0)
        self.assertEqual(len(with_lsp), 302)
        self.assertEqual(len(set(with_lsp.mapped('lsp_instance'))), 302)
        self.assertEqual(len(devices) - len(with_lsp), 51)
        self.assertEqual(self.device('3.SOC.01').lsp_instance, 33401)
        self.assertEqual(self.device('3.OFFICE.08').lsp_instance, 33508)
        self.assertEqual(self.device('2.FAC.07').lsp_instance, 21607)

    def test_address_loop_mismatch(self):
        with self.assertRaises(ValidationError):
            self.env['td.fire.device'].create({
                'address': '3.FAC.01', 'type': 'smoke', 'panel_id': self.panel.id, 'loop_id': self.loop2.id,
                'zone_id': self.z_fac.id, 'x': 50.0, 'y': 50.0, 'z': 8.85})
