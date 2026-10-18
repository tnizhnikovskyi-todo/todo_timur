import json
from datetime import datetime

from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger

from .. import hooks
from ..tools import params as P
from .common import AccessCase

# Додаток B base: (код сцени, бейдж, зона РЦ); у фікстурі «копія демо» — 35 працівників
WORKCENTER_ZONES = {'Z-CUT': 4, 'Z-EB': 3, 'Z-CNC': 5, 'Z-FAC': 6, 'Z-ASM': 6, 'Z-PACK': 4}
CSV_CODES = ['OP-W1', 'OP-W2', 'OP-W3', 'OP-W4', 'OP-W5', 'OP-W6', 'OP-W7']


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestHooks(AccessCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # чиста база: прибираємо тестових працівників і зв'язки з AccessCase, щоб порахувати хук
        cls.env['td.access.user.link'].sudo().search([]).unlink()
        cls.env['hr.employee'].sudo().search([]).write({'active': False})

    def make_demo_like(self):
        """35 працівників із бейджами й кодами, РЦ із зонами, обладнання, 35 відкритих відміток 2026-10-12."""
        Employee, Workcenter = self.env['hr.employee'].sudo(), self.env['mrp.workcenter'].sudo()
        zone_of = {}
        n = 0
        for zone, count in WORKCENTER_ZONES.items():
            wc_codes = []
            for i in range(count):
                n += 1
                code = 'T%d-%d' % (n, i)
                wc_codes.append(code)
                wc = Workcenter.create({'name': 'РЦ ' + code, 'td_code': code, 'td_zone_id': self.z_by_code(zone).id})
                zone_of[code] = wc
        people = []
        for code, wc in zone_of.items():
            people.append(('OP-' + code, wc))
        for code in CSV_CODES:
            people.append((code, None))
        for i, (code, _wc) in enumerate(people):
            emp = Employee.create({
                'name': 'Демо %s' % code, 'td_code': code, 'barcode': 'DM%03d' % i,
                'resource_calendar_id': self.cal.id, 'tz': 'Europe/Kyiv'})
            self.env['hr.attendance'].sudo().create({
                'employee_id': emp.id, 'check_in': datetime(2026, 10, 12, 3, 40 + i % 20), 'in_mode': 'manual'})
        Equipment = self.env['maintenance.equipment'].sudo()
        for code in ('ACCESS', 'TURNSTILES'):
            if not Equipment.search_f3d(code):
                Equipment.create({'name': 'Обладнання ' + code, 'td_code': code})
        return len(people)

    def z_by_code(self, code):
        return self.env['td.zone'].search_f3d(code)

    def test_demo_like_counts(self):  # AC-59
        total = self.make_demo_like()
        self.assertEqual(total, 35)
        report = hooks.run_all(self.env)
        for key, value in dict(servers=1, devices=5, doors=5, equipment_bound=5, links=35, home_zones=35,
                               from_workcenter=28, from_csv=7, home_zone_missing=0, presence_seeded=35,
                               attendances_touched=0, attendances_total=35, migration_state='done').items():
            self.assertEqual(report[key], value, key)
        saved = json.loads(P.get_str(self.env, 'migration_report'))
        self.assertEqual(saved['links'], 35)
        self.assertEqual(P.get_str(self.env, 'migration_state'), 'done')
        w3 = self.env['hr.employee'].search([('td_code', '=', 'OP-W3')])
        self.assertEqual(w3.td_home_zone_id, self.z_by_code('Z-RCV-2'))
        self.assertTrue(w3.td_access_present)
        self.assertEqual(w3.td_access_zone_id, w3.td_home_zone_id)
        self.assertEqual(self.env.ref('td_access.device_acr_in').equipment_id.td_code, 'TURNSTILES')
        self.assertEqual(self.env.ref('td_access.device_acr_srv').equipment_id.td_code, 'ACCESS')
        self.assertFalse(self.env['hr.attendance'].search_count([('in_mode', '=', 'biostar')]))
        self.assertEqual(self.env['hr.attendance'].search_count([]), 35)

    def test_idempotent(self):  # AC-60
        self.make_demo_like()
        hooks.run_all(self.env)
        counts = {m: self.env[m].with_context(active_test=False).search_count([])
                  for m in ('td.access.user.link', 'hr.attendance', 'hr.employee', 'td.access.device')}
        second = hooks.run_all(self.env)
        self.assertEqual((second['links'], second['home_zones'], second['presence_seeded'],
                          second['equipment_bound']), (0, 0, 0, 0))
        self.assertEqual(second['migration_state'], 'done')
        self.assertEqual(counts, {m: self.env[m].with_context(active_test=False).search_count([]) for m in counts})

    def test_clean_db_skipped(self):  # AC-60
        report = hooks.run_all(self.env)
        self.assertEqual((report['links'], report['home_zones'], report['presence_seeded'],
                          report['migration_state']), (0, 0, 0, 'skipped'))
        self.assertEqual(P.get_str(self.env, 'migration_state'), 'skipped')

    def test_read_enabled_default(self):  # AC-60
        icp = self.env['ir.config_parameter'].sudo()
        icp.search([('key', '=', 'td.access.read_enabled')]).unlink()
        icp.set_param('td.base.environment', 'test')
        hooks.run_all(self.env)
        self.assertEqual(P.get_str(self.env, 'read_enabled'), 'True')
        P.set_param(self.env, 'read_enabled', 'False')
        hooks.run_all(self.env)
        self.assertEqual(P.get_str(self.env, 'read_enabled'), 'False')
        icp.search([('key', '=', 'td.access.read_enabled')]).unlink()
        icp.set_param('td.base.environment', 'prod')
        hooks.run_all(self.env)
        self.assertEqual(P.get_str(self.env, 'read_enabled'), 'False')

    def test_uninstall_hook_cards_before_server(self):  # O-1: деінсталяція з картками не падає на FK card.server_id
        server = self.server
        cards = self.env['td.access.card'].create([
            {'number': '88000001', 'server_id': server.id, 'holder_type': 'employee', 'employee_id': self.emp_a.id},
            {'number': '88000002', 'server_id': server.id, 'holder_type': 'pool'}])
        visitor = self.env['td.access.visitor'].create(
            {'name': 'Гість', 'host_employee_id': self.emp_a.id, 'server_id': server.id, 'card_id': cards[1].id})
        visitor.write({'state': 'expected'})  # не чернетка: звичайний unlink заборонений, хук обходить через f3d_housekeeping
        # звичайна робота не змінилась: сервер із картками видалити не можна (SPEC: ondelete='restrict')
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            server.unlink()
            server.flush_recordset()
        hooks.uninstall_hook(self.env)
        self.assertFalse(cards.exists())
        self.assertFalse(visitor.exists())
        self.assertFalse(self.env['td.access.card'].with_context(active_test=False).search([]))
        # те, що робить стандартна деінсталяція далі: сервер (з пристроями, дверима, подіями) видаляється без FK
        server.unlink()
        server.flush_recordset()
        self.assertFalse(server.exists())

    def test_uninstall_hook(self):  # AC-61
        emp = self.env['hr.employee'].sudo().create({'name': 'Хук', 'td_code': 'OP-HOOK'})
        atts = self.env['hr.attendance'].sudo().create([
            {'employee_id': emp.id, 'check_in': datetime(2026, 10, 12, 3, 0), 'check_out': datetime(2026, 10, 12, 4, 0),
             'in_mode': 'biostar', 'out_mode': 'biostar'},
            {'employee_id': emp.id, 'check_in': datetime(2026, 10, 13, 3, 0), 'in_mode': 'biostar'}])
        hooks.uninstall_hook(self.env)
        self.assertFalse(self.env['ir.config_parameter'].sudo().search([('key', '=like', 'td.access.%')]))
        self.assertEqual(len(atts.exists()), 2)
