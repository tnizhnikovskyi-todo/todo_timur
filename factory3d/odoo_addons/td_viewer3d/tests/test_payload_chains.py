import copy
import json
import os

from odoo.tests import BaseCase, tagged

from odoo.addons.td_viewer3d.tools import chains, static_data
from odoo.addons.td_viewer3d.tools.cycle_check import check

from .common import F3dViewerBase, F3dViewerCase

DEMO_PAYLOAD = os.path.join(os.path.dirname(static_data.STATIC_PATH), "demo_payload.json")


def _fixture():
    """Еталонний payload макета без обчислюваних полів chains."""
    with open(DEMO_PAYLOAD, encoding="utf-8") as fh:
        ref = json.load(fh)
    data = copy.deepcopy(ref)
    for mo in data["productions"]:
        mo.pop("supply", None)
        mo.pop("delivery", None)
        for c in mo["components"]:
            for k in ("door", "receipt", "expected", "kind", "to", "path"):
                c.pop(k, None)
    for k in ("sheet_chain", "ship_chain", "material_paths", "full_cycle_mo"):
        data.pop(k, None)
    return ref, data


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestChainsPure(BaseCase):
    """Порт макета без бази: порівняння з еталоном `demo_payload.json`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ref, cls.data = _fixture()
        cls.top = chains.compute(cls.data)
        cls.mo = {m["name"]: m for m in cls.data["productions"]}

    def test_supply_mo231(self):
        """AC-44."""
        sup = self.mo["WH/MO/00231"]["supply"]
        codes = [s["code"] for s in sup["steps"]]
        self.assertEqual(codes[0], "GATE-W")
        self.assertIn("UNLOAD-1", codes)
        self.assertIn("QC-PLT-1", codes)
        self.assertTrue(any(c.startswith("RCK-") for c in codes))
        self.assertTrue(any(c.startswith("PLT-") for c in codes))
        self.assertEqual(sup, next(m for m in self.ref["productions"] if m["name"] == "WH/MO/00231")["supply"])

    def test_delivery_gate_e(self):
        mo = self.mo["WH/MO/00231"]
        self.assertEqual(mo["delivery"]["steps"][-1]["code"], "GATE-E")

    def test_fur_component_kit_tugger(self):
        """AC-44: фурнітура — `kind`, `to` ∈ ASM*, шлях з KIT-* і TUGGER-1."""
        comps = [c for m in self.data["productions"] for c in m["components"] if c["product"] == "FUR-CF-750"]
        self.assertTrue(comps)
        found = [c for c in comps if c.get("to", "").startswith("ASM")]
        self.assertTrue(found)
        for c in found:
            self.assertEqual(c["kind"], "фурнітура")
            codes = [s["code"] for s in c["path"]]
            self.assertTrue(any(x.startswith("KIT-") for x in codes) or "Z-PRE" in codes)
            self.assertIn("TUGGER-1", codes)
        self.assertTrue(any("KIT-" in str(c["path"]) for c in found))

    def test_components_paths_kinds(self):
        total = 0
        for mo in self.data["productions"]:
            for c in mo["components"]:
                total += 1
                self.assertIn("door", c)
                self.assertEqual(c["path"][0]["code"], "GATE-W")
        self.assertEqual(total, 200)
        ref_comps = {(m["name"], c["product"]): c for m in self.ref["productions"] for c in m["components"]}
        for mo in self.data["productions"]:
            for c in mo["components"]:
                self.assertEqual(c, ref_comps[(mo["name"], c["product"])])

    def test_unknown_prefix(self):
        data = copy.deepcopy(self.data)
        mo = data["productions"][0]
        mo["components"].append({"product": "ZZ-UNKNOWN", "qty": 1})
        chains.component_sources(data)
        c = mo["components"][-1]
        self.assertNotIn("kind", c)
        self.assertIsNone(c["to"])
        self.assertEqual([s["code"] for s in c["path"]][0], "GATE-W")
        self.assertEqual(len(c["path"]), 3)

    def test_delivery_fronts_via(self):
        via = [m for m in self.data["productions"] if m.get("delivery", {}).get("via")]
        self.assertTrue(via)
        for m in via:
            parent = self.mo[m["origin"]]
            self.assertEqual(m["delivery"]["via"], parent["name"])
            self.assertEqual(m["delivery"]["steps"][-len(parent["delivery"]["steps"]):], parent["delivery"]["steps"])
        ref = {m["name"]: m.get("delivery") for m in self.ref["productions"]}
        for m in self.data["productions"]:
            self.assertEqual(m.get("delivery"), ref[m["name"]])

    def test_full_cycle_mo(self):
        """AC-45."""
        name = self.top["full_cycle_mo"]
        self.assertEqual(name, self.ref["full_cycle_mo"])
        mo = self.mo[name]
        self.assertTrue(any(s["code"].startswith("TRUCK-OUT") for s in mo["delivery"]["steps"]))
        self.assertTrue(any(s["code"].startswith("TRUCK-IN") for s in mo["supply"]["steps"]))

    def test_sheet_chain_ship_chain_material_paths(self):
        """AC-45."""
        sheet = self.top["sheet_chain"]
        self.assertEqual(len(sheet["steps"]), 5)
        self.assertEqual(len(sheet["path"]), 6)
        for step in sheet["steps"]:
            self.assertTrue(step["codes"])
        ref = self.ref["sheet_chain"]
        self.assertEqual(sheet["path"], ref["path"])
        for a, b in zip(sheet["steps"], ref["steps"], strict=False):
            self.assertEqual(sorted(a["docs"]), sorted(b["docs"]))
            self.assertEqual({k: v for k, v in a.items() if k != "docs"}, {k: v for k, v in b.items() if k != "docs"})
        self.assertEqual(self.top["ship_chain"], self.ref["ship_chain"])
        self.assertEqual(len(self.top["material_paths"]), 6)
        self.assertEqual(self.top["material_paths"], self.ref["material_paths"])

    def test_sheet_chain_defaults(self):
        data = copy.deepcopy(self.data)
        data["pickings"] = [p for p in data["pickings"] if p["type"] not in ("putaway", "replenish")]
        path = chains.sheet_chain(data)["path"]
        self.assertEqual([p["code"] for p in path][3:5], ["RCK-R1-1A", "PLT-01A"])

    def test_cycle_check_ok(self):
        """AC-11."""
        data = copy.deepcopy(self.data)
        data.update(self.top)
        self.assertEqual(check(data), [])


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestChainsProvider(F3dViewerBase):

    def _collect(self, user, payload):
        env = self.env(user=user)
        ctx = {"sections": {}, "static": static_data.load(), "changes": {}, "codes": None}
        env["td.viewer.provider.chains"]._td_viewer_collect(payload, ctx)
        return ctx

    def test_registered(self):
        prov = self.env["td.viewer.provider.chains"]
        self.assertEqual(prov._td_sequence, 70)
        self.assertIn("sheet_chain", prov._td_sections)

    def test_collect_fixture(self):
        _ref, data = _fixture()
        ctx = self._collect(self.user_f3d, data)
        self.assertEqual(ctx["sections"]["chains"], "live")
        self.assertEqual(len(data["sheet_chain"]["steps"]), 5)
        self.assertIn("supply", data["productions"][0])

    def test_partial_without_stock_group(self):
        _ref, data = _fixture()
        users_cls = type(self.env["res.users"])
        orig = users_cls.has_group
        self.patch(users_cls, "has_group", lambda s, g: False if g == "stock.group_stock_user" else orig(s, g))
        ctx = self._collect(self.user_mrp_only, data)
        self.assertEqual(ctx["sections"]["chains"], "partial")
        self.assertEqual(data["sheet_chain"]["steps"], [])
        self.assertEqual(data["material_paths"], [])
        self.assertNotIn("supply", data["productions"][0])

    def test_partial_missing_section(self):
        _ref, data = _fixture()
        del data["pickings"]
        ctx = self._collect(self.user_f3d, data)
        self.assertEqual(ctx["sections"]["chains"], "partial")


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestChains(F3dViewerCase):

    def test_zones_45_outdoor_polygon_roof(self):
        """AC-61."""
        data = self.payload(self.user_f3d, full=True)
        zones = data["zones"]
        # test_td_viewer3d (якщо встановлений) додає власну зону Z-TEST — вона не з демо
        self.assertEqual(len([z for z in zones if z != "Z-TEST"]), 45)
        yard = zones["Z-YARD-W"]
        zone = self.env["td.zone"].search([("td_code", "=", "Z-YARD-W")])
        self.assertEqual(yard["zone_type"], "outdoor")
        self.assertEqual(yard["polygon"], zone.polygon)
        self.assertEqual(yard["locations"], [])
        self.assertEqual(yard["workcenters"], [])
        self.assertTrue(zones["Z-ROOF"]["is_roof"])
        self.assertNotIn("is_roof", zones["Z-CUT"])

    def test_supply_mo231_live(self):
        """AC-44."""
        data = self.payload(self.user_f3d)
        mo = next(m for m in data["productions"] if m["name"] == "WH/MO/00231")
        self.assertEqual(mo["supply"]["steps"][0]["code"], "GATE-W")
        self.assertEqual(mo["delivery"]["steps"][-1]["code"], "GATE-E")

    def test_live_chains(self):
        """AC-45."""
        data = self.payload(self.user_f3d)
        self.assertEqual(len(data["sheet_chain"]["steps"]), 5)
        self.assertEqual(len(data["sheet_chain"]["path"]), 6)
        self.assertEqual(len(data["material_paths"]), 6)
        self.assertEqual(data["meta"]["sections"]["chains"], "live")
        self.assertEqual(check(data), [])

    def test_delta_on_mrp_production_change(self):
        """R-14: дельта chains викликає collect вбудованих провайдерів без помилок."""
        from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder
        res = DeltaBuilder(self.env(user=self.user_f3d), since=None,
                           changes={"mrp.production": {"WH/MO/TST"}}).build()
        self.assertFalse(res["patch"]["meta"].get("errors"))
        self.assertIn("sheet_chain", res["patch"])
