import json

from odoo.tests import tagged

from .common import F3DBmsCase


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestBmsInstall(F3DBmsCase):
    def test_module_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "td_bms")])
        self.assertEqual(mod.state, "installed")

    def test_groups_chain(self):
        op = self.env.ref("td_bms.group_td_bms_operator")
        user = self.env.ref("td_factory3d.group_td_user")
        manager = self.env.ref("td_factory3d.group_td_manager")
        self.assertIn(user, op.implied_ids)
        self.assertIn(op, manager.implied_ids)
        self.assertTrue(self.user_manager.has_group("td_bms.group_td_bms_operator"))
        self.assertTrue(self.user_admin.has_group("td_bms.group_td_bms_operator"))
        self.assertTrue(self.user_operator.has_group("td_factory3d.group_td_user"))
        self.assertFalse(self.user_reader.has_group("td_bms.group_td_bms_operator"))

    def test_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("td.bms.write_enabled"), "False")
        self.assertEqual(icp.get_param("td.bms.light_uf"), "0.7")
        self.assertEqual(icp.get_param("td.bms.light_check_delay_min"), "10")
        self.assertIn(json.loads(icp.get_param("td.bms.install_report"))["state"], ("done", "partial"))
        keys = icp.search([("key", "=like", "td.bms.%")]).mapped("key")
        self.assertGreaterEqual(len(keys), 15)

    def test_menus(self):
        root = self.env.ref("td_bms.menu_td_bms")
        self.assertEqual(root.parent_id, self.env.ref("td_factory3d.menu_td_root"))
        self.assertEqual(root.sequence, 80)
        cfg = self.env.ref("td_bms.menu_td_bms_config")
        self.assertEqual(cfg.parent_id, self.env.ref("td_factory3d.menu_td_config"))
