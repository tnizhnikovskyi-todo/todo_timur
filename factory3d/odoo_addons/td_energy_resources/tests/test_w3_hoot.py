"""W3-C: hoot-набір екрана «Енергоресурси» (W3_SPEC розд. 13.1, AC-57).

Запускає `/web/tests` у headless Chrome за зразком `td_energy/tests/test_w1_hoot.py`: набір відбирається за ім'ям модуля
(`@td_energy_resources`), тож інші suite Odoo не виконуються. Тести — `static/tests/*.test.js`
(бандл `web.assets_unit_tests`): `resources.test.js`; відповіді API — `fixtures/contracts.js` (контракти C-01/C-02).
"""

from odoo.tests import HttpCase, tagged

from odoo.addons.web.tests.test_js import unit_test_error_checker


def _hoot_hash(text):
    """Той самий хеш, що в odoo.addons.web.tests.test_js.HOOTCommon._generate_hash (id-фільтр Hoot)."""
    h = 0
    for char in text:
        h = (h << 5) - h + ord(char)
        h &= 0xFFFFFFFF
    return f"{h:08x}"


@tagged("post_install", "-at_install", "td", "td_energy_resources")
class TestW3Hoot(HttpCase):
    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@td_energy_resources')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
