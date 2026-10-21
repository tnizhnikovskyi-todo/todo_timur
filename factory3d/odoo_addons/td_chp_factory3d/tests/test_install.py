"""AC-B01: установка моста — вузли, групи, меню, корінь меню, види команд моста."""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .. import hooks
from .common import TAGS, BridgeCase

BRIDGE_KINDS = {
    "chp_estop": "A",
    "chp_reset": "A",
    "chp_set_mode": "A",
    "chp_set_setpoint": "A",
    "chp_set_cos": "A",
    "chp_set_heat_dir": "A",
    "chp_set_bypass": "A",
}


@tagged(*TAGS)
class TestInstall(BridgeCase):
    def test_unit_nodes(self):
        self.assertEqual(self.unit.energy_node_id.code, "CHP")
        self.assertEqual(self.unit.energy_qf_node_id.code, "QF-CHP")
        self.assertEqual(self.unit.energy_node_id.kind, "generator")
        self.assertEqual(self.unit.energy_qf_node_id.kind, "cell")
        self.assertTrue(self.unit.energy_node_state)
        self.assertEqual(self.unit.energy_p_kw, self.unit.energy_node_id.p_now)

    def test_node_kind_is_checked(self):
        qf = self.env["td.energy.node"].search([("code", "=", "QF-CHP")], limit=1)
        chp = self.env["td.energy.node"].search([("code", "=", "CHP")], limit=1)
        with self.assertRaises(ValidationError):
            self.unit.write({"energy_node_id": qf.id})
        with self.assertRaises(ValidationError):
            self.unit.write({"energy_qf_node_id": chp.id})

    def test_open_energy_node(self):
        act = self.unit.action_open_energy_node()
        self.assertEqual((act["tag"], act["params"]), ("td_energy.node_card", {"code": "CHP"}))

    def test_groups_imply_chp_groups(self):
        def implies(parent, child):
            return self.env.ref(child) in self.env.ref(parent).all_implied_ids

        self.assertTrue(implies("td_energy.group_td_energy_user", "td_chp.group_td_chp_user"))
        self.assertTrue(implies("td_energy.group_td_energy_manager", "td_chp.group_td_chp_operator"))
        self.assertTrue(implies("td_energy.group_td_energy_chief", "td_chp.group_td_chp_chief"))
        self.assertFalse(implies("td_energy.group_td_energy_manager", "td_chp.group_td_chp_chief"))
        self.assertTrue(self.u_en1.has_group("td_chp.group_td_chp_operator"))
        self.assertTrue(self.e_chief.has_group("td_chp.group_td_chp_chief"))
        self.assertTrue(self.u_view.has_group("td_chp.group_td_chp_user"))
        self.assertFalse(self.u_view.has_group("td_chp.group_td_chp_operator"))

    def test_menus_under_generation_and_root_hidden(self):
        section = self.env.ref("td_energy.menu_td_energy_generation")
        expect = {
            "menu_chp_pult": ("Пульт КГУ", 25),
            "menu_chp_event": ("Події КГУ", 26),
            "menu_chp_rule": ("ТО КГУ", 27),
            "menu_chp_unit": ("Паспорт КГУ", 28),
        }
        for xmlid, (name, seq) in expect.items():
            menu = self.env.ref("td_chp_factory3d." + xmlid)
            self.assertEqual((menu.parent_id, menu.name, menu.sequence), (section, name, seq), xmlid)
        self.assertEqual(
            self.env.ref("td_chp_factory3d.menu_chp_pult").action, self.env.ref("td_chp.action_td_chp_pult")
        )
        self.assertFalse(self.env.ref("td_chp.menu_td_chp_root").active)

    def test_uninstall_hook_returns_root_menu_source_and_groups(self):
        hooks.uninstall_hook(self.env)
        self.assertTrue(self.env.ref("td_chp.menu_td_chp_root").active)
        self.assertEqual(self.unit.source_id.code, "CHP-U72")
        self.assertNotIn(
            self.env.ref("td_chp.group_td_chp_operator"), self.env.ref("td_energy.group_td_energy_manager").implied_ids
        )
        for code in ("chp_start", "chp_stop"):  # без мосту види td_energy_control знову ідуть інтентом збирача
            self.assertEqual(self.env["td.energy.command.kind"].search([("code", "=", code)]).executor, "intent")
        hooks.post_init(self.env)  # повторне встановлення відновлює злиття
        self.assertEqual(self.unit.source_id.code, "MB-U72-CHP")

    def test_bridge_kinds_registered(self):
        Kind = self.env["td.energy.command.kind"]
        for code, cls in BRIDGE_KINDS.items():
            kind = Kind.search([("code", "=", code)])
            self.assertEqual((kind.cls, kind.executor, kind.resource, kind.tile), (cls, "chp", "chp", False), code)
            self.assertFalse(kind.remote_gated, code)
            self.assertFalse(kind.checks, code)
        for code in ("chp_start", "chp_stop"):  # клас B лишається, виконавець — `chp` (запис у chp/ctl/cmd, не інтент)
            kind = Kind.search([("code", "=", code)])
            self.assertEqual((kind.cls, kind.executor, kind.resource), ("B", "chp", "chp"), code)
        self.assertTrue(Kind.search([("code", "=", "chp_start")]).checks)  # перевірки td_energy_control збережено
        self.assertTrue(Kind.search([("code", "=", "chp_start")]).remote_gated)
        self.assertIn("chp", dict(Kind._fields["executor"].selection))
        self.assertEqual(Kind.search([("code", "=", "chp_set_cos")]).params_schema[0]["name"], "cos")
