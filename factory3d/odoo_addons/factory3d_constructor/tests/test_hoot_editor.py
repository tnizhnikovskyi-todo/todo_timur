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
class TestEditorHoot(HttpCase):
    """HOOT-тести W2 (static/tests/editor/*.test.js, бандл web.assets_unit_tests) у headless Chrome.

    Дзеркала R-01…R-10 за золотими фікстурами W1 (AC-12, 14, 22, 31), OdooStore на мок-RPC (AC-48, 61, 66), ролі в UI (AC-49),
    DXF (AC-17, 18), сцена редактора з нульовим рендерером (AC-10, 63, 64, 65).
    Пакет відбирається за назвою `@factory3d_constructor/editor`; suite `@factory3d_constructor/model` (W3) не запускається.
    """

    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@factory3d_constructor/editor')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
