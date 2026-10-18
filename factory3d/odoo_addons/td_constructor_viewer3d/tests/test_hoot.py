from odoo.tests import HttpCase, tagged

from odoo.addons.factory3d_viewer.tests.test_hoot import _hoot_hash
from odoo.addons.web.tests.test_js import unit_test_error_checker


@tagged("post_install", "-at_install", "f3d", "f3d_constructor_viewer")
class TestLayoutHoot(HttpCase):
    """HOOT-тести моста (static/tests/hoot/*.test.js): applyLayout, додані об'єкти, порядок щодо stockLoad."""

    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@factory3d_constructor_viewer')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
