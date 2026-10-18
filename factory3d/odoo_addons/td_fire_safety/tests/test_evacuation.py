"""AC-33…AC-40: евакуація, виходи, димові зони, звіт (R-05…R-09, V-20)."""
from contextlib import contextmanager
from unittest import mock

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

MOD = 'td_fire_safety'
# R-09: потрібна кількість люків за зонами
NEED = {'SZ-1': 6, 'SZ-2': 6, 'SZ-3': 4, 'SZ-4': 6, 'SZ-5': 5, 'SZ-6': 6, 'SZ-7': 6, 'SZ-8': 5}
AREAS = {'SZ-1': 1440, 'SZ-2': 1584, 'SZ-3': 920, 'SZ-4': 1380, 'SZ-5': 1300, 'SZ-6': 1440, 'SZ-7': 1440,
         'SZ-8': 1296}
NEAREST = {'EX-S1': 37.0, 'EX-S2': 17.5, 'EX-S3': 17.5, 'EX-S4': 7.4, 'EX-S5': 12.4, 'EX-S6': 24.6,
           'EX-N1': 36.0, 'EX-N2': 25.0, 'EX-N3': 25.0, 'EX-N5': 29.0, 'EX-N4': 29.0, 'EX-IN': 7.4}


class EvacCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Exit = env['td.fire.exit']
        cls.Route = env['td.fire.route']
        cls.Smoke = env['td.fire.smoke.zone']
        cls.Norm = env['td.fire.norm']
        cls.icp = env['ir.config_parameter'].sudo()
        cls.refresh()

    @classmethod
    def refresh(cls):
        cls.Exit.search([])._recompute()
        cls.Route.search([])._recompute()
        cls.Smoke.search([])._recompute()

    def exit_(self, code):
        return self.Exit.search([('code', '=', code)], limit=1)

    def route(self, zone_code):
        return self.Route.search([('zone_code', '=', zone_code)], limit=1)

    def set_norm(self, key, value):
        self.Norm.search([('key', '=', key)], limit=1).write({'value': value, 'value_set': True})

    @contextmanager
    def viewer_installed(self, flag):
        from odoo.addons.td_factory3d.models.td_scene_mixin import F3dSceneMixin
        with mock.patch.object(F3dSceneMixin, '_f3d_viewer_installed', return_value=flag):
            yield


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestRoutes(EvacCase):

    def test_routes_ok(self):
        """AC-33: 32 маршрути відповідають нормі 240 м; найдовший Z-PRE 38,6."""
        routes = self.Route.search([])
        self.assertEqual(len(routes), 32)
        self.assertEqual(set(routes.mapped('compliance')), {'ok'})
        self.assertEqual(set(routes.mapped('norm_m')), {240.0})
        longest = routes.sorted('length_m', reverse=True)[:1]
        self.assertEqual((longest.zone_code, longest.length_m), ('Z-PRE', 38.6))

    def test_polymer(self):
        """AC-33: polymer_panels=True → норма 50, усі 32 відповідають."""
        self.icp.set_param('td.fire_safety.polymer_panels', 'True')
        routes = self.Route.search([])
        routes._recompute()
        self.assertEqual(set(routes.mapped('norm_m')), {50.0})
        self.assertEqual(len(routes.filtered(lambda r: r.compliance == 'ok')), 32)

    def test_short_norm(self):
        """AC-33: evac_distance_prod_B=30 → 26 відповідають, 6 зон fail."""
        self.set_norm('evac_distance_prod_B', 30)
        routes = self.Route.search([])
        routes._recompute()
        failed = routes.filtered(lambda r: r.compliance == 'fail')
        self.assertEqual(len(routes) - len(failed), 26)
        self.assertEqual(set(failed.mapped('zone_code')),
                         {'Z-RCV-4', 'Z-SHEETS', 'Z-PRE', 'Z-MAINT', 'Z-FG', 'Z-OUT-4'})
        panel = self.env['td.fire.panel'].search([], limit=1)
        if 'compliance_routes_ok' in panel._fields and hasattr(panel, 'action_recompute_compliance'):
            panel.action_recompute_compliance()
            self.assertEqual(panel.compliance_routes_ok, 26)

    def test_route_unique_zone(self):
        """AC-40: другий маршрут для Z-CUT → IntegrityError."""
        cut = self.route('Z-CUT')
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.Route.create({
                'code': 'EVAC-CUT-2', 'name': 'Дубль', 'zone_id': cut.zone_id.id, 'exit_id': cut.exit_id.id,
                'length_m': 10.0, 'path': cut.path})


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestExits(EvacCase):

    def test_dispersal(self):
        """AC-34: L = 31,6, найбільша пара 145,1, відстані до найближчого."""
        summary = self.Exit._dispersal_summary()
        self.assertEqual(summary['count'], 12)
        self.assertEqual(summary['l_m'], 31.6)
        self.assertEqual(summary['pair_m'], 145.1)
        self.assertTrue(summary['ok'])
        for code, dist in NEAREST.items():
            self.assertAlmostEqual(self.exit_(code).nearest_exit_m, dist, 1, code)
        self.assertEqual(self.exit_('EX-S4').nearest_exit_m, 7.4)
        self.assertEqual(self.exit_('EX-S1').nearest_exit_m, 37.0)
        panel = self.env['td.fire.panel'].search([], limit=1)
        if 'compliance_exits_ok' in panel._fields and hasattr(panel, 'action_recompute_compliance'):
            panel.action_recompute_compliance()
            self.assertAlmostEqual(panel.compliance_exit_l_m, 31.6, 1)
            self.assertAlmostEqual(panel.compliance_exit_pair_m, 145.1, 1)
            self.assertTrue(panel.compliance_exits_ok)

    def test_two_close_exits(self):
        """AC-34: лишити EX-S4 і EX-IN → пара 7,4 < 31,6 → не відповідає."""
        self.Exit.search([('code', 'not in', ('EX-S4', 'EX-IN'))]).write({'active': False})
        summary = self.Exit._dispersal_summary()
        self.assertEqual(summary['count'], 2)
        self.assertTrue(summary['n_ok'])
        self.assertEqual(summary['pair_m'], 7.4)
        self.assertFalse(summary['ok'])
        panel = self.env['td.fire.panel'].search([], limit=1)
        if 'compliance_exits_ok' in panel._fields and hasattr(panel, 'action_recompute_compliance'):
            panel.action_recompute_compliance()
            self.assertFalse(panel.compliance_exits_ok)

    def test_door_width(self):
        """AC-35: EX-S1.width_m=0.7 → вихід і маршрути до нього fail."""
        s1 = self.exit_('EX-S1')
        self.assertTrue(s1.width_ok)
        s1.width_m = 0.7
        self.assertFalse(s1.width_ok)
        self.assertEqual(s1.compliance, 'fail')
        self.assertFalse(self.Exit._dispersal_summary()['ok'])
        routes = s1.route_ids
        self.assertEqual(set(routes.mapped('zone_code')),
                         {'Z-RCV-1', 'Z-RCV-2', 'Z-RCV-3', 'Z-RCV-4', 'Z-SHEETS'})
        for route in routes:
            self.assertFalse(route.width_ok, route.zone_code)
            self.assertEqual(route.compliance, 'fail', route.zone_code)

    def test_exit_on_wall(self):
        """AC-40: вихід поза зовнішньою стіною → ValidationError."""
        with self.assertRaisesRegex(ValidationError, 'на зовнішній стіні'):
            self.Exit.create({'code': 'EX-X1', 'name': 'Тест', 'x': 75, 'y': 30, 'side': 'S'})
        with self.assertRaises(ValidationError):
            self.Exit.create({'code': 'EX-X2', 'name': 'Тест', 'x': 10, 'y': 0, 'side': 'S', 'width_m': 0})
        ok = self.Exit.create({'code': 'EX-X3', 'name': 'Тест', 'x': 10, 'y': 0.4, 'side': 'S'})
        self.assertEqual(ok.display, 'EX-X3 · Південна стіна')


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestSmokeZones(EvacCase):

    def test_need_table(self):
        """AC-36: потреба в люках за R-09, Σ 44, усі ok."""
        zones = self.Smoke.search([])
        self.assertEqual(len(zones), 8)
        self.assertEqual({z.code: z.need_vents for z in zones}, NEED)
        self.assertEqual({z.code: round(z.area_m2) for z in zones}, AREAS)
        self.assertEqual(sum(zones.mapped('need_vents')), 44)
        self.assertEqual(sum(zones.mapped('vent_count')), 44)
        self.assertEqual(set(zones.mapped('compliance')), {'ok'})
        self.assertEqual(set(zones.mapped('max_area_m2')), {1600.0})
        self.assertAlmostEqual(sum(zones.mapped('vent_area_m2')), 44.88, 2)

    def test_vent_archived(self):
        """AC-36: 0.SV.01 архівовано → SZ-1 warn."""
        vent = self.env['td.fire.device'].search([('address', '=', '0.SV.01')])
        self.assertEqual(len(vent), 1)
        vent.active = False
        sz1 = self.Smoke.search([('code', '=', 'SZ-1')])
        sz1._recompute()
        self.assertEqual(sz1.vent_count, 5)
        self.assertEqual(sz1.compliance, 'warn')
        self.assertFalse(sz1.vents_ok)
        self.assertTrue(sz1.area_ok)

    def test_area_fail(self):
        """AC-36: SZ-1.x1=25 → fail; x1=200 → ValidationError."""
        sz1 = self.Smoke.search([('code', '=', 'SZ-1')])
        sz1.x1 = 25
        self.assertEqual(round(sz1.area_m2), 1800)
        self.assertFalse(sz1.area_ok)
        self.assertEqual(sz1.compliance, 'fail')
        with self.assertRaisesRegex(ValidationError, 'поза будівлею'):
            sz1.x1 = 200
        self.assertTrue(sz1.point_inside(10, 10))


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestData(EvacCase):

    def test_exit_route_data(self):
        """AC-37: EX-S3, маршрут Z-CNC, параметри панелі."""
        self.assertEqual(self.Exit.search_count([]), 12)
        s3 = self.exit_('EX-S3')
        self.assertEqual((s3.x, s3.y, s3.side, s3.width_m), (68.5, 0.0, 'S', 1.2))
        self.assertEqual(self.exit_('EX-IN').kind, 'staff')
        cnc = self.route('Z-CNC')
        self.assertEqual(cnc.exit_id, s3)
        self.assertEqual(cnc.length_m, 29.8)
        self.assertEqual(cnc.point_count, 3)
        self.assertEqual(cnc.code, 'EVAC-CNC')
        panel = self.env['td.fire.panel'].search([], limit=1)
        self.assertEqual(panel.evac_max_distance_m, 45.3)
        self.assertEqual((panel.evac_worst_x, panel.evac_worst_y), (32.25, 33.75))
        self.assertEqual(self.env.ref('%s.exit_ex_s3' % MOD), s3)

    def test_path_validation(self):
        """AC-37: точка поза будівлею і кінець далеко від виходу → ValidationError."""
        cnc = self.route('Z-CNC')
        path = [list(p) for p in cnc.path]
        with self.assertRaisesRegex(ValidationError, 'Шлях маршруту'):
            cnc.path = path[:-1] + [[200, 0]]
        with self.assertRaisesRegex(ValidationError, 'Шлях маршруту'):
            cnc.path = path[:-1] + [[path[-1][0] + 5, path[-1][1] + 5]]
        with self.assertRaisesRegex(ValidationError, 'Шлях маршруту'):
            cnc.path = path[:1]
        with self.assertRaisesRegex(ValidationError, 'Шлях маршруту'):
            cnc.path = path[:-1] + [[True, 0]]
        cnc.path_text = '[[1, 1], [68.5, 0.25]]'
        self.assertEqual(cnc.point_count, 2)
        with self.assertRaises(ValidationError):
            cnc.path_text = 'не json'


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestReport(EvacCase):

    def test_report_html(self):
        """AC-38: HTML звіту V-20 містить таблиці й ключові значення."""
        panel = self.env['td.fire.panel'].search([], limit=1)
        if hasattr(panel, 'action_recompute_compliance'):
            panel.action_recompute_compliance()
        html, _fmt = self.env['ir.actions.report']._render_qweb_html(
            '%s.report_td_fire_evac_compliance' % MOD, panel.ids)
        html = html.decode()
        self.assertEqual(html.count('f3d-route-row'), 32)
        self.assertEqual(html.count('f3d-exit-row'), 12)
        self.assertEqual(html.count('f3d-smoke-row'), 8)
        self.assertEqual(html.count('f3d-zone-row'), 35)
        for text in ('38,6', '31,6', '145,1', '26,9', 'Зони цеху без сигналізації: немає'):
            self.assertIn(text, html)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestPlantZone(EvacCase):

    def test_zone_fields(self):
        """AC-39: поля M-13 на td.zone (потребує models/td_zone.py, W1)."""
        z_cnc = self.env.ref('td_factory3d.zone_z_cnc')
        self.assertEqual(z_cnc.td_fire_kind, 'multi')
        self.assertEqual(z_cnc.td_evac_exit_code, 'EX-S3')
        self.assertEqual(z_cnc.td_evac_length_m, 29.8)
        z_office = self.env.ref('td_factory3d.zone_z_office')
        self.assertEqual(z_office.td_fire_zone_count, 1)
        self.assertEqual(z_office.td_fire_kind, 'smoke')
        self.assertFalse(z_office.td_evac_route_id)
        z_energy = self.env.ref('td_factory3d.zone_z_energy')
        self.assertEqual(z_energy.td_fire_zone_count, 0)
        self.assertFalse(z_energy.td_fire_state)

    def test_route_show_3d(self):
        """AC-40: «Показати в 3D» повертає код шляху маршруту."""
        cnc = self.route('Z-CNC')
        with self.viewer_installed(True):
            act = cnc.action_f3d_show()
        self.assertEqual(act['tag'], 'f3d_viewer.action')
        self.assertEqual(act['params']['code'], 'EVAC-CNC')
        with self.viewer_installed(False):
            act = cnc.action_f3d_show()
        self.assertEqual(act['tag'], 'display_notification')
