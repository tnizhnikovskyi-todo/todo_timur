from odoo.tests import HttpCase, tagged

from odoo.addons.web.tests.test_js import unit_test_error_checker


def _hoot_hash(text):
    """Той самий хеш, що в odoo.addons.web.tests.test_js.HOOTCommon._generate_hash (id-фільтр Hoot)."""
    h = 0
    for char in text:
        h = (h << 5) - h + ord(char)
        h &= 0xFFFFFFFF
    return f"{h:08x}"


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestViewerHoot(HttpCase):
    """Запуск HOOT-тестів клієнта (static/tests/hoot/*.test.js, бандл web.assets_unit_tests) у headless Chrome.

    Пакет тестів відбирається за ім'ям модуля (`@factory3d_viewer`): будь-які інші suite Odoo не запускаються.
    """

    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@factory3d_viewer')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
