from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_rules import GensetCase

VIEWS = (
    "view_td_genset_link_form",
    "view_td_genset_link_list",
    "view_td_genset_profile_form",
    "view_td_genset_profile_list",
    "view_td_genset_event_map_list",
    "view_td_genset_event_map_form",
    "view_maintenance_equipment_form_td_genset",
    "res_config_settings_view_form",
    "view_maintenance_request_form_td_genset",
)
ACTIONS = (
    "action_td_genset_link",
    "action_td_genset_profile",
    "action_td_genset_event_map",
    "action_td_genset_requests",
    "action_td_genset_settings",
)


@tagged("post_install", "-at_install")
class TestViews(GensetCase):
    def test_views_load(self):  # V-01…V-09
        for name in VIEWS:
            view = self.env.ref("td_genset_factory3d." + name)
            self.env[view.model].get_views([(view.id, view.type)])
        self.env["td.genset.link"].get_views([(False, "form"), (False, "list")])

    def test_menus(self):  # AC-33
        def menu(name):
            return self.env.ref("td_genset_factory3d." + name)

        root = self.env.ref("td_factory3d.menu_td_root")
        self.assertEqual(menu("menu_td_genset").parent_id, root)
        self.assertEqual(menu("menu_td_genset").sequence, 55)
        for name, seq, group in (
            ("link", 10, "user"),
            ("profile", 20, "manager"),
            ("event_map", 30, "manager"),
            ("requests", 40, "user"),
        ):
            m = menu("menu_td_genset_" + name)
            self.assertEqual((m.parent_id, m.sequence), (menu("menu_td_genset"), seq), name)
            self.assertEqual(m.group_ids, self.env.ref("td_factory3d.group_td_" + group), name)

    def test_settings_readonly(self):  # AC-58
        view = self.env.ref("td_genset_factory3d.res_config_settings_view_form")
        self.assertRegex(view.arch_db, r'td_genset_write_enabled"\s+readonly="1"')

    def test_actions_view_mode(self):
        for name in ACTIONS:
            action = self.env.ref("td_genset_factory3d." + name)
            self.assertNotIn("tree", action.view_mode.split(","), name)

    def test_settings_menu_and_ats_values(self):  # AC-73, X-69
        m = self.env.ref("td_genset_factory3d.menu_td_genset_settings")
        self.assertEqual(m.parent_id, self.env.ref("td_factory3d.menu_td_config"))
        self.assertEqual(m.sequence, 55)
        Settings = self.env["res.config.settings"]
        Settings.create({"td_genset_ats_position_i_value": 1, "td_genset_ats_position_ii_value": 4}).set_values()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("td.genset.ats_position_i_value"), "1")
        self.assertEqual(icp.get_param("td.genset.ats_position_ii_value"), "4")
        self.assertIs(self.link._island_state_from_signals({}, pos=4)["island"], True)
        with self.assertRaises(ValidationError):
            Settings.create({"td_genset_ats_position_i_value": 3, "td_genset_ats_position_ii_value": 3}).set_values()
