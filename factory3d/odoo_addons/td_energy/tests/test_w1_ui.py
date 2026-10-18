"""W1-B: тести W1 «ui» (W1_SPEC розд. 12–13): клієнтські дії відкриваються без JS-помилок, меню в браузері (AC-144).

`HttpCase` + headless Chrome; помилки в консолі браузера (`console.error`, необроблені винятки) провалюють тест.
Дані Пульту/картки/мобільного/генерації віддає `td.energy.dashboard` (W1-A).
"""

import re
from pathlib import Path

from odoo.tests import HttpCase, tagged

STATIC_SRC = Path(__file__).resolve().parent.parent / "static" / "src"

# спільний JS-хелпер очікування: kind of `waitFor(selector)`; будь-який виняток → console.error → провал тесту
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


@tagged("post_install", "-at_install", "td", "td_energy")
class TestW1Ui(HttpCase):
    # ------------------------------------------------------------------ серверна частина (V-22…V-34, V-33)

    def test_client_actions(self):
        """V-22…V-25: клієнтські дії з тегами OWL-компонентів."""
        expected = {
            "action_td_energy_pult": "td_energy.pult",
            "action_td_energy_node_card": "td_energy.node_card",
            "action_td_energy_mobile": "td_energy.mobile",
            "action_td_energy_generation": "td_energy.generation",
        }
        for xmlid, tag in expected.items():
            action = self.env.ref(f"td_energy.{xmlid}")
            self.assertEqual(action._name, "ir.actions.client")
            self.assertEqual(action.tag, tag)
        self.assertIn("td_energy_period", self.env.ref("td_energy.action_td_energy_pult").context)

    def test_menu_definitions(self):
        """V-33 (розд. 3.3): ключові меню W1, батьки, послідовність, групи."""
        group_user = self.env.ref("td_energy.group_td_energy_user")
        root = self.env.ref("td_energy.menu_td_energy")
        table = {
            "menu_td_energy_pult": (root, 5, "td_energy.action_td_energy_pult"),
            "menu_td_energy_mobile": (root, 6, "td_energy.action_td_energy_mobile"),
            "menu_td_energy_overview": (root, 15, "td_energy.action_td_energy_overview"),
            "menu_td_energy_nodes": (root, 25, "td_energy.action_td_energy_node_list"),
            "menu_td_energy_generation": (root, 35, None),
            "menu_td_energy_outage_plan": (root, 72, "td_energy.action_td_energy_outage_plan"),
            "menu_td_energy_event": (root, 80, "td_energy.action_td_energy_event"),
        }
        for xmlid, (parent, sequence, action_xmlid) in table.items():
            menu = self.env.ref(f"td_energy.{xmlid}")
            self.assertEqual(menu.parent_id, parent, xmlid)
            self.assertEqual(menu.sequence, sequence, xmlid)
            self.assertIn(group_user, menu.group_ids, xmlid)
            if action_xmlid:
                self.assertEqual(menu.action, self.env.ref(action_xmlid), xmlid)
        overview = self.env.ref("td_energy.menu_td_energy_generation_overview")
        self.assertEqual(overview.parent_id, self.env.ref("td_energy.menu_td_energy_generation"))
        self.assertEqual(overview.action, self.env.ref("td_energy.action_td_energy_generation"))
        self.assertEqual(self.env.ref("td_energy.menu_td_energy_overview").name, "Завантаження вузлів")
        self.assertEqual(self.env.ref("td_energy.menu_td_energy_event").name, "Події")
        advice = self.env.ref("td_energy.menu_td_energy_advice")
        self.assertEqual(advice.parent_id, self.env.ref("td_energy.menu_td_energy_config"))
        self.assertIn(self.env.ref("td_energy.group_td_energy_manager"), advice.group_ids)

    def test_views_compile(self):
        """V-26…V-32, V-34: види W1 збираються (arch → get_view) без помилок."""
        cases = [
            ("td.energy.event", "list"),
            ("td.energy.event", "form"),
            ("td.energy.event", "search"),
            ("td.energy.node", "form"),
            ("td.energy.node", "list"),
            ("td.energy.meter", "form"),
            ("td.energy.meter", "list"),
            ("td.energy.interval", "list"),
            ("td.energy.interval", "search"),
            ("td.energy.outage.plan", "list"),
            ("td.energy.outage.plan", "form"),
            ("td.energy.outage.plan", "search"),
            ("td.energy.advice", "list"),
            ("td.energy.advice", "form"),
            ("td.energy.ticket.wizard", "form"),
        ]
        for model, view_type in cases:
            result = self.env[model].get_view(view_type=view_type)
            self.assertTrue(result["arch"], f"{model}/{view_type}")

    def test_node_action_list(self):
        """V-27: `action_td_energy_node_list` — список видів, що мають картку/схему; групування за видом."""
        action = self.env.ref("td_energy.action_td_energy_node_list")
        self.assertEqual(action.view_mode, "list,form")
        self.assertIn("search_default_group_kind", action.context)
        node = self.env["td.energy.node"].search([("code", "=", "BW-2")], limit=1)
        if node:
            card = node.action_open_card()
            self.assertEqual(card["tag"], "td_energy.node_card")
            self.assertEqual(card["params"]["code"], "BW-2")

    def test_no_nested_template_literals(self):
        """Вкладені шаблонні рядки в `${…}` ламає мініфікатор бандла (зникають пробіли) — заборонено в static/src."""
        nested = re.compile(r"\$\{[^}]*`")
        offenders = []
        for path in sorted(STATIC_SRC.rglob("*.js")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if nested.search(line):
                    offenders.append(f"{path.relative_to(STATIC_SRC)}:{number}")
        self.assertFalse(offenders, "вкладені шаблонні рядки: %s" % ", ".join(offenders))

    # ------------------------------------------------------------------ браузер: клієнтські дії й меню (AC-144)

    def _browse(self, action_xmlid, ready, body):
        self.browser_js(
            f"/odoo/action-td_energy.{action_xmlid}",
            JS_HELPERS + f"run(async () => {{ {body} }});",
            ready=f"!!({ready})",
            login="admin",
            timeout=120,
        )

    def test_pult_opens(self):
        """UI-01: Пульт відкривається, малює KPI, схему, профіль, тривоги; період і вибір вузла працюють."""
        self._browse(
            "action_td_energy_pult",
            "document.querySelector('.o_td_en_pult .o_td_en_kpi')",
            """
            if ($$('.o_td_en_kpi').length !== 6) { throw new Error("KPI: " + $$('.o_td_en_kpi').length); }
            await waitFor(() => $$('button.o_td_en_node').length > 0, "вузли схеми");
            await waitFor(() => $('.o_td_en_profile svg'), "профіль доби");
            await waitFor(() => $('.o_td_en_alarms_card'), "тривоги");
            $('.o_td_en_period_shift').click();
            await waitFor(() => $('.o_td_en_period_shift').getAttribute('aria-pressed') === 'true', "період Зміна");
            const node = await waitFor(() => $$('button.o_td_en_node').find((el) => el.dataset.nodeCode === 'T1'), "вузол T1");
            node.click();
            await waitFor(() => $('.o_td_en_sel'), "панель вибраного вузла");
            node.click();
            await waitFor(() => !$('.o_td_en_sel'), "зняття вибору");
            """,
        )

    def test_node_card_from_pult(self):
        """UI-05: з Пульту «Відкрити картку вузла» відкриває картку; діалог відключення відкривається й закривається."""
        self._browse(
            "action_td_energy_pult",
            "document.querySelector('.o_td_en_pult button.o_td_en_node')",
            """
            const node = await waitFor(() => $$('button.o_td_en_node').find((el) => el.dataset.nodeCode === 'BW-2'), "вузол BW-2");
            node.click();
            const open = await waitFor(() => $('.o_td_en_sel_card'), "кнопка картки");
            open.click();
            await waitFor(() => $('.o_td_en_node_card .o_td_en_kpi'), "картка вузла");
            $('.o_td_en_plan_outage').click();
            await waitFor(() => $('.o_td_en_dialog .o_td_en_out_submit'), "діалог відключення");
            $('.o_dialog .btn-secondary').click();
            await waitFor(() => !$('.o_td_en_dialog'), "закриття діалогу");
            """,
        )

    def test_generation_opens(self):
        """UI-08: «Генерація й резерв» малює картки СЕС, КГУ, BESS, АВР."""
        self._browse(
            "action_td_energy_generation",
            "document.querySelector('.o_td_en_generation .o_td_en_gen_card')",
            """
            if ($$('.o_td_en_gen_card').length < 4) { throw new Error("картки: " + $$('.o_td_en_gen_card').length); }
            """,
        )

    def test_mobile_opens(self):
        """UI-09: мобільний екран — три вкладки, перемикання."""
        self._browse(
            "action_td_energy_mobile",
            "document.querySelector('.o_td_en_mobile .o_td_en_m_tab')",
            """
            if ($$('.o_td_en_m_tab').length < 3) { throw new Error("вкладки: " + $$('.o_td_en_m_tab').length); }
            for (const id of ['alarms', 'scheme', 'state']) {
                $('.o_td_en_m_tab_' + id).click();
                await waitFor(() => $('.o_td_en_m_tab_' + id).getAttribute('aria-pressed') === 'true', "вкладка " + id);
            }
            """,
        )

    def test_menus_in_browser(self):
        """AC-144 (браузер): у меню «Енергетика» є Пульт, «Генерація й резерв» → «Огляд», Події; верхнього «Генератор» немає."""
        self._browse(
            "action_td_energy_generation",
            "document.querySelector('.o_menu_sections .dropdown-toggle')",
            """
            const toggle = await waitFor(() => $$('.o_menu_sections .dropdown-toggle').find((el) => el.innerText.trim() === 'Енергетика'), "меню Енергетика");
            if ($$('.o_menu_sections .dropdown-toggle').some((el) => el.innerText.trim() === 'Генератор')) {
                throw new Error("верхнє меню «Генератор» не має існувати");
            }
            toggle.click();
            await waitFor(() => $('.o-dropdown--menu'), "випадне меню");
            const texts = $$('.o-dropdown--menu .dropdown-item, .o-dropdown--menu .dropdown-header').map((el) => el.innerText.trim());
            for (const name of ['Пульт', 'Чергування (телефон)', 'Вузли мережі', 'Генерація й резерв', 'Огляд', 'Планові відключення', 'Події']) {
                if (!texts.includes(name)) { throw new Error("немає пункту «" + name + "»: " + texts.join(' | ')); }
            }
            if (texts.includes('Журнал подій')) { throw new Error("«Журнал подій» перейменовано на «Події»"); }
            """,
        )
