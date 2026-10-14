import importlib.util
import os

from odoo.tests import TransactionCase, tagged

from ..hooks import apply_read_enabled, post_init_hook

SPEC_KEY = 'factory3d.iot_sim.read_enabled'


@tagged('post_install', '-at_install', 'f3d', 'f3d_iot_sim')
class TestMigration(TransactionCase):
    """AC-25 (спрощено): повної фікстури data-модуля 19.0.1.0.0 немає — перевіряємо, що рівень 0
    переживає повторний запуск хука/міграції й лишається сумісним."""

    def test_upgrade_keeps_level0(self):
        Signal = self.env['x_f3d_signal']
        eq = self.env['maintenance.equipment'].create({'name': 'Мігр-Т'})
        for n in range(3):
            Signal.create({'x_name': 'S%d' % n, 'x_code': 'mig/test/%d' % n, 'x_equipment_id': eq.id,
                           'x_value': 10.0 + n, 'x_kind': 'x', 'x_unit': 'u', 'x_mode': 'noise',
                           'x_nominal': 10.0 + n})
        values = {s.x_code: s.x_value for s in Signal.search([('x_code', 'like', 'mig/test/')])}
        panels = self.env['f3d.sim.panel'].search_count([])
        scenarios = self.env['f3d.sim.scenario'].search_count([])
        signals = self.env['f3d.sim.signal'].search_count([])
        devices = self.env['f3d.sim.device'].search_count([])
        post_init_hook(self.env)  # повторний запуск — без дублікатів
        self.assertEqual({s.x_code: s.x_value for s in Signal.search([('x_code', 'like', 'mig/test/')])}, values)
        self.assertEqual(self.env['f3d.sim.panel'].search_count([]), panels)
        self.assertEqual(self.env['f3d.sim.scenario'].search_count([]), scenarios)
        self.assertEqual(self.env['f3d.sim.signal'].search_count([]), signals)
        self.assertEqual(self.env['f3d.sim.device'].search_count([]), devices)
        self.assertTrue(self.env.ref('factory3d_iot_sim.cron_iot_sim'))
        self.assertEqual(self.env.ref('factory3d_iot_sim.menu_iot_root').parent_id,
                         self.env.ref('factory3d_iot_sim.menu_f3d_sim_root'))

    def test_pre_migrate_runs(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', '19.0.2.0.0', 'pre-migrate.py')
        spec = importlib.util.spec_from_file_location('f3d_sim_pre_migrate', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.migrate(self.env.cr, '19.0.1.0.0')

    def test_hook_read_enabled_by_environment(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('factory3d.iot_sim.write_enabled', 'False')
        for environment, expected in (('test', 'True'), ('prod', 'False')):
            ICP.set_param('factory3d.base.environment', environment)
            for _ in range(2):  # повторний запуск — той самий результат
                apply_read_enabled(self.env)
                self.assertEqual(ICP.get_param(SPEC_KEY), expected)
                self.assertEqual(ICP.get_param('factory3d.iot_sim.write_enabled'), 'False')
        ICP.set_param('factory3d.base.environment', 'prod')
        post_init_hook(self.env)
        self.assertEqual(ICP.get_param(SPEC_KEY), 'False')
