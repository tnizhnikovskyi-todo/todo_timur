"""R-27 (WL-1…WL-6): екран планірки «стіна» — вхід, налаштування, сторінка кіоска з `?wall=1`, браузерна перевірка."""

import html
import json
import re

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged

from odoo.addons.td_viewer3d.controllers import kiosk as kiosk_ctrl

from .common import F3dViewerBase

WALL_JS = """
(async () => {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const t0 = Date.now();
    const need = (sel) => document.querySelector(sel);
    while (!need(".o_f3d_wall")) {
        if (Date.now() - t0 > 60000) { throw new Error("«стіну» не змонтовано"); }
        await wait(200);
    }
    const wall = window.odoo.f3dWall;
    if (!wall) { throw new Error("немає odoo.f3dWall"); }
    if (need(".o_main_navbar") || need(".o_navbar")) { throw new Error("у «стіні» є навігація Odoo"); }
    if (!document.querySelector("#f3d-kiosk").hasAttribute("inert")) { throw new Error("«стіна» інтерактивна"); }
    if (document.documentElement.dataset.theme !== "dark") { throw new Error("тема не темна"); }
    if (need(".o_f3d_wall").dataset.slide !== "overview") { throw new Error("перший слайд не overview"); }
    wall.next();
    const kpis = need(".o_f3d_wall-body").querySelectorAll(".o_f3d_wall-kpi").length;
    if (need(".o_f3d_wall").dataset.slide !== "kpi" || kpis !== 4) {
        throw new Error("слайд KPI не показано");
    }
    console.log("test successful");
})();
"""


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestWallSettings(F3dViewerBase):
    """WL-3: налаштування «стіни» (тривалість слайда, набір слайдів), адреса, права."""

    def test_defaults(self):
        params = self.env["ir.config_parameter"].sudo()
        self.assertEqual(params.get_param("td.viewer.wall_slide_s"), "20")
        self.assertEqual(params.get_param("td.viewer.wall_slides"), "overview,kpi,events,orders")

    def test_validation(self):
        Settings = self.env["res.config.settings"]
        for vals in (
            {"td_wall_slide_s": 4},
            {"td_wall_slide_s": 301},
            {"td_wall_slides": ""},
            {"td_wall_slides": "Overview"},
            {"td_wall_slides": "kpi;orders"},
            {"td_wall_slides": "kpi,,orders"},
        ):
            rec = Settings.create(vals)
            with self.assertRaises(ValidationError, msg=str(vals)):
                rec._td_validate()
        Settings.create({"td_wall_slide_s": 30, "td_wall_slides": "orders,kpi,td_energy"})._td_validate()

    def test_wall_url_admin_only(self):
        token = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        admin = self.env["res.config.settings"].with_user(self.user_admin).new({})
        self.assertTrue(admin.td_wall_url.endswith("/f3d/kiosk/%s?wall=1" % token))
        manager = self.env["res.config.settings"].with_user(self.user_manager).new({})
        self.assertFalse(manager.td_wall_url)
        with self.assertRaises(AccessError):
            manager.action_td_new_kiosk_token()


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestWallPage(HttpCase, F3dViewerBase):
    """WL-2: вхід у «стіну» — той самий кіоск за токеном (технічний користувач), `?wall=1`; нових маршрутів немає."""

    def setUp(self):
        super().setUp()
        kiosk_ctrl.reset_rate_limit()
        self.addCleanup(kiosk_ctrl.reset_rate_limit)
        self.set_param("kiosk_enabled", "True")
        self.token = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        self.base = "/f3d/kiosk/" + self.token

    def _params(self, query=""):
        res = self.url_open(self.base + query, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        raw = re.search(r'data-params="([^"]*)"', res.text).group(1)
        return json.loads(html.unescape(raw))

    def test_plain_kiosk_has_no_wall(self):
        self.assertNotIn("wall", self._params("?tab=production"))
        self.assertNotIn("wall", self._params("?wall=0"))
        self.assertNotIn("theme", self._params("?theme=light"))

    def test_wall_defaults(self):
        wall = self._params("?wall=1")["wall"]
        self.assertEqual(wall, {"slide_s": 20, "slides": ["overview", "kpi", "events", "orders"], "theme": "dark"})

    def test_wall_from_settings(self):
        self.set_param("wall_slide_s", "35")
        self.set_param("wall_slides", "orders, kpi,td_energy")
        wall = self._params("?wall=1&theme=light")["wall"]
        self.assertEqual(wall, {"slide_s": 35, "slides": ["orders", "kpi", "td_energy"], "theme": "light"})

    def test_wall_garbage_falls_back(self):
        self.set_param("wall_slide_s", "1")
        self.set_param("wall_slides", "<x>,;;,Bad Key")
        wall = self._params("?wall=1&theme=<x>")["wall"]
        self.assertEqual(wall["slide_s"], 20)
        self.assertEqual(wall["slides"], ["overview", "kpi", "events", "orders"])
        self.assertEqual(wall["theme"], "dark")
        self.set_param("wall_slide_s", "abc")
        self.assertEqual(self._params("?wall=1")["wall"]["slide_s"], 20)

    def test_wall_needs_token_and_enabled_kiosk(self):
        self.assertEqual(self.url_open("/f3d/kiosk/deadbeef?wall=1", allow_redirects=False).status_code, 404)
        self.set_param("kiosk_enabled", "False")
        res = self.url_open(self.base + "?wall=1", allow_redirects=False)
        self.assertEqual((res.status_code, res.content), (404, b""))

    def test_wall_data_is_kiosk_data(self):
        """«Стіна» читає дані тим самим кіосковим користувачем: без вартості замовлень і службових полів."""
        data = self.url_open(self.base + "/data", allow_redirects=False).json()
        self.assertTrue(data["meta"]["kiosk"])
        self.assertEqual(data["meta"]["user"], self.user_kiosk.name)

    def test_wall_browser(self):
        """WL-1 (браузер): «стіна» монтується без навігації, inert, темна тема, перший слайд — 3D, далі KPI."""
        self.browser_js(self.base + "?wall=1&f3d_test=1", WALL_JS, timeout=180)
