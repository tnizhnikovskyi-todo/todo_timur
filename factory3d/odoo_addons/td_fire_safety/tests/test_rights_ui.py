"""AC-63…AC-65: меню й дії (§3), матриця прав (§4.1), налаштування (§5.1)."""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import FireCase

U, M = "td_factory3d.group_td_user", "td_factory3d.group_td_manager"
ROOT = "td_fire_safety.menu_td_fire_root"
SAFETY = "td_factory3d.menu_td_safety"  # «Будівля і безпека»: «Пожежна безпека» й «Евакуація» — її розділи
# (xml-id меню, батько, sequence, група, xml-id дії, модель)
MENUS = [
    ("menu_td_fire_overview", ROOT, 10, U, "action_td_fire_overview", "td.fire.panel"),
    ("menu_td_fire_zone", ROOT, 20, U, "action_td_fire_zone", "td.fire.zone"),
    ("menu_td_fire_device", ROOT, 30, U, "action_td_fire_device", "td.fire.device"),
    ("menu_td_fire_event", ROOT, 40, U, "action_td_fire_event", "td.fire.event"),
    ("menu_td_fire_system", ROOT, 50, U, "action_td_fire_system", "td.fire.system"),
    ("menu_td_fire_evac", SAFETY, 50, U, None, None),
    ("menu_td_fire_exit", "menu_td_fire_evac", 10, U, "action_td_fire_exit", "td.fire.exit"),
    ("menu_td_fire_route", "menu_td_fire_evac", 20, U, "action_td_fire_route", "td.fire.route"),
    ("menu_td_fire_smoke_zone", "menu_td_fire_evac", 30, U, "action_td_fire_smoke_zone", "td.fire.smoke.zone"),
    ("menu_td_fire_evac_report", "menu_td_fire_evac", 40, U, "action_td_fire_evac_report", None),
    ("menu_td_fire_drill", ROOT, 70, U, "action_td_fire_drill", "td.fire.drill"),
    ("menu_td_fire_norm", ROOT, 80, U, "action_td_fire_norm", "td.fire.norm"),
    ("menu_td_fire_template", ROOT, 90, M, "action_td_fire_drill_template", "td.fire.drill.template"),
    ("menu_td_fire_loop", ROOT, 95, M, "action_td_fire_loop", "td.fire.loop"),
]
SETTINGS = {
    "td_fire_read_enabled": True,
    "td_fire_comm_stale_after_s": 120,
    "td_fire_comm_lost_after_s": 240,
    "td_fire_dust_warn_pct": 70.0,
    "td_fire_dust_alarm_pct": 88.0,
    "td_fire_polymer_panels": True,
    "td_fire_cover_tol_m": 0.4,
    "td_fire_drill_time_limit_s": 280,
    "td_fire_drill_auto_create": False,
    "td_fire_drill_match_window_min": 20,
    "td_fire_drill_auto_stop_s": 100,
    "td_fire_drill_sim_duration_s": 200,
    "td_fire_viewer_devices": True,
    "td_fire_event_ack_required": False,
}


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestMenusRights(FireCase):
    def xid(self, name):
        return name if "." in name else "td_fire_safety." + name

    def test_menus(self):
        root = self.env.ref(ROOT)
        self.assertEqual((root.parent_id, root.sequence), (self.env.ref(SAFETY), 40))
        self.assertEqual(root.group_ids, self.env.ref(U))
        for name, parent, seq, group, action, model in MENUS:
            menu = self.env.ref(self.xid(name))
            self.assertEqual(menu.parent_id, self.env.ref(self.xid(parent)), name)
            self.assertEqual(menu.sequence, seq, name)
            self.assertEqual(menu.group_ids, self.env.ref(group), name)
            if action:
                act = self.env.ref(self.xid(action))
                self.assertEqual(menu.action, act, name)
                if model:
                    self.assertEqual(act.res_model, model, name)
            else:
                self.assertFalse(menu.action, name)
        self.assertEqual(self.env.ref("td_fire_safety.action_td_fire_evac_report")._name, "ir.actions.server")
        settings = self.env.ref("td_fire_safety.menu_td_fire_settings")
        self.assertEqual(
            (settings.parent_id, settings.sequence, settings.group_ids),
            (self.env.ref("td_factory3d.menu_td_config"), 85, self.env.ref(M)),
        )
        action = self.env.ref("td_fire_safety.action_td_fire_settings")
        self.assertEqual(
            (settings.action, action.res_model, action.target), (action, "res.config.settings", "current")
        )  # 'inline' у Odoo 19 немає
        # контейнер «Налаштування» прибрано (4-й рівень): «Шаблони навчань» і «Шлейфи» лежать у «Пожежна безпека»
        self.assertFalse(self.env.ref("td_fire_safety.menu_td_fire_config", raise_if_not_found=False))
        children = self.env["ir.ui.menu"].search([("parent_id", "=", root.id)]) | self.env["ir.ui.menu"].search(
            [("parent_id", "=", self.env.ref("td_fire_safety.menu_td_fire_evac").id)]
        )
        self.assertEqual(len(children), 13)

    def test_acl_matrix(self):
        drill_group = "td_fire_safety.group_td_fire_drill"
        self.assertTrue(self.m.has_group(drill_group))
        # U: читає зони, не пише; не створює навчання
        self.assertTrue(self.z_cut.with_user(self.u).read(["name"]))
        with self.assertRaises(AccessError):
            self.z_cut.with_user(self.u).write({"name": "X"})
        with self.assertRaises(AccessError):
            self.env["td.fire.drill"].with_user(self.u).create(
                {"title": "U", "zone_id": self.z_cut.id, "mode": "tabletop"}
            )
        # D: створює навчання й читає людей
        drill = self.new_drill(zone_id=self.z_cut.id, mode="tabletop")
        emp = self.make_employee("Тест Права", "R-001")
        person = (
            self.env["td.fire.drill.person"]
            .sudo()
            .create({"drill_id": drill.id, "employee_id": emp.id, "seq": 1, "source": "manual"})
        )
        self.assertEqual(person.with_user(self.d).seq, 1)
        self.assertEqual(len(drill.with_user(self.d).person_ids), 1)
        # H читає людей
        self.assertEqual(self.env["td.fire.drill.person"].with_user(self.hr).search_count([("id", "=", person.id)]), 1)
        # M пише норму, але не видаляє
        norm = self.env["td.fire.norm"].search([("key", "=", "mcp_spacing")])
        norm.with_user(self.m).write({"note": "M"})
        with self.assertRaises(AccessError):
            norm.with_user(self.m).unlink()
        # A — успіх
        spare = (
            self.env["td.fire.norm"].with_user(self.a).create({"key": "tmp_norm", "name": "Тимчасова", "ref": "тест"})
        )
        spare.unlink()
        # події не видаляються нікому
        event = self.env["td.fire.event"]._log("info", "FACP-1", self.T0, "тест", source="manual")
        for user in (self.u, self.d, self.m, self.a):
            with self.assertRaises(UserError):  # AccessError ⊂ UserError
                event.with_user(user).unlink()

    def test_settings(self):
        Settings = self.env["res.config.settings"]
        icp = self.env["ir.config_parameter"].sudo()
        self.assertFalse([n for n in Settings._fields if n.startswith("td_fire_") and "write" in n])
        vals = dict(SETTINGS, td_fire_alert_group_id=self.g_alert.id, td_fire_team_id=self.team.id)
        Settings.create(vals).execute()
        P = "td.fire_safety."
        self.assertEqual(icp.get_param(P + "comm_stale_after_s"), "120")
        self.assertEqual(float(icp.get_param(P + "dust_warn_pct")), 70.0)
        self.assertEqual(icp.get_param(P + "event_ack_required"), "False")
        self.assertEqual(icp.get_param(P + "drill_auto_create"), "False")
        self.assertEqual(icp.get_param(P + "alert_group_xmlid"), "test_fire.group_alert")
        self.assertEqual(icp.get_param(P + "team_id"), str(self.team.id))
        values = Settings.default_get(list(vals))
        for name, value in vals.items():
            self.assertEqual(values[name], value, name)
        dust = self.env["td.signal"].search([("code", "=", "fire/groups/FA-FAC/dust")])
        self.assertEqual((dust.warn_high, dust.alarm_high), (70.0, 88.0))
        with self.assertRaises(UserError):
            Settings.create(dict(vals, td_fire_dust_warn_pct=90.0, td_fire_dust_alarm_pct=80.0)).execute()
