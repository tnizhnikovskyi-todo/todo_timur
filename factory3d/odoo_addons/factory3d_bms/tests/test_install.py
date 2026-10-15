from odoo.tests import tagged

from .common import F3DBmsCase


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestBmsInstall(F3DBmsCase):
    def test_module_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "factory3d_bms")])
        self.assertEqual(mod.state, "installed")

    def test_groups_chain(self):
        op = self.env.ref("factory3d_bms.group_f3d_bms_operator")
        user = self.env.ref("factory3d_base.group_f3d_user")
        manager = self.env.ref("factory3d_base.group_f3d_manager")
        self.assertIn(user, op.implied_ids)
        self.assertIn(op, manager.implied_ids)
        self.assertTrue(self.user_manager.has_group("factory3d_bms.group_f3d_bms_operator"))
        self.assertTrue(self.user_admin.has_group("factory3d_bms.group_f3d_bms_operator"))
        self.assertTrue(self.user_operator.has_group("factory3d_base.group_f3d_user"))
        self.assertFalse(self.user_reader.has_group("factory3d_bms.group_f3d_bms_operator"))

    def test_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("factory3d.bms.write_enabled"), "False")
        self.assertEqual(icp.get_param("factory3d.bms.light_uf"), "0.7")
        self.assertEqual(icp.get_param("factory3d.bms.light_check_delay_min"), "10")
        self.assertEqual(icp.get_param("factory3d.bms.install_report"), "{}")
        keys = icp.search([("key", "=like", "factory3d.bms.%")]).mapped("key")
        self.assertGreaterEqual(len(keys), 15)

    def test_menus(self):
        root = self.env.ref("factory3d_bms.menu_f3d_bms")
        self.assertEqual(root.parent_id, self.env.ref("factory3d_base.menu_f3d_root"))
        self.assertEqual(root.sequence, 80)
        cfg = self.env.ref("factory3d_bms.menu_f3d_bms_config")
        self.assertEqual(cfg.parent_id, self.env.ref("factory3d_base.menu_f3d_config"))
