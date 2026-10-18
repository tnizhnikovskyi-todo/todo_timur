import unittest
from datetime import timedelta

from odoo import fields
from odoo.tests import BaseCase, tagged

from odoo.addons.td_viewer3d.hooks import is_demo_db

from odoo.addons.td_viewer3d.tools import payload as payload_tools
from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder, deep_merge, default_delta

from .common import F3dViewerBase

ZZ = "td.viewer.provider.zz_"
LOGGER = "odoo.addons.td_viewer3d.tools.payload"


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
        from odoo.addons.td_viewer3d.tools.payload import deep_merge as imported
        self.assertIs(imported, payload_tools.deep_merge)


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDelta(F3dViewerBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if ZZ + "duck" not in cls.env:
            raise unittest.SkipTest("test_td_viewer3d не встановлено")

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
        if "td.viewer.event" not in self.env:
            self.skipTest("немає td.viewer.event")
        self.patch(type(self.env["td.viewer.event"]), "_since", lambda *a, **k: None)
        res = DeltaBuilder(self.env(user=self.user_f3d), None).build()
        self.assertEqual(res["full"], True)
        self.assertNotIn("patch", res)

    def test_opt_key_null(self):
        """Зниклий opt-ключ -> null у патчі."""
        cls = type(self.env[ZZ + "test"])
        self.patch(cls, "_f3d_sections", ("zones", "workorders"))
        self.patch(cls, "_f3d_viewer_collect",
                   lambda this, payload, ctx: payload.setdefault("workorders", {}).update(
                       {"WO00001": {"state": "done", "workcenter": "SAW-1"}}))
        wo = self._delta({"mrp.workorder": {"WO00001"}})["patch"]["workorders"]["WO00001"]
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
        self.assertNotIn("partial", res["patch"].get("fire", {}))  # частковий запис zz_fail відкотився

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

    # --- дельта за подіями шини (W3) ---------------------------------------

    def _settle(self):
        """Виконує накопичені precommit-обробники й скидає події фікстур."""
        self.env.flush_all()
        self.env.cr.precommit.run()
        self.env.flush_all()
        self.env["td.viewer.event"].sudo().search([]).unlink()

    def _delta_since(self, since):
        return DeltaBuilder(self.env(user=self.user_f3d), since).build()

    def _need_demo(self):
        if not is_demo_db(self.env):
            self.skipTest("потрібна демо-база")

    def test_quant_change_patch(self):
        """AC-16."""
        self._need_demo()
        self.demo_clock()
        loc = self.env["stock.location"].search([("td_code", "=", "PLT-04C")], limit=1)
        quant = self.env["stock.quant"].search([("location_id", "=", loc.id), ("quantity", ">", 0)], limit=1)
        if not quant:
            self.skipTest("немає залишку в PLT-04C")
        self._settle()
        since = fields.Datetime.now() - timedelta(seconds=2)
        quant.sudo().write({"quantity": quant.quantity + 1})
        self.env.flush_all()
        self.env.cr.precommit.run()
        res = self._delta_since(since)
        self.assertFalse(res["full"])
        self.assertEqual(set(res["patch"]["locations"]), {"PLT-04C"})
        self.assertTrue(res["patch"]["locations"]["PLT-04C"]["quants"])
        old = self._delta_since(fields.Datetime.now() - timedelta(days=3))
        self.assertEqual(old["full"], True)

    def test_workorder_done_patch(self):
        """AC-46."""
        self._need_demo()
        self.demo_clock()
        wo = self.env["mrp.workorder"].search([("state", "in", ("ready", "progress"))], limit=1)
        if not wo:
            self.skipTest("немає активного завдання")
        mo, wc = wo.production_id, wo.workcenter_id
        self._settle()
        since = fields.Datetime.now() - timedelta(seconds=2)
        if wo.state == "ready":
            wo.button_start()
        wo.button_finish()
        self.env.flush_all()
        self.env.cr.precommit.run()
        patch_ = self._delta_since(since)["patch"]
        self.assertEqual(patch_["workorders"]["WO%05d" % wo.id]["state"], "done")
        if wc.td_code:
            self.assertIn(wc.td_code, patch_["workcenters"])
        self.assertIn(mo.name, [p["name"] for p in patch_["productions"]])
        self.assertIn("sheet_chain", patch_)

    def test_removed_cancelled_mo(self):
        fin = self.env["product.product"].create({"name": "TST del", "default_code": "TST-DEL", "is_storable": True})
        mo = self.env["mrp.production"].create({"product_id": fin.id, "product_qty": 1})
        mo.action_confirm()
        name = mo.name
        self._settle()
        since = fields.Datetime.now() - timedelta(seconds=2)
        mo.action_cancel()
        self.env.flush_all()
        self.env.cr.precommit.run()
        res = self._delta_since(since)
        self.assertIn(name, res["removed"]["productions"])
        mo.unlink()
        self.env.flush_all()
        self.env.cr.precommit.run()
        self.assertIn(name, self._delta_since(since)["removed"]["productions"])
