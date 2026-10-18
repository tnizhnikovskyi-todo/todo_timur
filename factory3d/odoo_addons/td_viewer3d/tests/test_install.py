from odoo.exceptions import AccessDenied
from odoo.tests import tagged

from odoo.addons.td_viewer3d.hooks import is_demo_db, uninstall

from .common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestInstall(F3dViewerBase):

    def _param(self, key):
        return self.env["ir.config_parameter"].sudo().get_param("td.viewer." + key)

    def _menu(self, xmlid):
        return self.env.ref("td_viewer3d." + xmlid, raise_if_not_found=False)

    def _visible(self, user):
        return set(self.env["ir.ui.menu"].with_user(user)._visible_menu_ids())

    def test_params_defaults(self):
        expected = {"snapshot_minutes": "10", "snapshot_hours": "06:30-16:00", "snapshot_keep_days": "14",
                    "event_keep_hours": "48", "delta_debounce_ms": "1500", "kiosk_enabled": "True",
                    "kiosk_refresh_s": "15", "bus_enabled": "True", "lite_default": "auto"}
        for key, val in expected.items():
            self.assertEqual(self._param(key), val, key)
        self.assertRegex(self._param("kiosk_token") or "", r"^[0-9a-f]{32}$")
        self.assertIn(self._param("demo_enabled"), ("True", "False"))

    def test_params_on_demo_db(self):  # AC-53 (частина без знімка/крону)
        if not is_demo_db(self.env):
            self.skipTest("немає демо-даних")
        self.assertEqual(self._param("demo_enabled"), "True")
        self.assertEqual(self._param("demo_clock"), "2026-10-12 10:30")

    def test_kiosk_user_cannot_login(self):  # AC-39
        user = self.user_kiosk
        self.assertFalse(user.share)
        self.assertTrue(user.has_group("td_viewer3d.group_td_kiosk"))
        self.assertEqual(user.login, "f3d_kiosk")
        self.assertEqual(user.action_id.id, self.env.ref("td_viewer3d.action_td_viewer").id)
        with self.assertRaises(AccessDenied):
            user.sudo()._check_credentials({"type": "password", "password": "anything"},
                                           {"interactive": True})

    def test_menus_by_group(self):  # AC-54
        nobody, f3d = self._visible(self.user_nobody), self._visible(self.user_f3d)
        manager, admin = self._visible(self.user_manager), self._visible(self.user_admin)
        viewer, journal = self._menu("menu_td_viewer"), self._menu("menu_td_journal")
        self.assertIn(viewer.id, f3d)
        self.assertNotIn(viewer.id, nobody)
        # контейнер без дітей _visible_menu_ids відсікає, тож перевіряємо групи меню
        self.assertEqual(journal.group_ids, self.env.ref("td_factory3d.group_td_manager"))
        self.assertNotIn(journal.id, f3d)
        # пункти, що додаються разом із діями інших воркерів, — лише якщо вже є
        cycle = self._menu("menu_td_cycle_check")
        if cycle:
            self.assertNotIn(cycle.id, f3d)
            self.assertIn(cycle.id, manager)
        for xmlid in ("menu_td_demo", "menu_td_settings"):
            menu = self._menu(xmlid)
            if menu:
                self.assertNotIn(menu.id, manager)
                self.assertIn(menu.id, admin)

    def test_menu_sequences(self):  # AC-64
        root = self.env.ref("td_factory3d.menu_td_root")
        expected = {"menu_td_viewer": 10, "menu_td_journal": 12, "menu_td_cycle_check": 14,
                    "menu_td_demo": 16}
        for xmlid, seq in expected.items():
            menu = self._menu(xmlid)
            if not menu:
                continue  # додається разом з дією іншого воркера
            self.assertEqual(menu.parent_id, root, xmlid)
            self.assertEqual(menu.sequence, seq, xmlid)
        for menu in root.child_id:
            if menu.get_external_id().get(menu.id, "").startswith("td_viewer3d."):
                self.assertTrue(10 <= menu.sequence <= 19, menu.name)
        settings = self._menu("menu_td_settings")
        if settings:
            self.assertEqual(settings.parent_id, self.env.ref("td_factory3d.menu_td_config"))
            self.assertEqual(settings.sequence, 10)
        self.assertEqual(len(root.child_id.filtered(lambda m: m.name == "Налаштування")), 1)

    def test_kiosk_privilege(self):  # AC-67
        group = self.env.ref("td_viewer3d.group_td_kiosk")
        privilege = self.env.ref("td_viewer3d.privilege_td_viewer")
        self.assertEqual(group.privilege_id, privilege)
        self.assertEqual(privilege.category_id, self.env.ref("td_factory3d.module_category_factory3d"))
        self.assertEqual(privilege.sequence, 10)
        self.assertNotEqual(group.privilege_id, self.env.ref("td_factory3d.privilege_td"))
        implied = {self.env.ref(x) for x in ("base.group_user", "td_factory3d.group_td_user",
                                              "stock.group_stock_user", "mrp.group_mrp_user")}
        self.assertEqual(set(group.implied_ids), implied)

    def test_uninstall_archives_kiosk_user(self):  # ARCHITECTURE §2.8
        user = self.env.ref("td_viewer3d.user_kiosk")
        uninstall(self.env)
        data = self.env["ir.model.data"].sudo().search(
            [("module", "=", "td_viewer3d"), ("name", "=", "user_kiosk")])
        self.assertFalse(data, "xmlid user_kiosk має бути видалений, щоб користувач пережив деінсталяцію")
        self.assertTrue(user.exists())
        self.assertFalse(user.active)
        self.assertFalse(self._param("kiosk_token"))
