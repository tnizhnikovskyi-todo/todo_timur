"""W4-B: hoot-набір екрана «Аналітика» (W4_SPEC розд. 13.1, AC-48).

Запускає `/web/tests` у headless Chrome за зразком `td_energy_resources/tests/test_w3_hoot.py`: набір відбирається за
ім'ям модуля (`@td_energy_analytics`), тож інші suite Odoo не виконуються. Тести — `static/tests/analytics.test.js`
(бандл `web.assets_unit_tests`); відповідь API-01 мокається всередині файлу за контрактом `contracts/api01_*.json`.
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


@tagged("post_install", "-at_install", "td", "td_w4", "td_energy_analytics")
class TestW4Hoot(HttpCase):
    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@td_energy_analytics')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
