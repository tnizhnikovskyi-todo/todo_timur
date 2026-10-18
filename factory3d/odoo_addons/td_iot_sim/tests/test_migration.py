import importlib.util
import os

from odoo.tests import TransactionCase, tagged

from ..hooks import apply_read_enabled, post_init_hook

SPEC_KEY = 'td.iot_sim.read_enabled'


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
        panels = self.env['td.sim.panel'].search_count([])
        scenarios = self.env['td.sim.scenario'].search_count([])
        signals = self.env['td.sim.signal'].search_count([])
        devices = self.env['td.sim.device'].search_count([])
        post_init_hook(self.env)  # повторний запуск — без дублікатів
        self.assertEqual({s.x_code: s.x_value for s in Signal.search([('x_code', 'like', 'mig/test/')])}, values)
        self.assertEqual(self.env['td.sim.panel'].search_count([]), panels)
        self.assertEqual(self.env['td.sim.scenario'].search_count([]), scenarios)
        self.assertEqual(self.env['td.sim.signal'].search_count([]), signals)
        self.assertEqual(self.env['td.sim.device'].search_count([]), devices)
        self.assertTrue(self.env.ref('td_iot_sim.cron_iot_sim'))
        self.assertEqual(self.env.ref('td_iot_sim.menu_iot_root').parent_id,
                         self.env.ref('td_iot_sim.menu_td_sim_root'))

    def test_pre_migrate_runs(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', '19.0.2.0.0', 'pre-migrate.py')
        spec = importlib.util.spec_from_file_location('f3d_sim_pre_migrate', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.migrate(self.env.cr, '19.0.1.0.0')

    def _load_post_migrate(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations', '19.0.2.0.0',
                            'post-migrate.py')
        spec = importlib.util.spec_from_file_location('f3d_sim_post_migrate', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _registry_snapshot(self):
        """{модель: {id: (code, write_date)}} — щоб побачити і дублікати, і зайві записи."""
        return {model: {r.id: (getattr(r, 'code', False), r.write_date) for r in self.env[model].sudo().search([])}
                for model in ('td.sim.device', 'td.sim.signal', 'td.sim.panel', 'td.sim.scenario')}

    def test_post_migrate_fills_registry_idempotently(self):
        """S-1: при `-u` з прототипу `post_init_hook` не викликається, реєстр порожній — post-migrate
        наповнює його тими самими кроками; другий виклик (база, де вже наповнено) нічого не змінює."""
        Device = self.env['td.sim.device'].sudo()
        Signal = self.env['td.sim.signal'].sudo()
        devices, signals = Device.search_count([]), Signal.search_count([])
        self.assertTrue(devices and signals)
        # база прототипу після `-u`: каталог і реєстр порожні
        Signal.search([]).unlink()
        Device.search([]).unlink()
        self.assertEqual((Device.search_count([]), Signal.search_count([])), (0, 0))
        mod = self._load_post_migrate()
        mod.migrate(self.env.cr, '19.0.1.0.0')
        self.assertEqual(Device.search_count([]), devices)
        self.assertEqual(Signal.search_count([]), signals)
        self.assertEqual(Signal.search_count([('origin', '=', 'mock')]), 196)
        self.assertFalse(Signal.search([('device_id', '=', False)]))
        snapshot = self._registry_snapshot()
        mod.migrate(self.env.cr, '19.0.1.0.0')  # повторний запуск — без дублікатів і без записів
        self._assert_unchanged(snapshot)

    def test_post_migrate_on_filled_registry_changes_nothing(self):
        """Тестовий сервер: реєстр уже наповнено (276/1168) — post-migrate нічого не створює й не пише."""
        snapshot = self._registry_snapshot()
        self._load_post_migrate().migrate(self.env.cr, '19.0.1.0.0')
        self._assert_unchanged(snapshot)

    def _assert_unchanged(self, snapshot):
        now = self._registry_snapshot()
        changed = {model: sorted(code for rid, (code, _wd) in recs.items() if snapshot[model].get(rid) != (code, _wd))[:10]
                   for model, recs in now.items()}
        self.assertEqual({m: v for m, v in changed.items() if v}, {}, "змінені записи")
        self.assertEqual({m: len(r) for m, r in now.items()}, {m: len(r) for m, r in snapshot.items()})

    def test_hook_read_enabled_by_environment(self):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('td.iot_sim.write_enabled', 'False')
        for environment, expected in (('test', 'True'), ('prod', 'False')):
            ICP.set_param('td.base.environment', environment)
            for _ in range(2):  # повторний запуск — той самий результат
                apply_read_enabled(self.env)
                self.assertEqual(ICP.get_param(SPEC_KEY), expected)
                self.assertEqual(ICP.get_param('td.iot_sim.write_enabled'), 'False')
        ICP.set_param('td.base.environment', 'prod')
        post_init_hook(self.env)
        self.assertEqual(ICP.get_param(SPEC_KEY), 'False')
