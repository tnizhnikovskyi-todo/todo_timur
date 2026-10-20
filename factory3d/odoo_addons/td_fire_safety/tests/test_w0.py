"""W0-скелет: групи (§4.2), параметри (§5.1), меню (§3)."""

import json

from odoo.tests import TransactionCase, tagged

PARAMS = {
    "read_enabled": "True",
    "comm_stale_after_s": "90",
    "comm_lost_after_s": "180",
    "dust_warn_pct": "80",
    "dust_alarm_pct": "90",
    "polymer_panels": "False",
    "cover_tol_m": "0.5",
    "drill_time_limit_s": "300",
    "drill_auto_create": "True",
    "drill_match_window_min": "30",
    "drill_auto_stop_s": "120",
    "drill_sim_duration_s": "300",
    "alert_group_xmlid": "td_factory3d.group_td_user",
    "team_id": "",
    "viewer_devices": "False",
    "event_ack_required": "True",
    "migration_report": "{}",
}


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestW0Skeleton(TransactionCase):
    def test_groups(self):
        drill = self.env.ref("td_fire_safety.group_td_fire_drill")
        user = self.env.ref("td_factory3d.group_td_user")
        manager = self.env.ref("td_factory3d.group_td_manager")
        admin = self.env.ref("td_factory3d.group_td_admin")
        self.assertIn(user, drill.implied_ids)
        self.assertIn(drill, manager.implied_ids)
        # цепочка U ⊂ D ⊂ M ⊂ A (CB-10)
        self.assertIn(drill, admin.all_implied_ids)
        self.assertIn(user, drill.all_implied_ids)
        self.assertEqual(drill.privilege_id, self.env.ref("td_fire_safety.privilege_td_fire"))

    def test_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(len(PARAMS), 17)
        for key, value in PARAMS.items():
            if key == "migration_report":  # після установки — звіт хука (§5.4 п. 9), а не '{}'
                self.assertIn(json.loads(icp.get_param("td.fire_safety." + key))["state"], ("done", "partial"))
                continue
            self.assertEqual(icp.get_param("td.fire_safety." + key) or "", value, key)
        self.assertFalse(icp.get_param("td.fire_safety.write_enabled"))

    def test_drill_sequence(self):
        seq = self.env.ref("td_fire_safety.seq_td_fire_drill")
        self.assertEqual((seq.code, seq.prefix, seq.padding), ("td.fire.drill", "DRILL/%(year)s/", 4))

    def test_menus(self):
        root = self.env.ref("td_fire_safety.menu_td_fire_root")
        safety = self.env.ref("td_factory3d.menu_td_safety")
        self.assertEqual(root.parent_id, safety)
        self.assertEqual(root.sequence, 40)
        evac = self.env.ref("td_fire_safety.menu_td_fire_evac")
        self.assertEqual((evac.parent_id, evac.sequence), (safety, 50))
        for xmlid in ("menu_td_fire_template", "menu_td_fire_loop"):
            menu = self.env.ref("td_fire_safety." + xmlid)
            self.assertEqual(menu.parent_id, root, xmlid)
            self.assertIn(self.env.ref("td_factory3d.group_td_manager"), menu.group_ids, xmlid)
