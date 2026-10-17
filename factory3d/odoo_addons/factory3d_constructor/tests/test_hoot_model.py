from odoo.tests import HttpCase, tagged

from odoo.addons.web.tests.test_js import unit_test_error_checker


def _hoot_hash(text):
    """Той самий хеш, що в odoo.addons.web.tests.test_js.HOOTCommon._generate_hash (id-фільтр Hoot)."""
    h = 0
    for char in text:
        h = (h << 5) - h + ord(char)
        h &= 0xFFFFFFFF
    return f"{h:08x}"


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestModelHoot(HttpCase):
    """HOOT-тести W3 (static/tests/model/*.test.js, бандл web.assets_unit_tests) у headless Chrome.

    Конвеєр моделі R-15…R-17 і віджети f3d_model_preview / f3d_model_upload: AC-34(JS), 35(JS), 37…42.
    Пакет відбирається за назвою `@factory3d_constructor/model`; suite `@factory3d_constructor/editor` (W2) не запускається.
    """

    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@factory3d_constructor/model')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
