import os
import re
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.td_viewer3d.controllers import kiosk as kiosk_ctrl

from .common import F3dViewerBase

MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestKiosk(F3dViewerBase):
    """API-08/09 (параметри і налаштування): токен, стоп-кран, права на «Новий токен»."""

    def test_token_generated_32hex(self):
        token = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        self.assertRegex(token or "", r"^[0-9a-f]{32}$")

    def test_new_token_admin_only(self):
        """AC-50: менеджер без group_td_admin — URL порожній, «Новий токен» -> AccessError; адмін — працює."""
        Settings = self.env["res.config.settings"]
        manager = Settings.with_user(self.user_manager).new({})
        self.assertFalse(manager.td_kiosk_url)
        with self.assertRaises(AccessError):
            manager.action_td_new_kiosk_token()
        admin = Settings.with_user(self.user_admin).new({})
        old = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        self.assertIn("/f3d/kiosk/" + old, admin.td_kiosk_url)
        admin.action_td_new_kiosk_token()
        new = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        self.assertRegex(new, r"^[0-9a-f]{32}$")
        self.assertNotEqual(old, new)

    def test_kiosk_disabled_param(self):
        self.set_param("kiosk_enabled", "False")
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_enabled"), "False")

    def test_kiosk_ctx_hides_costs(self):
        data = self.payload(self.user_kiosk, kiosk=True, lite=True)
        self.assertTrue(data["meta"]["kiosk"])
        for so in data.get("sale_orders") or []:
            self.assertNotIn("amount", so)

    def test_compare_digest_in_source(self):
        """§13.3: токен порівнюється через hmac.compare_digest, не через ==."""
        with open(os.path.join(MODULE, "controllers", "kiosk.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("hmac.compare_digest(", src)
        self.assertFalse(re.search(r"token\s*==|==\s*token|stored\s*==|==\s*stored", src))


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestKioskHttp(HttpCase, F3dViewerBase):
    """AC-28, AC-29, AC-48, §13.3: маршрути кіоска без сесії."""

    def setUp(self):
        super().setUp()
        kiosk_ctrl.reset_rate_limit()
        self.addCleanup(kiosk_ctrl.reset_rate_limit)
        self.set_param("kiosk_enabled", "True")
        self.token = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        self.base = "/f3d/kiosk/" + self.token

    def _get(self, path="", **kw):
        return self.url_open(self.base + path, allow_redirects=False, **kw)

    def test_page(self):
        """AC-28."""
        res = self._get("?tab=production&lite=1&refresh=20&bad=<x>")
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/html", res.headers["Content-Type"])
        self.assertNotIn("o_main_navbar", res.text)
        self.assertNotIn("o_navbar", res.text)
        self.assertIn('id="f3d-kiosk"', res.text)
        self.assertIn('data-token="%s"' % self.token, res.text)
        self.assertIn("&#34;tab&#34;: &#34;production&#34;", res.text)
        self.assertNotIn("<x>", res.text)
        self.assertNotIn("Set-Cookie", res.headers)

    def test_bad_token_and_disabled(self):
        for bad in ("deadbeef", "0" * 32, "%00", "a'b", "x" * 5000):
            self.assertEqual(self.url_open("/f3d/kiosk/" + bad, allow_redirects=False).status_code, 404, bad[:20])
            self.assertEqual(self.url_open("/f3d/kiosk/%s/data" % bad, allow_redirects=False).status_code, 404)
        self.set_param("kiosk_enabled", "False")
        for path in ("", "/data", "/static", "/delta?since=2026-10-12T00:00:00Z", "/snapshots", "/parts/manifest.json"):
            res = self._get(path)
            self.assertEqual(res.status_code, 404, path)
            self.assertEqual(res.content, b"")

    def test_data_for_kiosk(self):
        """AC-29."""
        res = self._get("/data")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("Set-Cookie", res.headers)
        data = res.json()
        self.assertEqual(data["meta"]["user"], self.user_kiosk.name)
        self.assertTrue(data["meta"]["kiosk"])
        for so in data.get("sale_orders") or []:
            self.assertNotIn("amount", so)
        for mo in data.get("productions") or []:
            self.assertNotIn("energy_cost", mo)
        for emp in data.get("employees") or []:
            self.assertNotIn("email", emp)

    def test_other_endpoints(self):
        static = self._get("/static")
        self.assertEqual(static.status_code, 200)
        self.assertIn("passports", static.json())
        self.assertNotIn("Set-Cookie", static.headers)
        self.assertEqual(self._get("/parts/manifest.json").status_code, 200)
        self.assertEqual(self._get("/snapshots").status_code, 200)
        self.assertEqual(self._get("/snapshot/999999").status_code, 404)
        self.assertEqual(self._get("/delta?since=2026-10-12T00:00:00Z").status_code, 200)
        self.assertEqual(self._get("/delta?since=bad").status_code, 400)
        self.assertEqual(self._get("/data?codes=" + "A" * 10000).status_code, 400)

    def test_rate_limit(self):
        """AC-48: 11 запитів за 1 с з одного IP -> 11-й 429 (час заморожено підміною таймера)."""
        with patch.object(kiosk_ctrl, "_now", lambda: 1000.0):
            codes = [self._get("/delta?since=2026-10-12T00:00:00Z").status_code for _i in range(11)]
        self.assertEqual(codes[:10], [200] * 10)
        self.assertEqual(codes[10], 429)
        self.assertNotIn("Set-Cookie", self._get("/delta?since=2026-10-12T00:00:00Z").headers)


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestKioskAssets(TransactionCase):
    """QA 16.10.2026: бандл `assets_kiosk` не компілювався (Undefined variable $theme-colors-rgb) -> кіоск без
    стилів."""

    def test_kiosk_bundle_compiles(self):
        bundle = self.env["ir.qweb"]._get_asset_bundle("td_viewer3d.assets_kiosk", css=True, js=False)
        bundle.css()
        self.assertFalse(bundle.css_errors, "SCSS бандла assets_kiosk: %s" % "\n".join(bundle.css_errors))
