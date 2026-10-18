from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestInstall(TransactionCase):
    """Каркас W0: модуль встановлюється, меню, параметри й групи на місці."""

    def test_root_menu(self):
        menu = self.env.ref("td_telemetry.menu_td_telemetry")
        self.assertEqual(menu.name, "Телеметрія")
        self.assertEqual(menu.parent_id, self.env.ref("td_factory3d.menu_td_root"))
        self.assertEqual(menu.sequence, 30)
        self.assertIn(self.env.ref("td_factory3d.group_td_user"), menu.group_ids)

    def test_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        expected = {
            "write_enabled": "False",
            "keep_days": "30",
            "keep_hours_days": "400",
            "default_store_period_s": "300",
            "stale_periods": "3",
            "stale_min_s": "60",
            "bus_min_interval_s": "10",
            "realarm_cooldown_s": "3600",
            "push_max_readings": "2000",
            "push_rate_per_min": "60",
            "meter_lead_pct": "5",
            "drop_level0": "False",
            "stale_notify_min": "0",
        }
        for key, val in expected.items():
            self.assertEqual(icp.get_param("td.telemetry." + key), val, key)
        self.assertIn(icp.get_param("td.telemetry.read_enabled"), ("True", "False"))
        self.assertFalse(icp.get_param("td.telemetry.default_team_id") is None)

    def test_groups(self):
        for xmlid in ("group_td_user", "group_td_manager", "group_td_admin"):
            self.assertTrue(self.env.ref("td_factory3d." + xmlid))
