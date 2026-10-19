from unittest.mock import patch

from odoo.tests import TransactionCase

from odoo.addons.td_viewer3d.hooks import is_demo_db


class F3dViewerBase(TransactionCase):
    """Фікстури без вимоги демо-бази: користувачі, параметри, шина."""

    @classmethod
    def _make_user(cls, login, xmlids):
        groups = [cls.env.ref(x).id for x in xmlids]
        return (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create({"name": login, "login": login, "group_ids": [(6, 0, groups)]})
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_nobody = cls._make_user("f3d_nobody", ["base.group_user"])
        cls.user_f3d = cls._make_user(
            "f3d_user",
            ["base.group_user", "td_factory3d.group_td_user", "stock.group_stock_user", "mrp.group_mrp_user"],
        )
        cls.user_stock_only = cls._make_user(
            "f3d_stock", ["base.group_user", "td_factory3d.group_td_user", "stock.group_stock_user"]
        )
        cls.user_mrp_only = cls._make_user(
            "f3d_mrp", ["base.group_user", "td_factory3d.group_td_user", "mrp.group_mrp_user"]
        )
        cls.user_manager = cls._make_user("f3d_manager", ["base.group_user", "td_factory3d.group_td_manager"])
        cls.user_admin = cls._make_user("f3d_admin", ["base.group_user", "td_factory3d.group_td_admin"])
        cls.user_kiosk = cls.env.ref("td_viewer3d.user_kiosk")

    def set_param(self, key, val):
        self.env["ir.config_parameter"].sudo().set_param(key if key.startswith("td.") else f"td.viewer.{key}", val)

    def demo_clock(self, value="2026-10-12 10:30"):
        self.set_param("demo_clock", value)

    def payload(self, user, **kw):
        from odoo.addons.td_viewer3d.tools.payload import PayloadBuilder

        return PayloadBuilder(self.env(user=user), **kw).build()

    def events_since(self, ts):
        return self.env["td.viewer.event"].sudo().search([("create_date", ">=", ts)])

    def bus_messages(self):
        """Повертає список, який наповнює патч bus.bus._sendone (знімається в cleanup)."""
        sent = []
        patcher = patch.object(
            type(self.env["bus.bus"]),
            "_sendone",
            lambda s, target, notification_type, message: sent.append((target, notification_type, message)),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return sent


def _has_demo_data(env):
    """Тестова перевірка: є самі демо-дані (MO WH/MO/00231 і локація PLT-04C), а не лише iot_sim."""
    if not is_demo_db(env):
        return False
    return bool(
        env["mrp.production"].sudo().search_count([("name", "=", "WH/MO/00231")])
        and env["stock.location"].sudo().search_count([("td_code", "=", "PLT-04C")])
    )


class F3dViewerCase(F3dViewerBase):
    """Потребує демо-бази (td_iot_sim / компанія демо); інакше skipTest (§13.0)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_demo = _has_demo_data(cls.env)
        if not cls.has_demo:
            cls.skipTest(cls, "немає демо-даних (td_iot_sim)")

    def setUp(self):
        super().setUp()
        self.demo_clock("2026-10-12 10:30")
