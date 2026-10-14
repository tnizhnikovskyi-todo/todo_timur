from datetime import timedelta

import requests

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TAG_ARGS, SimCase

STATUS = {
    'enabled': True, 'version': '0.1.0', 'mode': 'follow_odoo', 'factor': 1.0,
    'sim_now': '2026-10-13T20:05:11+03:00', 'uptime_s': 3600, 'seed': 20261012, 'alarms': 1,
    'devices_fault': [], 'runs': [], 'protocols': {'opcua': 'ok', 'modbus': 'ok'},
    'odoo': {'stale': False},
}


@tagged(*TAG_ARGS)
class TestPanel(SimCase):

    def setUp(self):
        super().setUp()
        self.cron = self.env.ref('factory3d_iot_sim.cron_iot_sim')

    def test_poll_online_disables_level0(self):
        self.cron.active = True
        self.respond('GET', '/status', 200, STATUS)
        self.env['f3d.sim.panel']._cron_poll_status()
        panel = self.panel
        self.assertEqual(panel.state, 'online')
        self.assertEqual(panel.version, '0.1.0')
        self.assertEqual(panel.mode, 'follow_odoo')
        self.assertEqual(panel.factor, 1.0)
        self.assertEqual(panel.sim_time.hour, 17)  # 20:05 +03:00 → 17:05 UTC
        self.assertFalse(self.cron.active)
        self.assertEqual(panel.level0_state, 'auto_off')
        self.assertEqual(self.calls[0]['headers']['Authorization'], 'Bearer secret-sim-token')

    def test_poll_offline_enables_level0_after_n_min(self):
        self.cron.active = False
        self.panel.write({'state': 'offline', 'level0_state': 'auto_off',
                          'last_contact': fields.Datetime.now() - timedelta(minutes=6)})
        self.respond('GET', '/status', requests.ConnectionError('down'), None)
        self.env['f3d.sim.panel']._cron_poll_status()
        self.assertEqual(self.panel.state, 'offline')
        self.assertTrue(self.cron.active)
        self.assertEqual(self.panel.level0_state, 'auto_on')
        self.assertTrue(self.panel.message_ids)

    def test_offline_shorter_than_threshold_keeps_level0(self):
        self.cron.active = False
        self.panel.write({'state': 'offline', 'last_contact': fields.Datetime.now() - timedelta(minutes=1)})
        self.respond('GET', '/status', requests.ConnectionError('down'), None)
        self.env['f3d.sim.panel']._cron_poll_status()
        self.assertFalse(self.cron.active)

    def test_apply_factor_blocked_by_stop_crane(self):
        self.set_params(write_enabled='False')
        self.panel.factor_new = 5
        with self.assertRaisesRegex(UserError, 'стоп-краном'):
            self.panel.action_apply_factor()
        self.assertEqual(self.calls, [])

    def test_apply_factor_follow_odoo_409(self):
        self.panel.write({'mode': 'follow_odoo', 'factor_new': 5})
        with self.assertRaisesRegex(UserError, 'За Odoo'):
            self.panel.action_apply_factor()
        self.assertEqual(self.calls, [])

    def test_apply_factor_posts_time(self):
        self.panel.write({'mode': 'scenario', 'factor_new': 5})
        self.respond('POST', '/time', 200, {'factor': 5})
        self.panel.action_apply_factor()
        self.assertEqual(self.calls[-1]['json'], {'factor': 5})

    def test_http_errors_mapped(self):
        for status, text in ((401, 'відхилив токен'), (423, 'стоп-краном'), (404, "Невідомий об'єкт"),
                             (500, 'недоступний')):
            self.respond('GET', '/status', status, {'detail': 'x'})
            with self.assertRaisesRegex(UserError, text):
                self.panel._sim_get('/status')

    def test_stop_all_sets_locked(self):
        self.respond('POST', '/stop-all', 200, {})
        self.panel.action_stop_all()
        self.assertEqual(self.panel.state, 'locked')

    def test_menu_under_base_root(self):
        root = self.env.ref('factory3d_iot_sim.menu_f3d_sim_root')
        self.assertEqual(root.parent_id, self.env.ref('factory3d_base.menu_f3d_root'))
        self.assertEqual(root.sequence, 90)
        level0 = self.env.ref('factory3d_iot_sim.menu_iot_root')
        self.assertEqual(level0.parent_id, root)
        self.assertEqual(level0.sequence, 9)
        settings = self.env.ref('factory3d_iot_sim.menu_f3d_sim_settings')
        self.assertEqual(settings.parent_id, self.env.ref('factory3d_base.menu_f3d_config'))
        self.assertEqual(settings.sequence, 90)
        maintenance = self.env.ref('maintenance.menu_maintenance_title')
        xmlids = self.env['ir.model.data'].search([
            ('module', '=', 'factory3d_iot_sim'), ('model', '=', 'ir.ui.menu'),
            ('res_id', 'in', maintenance.child_id.ids)])
        self.assertFalse(xmlids)
