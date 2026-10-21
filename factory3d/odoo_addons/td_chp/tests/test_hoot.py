"""AC-21…23: Hoot-набір клієнта пульта КГУ (`static/tests/hoot/*.test.js`, бандл `web.assets_unit_tests`).

Запускає `/web/tests` у headless Chrome за зразком `td_energy/tests/test_w1_hoot.py`: набір відбирається за ім'ям модуля
(`@td_chp`), тож інші suite Odoo не виконуються. Окремі Python-тести: `web.assets_backend` без `static/lib/three`
(AC-21), фікстура `state.js` збігається з `state.json` (C-chp-02), `static/lib/three` — r147 заданого розміру (D-10).
"""

import json
import os

from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.web.tests.test_js import unit_test_error_checker

STATIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")


def _hoot_hash(text):
    """Той самий хеш, що в odoo.addons.web.tests.test_js.HOOTCommon._generate_hash (id-фільтр Hoot)."""
    h = 0
    for char in text:
        h = (h << 5) - h + ord(char)
        h &= 0xFFFFFFFF
    return f"{h:08x}"


@tagged("post_install", "-at_install", "td", "td_chp")
class TestChpHoot(HttpCase):
    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@td_chp')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )


@tagged("post_install", "-at_install", "td", "td_chp")
class TestChpAssets(TransactionCase):
    def test_backend_bundle_without_three(self):
        """AC-21: у `web.assets_backend` немає `static/lib/three` (three.js — `loadJS` лише при відкритті дії)."""
        files = self.env["ir.asset"]._get_asset_paths("web.assets_backend", {})
        urls = [f[0] for f in files]
        self.assertTrue(any(u.startswith("/td_chp/static/src/pult/") for u in urls), "код пульта має бути в бандлі")
        self.assertFalse(
            [u for u in urls if "/td_chp/static/lib" in u], "three.js не повинен бути в web.assets_backend"
        )
        self.assertFalse([u for u in urls if "/td_chp/" in u and "three" in u.lower()])

    def test_unit_tests_bundle_has_hoot(self):
        files = self.env["ir.asset"]._get_asset_paths("web.assets_unit_tests", {})
        urls = [f[0] for f in files]
        self.assertTrue([u for u in urls if u.startswith("/td_chp/static/tests/hoot/")])
        self.assertFalse([u for u in urls if "/td_chp/static/lib" in u])

    def test_three_copy_is_r147(self):
        """D-10: власна копія three r147 — `three.min.js` 607 784 Б, `OrbitControls.js` 26 660 Б, LICENSE."""
        lib = os.path.join(STATIC, "lib", "three")
        self.assertEqual(os.path.getsize(os.path.join(lib, "three.min.js")), 607784)
        self.assertEqual(os.path.getsize(os.path.join(lib, "OrbitControls.js")), 26660)
        self.assertTrue(os.path.getsize(os.path.join(lib, "LICENSE")) > 0)
        with open(os.path.join(lib, "three.min.js"), encoding="utf-8") as f:
            self.assertIn('const e="147"', f.read(600))

    def test_fixture_in_sync(self):
        """C-chp-02: `hoot/state_fixture.js` — копія `fixtures/state.json`."""
        with open(os.path.join(STATIC, "tests", "fixtures", "state.json"), encoding="utf-8") as f:
            expected = json.load(f)
        with open(os.path.join(STATIC, "tests", "hoot", "state_fixture.js"), encoding="utf-8") as f:
            text = f.read()
        body = text.split("export const STATE =", 1)[1].strip().rstrip(";")
        self.assertEqual(json.loads(body), expected)
