from unittest.mock import patch

from odoo.tests import TransactionCase

from odoo.addons.factory3d_viewer.hooks import is_demo_db


class F3dViewerBase(TransactionCase):
    """Фікстури без вимоги демо-бази: користувачі, параметри, шина."""

    @classmethod
    def _make_user(cls, login, xmlids):
        groups = [cls.env.ref(x).id for x in xmlids]
        return cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": login, "login": login, "group_ids": [(6, 0, groups)]})

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_nobody = cls._make_user("f3d_nobody", ["base.group_user"])
        cls.user_f3d = cls._make_user("f3d_user", [
            "base.group_user", "factory3d_base.group_f3d_user", "stock.group_stock_user", "mrp.group_mrp_user"])
        cls.user_stock_only = cls._make_user(
            "f3d_stock", ["base.group_user", "factory3d_base.group_f3d_user", "stock.group_stock_user"])
        cls.user_mrp_only = cls._make_user(
            "f3d_mrp", ["base.group_user", "factory3d_base.group_f3d_user", "mrp.group_mrp_user"])
        cls.user_manager = cls._make_user("f3d_manager", ["base.group_user", "factory3d_base.group_f3d_manager"])
        cls.user_admin = cls._make_user("f3d_admin", ["base.group_user", "factory3d_base.group_f3d_admin"])
        cls.user_kiosk = cls.env.ref("factory3d_viewer.user_kiosk")

    def set_param(self, key, val):
        self.env["ir.config_parameter"].sudo().set_param(
            key if key.startswith("factory3d.") else f"factory3d.viewer.{key}", val)

    def demo_clock(self, value="2026-10-12 10:30"):
        self.set_param("demo_clock", value)

    def payload(self, user, **kw):
        from odoo.addons.factory3d_viewer.tools.payload import PayloadBuilder
        return PayloadBuilder(self.env(user=user), **kw).build()

    def events_since(self, ts):
        return self.env["f3d.viewer.event"].sudo().search([("create_date", ">=", ts)])

    def bus_messages(self):
        """Повертає список, який наповнює патч bus.bus._sendone (знімається в cleanup)."""
        sent = []
        patcher = patch.object(type(self.env["bus.bus"]), "_sendone",
                               lambda s, target, notification_type, message: sent.append(
                                   (target, notification_type, message)))
        patcher.start()
        self.addCleanup(patcher.stop)
        return sent


class F3dViewerCase(F3dViewerBase):
    """Потребує демо-бази (factory3d_iot_sim / компанія демо); інакше skipTest (§13.0)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_demo = is_demo_db(cls.env)
        if not cls.has_demo:
            cls.skipTest(cls, "немає демо-даних (factory3d_iot_sim)")

    def setUp(self):
        super().setUp()
        self.demo_clock("2026-10-12 10:30")
