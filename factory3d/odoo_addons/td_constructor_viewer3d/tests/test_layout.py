"""Провайдер `layout`: payload за версією з переміщеним, новим, прибраним і заміненим; права; шина; GLB кіоска."""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.factory3d_constructor.services import snapshot
from odoo.addons.factory3d_constructor.tests.common import make_glb
from odoo.addons.factory3d_viewer.controllers import kiosk as kiosk_ctrl
from odoo.addons.factory3d_viewer.tools.payload import DeltaBuilder, PayloadBuilder, get_providers

from ..tools import layout as layout_tools


class LayoutBase(TransactionCase):
    """Площадка seed `main_demo` з базовою версією v1 (імпорт із макета) — те, що запечено в GLB «Переглядача»."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.site = env["f3d.site"].search([("seed_key", "=", "main_demo")])
        assert cls.site and cls.site.active_version_id.is_seed, "seed-площадка main_demo не завантажена"
        cls.base = cls.site.active_version_id
        cls.Placement = env["f3d.placement"]
        cls.Slot = env["f3d.slot"]
        cls.prod_layer = cls.site.layer_ids.filtered(lambda layer: layer.kind == "production")[:1]
        cls.generic = env["f3d.equipment.variant"].search([("passport_id.role", "=", "generic_machine")], limit=1)
        cls.user_f3d = env["res.users"].with_context(no_reset_password=True).create(
            {"name": "f3d_lv", "login": "f3d_lv", "group_ids": [(6, 0, [
                env.ref("base.group_user").id, env.ref("factory3d_base.group_f3d_user").id])]})
        cls.user_nobody = env["res.users"].with_context(no_reset_password=True).create(
            {"name": "f3d_nolv", "login": "f3d_nolv", "group_ids": [(6, 0, [env.ref("base.group_user").id])]})

    def placement(self, code):
        rec = self.Placement.search([("site_id", "=", self.site.id), ("code", "=", code)])
        self.assertTrue(rec, code)
        return rec

    def slot(self, prefix):
        rec = self.Slot.search([("site_id", "=", self.site.id), ("code_prefix", "=", prefix)])
        self.assertTrue(rec, prefix)
        return rec

    def publish(self, note="тест"):
        """Нова діюча версія зі знімка чернетки (те, що робить публікація після застосування плану)."""
        return snapshot.create_version(self.site, note=note, report={})

    def layout(self, env=None):
        return layout_tools.build_layout(env or self.env)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor_viewer")
class TestLayoutPayload(LayoutBase):

    def test_provider_registered(self):
        provider = {p._name: p for p in get_providers(self.env)}["f3d.viewer.provider.layout"]
        self.assertEqual((provider._f3d_sequence, provider._f3d_sections), (180, ("layout",)))
        self.assertEqual(provider._f3d_group, "factory3d_base.group_f3d_user")
        self.assertEqual(provider._f3d_viewer_bus_models(), ["f3d.layout.version", "f3d.site"])

    def test_no_published_version_no_key(self):
        """Лише база (v1 seed) — ключа немає; площадка без версій — теж."""
        self.assertIsNone(self.layout())
        data = PayloadBuilder(self.env(user=self.user_f3d), sections=["layout"]).build()
        self.assertNotIn("layout", data)
        blank = self.env["f3d.site"].with_context(f3d_blank=True).create({"name": "Порожня", "code": "BLK"})
        self.assertFalse(blank.active_version_id)
        self.assertIsNone(self.layout())

    def test_moved_added_hidden_replaced(self):
        """CNC-2 на 3 м, новий верстат із каталогу, FG-R5 на 5 ярусів, PACK-2 прибрано."""
        self.placement("CNC-2").x_m += 3.0
        self.Placement.create({
            "layer_id": self.prod_layer.id, "variant_id": self.generic.id, "code": "NEWM-1", "name": "Новий верстат",
            "x_m": 100.0, "y_m": 40.0, "rotation": 90})
        fg5 = self.slot("FG-R5")
        fg5.params = dict(fg5.params, levels=5)
        self.placement("PACK-2").unlink()
        version = self.publish()
        lay = self.layout()
        json.dumps(lay)
        self.assertEqual(lay["version"]["n"], version.n)
        self.assertEqual(lay["base_version"]["n"], 1)
        self.assertEqual(lay["site"]["code"], self.site.code)
        self.assertEqual(lay["moved"]["CNC-2"], {"dx": 3.0, "dy": 0.0, "drot": 0.0, "delev": 0.0})
        self.assertNotIn("CNC-1", lay["moved"])
        added = {e["code"]: e for e in lay["added"]}
        self.assertEqual(set(added), {"NEWM-1", "FG-R5"})
        new = added["NEWM-1"]
        self.assertEqual((new["kind"], new["category"], new["rot"], new["elev"]), ("placement", "machine", 90.0, 0.0))
        self.assertEqual((new["x"], new["y"]), (100.0, 40.0))
        self.assertEqual(new["dims"], {"L": 3.0, "W": 1.5, "H": 1.8})
        self.assertIsNone(new["model_url"])
        rack = added["FG-R5"]
        self.assertEqual((rack["kind"], rack["template"], rack["rot"]), ("slot", "pallet_rack", 90.0))
        self.assertEqual(len(rack["cells"]), 90)
        self.assertEqual({c["code"] for c in rack["cells"]} & {"FG-R5-B01-L5", "FG-R5-B18-L5"},
                         {"FG-R5-B01-L5", "FG-R5-B18-L5"})
        cell = next(c for c in rack["cells"] if c["code"] == "FG-R5-B01-L3")
        self.assertEqual(
            (cell["lz"], cell["h"], cell["w"], cell["d"], cell["kind"]), (3.8, 1.9, 2.7, 1.1, "pallet_cell"))
        self.assertEqual(lay["replaced"], ["FG-R5"])
        self.assertEqual(lay["frames"]["FG-R5"]["x"], 134.2)
        self.assertEqual(lay["frames"]["FG-R5"]["y"], 27.3)
        old_cells = {"FG-R5-B%02d-L%d" % (b, lv) for b in range(1, 19) for lv in range(1, 5)}
        self.assertTrue(old_cells <= set(lay["hidden"]))
        self.assertIn("PACK-2", lay["hidden"])
        self.assertNotIn("FG-R4-B01-L1", lay["hidden"])

    def test_rotation_and_anchor(self):
        """Поворот: drot у (−180, 180]; зсув центра враховує прив'язку варіанта."""
        saw = self.placement("SAW-1")
        saw.rotation = 270.0
        self.publish()
        move = self.layout()["moved"]["SAW-1"]
        self.assertEqual(move["drot"], -90.0)
        variant = saw.variant_id._f3d_local_geometry()
        if (variant.get("anchor") or "center") == "center":
            self.assertEqual((move["dx"], move["dy"]), (0.0, 0.0))

    def test_slot_moved_all_cells(self):
        """Зсув місця зсуває каркас (за префіксом) і всі комірки; параметри ті самі — це не заміна."""
        fg1 = self.slot("FG-R1")
        fg1.x_m += 2.0
        self.publish()
        lay = self.layout()
        self.assertEqual(lay["moved"]["FG-R1"]["dx"], 2.0)
        cells = [code for code in lay["moved"] if code.startswith("FG-R1-B")]
        self.assertEqual(len(cells), 72)
        self.assertEqual({lay["moved"][c]["dx"] for c in cells}, {2.0})
        self.assertEqual((lay["replaced"], lay["added"], lay["hidden"]), ([], [], []))
        self.assertIn("FG-R1", lay["frames"])

    def test_slot_rotated_cells_follow(self):
        """Поворот місця на 90°: клітинка рухається по дузі (її dx, dy — зсув центра), drot = 90."""
        fg1 = self.slot("FG-R1")
        fg1.rotation = 180
        self.publish()
        lay = self.layout()
        first = lay["moved"]["FG-R1-B01-L1"]
        self.assertEqual(first["drot"], 90.0)
        self.assertNotEqual((first["dx"], first["dy"]), (0.0, 0.0))

    def test_slot_removed_hides_frame_and_cells(self):
        self.slot("FUR-R6").unlink()
        self.publish()
        lay = self.layout()
        self.assertIn("FUR-R6", lay["hidden"])
        self.assertTrue({"FUR-R6-S01-L1", "FUR-R6-S06-L4"} <= set(lay["hidden"]))
        self.assertEqual(lay["frames"]["FUR-R6"]["x"], 21.5)

    def test_cell_disabled_is_replacement(self):
        """Вимкнена комірка змінює параметри шаблону: місце замінено, старі комірки сховано."""
        fg2 = self.slot("FG-R2")
        fg2.overrides = {"FG-R2-B01-L1": {"disabled": True}}
        self.publish()
        lay = self.layout()
        self.assertEqual(lay["replaced"], ["FG-R2"])
        added = {e["code"]: e for e in lay["added"]}["FG-R2"]
        self.assertNotIn("FG-R2-B01-L1", {c["code"] for c in added["cells"]})
        self.assertEqual(len(added["cells"]), 71)

    def test_variant_change_is_replacement(self):
        saw = self.placement("SAW-1")
        saw.variant_id = self.generic
        self.publish()
        lay = self.layout()
        self.assertEqual(lay["replaced"], ["SAW-1"])
        entry = {e["code"]: e for e in lay["added"]}["SAW-1"]
        self.assertEqual((entry["variant_id"], entry["kind"]), (self.generic.id, "placement"))

    def test_model_url_for_variant_with_glb(self):
        self.generic._f3d_set_model(glb=("m.glb", make_glb()), status="ok")
        self.Placement.create({
            "layer_id": self.prod_layer.id, "variant_id": self.generic.id, "code": "NEWM-2", "name": "З моделлю",
            "x_m": 100.0, "y_m": 30.0})
        self.publish()
        entry = {e["code"]: e for e in self.layout()["added"]}["NEWM-2"]
        self.assertEqual(entry["model_url"], "/f3d/constructor/model/%d/glb" % self.generic.id)

    def test_rights(self):
        self.placement("CNC-2").x_m += 1.0
        self.publish()
        # без групи f3d_user розділ закритий збирачем
        denied = PayloadBuilder(self.env(user=self.user_nobody), sections=["layout"]).build()
        self.assertNotIn("layout", denied)
        self.assertEqual(denied["meta"]["sections"]["layout"], "denied")
        # читач без прав змін бачить розкладку
        data = PayloadBuilder(self.env(user=self.user_f3d), sections=["layout"]).build()
        self.assertEqual(data["meta"]["sections"]["layout"], "live")
        self.assertIn("CNC-2", data["layout"]["moved"])
        # кіоск: той самий payload
        kiosk = PayloadBuilder(self.env(user=self.env.ref("factory3d_viewer.user_kiosk")), kiosk=True,
                               sections=["layout"]).build()
        self.assertEqual(kiosk["layout"], data["layout"])

    def test_kiosk_silent_without_read_access(self):
        """Немає права читати версії: ключа немає, без помилок і без «denied»."""
        self.placement("CNC-2").x_m += 1.0
        self.publish()
        user = self.env.ref("factory3d_viewer.user_kiosk")
        model = type(self.env["f3d.layout.version"])
        with patch.object(model, "has_access", return_value=False):
            data = PayloadBuilder(self.env(user=user), kiosk=True, sections=["layout"]).build()
        self.assertNotIn("layout", data)
        self.assertEqual(data["meta"]["errors"], [])
        self.assertNotEqual(data["meta"]["sections"].get("layout"), "error")

    def test_bus_event_and_delta(self):
        self.env.cr.precommit.data.pop("f3d_viewer.notify", None)
        Event = self.env["f3d.viewer.event"].sudo()
        before = Event.search([("model", "=", "f3d.layout.version")]).ids
        since = fields.Datetime.now() - timedelta(seconds=1)
        self.placement("CNC-2").x_m += 3.0
        self.publish()
        self.env.flush_all()
        self.env.cr.precommit.run()
        events = Event.search([("model", "=", "f3d.layout.version"), ("id", "not in", before)])
        self.assertEqual([(e.kind, e.codes) for e in events], [("state", [self.site.code])])
        user = self.env(user=self.user_f3d)
        delta = DeltaBuilder(user, since=since, changes={"f3d.layout.version": {self.site.code}}).build()
        self.assertEqual(delta["patch"]["layout"]["moved"]["CNC-2"]["dx"], 3.0)
        other = DeltaBuilder(user, since=since, changes={"stock.quant": {"LOC-1"}}).build()
        self.assertNotIn("layout", other["patch"])

    def test_delta_after_version_removed_clears_layout(self):
        """Версію видалено (адмін): дельта несе `layout = null`, клієнт скидає розкладку до бази."""
        since = fields.Datetime.now() - timedelta(seconds=1)
        delta = DeltaBuilder(self.env(user=self.user_f3d), since=since,
                             changes={"f3d.layout.version": {self.site.code}}).build()
        self.assertIn("layout", delta["patch"])
        self.assertIsNone(delta["patch"]["layout"])


@tagged("post_install", "-at_install", "f3d", "f3d_constructor_viewer")
class TestLayoutPublishedEndToEnd(LayoutBase):
    """Повний шлях: чернетка → майстер публікації → версія → payload."""

    def test_publish_wizard_then_payload(self):
        self.env["ir.config_parameter"].sudo().set_param("factory3d.constructor.publish_enabled", "True")
        self.placement("CNC-2").x_m += 3.0
        manager = self.env.ref("base.user_admin")
        action = self.site.with_user(manager).action_publish_wizard()
        wizard = self.env["f3d.publish.wizard"].with_user(manager).browse(action["res_id"])
        if not wizard.can_publish:
            self.skipTest("seed-розкладка блокує публікацію: %s" % wizard.issue_ids.mapped("message")[:2])
        wizard.action_confirm()
        self.assertEqual(self.site.active_version_id.n, 2)
        self.assertEqual(self.layout()["moved"]["CNC-2"]["dx"], 3.0)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor_viewer")
class TestKioskModel(HttpCase, LayoutBase):
    """GLB варіанта для кіоска за токеном (без сесії)."""

    def setUp(self):
        super().setUp()
        kiosk_ctrl.reset_rate_limit()
        self.addCleanup(kiosk_ctrl.reset_rate_limit)
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("factory3d.viewer.kiosk_enabled", "True")
        self.kiosk_url = "/f3d/kiosk/" + params.get_param("factory3d.viewer.kiosk_token")
        self.generic._f3d_set_model(glb=("m.glb", make_glb()), status="ok")
        self.env.flush_all()
        self.env.cr.commit = lambda: None  # HttpCase: дані тесту видно серверу через спільний курсор

    def test_serves_glb_by_token(self):
        res = self.url_open("%s/layout/model/%d" % (self.kiosk_url, self.generic.id), allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["Content-Type"], "model/gltf-binary")
        self.assertTrue(res.content.startswith(b"glTF"))

    def test_bad_token_and_no_model(self):
        res = self.url_open("/f3d/kiosk/%s/layout/model/%d" % ("0" * 32, self.generic.id), allow_redirects=False)
        self.assertEqual(res.status_code, 404)
        other = self.env["f3d.equipment.variant"].search([("model_glb_id", "=", False)], limit=1)
        res = self.url_open("%s/layout/model/%d" % (self.kiosk_url, other.id), allow_redirects=False)
        self.assertEqual(res.status_code, 404)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor_viewer")
class TestLayoutInventory(LayoutBase):
    """База розміщення — з опису сцени `scene_inventory.json` (код → {x, y, z, L, W, H, yaw}), коли він є."""

    def test_inventory_pose_is_baseline(self):
        cnc2 = self.placement("CNC-2")
        self.publish()  # діюча версія відрізняється від бази лише номером: зсувів немає
        self.assertEqual(self.layout()["moved"], {})
        inventory = {"CNC-2": {"x": cnc2.x_m - 3.0, "y": cnc2.y_m, "z": 0.0, "L": 4.0, "W": 2.0, "H": 2.0, "yaw": 0}}
        with patch.object(layout_tools, "load_inventory", return_value=inventory):
            lay = self.layout()
        self.assertEqual(lay["moved"], {"CNC-2": {"dx": 3.0, "dy": 0.0, "drot": 0.0, "delev": 0.0}})

    def test_inventory_missing_file_is_empty(self):
        with patch.object(layout_tools, "file_open", side_effect=FileNotFoundError):
            self.assertEqual(layout_tools.load_inventory(), {})

    def test_inventory_agrees_with_seed(self):
        """Коли опис сцени вже є в модулі: версія без змін планування не дає ні зсувів, ні прибраного, ні доданого."""
        if not layout_tools.load_inventory():
            self.skipTest("data/scene_inventory.json ще немає (гілка опису сцени не злита)")
        self.publish()
        lay = self.layout()
        self.assertEqual((lay["moved"], lay["hidden"], lay["added"], lay["replaced"]), ({}, [], [], []))
