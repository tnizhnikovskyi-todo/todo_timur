"""W3-C: тести екрана «Енергоресурси» (W3_SPEC AC-58): клієнтська дія, меню, види й браузерний прохід вкладок.

`HttpCase` + headless Chrome; помилки в консолі браузера (`console.error`, необроблені винятки) провалюють тест.
Дані екрана віддає `td.energy.res.dashboard.get_resources` (W3-E), резерви — `td.energy.opportunity` (W3-B).
"""

import json
import re
from pathlib import Path

from odoo.tests import HttpCase, new_test_user, tagged

STATIC_SRC = Path(__file__).resolve().parent.parent / "static" / "src"

# усі п'ять ресурсів; «Тепло» з'являється лише з мостом (теплосчётчики BMS, D-48)
ALL_CODES = ("el", "gas", "heat", "air", "water")

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


@tagged("post_install", "-at_install", "td", "td_energy_resources")
class TestW3Ui(HttpCase):
    # ------------------------------------------------------------------ серверна частина (V-01…V-13)

    def test_client_action(self):
        """V-01: клієнтська дія з тегом OWL-компонента й початковим ресурсом у контексті."""
        action = self.env.ref("td_energy_resources.action_td_energy_resources")
        self.assertEqual(action._name, "ir.actions.client")
        self.assertEqual(action.tag, "td_energy_resources.resources")
        self.assertEqual(action.name, "Енергоресурси заводу")
        self.assertEqual(json.loads(action.context or "{}").get("td_energy_resource"), "el")

    def test_menu_definitions(self):
        """V-13 (3.3): меню, батьки, послідовність, групи й дії."""
        ref = self.env.ref
        user = ref("td_energy.group_td_energy_user")
        cost = ref("td_energy.group_td_energy_cost")
        manager = ref("td_energy.group_td_energy_manager")
        root = ref("td_energy.menu_td_energy")
        config = ref("td_energy.menu_td_energy_config")
        section = ref("td_energy_resources.menu_td_energy_resources_config")
        table = {
            "menu_td_energy_resources": (root, 10, user, "action_td_energy_resources"),
            "menu_td_energy_opportunity": (root, 74, user, "action_td_energy_opportunity"),
            "menu_td_energy_resources_config": (config, 50, manager, None),
            "menu_td_energy_resource": (section, 10, manager, "action_td_energy_resource"),
            "menu_td_energy_price": (section, 20, cost, "action_td_energy_price"),
            "menu_td_energy_point": (section, 30, manager, "action_td_energy_point"),
            "menu_td_energy_meter_resources": (section, 40, manager, "action_td_energy_meter_resources"),
            "menu_td_energy_res_interval": (section, 50, manager, "action_td_energy_res_interval"),
            "menu_td_energy_usage": (section, 60, manager, "action_td_energy_usage"),
            "menu_td_energy_opportunity_rule": (section, 70, manager, "action_td_energy_opportunity_rule"),
            "menu_td_energy_resources_rebind": (section, 80, manager, "action_td_energy_resources_rebind"),
        }
        for xmlid, (parent, sequence, group, action_xmlid) in table.items():
            menu = ref(f"td_energy_resources.{xmlid}")
            self.assertEqual(menu.parent_id, parent, xmlid)
            self.assertEqual(menu.sequence, sequence, xmlid)
            self.assertEqual(menu.group_ids, group, xmlid)
            if action_xmlid:
                self.assertEqual(menu.action, ref(f"td_energy_resources.{action_xmlid}"), xmlid)
            else:
                self.assertFalse(menu.action, xmlid)
        self.assertEqual(ref("td_energy_resources.menu_td_energy_resources").name, "Енергоресурси")

    def test_menu_visibility(self):
        """AC-58: «Енергоресурси» бачить `group_td_energy_user`, розділ налаштувань — лише енергетик."""
        viewer = new_test_user(self.env, login="w3c_viewer", groups="base.group_user,td_energy.group_td_energy_user")
        manager = new_test_user(
            self.env, login="w3c_manager", groups="base.group_user,td_energy.group_td_energy_manager"
        )
        plain = new_test_user(self.env, login="w3c_plain", groups="base.group_user")
        main = self.env.ref("td_energy_resources.menu_td_energy_resources").id
        opportunity = self.env.ref("td_energy_resources.menu_td_energy_opportunity").id
        settings = [
            self.env.ref(f"td_energy_resources.{name}").id
            for name in (
                "menu_td_energy_resources_config",
                "menu_td_energy_resource",
                "menu_td_energy_point",
                "menu_td_energy_meter_resources",
                "menu_td_energy_opportunity_rule",
                "menu_td_energy_resources_rebind",
            )
        ]
        visible = lambda user: set(self.env["ir.ui.menu"].with_user(user)._visible_menu_ids())  # noqa: E731
        seen = visible(viewer)
        self.assertIn(main, seen)
        self.assertIn(opportunity, seen)
        for menu_id in settings:
            self.assertNotIn(menu_id, seen)
        seen = visible(manager)
        self.assertIn(main, seen)
        for menu_id in settings:
            self.assertIn(menu_id, seen)
        self.assertNotIn(main, visible(plain))

    def test_views_compile(self):
        """V-02…V-12: види збираються (arch → get_view) без помилок; розширення форм підхоплюються."""
        cases = [
            ("td.energy.resource", "list"),
            ("td.energy.resource", "form"),
            ("td.energy.price", "list"),
            ("td.energy.price", "form"),
            ("td.energy.price", "search"),
            ("td.energy.point", "list"),
            ("td.energy.point", "form"),
            ("td.energy.point", "search"),
            ("td.energy.point", "kanban"),
            ("td.energy.meter", "form"),
            ("td.energy.res.interval", "list"),
            ("td.energy.res.interval", "pivot"),
            ("td.energy.res.interval", "graph"),
            ("td.energy.res.interval", "search"),
            ("td.energy.usage", "pivot"),
            ("td.energy.usage", "graph"),
            ("td.energy.usage", "search"),
            ("td.energy.opportunity.rule", "list"),
            ("td.energy.opportunity.rule", "form"),
            ("td.energy.opportunity", "list"),
            ("td.energy.opportunity", "form"),
            ("td.energy.opportunity", "search"),
            ("td.energy.opportunity", "kanban"),
            ("td.energy.tariff", "form"),
            ("res.config.settings", "form"),
        ]
        for model, view_type in cases:
            result = self.env[model].get_view(view_type=view_type)
            self.assertTrue(result["arch"], f"{model}/{view_type}")
        meter_form = self.env["td.energy.meter"].get_view(view_type="form")["arch"]
        self.assertIn("td_resource", meter_form)
        self.assertIn("e_react_signal_id", meter_form)
        tariff_form = self.env["td.energy.tariff"].get_view(view_type="form")["arch"]
        self.assertIn("tg_phi_limit", tariff_form)
        settings = self.env["res.config.settings"].get_view(view_type="form")["arch"]
        self.assertIn("td_energy_resources_boiler_eff", settings)

    def test_actions_defined(self):
        """V-02…V-11: дії довідників мають очікувані моделі й режими; ресурси лічильників — без електрики."""
        ref = self.env.ref
        expected = {
            "action_td_energy_resource": ("td.energy.resource", "list,form"),
            "action_td_energy_price": ("td.energy.price", "list,form"),
            "action_td_energy_point": ("td.energy.point", "list,kanban,form"),
            "action_td_energy_meter_resources": ("td.energy.meter", "list,form"),
            "action_td_energy_res_interval": ("td.energy.res.interval", "list,pivot,graph"),
            "action_td_energy_usage": ("td.energy.usage", "pivot,graph"),
            "action_td_energy_opportunity_rule": ("td.energy.opportunity.rule", "list,form"),
            "action_td_energy_opportunity": ("td.energy.opportunity", "list,kanban,form"),
        }
        for xmlid, (model, modes) in expected.items():
            action = ref(f"td_energy_resources.{xmlid}")
            self.assertEqual((action.res_model, action.view_mode), (model, modes), xmlid)
        self.assertIn("resource_id.code", ref("td_energy_resources.action_td_energy_meter_resources").domain)
        self.assertIn("search_default_open", ref("td_energy_resources.action_td_energy_opportunity").context)
        self.assertEqual(ref("td_energy_resources.action_td_energy_resources_rebind")._name, "ir.actions.server")
        self.assertEqual(ref("td_energy_resources.action_td_energy_opportunity_rule_run")._name, "ir.actions.server")

    def test_no_nested_template_literals(self):
        """Вкладені шаблонні рядки в `${…}` ламає мініфікатор бандла — заборонено в static/src."""
        nested = re.compile(r"\$\{[^}]*`")
        offenders = []
        for path in sorted(STATIC_SRC.rglob("*.js")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if nested.search(line):
                    offenders.append(f"{path.relative_to(STATIC_SRC)}:{number}")
        self.assertFalse(offenders, "вкладені шаблонні рядки: %s" % ", ".join(offenders))

    def test_run_rule_action(self):
        """«Запустити зараз»: серверна дія загортає статистику `action_run` у сповіщення."""
        rule = self.env["td.energy.opportunity.rule"].search([], limit=1)
        self.assertTrue(rule, "правила резервів не завантажено")
        action = self.env.ref("td_energy_resources.action_td_energy_opportunity_rule_run")
        result = action.with_context(active_model=rule._name, active_ids=rule.ids, active_id=rule.id).run()
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("Знайдено", result["params"]["message"])

    # ------------------------------------------------------------------ браузер: екран і вкладки (AC-58)

    def _expected_tabs(self):
        """Вкладки, які бачить адміністратор: ресурс має активний лічильник (D-48)."""
        tabs = self.env["td.energy.res.dashboard"].get_resources()["tabs"]
        return [tab["code"] for tab in tabs]

    def _browse(self, ready, body, path="/odoo/action-td_energy_resources.action_td_energy_resources"):
        self.browser_js(
            path,
            JS_HELPERS + f"run(async () => {{ {body} }});",
            ready=f"!!({ready})",
            login="admin",
            timeout=120,
        )

    def test_screen_tabs(self):
        """AC-58: екран відкривається для кожної вкладки без JS-помилок; кожна малює KPI, графік, список, резерви."""
        codes = self._expected_tabs()
        self.assertGreaterEqual(len(codes), 4, f"очікується ≥ 4 вкладок, є: {codes}")
        for code in ("el", "gas", "air", "water"):
            self.assertIn(code, codes)
        self._browse(
            "document.querySelector('.o_td_res .o_td_res_tab')",
            """
            const codes = %s;
            const names = $$('.o_td_res_tab').map((el) => el.dataset.code);
            if (JSON.stringify(names) !== JSON.stringify(codes)) {
                throw new Error("вкладки: " + JSON.stringify(names) + " ≠ " + JSON.stringify(codes));
            }
            for (const code of codes) {
                $('.o_td_res_tab_' + code).click();
                await waitFor(() => $('.o_td_res_tab_' + code).getAttribute('aria-selected') === 'true', "вибір " + code);
                await waitFor(() => $('.o_td_res_body') && $('.o_td_res_body').dataset.resource === code, "дані " + code);
                await waitFor(() => $$('.o_td_res_kpi').length >= 3, "KPI " + code);
                await waitFor(() => $('.o_td_res_chart svg'), "графік " + code);
                await waitFor(() => $('.o_td_res_list_card'), "список " + code);
                await waitFor(() => $('.o_td_res_notes'), "резерви " + code);
            }
            if (!$('.o_td_res_export')) { throw new Error("немає кнопки експорту"); }
            if (!/Енергоресурси заводу/.test($('.o_td_en_h1').textContent)) { throw new Error("заголовок"); }
            """
            % json.dumps(codes),
        )

    def test_notes_settings_and_export_link(self):
        """UI-06 і UI-01: «Усі резерви» відкриває резерви; кнопка експорту несе адресу з `day`."""
        self._browse(
            "document.querySelector('.o_td_res .o_td_res_export')",
            """
            const href = $('.o_td_res_export').dataset.href;
            if (!/^\\/td\\/energy\\/resources\\/export\\?day=\\d{4}-\\d{2}-\\d{2}$/.test(href)) { throw new Error("адреса експорту: " + href); }
            const all = await waitFor(() => $('.o_td_res_all_notes'), "«Усі резерви»");
            all.click();
            await waitFor(() => $('.o_list_view, .o_kanban_view, .o_form_view'), "відкрились резерви економії");
            """,
        )
