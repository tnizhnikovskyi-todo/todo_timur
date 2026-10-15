import unittest

from odoo.tests import BaseCase, tagged

from odoo.addons.factory3d_viewer.tools import payload as payload_tools
from odoo.addons.factory3d_viewer.tools.payload import DeltaBuilder, deep_merge, default_delta

from .common import F3dViewerBase

ZZ = "f3d.viewer.provider.zz_"
LOGGER = "odoo.addons.factory3d_viewer.tools.payload"


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDeepMerge(BaseCase):

    def test_semantics(self):
        """AC-56."""
        dst = {"cards": {"PV-INV": {"rows": [1]}}, "totals": {"pv_now": 468}}
        res = deep_merge(dst, {"cards": {"GENSET": {"rows": [2]}}, "totals": {"island": False}})
        self.assertIs(res, dst)
        self.assertEqual(res, {"cards": {"PV-INV": {"rows": [1]}, "GENSET": {"rows": [2]}},
                               "totals": {"pv_now": 468, "island": False}})
        self.assertEqual(deep_merge({"a": [1, 2]}, {"a": [3]}), {"a": [3]})
        self.assertEqual(deep_merge({"a": {"x": 1}}, {"a": 5}), {"a": 5})
        self.assertEqual(deep_merge({"a": 1}, {"a": None}), {"a": None})
        src = {"k": {"n": 1}}
        d = deep_merge({}, src)
        src["k"]["n"] = 2
        self.assertEqual(d, {"k": {"n": 1}})
        with self.assertRaises(TypeError):
            deep_merge([], {})
        with self.assertRaises(TypeError):
            deep_merge({}, [])

    def test_import_path(self):
        from odoo.addons.factory3d_viewer.tools.payload import deep_merge as imported
        self.assertIs(imported, payload_tools.deep_merge)


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDelta(F3dViewerBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if ZZ + "duck" not in cls.env:
            raise unittest.SkipTest("test_factory3d_viewer не встановлено")

    def _delta(self, changes, **kw):
        env = self.env(user=self.user_f3d)
        return DeltaBuilder(env, None, changes=changes, **kw).build()

    def _ctx(self, changes):
        return {"user": self.user_f3d, "changes": changes, "codes": set(), "static": {}, "kiosk": False}

    def test_default_delta_deep_merge(self):
        """AC-58: дельта за замовчуванням зливає infra через deep_merge, не затираючи ключі energy."""
        patch = {"infra": {"cards": {"PV-INV": {"rows": [["Зараз", "468 кВт"]]}}, "totals": {"pv_now": 468}}}
        default_delta(self.env[ZZ + "duck"], patch, self._ctx({"x": {"A"}}))
        self.assertEqual(set(patch["infra"]["cards"]), {"PV-INV", "ZZ-DUCK"})
        self.assertEqual(patch["infra"]["totals"]["pv_now"], 468)
        self.assertEqual(patch["zz_duck"], {"ok": True})

    def test_builder_uses_default_delta_for_duck(self):
        res = self._delta({"stock.quant": {"PLT-04C"}})
        self.assertFalse(res["full"])
        self.assertEqual(res["events"], 1)
        self.assertIn("ZZ-DUCK", res["patch"]["infra"]["cards"])
        self.assertIn("now", res["patch"]["meta"])
        self.assertRegex(res["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_empty_delta(self):
        res = self._delta({})
        self.assertEqual(res["events"], 0)
        self.assertEqual((res["patch"], res["removed"]), ({}, {}))

    def test_codes_param_without_events(self):
        res = self._delta({}, codes={"SAW-1"})
        self.assertIn("patch", res)
        self.assertFalse(res["full"])
        self.assertEqual(res["events"], 0)

    def test_full_when_old_since(self):
        if "f3d.viewer.event" not in self.env:
            self.skipTest("немає f3d.viewer.event")
        self.patch(type(self.env["f3d.viewer.event"]), "_since", lambda *a, **k: None)
        res = DeltaBuilder(self.env(user=self.user_f3d), None).build()
        self.assertEqual(res["full"], True)
        self.assertNotIn("patch", res)

    def test_opt_key_null(self):
        """Зниклий opt-ключ -> null у патчі."""
        cls = type(self.env[ZZ + "test"])
        self.patch(cls, "_f3d_sections", ("zones", "workorders"))
        self.patch(cls, "_f3d_viewer_collect",
                   lambda this, payload, ctx: payload.setdefault("workorders", {}).update(
                       {"WO00051": {"state": "done", "workcenter": "CNC-2"}}))
        wo = self._delta({"mrp.workorder": {"WO00051"}})["patch"]["workorders"]["WO00051"]
        self.assertIsNone(wo["blocked"])
        self.assertEqual(wo["state"], "done")
        self.assertIn("duration", wo)

    def test_removed(self):
        res = self._delta({"mrp.production": {"WH/MO/09999"}, "stock.location": {"ZZ-LOC"}})
        self.assertEqual(res["removed"]["productions"], ["WH/MO/09999"])
        self.assertEqual(res["removed"]["locations"], ["ZZ-LOC"])
        self.assertEqual(res["removed"]["pickings"], [])

    def test_provider_error_in_delta(self):
        with self.assertLogs(LOGGER, level="ERROR"):
            res = DeltaBuilder(self.env(user=self.user_f3d, context=dict(self.env.context, zz_fail=True)), None,
                               changes={"x": {"A"}}).build()
        self.assertIn({"provider": ZZ + "fail", "error": "ValueError"}, res["patch"]["meta"]["errors"])
        self.assertNotIn("fire", res["patch"])

    def test_delta_too_large(self):
        cls = type(self.env[ZZ + "test"])
        big = {"k%d" % i: "x" * 100 for i in range(3000)}
        self.patch(cls, "_f3d_viewer_collect", lambda this, payload, ctx: payload.update({"zones": big}))
        with self.assertLogs(LOGGER, level="WARNING"):
            res = self._delta({"x": {"A"}})
        self.assertIn({"provider": ZZ + "test", "error": "DeltaTooLarge"}, res["patch"]["meta"]["errors"])
        self.assertNotIn("zones", res["patch"])

    def test_group_skip(self):
        res = DeltaBuilder(self.env(user=self.user_nobody), None, changes={"x": {"A"}}).build()
        self.assertNotIn("zz_duck", res["patch"])
