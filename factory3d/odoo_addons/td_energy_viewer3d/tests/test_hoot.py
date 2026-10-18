"""W2-D: запуск hoot-тестів моста (static/tests/hoot/*.test.js) у headless Chrome: AC-288…AC-290, UI-27."""

from odoo.tests import HttpCase, tagged

from odoo.addons.td_viewer3d.tests.test_hoot import _hoot_hash
from odoo.addons.web.tests.test_js import unit_test_error_checker


@tagged("post_install", "-at_install", "f3d", "f3d_energy_viewer3d")
class TestEnergyLayerHoot(HttpCase):
    """Пакет відбирається за ім'ям модуля (`@td_energy_viewer3d`): інші suite Odoo не запускаються."""

    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@td_energy_viewer3d')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
