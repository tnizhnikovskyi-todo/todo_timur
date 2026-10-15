import json
import unittest

from odoo.tests import tagged

from odoo.addons.factory3d_viewer.tools.payload import BASE_KEYS, PayloadBuilder, get_providers

from .common import F3dViewerBase

ZZ = "f3d.viewer.provider.zz_"


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestProviders(F3dViewerBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if ZZ + "test" not in cls.env:
            raise unittest.SkipTest("test_factory3d_viewer не встановлено")

    def _builder(self, user=None, ctx=None, **kw):
        env = self.env(user=user or self.user_f3d)
        if ctx:
            env = env(context=dict(env.context, **ctx))
        return PayloadBuilder(env, **kw)

    def _record_calls(self):
        calls = []
        for p in get_providers(self.env):
            cls = type(p)
            orig = cls._f3d_viewer_collect

            def wrapper(this, payload, ctx, orig=orig, name=p._name):
                calls.append(name)
                return orig(this, payload, ctx)
            self.patch(cls, "_f3d_viewer_collect", wrapper)
        return calls

    def test_order_and_sections(self):
        """AC-12."""
        names = [p._name for p in get_providers(self.env)]
        self.assertEqual(names[0], ZZ + "test")
        seqs = [getattr(p, "_f3d_sequence", 1000) for p in get_providers(self.env)]
        self.assertEqual(seqs, sorted(seqs))
        calls = self._record_calls()
        data = self._builder().build()
        self.assertEqual(calls, names)
        self.assertEqual(data["meta"]["sections"]["zones"], "live")
        self.assertIn("Z-TEST", data["zones"])

    def test_failed_provider_isolated(self):
        """AC-13."""
        logger = "odoo.addons.factory3d_viewer.tools.payload"
        with self.assertLogs(logger, level="ERROR"):
            data = self._builder(ctx={"zz_fail": True}).build()
        meta = data["meta"]
        self.assertEqual(meta["sections"]["fire"], "error")
        errs = [e for e in meta["errors"] if e["provider"] == ZZ + "fail"]
        self.assertEqual(errs, [{"provider": ZZ + "fail", "error": "ValueError"}])
        self.assertNotIn("boom", json.dumps(meta))
        self.assertEqual(meta["sections"]["zones"], "live")
        self.assertNotIn("partial", data["fire"])  # частковий запис відкотився

    def test_failed_provider_restores_static_full(self):
        from odoo.addons.factory3d_viewer.tools import static_data
        with self.assertLogs("odoo.addons.factory3d_viewer.tools.payload", level="ERROR"):
            data = self._builder(ctx={"zz_fail": True}, full=True).build()
        self.assertEqual(data["fire"], static_data.load()["fire"])

    def test_group_denied(self):
        cls = type(self.env[ZZ + "duck"])
        self.patch(cls, "_f3d_group", "factory3d_viewer.no_such_group")
        data = self._builder().build()
        self.assertEqual(data["meta"]["sections"]["zz_duck"], "denied")
        self.assertEqual(data["meta"]["sections"]["infra"], "denied")
        self.assertNotIn("zz_duck", data)

    def test_sections_filter(self):
        data = self._builder(sections={"zones"}).build()
        self.assertIn("Z-TEST", data["zones"])
        self.assertNotIn("zz_duck", data)
        self.assertNotIn("infra", data["meta"]["sections"])

    def test_provider_without_collect_skipped(self):
        cls = type(self.env[ZZ + "test"])
        self.patch(cls, "_f3d_viewer_collect", None)
        with self.assertLogs("odoo.addons.factory3d_viewer.tools.payload", level="WARNING") as cm:
            data = self._builder().build()
        self.assertTrue(any("без _f3d_viewer_collect" in m for m in cm.output))
        self.assertNotIn("zones", data["meta"]["sections"])

    def test_duck_typed_provider_getattr(self):
        """AC-57."""
        duck = self.env[ZZ + "duck"]
        self.assertNotIn("f3d.viewer.provider", type(duck)._inherit)
        self.assertFalse(hasattr(duck, "_f3d_viewer_delta"))
        calls = self._record_calls()
        data = self._builder().build()
        self.assertIn(ZZ + "duck", calls)
        self.assertEqual(calls[-1], ZZ + "duck")
        self.assertEqual(data["infra"]["cards"]["ZZ-DUCK"], {"rows": [["Тест", "так"]]})
        self.assertEqual(data["zz_duck"], {"ok": True})
        self.assertEqual(data["meta"]["sections"]["infra"], "live")

    def test_top_level_order_schema_11(self):
        """AC-59."""
        data = self._builder(full=True).build()
        keys = list(data)
        base = [k for k in keys if k in BASE_KEYS]
        self.assertEqual(keys[:len(base)], base)
        self.assertEqual(base, [k for k in BASE_KEYS if k in base])
        self.assertEqual(keys[len(base):], ["zz_duck"])
        self.assertEqual(data["meta"]["schema"], "1.1")
        for k in ("energy", "lighting", "ventilation", "evacuation", "passports"):
            self.assertEqual(data["meta"]["sections"].get(k), "static")

    def test_abstract_defaults(self):
        base = self.env["f3d.viewer.provider"]
        self.assertEqual(base._f3d_sequence, 1000)
        self.assertEqual(base._f3d_sections, ())
        self.assertEqual(base._f3d_viewer_bus_models(), [])
        self.assertEqual(base._f3d_providers()[0]._name, ZZ + "test")
