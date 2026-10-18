"""W1-C: розділ «Генерація й резерв», меню мосту і групи (V-10, V-11, M-11, R-14, R-16), AC-74…AC-77 (W1_SPEC B.12)."""

from odoo.tests import TransactionCase, new_test_user, tagged

SECTION = "td_energy.menu_td_energy_generation"
USER, TECH = "td_genset.group_user", "td_genset.group_tech"
TD_USER, TD_MANAGER = "td_factory3d.group_td_user", "td_factory3d.group_td_manager"
BRIDGE = "td_genset_factory3d."


def _row(parent, seq, action, group):
    return (parent, seq, action, group)


def _gf(name):
    return BRIDGE + "menu_gf_" + name


# B.3.1: xml-id → (батько, sequence, дія, група); дії td_genset — з модульним префіксом
EXPECTED = {
    "genset": _row(SECTION, 20, "td_genset.action_td_genset_main", USER),
    "reading": _row(SECTION, 30, "td_genset.action_td_genset_reading", USER),
    "event": _row(SECTION, 40, "td_genset.action_td_genset_event", USER),
    "fuel": _row(SECTION, 50, None, USER),
    "fuel_canister": _row(_gf("fuel"), 10, "td_genset.action_td_genset_canister", USER),
    "fuel_refuel": _row(_gf("fuel"), 20, "td_genset.action_td_genset_refuel", USER),
    "fuel_move": _row(_gf("fuel"), 30, "td_genset.action_td_genset_fuel_move", USER),
    "analytics": _row(SECTION, 60, None, USER),
    "analytics_run_outage": _row(_gf("analytics"), 10, "td_genset.action_td_genset_analytics_run_outage", USER),
    "analytics_energy": _row(_gf("analytics"), 20, "td_genset.action_td_genset_analytics_energy", USER),
    "analytics_cranks": _row(_gf("analytics"), 30, "td_genset.action_td_genset_analytics_cranks", USER),
    "analytics_fuel_used": _row(_gf("analytics"), 40, "td_genset.action_td_genset_analytics_fuel_used", USER),
    "analytics_fuel_level": _row(_gf("analytics"), 50, "td_genset.action_td_genset_analytics_fuel_level", USER),
    "analytics_battery": _row(_gf("analytics"), 60, "td_genset.action_td_genset_analytics_battery", USER),
    "analytics_load": _row(_gf("analytics"), 70, "td_genset.action_td_genset_analytics_last_run", USER),
    "link": _row(SECTION, 70, BRIDGE + "action_td_genset_link", TD_USER),
    "requests": _row(SECTION, 80, BRIDGE + "action_td_genset_requests", TD_USER),
    "config": _row(SECTION, 90, None, "td_energy.group_td_energy_manager"),
    "config_profile": _row(_gf("config"), 10, BRIDGE + "action_td_genset_profile", TD_MANAGER),
    "config_event_map": _row(_gf("config"), 20, BRIDGE + "action_td_genset_event_map", TD_MANAGER),
    "config_td": _row(_gf("config"), 30, "td_genset.action_td_genset_config", USER),
    "config_gensets": _row(_gf("config"), 40, "td_genset.action_td_genset", USER),
    "config_levels": _row(_gf("config"), 50, "td_genset.action_td_genset_notify_level", USER),
    "config_locations": _row(_gf("config"), 60, "td_genset.action_td_genset_storage_location", USER),
    "config_controllers": _row(_gf("config"), 70, "td_genset.action_td_genset_controller_model", TECH),
}
TOP_LEVEL = ("genset", "reading", "event", "fuel", "analytics", "link", "requests", "config")


@tagged("post_install", "-at_install")
class TestW1Section(TransactionCase):
    def Menu(self):
        return self.env["ir.ui.menu"].with_context(active_test=False)

    def test_old_top_menu_removed(self):  # AC-74
        root = self.env.ref("td_factory3d.menu_td_root")
        self.assertFalse(self.Menu().search([("name", "=", "Генератор"), ("parent_id", "=", root.id)]))
        for old in ("menu_td_genset", "menu_td_genset_link", "menu_td_genset_profile", "menu_td_genset_requests"):
            self.assertFalse(self.env.ref(BRIDGE + old, raise_if_not_found=False), old)

    def test_section_children(self):  # AC-74
        section = self.env.ref(SECTION)
        children = self.Menu().search([("parent_id", "=", section.id)])
        host = {self.env.ref(_gf(name)).id for name in TOP_LEVEL}
        self.assertLessEqual(host, set(children.ids))

    def test_menus_25(self):  # AC-76
        ids = self.env["ir.model.data"].search(
            [("module", "=", "td_genset_factory3d"), ("model", "=", "ir.ui.menu"), ("name", "=like", "menu_gf_%")]
        )
        self.assertEqual(len(ids), 25)
        self.assertEqual(len(EXPECTED), 25)

    def test_menu_attributes(self):  # AC-76
        for name, (parent, seq, action, group) in EXPECTED.items():
            menu = self.env.ref(_gf(name))
            self.assertEqual(menu.parent_id, self.env.ref(parent), name)
            self.assertEqual(menu.sequence, seq, name)
            self.assertEqual(menu.group_ids, self.env.ref(group), name)
            if action:
                self.assertEqual(menu.action, self.env.ref(action), name)
            else:
                self.assertFalse(menu.action, name)
        for name in ("fuel", "analytics", "config"):  # розділи-контейнери з дітьми
            self.assertTrue(self.Menu().search([("parent_id", "=", self.env.ref(_gf(name)).id)]), name)

    def test_td_genset_menus_not_reparented(self):  # AC-76, A-19
        root = self.env.ref("td_genset.menu_root")
        for name, parent in (
            ("menu_genset", root),
            ("menu_reading", root),
            ("menu_event", root),
            ("menu_fuel", root),
            ("menu_config", root),
            ("menu_fuel_canister", self.env.ref("td_genset.menu_fuel")),
            ("menu_analytics_load", self.env.ref("td_genset.menu_analytics")),
            ("menu_config_gensets", self.env.ref("td_genset.menu_config")),
        ):
            self.assertEqual(self.env.ref("td_genset." + name).parent_id, parent, name)

    def test_td_genset_root_hidden(self):  # AC-75 (R-14 п.3, V-11)
        self.assertFalse(self.env.ref("td_genset.menu_root").active)

    def test_settings_menu_stays(self):  # B.3.1: «Налаштування генератора» (адмін) лишається в td_factory3d
        menu = self.env.ref(BRIDGE + "menu_td_genset_settings")
        self.assertEqual(menu.parent_id, self.env.ref("td_factory3d.menu_td_config"))

    def test_groups_and_visibility(self):  # AC-77 (M-11, R-16)
        user_a = new_test_user(self.env, login="w1c_mgr", groups="base.group_user,td_energy.group_td_energy_manager")
        user_b = new_test_user(self.env, login="w1c_view", groups="base.group_user,td_energy.group_td_energy_user")
        self.assertTrue(user_a.has_group(USER))
        self.assertFalse(user_b.has_group(USER))
        section, genset, link = (self.env.ref(x) for x in (SECTION, _gf("genset"), _gf("link")))
        visible_a = self.env["ir.ui.menu"].with_user(user_a)._visible_menu_ids()
        visible_b = self.env["ir.ui.menu"].with_user(user_b)._visible_menu_ids()
        self.assertIn(section.id, visible_b)  # розділ бачить (через «Зв'язку»/«Заявки» за group_td_user)
        self.assertIn(link.id, visible_b)
        self.assertNotIn(genset.id, visible_b)
        self.assertIn(genset.id, visible_a)
        self.assertIn(section.id, visible_a)
