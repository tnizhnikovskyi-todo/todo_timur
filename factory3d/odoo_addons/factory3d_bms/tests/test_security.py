from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import F3DBmsCase

MODELS = (
    "f3d.bms.light.norm",
    "f3d.bms.light.panel",
    "f3d.bms.light.group",
    "f3d.bms.light.scene",
    "f3d.bms.hvac.unit",
    "f3d.bms.heat.balance",
    "f3d.bms.deviation",
)


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestRights(F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_none = new_test_user(cls.env, "bms_none", groups="base.group_user")
        sig = cls.env["f3d.signal"].search([("module", "=", "bms")], limit=1)
        cls.dev = cls.env["f3d.bms.deviation"].create(
            {"name": "Тест", "signal_id": sig.id, "rule": "other", "started": fields.Datetime.now()}
        )

    def test_acl_matrix(self):
        for model in MODELS:
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(self.user_none).search([])
            self.env[model].with_user(self.user_reader).search([], limit=1)
        group = self.env["f3d.bms.light.group"].search([], limit=1)
        with self.assertRaises(AccessError):
            group.with_user(self.user_reader).write({"note": "x"})
        with self.assertRaises(AccessError):
            group.with_user(self.user_operator).write({"note": "x"})
        group.with_user(self.user_manager).write({"note": "x"})
        dev = self.dev
        dev.with_user(self.user_operator).write({"note": "ok"})
        with self.assertRaises(AccessError):
            dev.with_user(self.user_operator).write({"state": "closed"})
        with self.assertRaises(AccessError):
            dev.with_user(self.user_operator).unlink()
        with self.assertRaises(AccessError):
            dev.with_user(self.user_manager).unlink()
        dev.with_user(self.user_admin).unlink()

    def test_groups_chain(self):
        operator = self.env.ref("factory3d_bms.group_f3d_bms_operator")
        self.assertIn(self.env.ref("factory3d_base.group_f3d_user"), operator.implied_ids)
        self.assertIn(operator, self.env.ref("factory3d_base.group_f3d_manager").implied_ids)

    def test_own_privilege(self):
        operator = self.env.ref("factory3d_bms.group_f3d_bms_operator")
        self.assertEqual(operator.privilege_id, self.env.ref("factory3d_bms.privilege_f3d_bms"))
        self.assertEqual(operator.privilege_id.category_id, self.env.ref("factory3d_base.module_category_factory3d"))
        self.assertNotIn(operator, self.env.ref("factory3d_base.privilege_f3d").group_ids)

    def test_menus(self):
        expected = {
            "menu_f3d_bms": ("factory3d_base.menu_f3d_root", 80),
            "menu_f3d_bms_overview": ("menu_f3d_bms", 10),
            "menu_f3d_bms_lighting": ("menu_f3d_bms", 20),
            "menu_f3d_bms_light_group": ("menu_f3d_bms_lighting", 10),
            "menu_f3d_bms_light_panel": ("menu_f3d_bms_lighting", 20),
            "menu_f3d_bms_light_norm": ("menu_f3d_bms_lighting", 30),
            "menu_f3d_bms_hvac": ("menu_f3d_bms", 30),
            "menu_f3d_bms_hvac_unit": ("menu_f3d_bms_hvac", 10),
            "menu_f3d_bms_heat_balance": ("menu_f3d_bms_hvac", 20),
            "menu_f3d_bms_deviation": ("menu_f3d_bms", 40),
            "menu_f3d_bms_config": ("factory3d_base.menu_f3d_config", 80),
            "menu_f3d_bms_config_scene": ("menu_f3d_bms_config", 10),
            "menu_f3d_bms_config_settings": ("menu_f3d_bms_config", 20),
            "menu_f3d_bms_config_reinstall": ("menu_f3d_bms_config", 90),
        }
        for xid, (parent, seq) in expected.items():
            menu = self.env.ref("factory3d_bms." + xid)
            parent_ref = parent if "." in parent else "factory3d_bms." + parent
            self.assertEqual(menu.parent_id, self.env.ref(parent_ref), xid)
            self.assertEqual(menu.sequence, seq, xid)
        self.assertTrue(self.env.ref("factory3d_bms.menu_f3d_bms_deviation").action)
        self.assertEqual(
            self.env.ref("factory3d_bms.menu_f3d_bms_config_settings").group_ids,
            self.env.ref("factory3d_base.group_f3d_admin"),
        )

    def test_reinstall_admin_only(self):
        with self.assertRaises(AccessError):
            self.env["f3d.bms.check"].with_user(self.user_manager).f3d_bms_reinstall_data()
        res = self.env["f3d.bms.check"].with_user(self.user_admin).f3d_bms_reinstall_data()
        self.assertEqual(res["tag"], "display_notification")
