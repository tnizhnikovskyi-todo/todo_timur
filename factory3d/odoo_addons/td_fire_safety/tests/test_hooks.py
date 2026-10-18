"""AC-01…AC-04, AC-60…AC-62, AC-69, AC-76: дані установки, хуки, нейтралізація, відповідність."""
import json

from odoo.addons.td_telemetry.tools.address import validate_address, validate_params
from odoo.tools import file_path
from odoo.tests import TransactionCase, tagged

from .common import FireCase

PREFIX = 'td.fire_safety.'
COUNT_MODELS = ('td.fire.norm', 'td.fire.panel', 'td.fire.loop', 'td.fire.zone', 'td.fire.device',
                'td.fire.system', 'td.fire.smoke.zone', 'td.fire.exit', 'td.fire.route',
                'td.fire.drill.template', 'td.fire.drill.template.step', 'td.fire.event', 'td.fire.drill',
                'td.fire.drill.person', 'td.signal', 'td.source', 'maintenance.request')


def _count(env, model):
    return env[model].with_context(active_test=False).search_count([])


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestInstallData(TransactionCase):

    def count(self, model, domain=None):
        return self.env[model].with_context(active_test=False).search_count(domain or [])

    def test_counts(self):
        self.assertEqual(self.count('td.fire.norm'), 27)
        self.assertEqual(self.count('td.fire.panel'), 1)
        self.assertEqual(self.count('td.fire.loop'), 4)
        self.assertEqual(self.count('td.fire.zone'), 35)
        self.assertEqual(self.count('td.fire.device'), 353)
        self.assertEqual(self.count('td.fire.system'), 3)
        self.assertEqual(self.count('td.fire.smoke.zone'), 8)
        self.assertEqual(self.count('td.fire.exit'), 12)
        routes = self.env['td.fire.route'].search([])
        self.assertEqual(len(routes), 32)
        self.assertEqual(sum(routes.mapped('point_count')), 132)
        template = self.env.ref('td_fire_safety.drill_template_default')
        self.assertEqual(len(template.step_ids), 8)
        self.assertEqual(self.count('td.fire.drill.template'), 1)

    def test_kinds(self):
        zones = self.env['td.fire.zone'].with_context(active_test=False)._read_group([], ['kind'], ['__count'])
        self.assertEqual(dict(zones), {'smoke': 25, 'multi': 9, 'heat': 1})
        devices = self.env['td.fire.device'].with_context(active_test=False)._read_group([], ['type'], ['__count'])
        self.assertEqual(dict(devices), {
            'smoke': 138, 'multi': 82, 'heat': 2, 'mcp': 36, 'sounder': 41, 'flame': 3, 'spark_detector': 4,
            'spark_nozzle': 3, 'smoke_vent': 44})

    def test_sources_readonly(self):
        sources = self.env['td.source'].search([('module', '=', 'fire_safety')])
        self.assertEqual(len(sources), 2)
        self.assertEqual(self.count('td.source', [('td_fire_readonly', '=', True)]), 2)
        for source in sources:
            self.assertTrue(source.td_fire_readonly)
            self.assertFalse(source.write_enabled)
        bacnet = self.env.ref('td_fire_safety.source_bacnet_facp_1')
        self.assertTrue(bacnet.params.get('read_only'))

    def test_signals_readonly(self):
        signals = self.env['td.signal'].with_context(active_test=False).search([('module', '=', 'fire_safety')])
        self.assertEqual(len(signals), 55)
        self.assertFalse(signals.filtered('write_enabled'))

    def test_dust_created_clean(self):
        sig = self.env['td.signal'].search([('code', '=', 'fire/groups/FA-FAC/dust')])
        self.assertEqual(len(sig), 1)
        self.assertFalse(self.env['ir.model.data'].search([('model', '=', 'td.signal'), ('res_id', '=', sig.id)]))
        self.assertEqual(sig.origin, 'module')
        self.assertEqual(sig.address, {'object': 'PIV', 'instance': 21607, 'mode': 'poll'})
        report = json.loads(self.env['ir.config_parameter'].sudo().get_param(PREFIX + 'migration_report'))
        self.assertEqual(report['state'], 'partial')
        self.assertEqual(report['missing'], 44)
        self.assertEqual(report['dust_signal'], 'created')
        self.assertFalse(report['pressure_signal'])
        self.assertEqual(self.env.ref('td_fire_safety.system_sprinklers').state, 'unknown')

    def test_bacnet_params_addresses(self):
        bacnet = self.env.ref('td_fire_safety.source_bacnet_facp_1')
        self.assertEqual(bacnet.code, 'BAC-200-FACP-1')
        self.assertEqual(bacnet.params, {'host': 'iot-sim', 'port': 47808, 'device': 200, 'network': 2,
                                         'read_only': True, 'timeout_s': 5, 'rpm': True, 'rpm_max': 50})
        self.assertEqual(validate_params('bacnet_ip', bacnet.params), [])
        signals = self.env['td.signal'].with_context(active_test=False).search(
            [('source_id', '=', bacnet.id), ('code', '!=', 'fire/groups/FA-FAC/dust')])
        self.assertEqual(len(signals), 46)
        for sig in signals:
            self.assertNotIn('device', sig.address, sig.code)
            self.assertEqual(validate_address('bacnet_ip', sig.address), [], sig.code)
            self.assertIn(sig.address['object'], ('LSZ', 'MSV', 'BV', 'PIV'), sig.code)
            self.assertEqual(sig.origin, 'module', sig.code)
        data = self.env['td.signal'].with_context(active_test=False).search([('module', '=', 'fire_safety')])
        self.assertTrue(all(s.origin == 'module' for s in data))


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestRerun(TransactionCase):

    def test_run_all_idempotent(self):
        from odoo.addons.td_fire_safety import hooks
        before = {m: _count(self.env, m) for m in COUNT_MODELS}
        for _i in range(2):
            hooks.run_all(self.env)
        self.assertEqual({m: _count(self.env, m) for m in COUNT_MODELS}, before)
        self.assertEqual(self.env['td.fire.event'].search_count([('dedup_key', '=like', 'demo:%')]), 4)
        self.assertEqual(self.env['td.fire.drill'].search_count([('origin', '=', 'demo')]), 1)
        self.assertEqual(self.env['td.fire.event'].search_count([('source', '=', 'demo')]), 4)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestUninstallNeutralize(FireCase):

    def test_uninstall_hook(self):
        from odoo.addons.td_fire_safety import hooks
        self.addCleanup(self.env.registry.clear_cache)
        hooks.uninstall_hook(self.env)
        sig = self.env['td.signal'].search([('code', '=', 'fire/groups/FA-FAC/dust')])
        self.assertEqual(len(sig), 1)
        self.assertFalse(sig.source_id)
        self.assertEqual(sig.address or {}, {})
        self.assertEqual(sig.module, 'fire_safety')
        self.assertEqual(self.env['ir.config_parameter'].sudo().search_count([('key', '=like', PREFIX + '%')]), 0)

    def test_neutralize_sql(self):
        self.addCleanup(self.env.registry.clear_cache)
        drill = self.new_drill(zone_id=self.z_cnc.id, mode='tabletop')
        drill.sudo().write({'sim_run_ref': 'run-1'})
        emp = self.make_employee('Тест Нейтралізація', 'N-001')
        self.env['td.fire.drill.person'].sudo().create(
            {'drill_id': drill.id, 'employee_id': emp.id, 'seq': 1, 'source': 'manual'})
        act_type = self.env.ref('td_fire_safety.mail_act_fire_alarm')
        self.env['mail.activity'].create({
            'activity_type_id': act_type.id, 'res_model_id': self.env['ir.model']._get_id('td.fire.panel'),
            'res_id': self.panel.id, 'user_id': self.guard1.id, 'summary': 'Пожежна тривога'})
        self.panel.sudo().comm = 'online'
        self.assertTrue(self.env['mail.activity'].search_count([('activity_type_id', '=', act_type.id)]))
        self.env.flush_all()
        path = file_path('td_fire_safety/data/neutralize.sql')
        with open(path, encoding='utf-8') as fh:
            self.env.cr.execute(fh.read())
        self.env.invalidate_all()
        cr = self.env.cr
        cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (PREFIX + 'read_enabled',))
        self.assertEqual(cr.fetchone()[0], 'False')
        cr.execute("""SELECT count(*) FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' AND d.res_id = c.id
                       WHERE d.module = 'td_fire_safety' AND c.active""")
        self.assertEqual(cr.fetchone()[0], 0)
        cr.execute("SELECT count(*) FROM td_source WHERE td_fire_readonly AND (read_enabled OR write_enabled)")
        self.assertEqual(cr.fetchone()[0], 0)
        cr.execute("SELECT count(*) FROM td_fire_drill_person WHERE employee_id IS NOT NULL")
        self.assertEqual(cr.fetchone()[0], 0)
        cr.execute("SELECT count(*) FROM td_fire_drill WHERE sim_run_ref IS NOT NULL")
        self.assertEqual(cr.fetchone()[0], 0)
        cr.execute("""SELECT count(*) FROM mail_activity a JOIN ir_model_data d ON d.res_id = a.activity_type_id
                       WHERE d.module = 'td_fire_safety' AND d.name = 'mail_act_fire_alarm'
                         AND d.model = 'mail.activity.type'""")
        self.assertEqual(cr.fetchone()[0], 0)
        cr.execute("SELECT count(*) FROM td_fire_panel WHERE comm != 'off'")
        self.assertEqual(cr.fetchone()[0], 0)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestCompliance(TransactionCase):

    def test_after_install(self):
        panel = self.env['td.fire.panel'].search([], limit=1)
        self.assertEqual(panel.compliance_zones_ok, 35)
        self.assertEqual(panel.compliance_mcp_max_m, 26.9)
        self.assertEqual(panel.compliance_routes_ok, 32)
        self.assertTrue(panel.compliance_exits_ok)
        self.assertEqual(panel.compliance_smoke_ok, 8)
        self.assertFalse(panel.compliance_missing_zones)
        self.assertFalse(panel.compliance_dirty)

    def test_notification(self):
        panel = self.env['td.fire.panel'].search([], limit=1)
        panel.compliance_ts = False
        res = panel.action_recompute_compliance()
        self.assertEqual(res['params']['message'],
                         'Перераховано: зони 35/35, ручні max 26,9 м, маршрути 32/32, димові зони 8/8')
        self.assertTrue(panel.compliance_ts)
        values = (panel.compliance_zones_ok, panel.compliance_mcp_max_m, panel.compliance_routes_ok)
        panel.write({'compliance_ts': False, 'compliance_dirty': True})
        panel._cron_compliance()
        self.assertTrue(panel.compliance_ts)
        self.assertEqual((panel.compliance_zones_ok, panel.compliance_mcp_max_m, panel.compliance_routes_ok), values)
