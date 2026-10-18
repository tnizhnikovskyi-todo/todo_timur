"""W2-D: AC-291 — «Відкрити в 3D» (`action_td_open_3d`, R-58); V-46 (налаштування), V-47 (серверна дія й меню)."""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from ..tools import layer as layer_tools
from .common import TAGS, LayerCase


@tagged(*TAGS)
class TestDeepLink(LayerCase):
    def open3d(self, code=None, user=None):
        env = self.env(user=(user or self.u_view).id)
        return env["td.energy.node"].action_td_open_3d(code)

    def test_open_node(self):  # AC-291
        action = self.open3d("BW-2")
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "f3d_viewer.action")
        self.assertEqual(action["target"], "current")
        self.assertEqual(
            action["params"],
            {
                "layers": layer_tools.DEFAULT_LAYERS,
                "mode": "td_energy",
                "tab": "energy",
                "code": "BW-2",
                "td_energy_node": "BW-2",
            },
        )
        self.env["ir.config_parameter"].sudo().set_param("td.energy_viewer3d.layers", '["energy"]')
        self.assertEqual(self.open3d("BW-2")["params"]["layers"], ["energy"])
        self.assertEqual(self.open3d("C2")["params"]["code"], "CABLES")

    def test_open_without_code(self):  # AC-291: без вузла — лише шар
        params = self.open3d()["params"]
        self.assertIsNone(params["code"])
        self.assertIsNone(params["td_energy_node"])
        self.assertEqual((params["mode"], params["tab"]), ("td_energy", "energy"))

    def test_node_without_scene_and_unknown(self):  # AC-291
        node = self.Node.search([("code", "=", "BW-4")])
        node.equipment_id = self.env["maintenance.equipment"].create({"name": "Без 3D", "td_code": "ZZ-NOT-IN-SCENE"})
        params = self.open3d("BW-4")["params"]
        self.assertIsNone(params["code"])  # вузол без об'єкта в 3D: code=null, клієнт покаже застереження
        self.assertEqual(params["td_energy_node"], "BW-4")
        with self.assertRaisesRegex(UserError, "Вузол NOPE-1 не знайдено"):
            self.open3d("NOPE-1")

    def test_access(self):
        with self.assertRaises(AccessError):
            self.open3d("BW-2", user=self.u_plain)

    def test_server_action_and_menu(self):  # V-47
        action = self.env.ref("td_energy_viewer3d.action_td_energy_3d")
        self.assertEqual(action.state, "code")
        menu = self.env.ref("td_energy_viewer3d.menu_td_energy_3d")
        self.assertEqual(menu.parent_id, self.env.ref("td_energy.menu_td_energy"))
        self.assertEqual(menu.sequence, 90)
        self.assertIn(self.env.ref("td_energy.group_td_energy_user"), action.group_ids)
        self.assertIn(self.env.ref("td_energy.group_td_energy_user"), menu.group_ids)
        result = action.with_user(self.u_view).run()
        self.assertEqual(result["tag"], "f3d_viewer.action")
        self.assertEqual(result["params"]["mode"], "td_energy")

    def test_settings_form(self):  # V-46, M-42
        Settings = self.env["res.config.settings"]
        vals = Settings.default_get(
            ["td_energy_viewer3d_layers", "td_energy_viewer3d_marker_limit", "td_energy_viewer3d_show_markers"]
        )
        self.assertEqual(vals["td_energy_viewer3d_marker_limit"], 40)
        self.assertTrue(vals["td_energy_viewer3d_show_markers"])
        view = Settings.get_view(self.env.ref("td_energy_viewer3d.res_config_settings_view_form_td_energy_viewer3d").id)
        for name in ("td_energy_viewer3d_layers", "td_energy_viewer3d_marker_limit", "td_energy_viewer3d_show_markers"):
            self.assertIn(name, view["arch"])
        icp = self.env["ir.config_parameter"].sudo()
        rec = Settings.create(
            {
                "td_energy_viewer3d_layers": '["energy", "backup"]',
                "td_energy_viewer3d_marker_limit": 12,
                "td_energy_viewer3d_show_markers": False,
            }
        )
        rec.execute()
        self.assertEqual(icp.get_param("td.energy_viewer3d.layers"), '["energy", "backup"]')
        self.assertEqual(icp.get_param("td.energy_viewer3d.marker_limit"), "12")
        self.assertEqual(icp.get_param("td.energy_viewer3d.show_markers"), "False")
        self.assertEqual(
            layer_tools.params(self.env), {"layers": ["energy", "backup"], "marker_limit": 12, "show_markers": False}
        )
        self.assertFalse(Settings.create({}).td_energy_viewer3d_show_markers)  # False не повертається до типового True
        with self.assertRaises(Exception):  # noqa: B017 — ValidationError у create
            Settings.create({"td_energy_viewer3d_layers": "не json"})
        with self.assertRaises(Exception):  # noqa: B017
            Settings.create({"td_energy_viewer3d_marker_limit": 0})
