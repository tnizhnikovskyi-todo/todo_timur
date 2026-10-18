"""W2-B: hoot-набір клієнта «Керування» (AC-295…AC-300; AC-292, AC-301, AC-302 — у наборі `@td_energy`).

Запускає `/web/tests` у headless Chrome за зразком `td_energy/tests/test_w1_hoot.py`: набір відбирається за ім'ям модуля
(`@td_energy_control`). Тести — `static/tests/*.test.js` (бандл `web.assets_unit_tests`): `control.test.js` (екран),
`confirm_dialog.test.js` (ConfirmDialog, ParamsDialog), `advice_handler.test.js` (обробник рекомендацій, баннер
«Виконано»), `node_actions.test.js` (кнопки панелі вузла).
"""

from odoo.tests import HttpCase, tagged

from odoo.addons.web.tests.test_js import unit_test_error_checker

from .common import TAGS


def _hoot_hash(text):
    """Той самий хеш, що в odoo.addons.web.tests.test_js.HOOTCommon._generate_hash (id-фільтр Hoot)."""
    h = 0
    for char in text:
        h = (h << 5) - h + ord(char)
        h &= 0xFFFFFFFF
    return f"{h:08x}"


@tagged(*TAGS)
class TestControlHoot(HttpCase):
    def test_hoot_suite(self):
        flt = f"&id={_hoot_hash('@td_energy_control')}"
        self.browser_js(
            f"/web/tests?headless&loglevel=2&preset=desktop&timeout=60000{flt}",
            "",
            "",
            login="admin",
            timeout=1800,
            success_signal="[HOOT] Test suite succeeded",
            error_checker=unit_test_error_checker,
        )
