"""AC-33, AC-58, AC-59, AC-60, ТБ-01, ТБ-02, ТБ-03 (SPEC §13.1, §13.4)."""

from odoo.exceptions import AccessError
from odoo.service.model import call_kw
from odoo.tests import tagged


from ..adapters import td_genset as td
from .test_rules import GensetCase

MODELS = ("f3d.genset.link", "f3d.genset.profile", "f3d.genset.event.map")


@tagged("post_install", "-at_install")
class TestAccess(GensetCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_nobody = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Nobody genset",
                    "login": "genset_nobody",
                    "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
                }
            )
        )
        cls.has_viewer = "f3d.viewer.event" in cls.env

    def payload(self, user, **kw):
        from odoo.addons.factory3d_viewer.tools.payload import PayloadBuilder

        return PayloadBuilder(self.env(user=user), **kw).build()

    def test_acl_matrix(self):  # AC-33, ТБ-01
        for model in MODELS:
            rec = self.env[model].search([], limit=1)
            self.assertTrue(rec, model)
            # nobody — відмова на все
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(self.user_nobody).search([])
            with self.assertRaises(AccessError, msg=model):
                rec.with_user(self.user_nobody).read(["id"])
            # reader — лише читання
            self.assertTrue(rec.with_user(self.user_reader).read(["id"]))
            with self.assertRaises(AccessError, msg=model):
                rec.with_user(self.user_reader).write({"name": "x"} if "name" in rec._fields else {})
            with self.assertRaises(AccessError, msg=model):
                rec.with_user(self.user_reader).unlink()
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(self.user_reader).create({})
            # manager / admin — усе
            for user in (self.user_manager, self.user_admin):
                for mode in ("read", "write", "create", "unlink"):
                    self.assertTrue(self.env[model].with_user(user).has_access(mode), (model, mode, user.login))
            for mode in ("write", "create", "unlink"):
                self.assertFalse(self.env[model].with_user(self.user_reader).has_access(mode), (model, mode))
                self.assertFalse(self.env[model].with_user(self.user_nobody).has_access(mode), (model, mode))
            self.assertFalse(self.env[model].with_user(self.user_nobody).has_access("read"), model)

    def test_params_admin_only(self):  # AC-33
        icp = self.env["ir.config_parameter"].with_user(self.user_manager)
        with self.assertRaises(AccessError):
            icp.set_param("factory3d.genset.read_enabled", "True")
        with self.assertRaises(AccessError):
            self.env["ir.config_parameter"].with_user(self.user_reader).search([("key", "=like", "factory3d.genset.%")])

    def test_no_commands_runtime(self):  # AC-58, ТБ-03
        self.set_param("write_enabled", "True")
        self.link._cron_publish()
        self.link._cron_events()
        self.link._cron_service()
        self.link.with_user(self.user_manager).action_check()
        if self.has_viewer:
            self.payload(self.user_reader)
        self.assertEqual(td.set_fuel_rate.call_count, 0)
        self.assertGreater(td.snapshot.call_count, 0)

    def test_nobody(self):  # AC-59
        with self.assertRaises(AccessError):
            self.env["f3d.genset.link"].with_user(self.user_nobody).search([])
        menu = self.env.ref("factory3d_genset.menu_f3d_genset")
        self.assertNotIn(menu.id, self.env["ir.ui.menu"].with_user(self.user_nobody)._visible_menu_ids())
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(self.user_reader)._visible_menu_ids())
        # reader читає зв'язку й профіль
        self.assertTrue(self.link.with_user(self.user_reader).read(["id"]))
        self.assertTrue(self.profile.with_user(self.user_reader).read(["id"]))
        if not self.has_viewer:
            return
        self.link._cron_publish()
        nobody = self.payload(self.user_nobody)
        self.assertNotIn("genset", nobody.get("infra", {}))
        self.assertNotIn("GENSET", nobody.get("infra", {}).get("cards", {}))
        reader = self.payload(self.user_reader)
        self.assertEqual(len(reader["infra"]["cards"]["GENSET"]["rows"]), 14)

    def test_actions_manager_only(self):  # AC-60
        link, profile = self.link, self.profile
        with self.assertRaises(AccessError):
            link.with_user(self.user_reader).action_check()
        with self.assertRaises(AccessError):
            profile.with_user(self.user_reader).action_apply_to_td()
        with self.assertRaises(AccessError):
            profile.with_user(self.user_reader).action_export_relay_profile()
        link.with_user(self.user_manager).action_check()
        profile.with_user(self.user_manager).action_apply_to_td()
        profile.with_user(self.user_manager).action_export_relay_profile()

    def test_private_methods_rpc(self):  # ТБ-02
        link = self.link.with_user(self.user_reader)
        for name in ("_publish_one", "_cron_publish", "_apply_event", "_compute_values"):
            if not hasattr(self.env["f3d.genset.link"], name):
                continue
            with self.assertRaises(AccessError, msg=name):
                call_kw(link, name, [link.ids], {})
        with self.assertRaises(AccessError):
            call_kw(link, "action_check", [link.ids], {})
