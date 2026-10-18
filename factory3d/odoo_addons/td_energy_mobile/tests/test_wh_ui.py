"""W4-C: UI вкладки «Обхід» в браузері (HttpCase, headless Chrome): відкривається без JS-помилок, відмітка пункту,
тост «Завершити обхід», навігація з чотирьох вкладок. Помилки консолі браузера провалюють тест."""

from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from odoo.addons.td_energy.tools import dates

from .common import TAGS

# спільний JS-хелпер очікування (як у `td_energy/tests/test_w1_ui.py`): виняток → console.error → провал тесту
JS_HELPERS = """
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const waitFor = async (check, label, ms = 30000) => {
    const started = Date.now();
    for (;;) {
        const value = check();
        if (value) { return value; }
        if (Date.now() - started > ms) { throw new Error("timeout: " + label); }
        await sleep(100);
    }
};
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const run = (body) => body().then(() => console.log("test successful")).catch((error) => console.error("UI test failed: " + error));
"""


@tagged(*TAGS)
class TestWHUi(HttpCase):
    def _open_round(self):
        """Відкритий обхід «поза розкладом» на реальний «зараз» (HTTP-запит не бачить контексту `f3d_now`)."""
        Round = self.env["td.energy.round"]
        Round.search([]).unlink()
        template = self.env.ref("td_energy_mobile.round_tpl_tp_grsh")
        now = fields.Datetime.now()
        return Round._td_create_round(
            template, self.env["td.energy.round.slot"], dates.local_day(now), now - timedelta(hours=1),
            now + timedelta(hours=1), slot_name="поза розкладом",
        )  # fmt: skip

    def test_round_tab_opens(self):
        """UI-H1: чотири вкладки, «Обхід» малює 6 пунктів; відмітка змінює лічильник; «Завершити» неактивна → тост."""
        rnd = self._open_round()
        self.assertEqual(len(rnd.item_ids), 6)
        self.browser_js(
            "/odoo/action-td_energy.action_td_energy_mobile",
            JS_HELPERS
            + """run(async () => {
            await waitFor(() => $('.o_td_en_mobile .o_td_en_m_tab_round'), "вкладка Обхід");
            if ($$('.o_td_en_m_tab').length !== 4) { throw new Error("вкладки: " + $$('.o_td_en_m_tab').length); }
            $('.o_td_en_m_tab_round').click();
            await waitFor(() => $$('.o_td_wh_item').length === 6, "6 пунктів обходу");
            const count = () => $('.o_td_wh_count').innerText.trim();
            if (count() !== '0 / 6') { throw new Error("лічильник: " + count()); }
            $('.o_td_wh_item .o_td_wh_check').click();
            await waitFor(() => count() === '1 / 6', "лічильник після відмітки");
            $('.o_td_wh_finish').click();
            await waitFor(() => $('.o_notification_body') && $('.o_notification_body').innerText.includes('залишилось 5'), "тост");
            const width = document.documentElement.scrollWidth;
            if (width > document.documentElement.clientWidth) { throw new Error("горизонтальна прокрутка: " + width); }
            });""",
            ready="!!(document.querySelector('.o_td_en_mobile .o_td_en_m_tab'))",
            login="admin",
            timeout=120,
        )
        item = rnd.item_ids.sorted("sequence")[0]
        self.assertTrue(item.done)
        self.assertEqual(rnd.state, "in_progress")
