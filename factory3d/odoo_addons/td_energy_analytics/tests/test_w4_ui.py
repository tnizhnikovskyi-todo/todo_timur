"""W4-B: екран «Аналітика», меню, види й браузерний прохід (AC-49, AC-59; V-01…V-16).

`HttpCase` + headless Chrome; помилки в консолі браузера (`console.error`, необроблені винятки) провалюють тест.
Дані екрана — `td.energy.analytics.get_dashboard` (W4-A): тут вони мінімальні, повні блоки перевіряє hoot (AC-48).
"""

import json
import re
from datetime import timedelta
from pathlib import Path

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.td_energy.tools import dates

STATIC_SRC = Path(__file__).resolve().parent.parent / "static" / "src"
ACTION = "td_energy_analytics.action_td_energy_analytics"

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
const run = (body) => body()
    .then(() => console.log("test successful"))
    .catch((error) => console.error("UI test failed: " + error));
"""


@tagged("post_install", "-at_install", "td", "td_w4")
class TestW4Ui(HttpCase):
    # ------------------------------------------------------------------ серверна частина (V-01…V-16)

    def test_client_action(self):
        """V-01: клієнтська дія з тегом OWL-компонента й початковим періодом у контексті."""
        action = self.env.ref(ACTION)
        self.assertEqual(action._name, "ir.actions.client")
        self.assertEqual(action.tag, "td_energy_analytics.analytics")
        self.assertEqual(action.name, "Аналітика енергетики заводу")
        self.assertEqual(json.loads(action.context or "{}").get("td_energy_period"), "m")

    def test_menu_definitions(self):
        """V-15 (3.3): меню, батьки, послідовність, групи й дії."""
        ref = self.env.ref
        user = ref("td_energy.group_td_energy_user")
        cost = ref("td_energy.group_td_energy_cost")
        manager = ref("td_energy.group_td_energy_manager")
        root = ref("td_energy.menu_td_energy")
        config = ref("td_energy.menu_td_energy_config")
        section = ref("td_energy_analytics.menu_td_energy_analytics_config")
        table = {
            "menu_td_energy_analytics": (root, 12, user, "action_td_energy_analytics"),
            "menu_td_energy_analytics_config": (config, 60, manager, None),
            "menu_td_energy_area": (section, 10, manager, "action_td_energy_area"),
            "menu_td_energy_driver": (section, 20, manager, "action_td_energy_driver"),
            "menu_td_energy_driver_value": (section, 25, manager, "action_td_energy_driver_value"),
            "menu_td_energy_baseline": (section, 30, manager, "action_td_energy_baseline"),
            "menu_td_energy_enpi": (section, 40, manager, "action_td_energy_enpi"),
            "menu_td_energy_budget": (section, 50, cost, "action_td_energy_budget"),
            "menu_td_energy_daily": (section, 60, manager, "action_td_energy_daily"),
            "menu_td_energy_daily_rebuild": (section, 70, manager, "action_td_energy_daily_rebuild"),
        }
        for xmlid, (parent, sequence, group, action_xmlid) in table.items():
            menu = ref(f"td_energy_analytics.{xmlid}")
            self.assertEqual(menu.parent_id, parent, xmlid)
            self.assertEqual(menu.sequence, sequence, xmlid)
            self.assertEqual(menu.group_ids, group, xmlid)
            if action_xmlid:
                self.assertEqual(menu.action, ref(f"td_energy_analytics.{action_xmlid}"), xmlid)
            else:
                self.assertFalse(menu.action, xmlid)
        self.assertEqual(ref("td_energy_analytics.menu_td_energy_analytics").name, "Аналітика")
        # «Аналітика» (12) іде перед «Завантаження вузлів» (15)
        siblings = self.env["ir.ui.menu"].search([("parent_id", "=", root.id)], order="sequence, id")
        self.assertLess(
            siblings.ids.index(ref("td_energy_analytics.menu_td_energy_analytics").id),
            siblings.ids.index(ref("td_energy.menu_td_energy_overview").id),
        )

    def test_menu_visibility(self):
        """AC-49, AC-59: «Аналітика» — `group_td_energy_user`, розділ налаштувань — «Енергетик», «Бюджет» — вартість."""
        viewer = new_test_user(self.env, login="w4b_viewer", groups="base.group_user,td_energy.group_td_energy_user")
        manager = new_test_user(
            self.env, login="w4b_manager", groups="base.group_user,td_energy.group_td_energy_manager"
        )
        plain = new_test_user(self.env, login="w4b_plain", groups="base.group_user")
        main = self.env.ref("td_energy_analytics.menu_td_energy_analytics").id
        settings = [
            self.env.ref(f"td_energy_analytics.{name}").id
            for name in (
                "menu_td_energy_analytics_config",
                "menu_td_energy_area",
                "menu_td_energy_driver",
                "menu_td_energy_baseline",
                "menu_td_energy_enpi",
                "menu_td_energy_budget",
                "menu_td_energy_daily",
                "menu_td_energy_daily_rebuild",
            )
        ]
        budget = self.env.ref("td_energy_analytics.menu_td_energy_budget").id
        visible = lambda user: set(self.env["ir.ui.menu"].with_user(user)._visible_menu_ids())  # noqa: E731
        seen = visible(viewer)
        self.assertIn(main, seen)
        for menu_id in settings:
            self.assertNotIn(menu_id, seen)
        seen = visible(manager)
        self.assertIn(main, seen)
        for menu_id in settings:
            self.assertIn(menu_id, seen)
        self.assertNotIn(main, visible(plain))
        # «Бюджет енергії» — лише з групою вартості (її не має користувач без `cost`)
        cost_only = new_test_user(self.env, login="w4b_cost", groups="base.group_user,td_energy.group_td_energy_cost")
        self.assertNotIn(budget, visible(viewer))
        self.assertIn(budget, visible(manager))
        self.assertTrue(self.env.ref("td_energy_analytics.menu_td_energy_budget").group_ids <= cost_only.all_group_ids)

    def test_views_compile(self):
        """V-02…V-16: види збираються (arch → get_view) без помилок; розширення форм і пошуку підхоплюються."""
        cases = [
            ("td.energy.area", "list"),
            ("td.energy.area", "form"),
            ("td.energy.driver", "list"),
            ("td.energy.driver", "form"),
            ("td.energy.driver.value", "list"),
            ("td.energy.driver.value", "pivot"),
            ("td.energy.driver.value", "search"),
            ("td.energy.baseline", "list"),
            ("td.energy.baseline", "form"),
            ("td.energy.enpi", "list"),
            ("td.energy.enpi", "graph"),
            ("td.energy.enpi", "pivot"),
            ("td.energy.enpi", "search"),
            ("td.energy.budget", "list"),
            ("td.energy.budget", "form"),
            ("td.energy.daily", "list"),
            ("td.energy.daily", "pivot"),
            ("td.energy.daily", "graph"),
            ("td.energy.daily", "search"),
            ("td.energy.daily.rebuild.wizard", "form"),
            ("td.energy.node", "form"),
            ("td.energy.alloc", "search"),
            ("product.template", "form"),
            ("res.config.settings", "form"),
        ]
        for model, view_type in cases:
            result = self.env[model].get_view(view_type=view_type)
            self.assertTrue(result["arch"], f"{model}/{view_type}")
        self.assertIn("area_id", self.env["td.energy.node"].get_view(view_type="form")["arch"])
        self.assertIn("group_product", self.env["td.energy.alloc"].get_view(view_type="search")["arch"])
        self.assertIn(
            "td_plate_area_m2",
            self.env["product.template"].get_view(self.env.ref("product.product_template_only_form_view").id, "form")[
                "arch"
            ],
        )
        settings = self.env["res.config.settings"].get_view(view_type="form")["arch"]
        for name in ("daily_close_h", "catchup_days", "forecast_weeks", "forecast_min_days", "r2_min",
                     "baseline_min_days", "refresh_s", "top_equipment", "top_mo"):  # fmt: skip
            self.assertIn("td_energy_analytics_" + name, settings)

    def test_actions_defined(self):
        """V-02…V-11: дії довідників мають очікувані моделі й режими; майстер — `target=new`."""
        ref = self.env.ref
        expected = {
            "action_td_energy_area": ("td.energy.area", "list,form"),
            "action_td_energy_driver": ("td.energy.driver", "list,form"),
            "action_td_energy_driver_value": ("td.energy.driver.value", "list,pivot"),
            "action_td_energy_baseline": ("td.energy.baseline", "list,form"),
            "action_td_energy_enpi": ("td.energy.enpi", "list,graph,pivot"),
            "action_td_energy_budget": ("td.energy.budget", "list,form"),
            "action_td_energy_daily": ("td.energy.daily", "list,pivot,graph"),
            "action_td_energy_daily_rebuild": ("td.energy.daily.rebuild.wizard", "form"),
        }
        for xmlid, (model, modes) in expected.items():
            action = ref(f"td_energy_analytics.{xmlid}")
            self.assertEqual((action.res_model, action.view_mode), (model, modes), xmlid)
        self.assertEqual(ref("td_energy_analytics.action_td_energy_daily_rebuild").target, "new")

    def test_no_nested_template_literals(self):
        """Вкладені шаблонні рядки в `${…}` ламає мініфікатор бандла — заборонено в static/src."""
        nested = re.compile(r"\$\{[^}]*`")
        offenders = []
        for path in sorted(STATIC_SRC.rglob("*.js")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if nested.search(line):
                    offenders.append(f"{path.relative_to(STATIC_SRC)}:{number}")
        self.assertFalse(offenders, "вкладені шаблонні рядки: %s" % ", ".join(offenders))

    # ------------------------------------------------------------------ браузер: екран і періоди (AC-49)

    def _fixture_screen(self):
        """Мінімум даних за 14 діб (плюс сьогодні), щоб блоки екрана мали що малювати."""
        daily = self.env["td.energy.daily"]
        node = self.env["td.energy.node"].search([("code", "=", "SAW-1")], limit=1)
        today = dates.local_day(dates.now_utc(self.env))
        built = dates.now_utc(self.env)
        for i in range(15):
            day = today - timedelta(days=i)
            common = {"day": day, "built_at": built, "quality": "ok"}
            daily.create({**common, "scope": "plant", "qty": 5000.0 + 10 * i, "import_qty": 4800.0})
            daily.create({**common, "scope": "node", "node_id": node.id, "area_id": node.area_id.id, "qty": 800.0})

    def _browse(self, ready, body):
        self.browser_js(
            f"/odoo/action-{ACTION}",
            JS_HELPERS + f"run(async () => {{ {body} }});",
            ready=f"!!({ready})",
            login="admin",
            timeout=120,
        )

    def test_screen_periods(self):
        """AC-49: екран відкривається й перемикає періоди `w`, `m`, `q`, `y` без JS-помилок; блоки на місці."""
        self._fixture_screen()
        self._browse(
            "document.querySelector('.o_td_an .o_td_an_kpi')",
            """
            if (!/Аналітика енергетики заводу/.test($('.o_td_en_h1').textContent)) { throw new Error("заголовок"); }
            for (const period of ["w", "q", "y", "m"]) {
                $('.o_td_an_period--' + period).click();
                const button = $('.o_td_an_period--' + period);
                await waitFor(() => button.getAttribute('aria-pressed') === 'true', "період " + period);
                await waitFor(() => !$('.o_td_an_body.o_td_an_loading'), "завантаження " + period);
                await waitFor(() => $$('.o_td_an_kpi').length >= 6, "KPI " + period);
                await waitFor(() => $('.o_td_an_stack'), "стек " + period);
                await waitFor(() => $$('.o_td_an_hm_cell').length === 168, "теплокарта " + period);
                await waitFor(() => $('.o_td_an_enpi'), "EnPI " + period);
                await waitFor(() => $('.o_td_an_cut'), "розріз " + period);
                await waitFor(() => $('.o_td_an_opps'), "резерви " + period);
                if ($('.o_td_an_error')) { throw new Error("блок із помилкою: " + $('.o_td_an_error').textContent); }
            }
            if (!$('.o_td_an_report')) { throw new Error("немає кнопки звіту"); }
            """,
        )

    def test_screen_dims(self):
        """UI-06: кожна вкладка розрізу вантажить таблицю або порожній стан без помилок."""
        self._fixture_screen()
        self._browse(
            "document.querySelector('.o_td_an .o_td_an_cut')",
            """
            for (const dim of ["eq", "mo", "prod", "shift", "area"]) {
                $('.o_td_an_tab--' + dim).click();
                const tab = $('.o_td_an_tab--' + dim);
                await waitFor(() => tab.getAttribute('aria-selected') === 'true', "вкладка " + dim);
                await waitFor(() => $('.o_td_an_cut .o_td_an_table, .o_td_an_cut .o_td_an_nodata'), "розріз " + dim);
                if ($('.o_td_an_error')) { throw new Error("блок із помилкою: " + $('.o_td_an_error').textContent); }
            }
            """,
        )

    def test_shift_report_action_via_web_client(self):
        """C-02: серверну дію «Звіт за зміну» запускає клієнт Пульту (`/web/action/load` → `/web/action/run`) від імені
        звичайного користувача «Енергетики»: у відповідь — `ir.actions.report`."""
        xmlid = "td_energy_analytics.action_td_energy_shift_report"
        new_test_user(
            self.env, login="w4b_http", password="w4b_http", groups="base.group_user,td_energy.group_td_energy_user"
        )
        self.authenticate("w4b_http", "w4b_http")

        def call(route, **params):
            body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params})
            response = self.url_open(route, data=body, headers={"Content-Type": "application/json"})
            payload = response.json()
            self.assertNotIn("error", payload, payload.get("error"))
            return payload["result"]

        loaded = call("/web/action/load", action_id=xmlid)
        self.assertEqual(loaded["type"], "ir.actions.server")
        result = call("/web/action/run", action_id=loaded["id"], context={})
        self.assertEqual(result["type"], "ir.actions.report")
        self.assertEqual(result["report_name"], "td_energy_analytics.report_shift_document")
