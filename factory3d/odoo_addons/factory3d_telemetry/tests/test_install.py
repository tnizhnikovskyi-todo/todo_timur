from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'f3d', 'f3d_telemetry')
class TestInstall(TransactionCase):
    """Каркас W0: модуль встановлюється, меню, параметри й групи на місці."""

    def test_root_menu(self):
        menu = self.env.ref('factory3d_telemetry.menu_f3d_telemetry')
        self.assertEqual(menu.name, 'Телеметрія')
        self.assertEqual(menu.parent_id, self.env.ref('factory3d_base.menu_f3d_root'))
        self.assertEqual(menu.sequence, 30)
        self.assertIn(self.env.ref('factory3d_base.group_f3d_user'), menu.group_ids)

    def test_params(self):
        icp = self.env['ir.config_parameter'].sudo()
        expected = {
            'write_enabled': 'False', 'keep_days': '30', 'keep_hours_days': '400',
            'default_store_period_s': '300', 'stale_periods': '3', 'stale_min_s': '60',
            'bus_min_interval_s': '10', 'realarm_cooldown_s': '3600', 'push_max_readings': '2000',
            'push_rate_per_min': '60', 'meter_lead_pct': '5', 'drop_level0': 'False',
            'stale_notify_min': '0',
        }
        for key, val in expected.items():
            self.assertEqual(icp.get_param('factory3d.telemetry.' + key), val, key)
        self.assertIn(icp.get_param('factory3d.telemetry.read_enabled'), ('True', 'False'))
        self.assertFalse(icp.get_param('factory3d.telemetry.default_team_id') is None)

    def test_groups(self):
        for xmlid in ('group_f3d_user', 'group_f3d_manager', 'group_f3d_admin'):
            self.assertTrue(self.env.ref('factory3d_base.' + xmlid))
