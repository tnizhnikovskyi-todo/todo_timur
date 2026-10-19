import os
import re
import unittest

from odoo.tests import tagged

from odoo.addons.td_viewer3d.tools import payload as payload_tools
from odoo.addons.td_viewer3d.tools.payload import PayloadBuilder

from .common import F3dViewerBase

ZZ_TEST = "td.viewer.provider.zz_test"
MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestAccess(F3dViewerBase):
    def _capture_ctx(self):
        """Перехоплює ctx, який збирач передає першому провайдеру (потрібен zz_test)."""
        if ZZ_TEST not in self.env:
            raise unittest.SkipTest("test_td_viewer3d не встановлено")
        seen = []
        cls = type(self.env[ZZ_TEST])
        orig = cls._td_viewer_collect

        def wrapper(this, payload, ctx):
            seen.append(ctx)
            return orig(this, payload, ctx)

        self.patch(cls, "_td_viewer_collect", wrapper)
        return seen

    def test_nobody_gets_denied(self):
        if ZZ_TEST not in self.env:
            self.skipTest("test_td_viewer3d не встановлено")
        data = PayloadBuilder(self.env(user=self.user_nobody)).build()
        self.assertEqual(data["meta"]["sections"]["zones"], "denied")
        self.assertNotIn("Z-TEST", data.get("zones", {}))

    def test_kiosk_ctx(self):
        """AC-29 (контекст): kiosk=True -> ctx.kiosk, energy_cost вимкнено."""
        seen = self._capture_ctx()
        data = PayloadBuilder(self.env(user=self.user_kiosk), kiosk=True, lite=True).build()
        ctx = seen[0]
        self.assertTrue(ctx["kiosk"] and ctx["lite"])
        self.assertFalse(ctx["energy_cost"])
        self.assertTrue(data["meta"]["kiosk"])
        self.assertEqual(data["meta"]["user"], self.user_kiosk.name)

    def test_energy_cost_flag(self):
        """AC-60 (мок): група вартості існує й користувач у ній -> ctx.energy_cost; kiosk -> ні."""
        seen = self._capture_ctx()
        real = payload_tools.group_ok

        def fake(env, xmlid):
            return True if xmlid == payload_tools.ENERGY_COST_GROUP else real(env, xmlid)

        self.patch(payload_tools, "group_ok", fake)
        PayloadBuilder(self.env(user=self.user_f3d)).build()
        PayloadBuilder(self.env(user=self.user_kiosk), kiosk=True).build()
        self.assertTrue(seen[0]["energy_cost"])
        self.assertFalse(seen[1]["energy_cost"])

    def test_energy_cost_without_group(self):
        seen = self._capture_ctx()
        PayloadBuilder(self.env(user=self.user_f3d)).build()
        self.assertFalse(seen[0]["energy_cost"])

    def test_mrp_denied(self):
        """AC-14 (потрібні вбудовані провайдери W1b)."""
        if "td.viewer.provider.production" not in self.env:
            self.skipTest("немає вбудованого провайдера production")
        data = PayloadBuilder(self.env(user=self.user_stock_only)).build()
        self.assertEqual(data["productions"], [])
        self.assertEqual(data["workorders"], {})
        self.assertEqual(data["workcenters"], {})
        self.assertEqual(data["meta"]["sections"]["productions"], "denied")

    def test_stock_denied(self):
        if "td.viewer.provider.stock" not in self.env:
            self.skipTest("немає вбудованого провайдера stock")
        plain = self._make_user("f3d_plain_only", ["base.group_user", "td_factory3d.group_td_user"])
        data = PayloadBuilder(self.env(user=plain)).build()
        self.assertEqual(data["locations"], {})
        self.assertEqual(data["meta"]["sections"]["locations"], "denied")

    def test_access_ok(self):
        self.assertTrue(payload_tools.access_ok(self.env(user=self.user_mrp_only), "mrp.workcenter"))
        self.assertFalse(payload_tools.access_ok(self.env(user=self.user_nobody), "mrp.workcenter"))
        self.assertFalse(payload_tools.access_ok(self.env, "no.such.model"))

    def test_no_sudo_lint(self):
        """AC-14: `.sudo(` лише разом з ir.config_parameter."""
        files = []
        for sub in ("tools", "controllers"):
            d = os.path.join(MODULE, sub)
            files += [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".py")]
        files.append(os.path.join(MODULE, "models", "viewer_provider.py"))
        bad = []
        for path in files:
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if re.search(r"\.sudo\(", line) and "ir.config_parameter" not in line:
                        bad.append(f"{os.path.basename(path)}:{n}")
        self.assertEqual(bad, [])
