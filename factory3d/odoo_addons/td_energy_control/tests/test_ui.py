"""W2-B: тест `TestControlUi` (AC-294): екран «Керування» відкривається без JS-помилок; меню, види, чип зв'язку.

`HttpCase` + headless Chrome; помилки в консолі браузера (`console.error`, необроблені винятки) провалюють тест.
Дані екрана віддає `td.energy.control.get_control()` (W2-A).
"""

from datetime import timedelta

from odoo import Command, fields
from odoo.tests import HttpCase, tagged

from .common import TAGS

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

MENUS = {
    # xml-id: (батько, seq, група, дія)
    "menu_td_energy_control": (
        "td_energy.menu_td_energy",
        8,
        "td_energy.group_td_energy_user",
        "action_td_energy_control",
    ),
    "menu_td_energy_action": (
        "td_energy.menu_td_energy",
        9,
        "td_energy.group_td_energy_user",
        "action_td_energy_action",
    ),
    "menu_td_energy_scenario": (
        "td_energy.menu_td_energy_config",
        50,
        "td_energy.group_td_energy_manager",
        "action_td_energy_scenario",
    ),
    "menu_td_energy_shed_item": (
        "td_energy.menu_td_energy_config",
        51,
        "td_energy.group_td_energy_manager",
        "action_td_energy_shed_item",
    ),
    "menu_td_energy_schedule_slot": (
        "td_energy.menu_td_energy_config",
        52,
        "td_energy.group_td_energy_manager",
        "action_td_energy_schedule_slot",
    ),
    "menu_td_energy_interlock": (
        "td_energy.menu_td_energy_config",
        53,
        "td_energy.group_td_energy_manager",
        "action_td_energy_interlock",
    ),
    "menu_td_energy_command_kind": (
        "td_energy.menu_td_energy_config",
        54,
        "td_factory3d.group_td_admin",
        "action_td_energy_command_kind",
    ),
    "menu_td_energy_control_state": (
        "td_energy.menu_td_energy_config",
        55,
        "td_factory3d.group_td_admin",
        "action_td_energy_control_state",
    ),
}

VIEWS = [
    ("td.energy.scenario", "list"),
    ("td.energy.scenario", "form"),
    ("td.energy.shed.item", "list"),
    ("td.energy.shed.item", "form"),
    ("td.energy.command.kind", "list"),
    ("td.energy.command.kind", "form"),
    ("td.energy.interlock", "list"),
    ("td.energy.interlock", "form"),
    ("td.energy.action", "list"),
    ("td.energy.action", "form"),
    ("td.energy.action", "search"),
    ("td.energy.action", "pivot"),
    ("td.energy.schedule.slot", "list"),
    ("td.energy.schedule.slot", "form"),
    ("td.energy.schedule.slot", "search"),
    ("td.energy.control.state", "list"),
    ("td.energy.control.state", "form"),
    ("td.command", "form"),
    ("res.config.settings", "form"),
]


@tagged(*TAGS)
class TestControlUi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chief = cls.env.ref("td_energy.group_td_energy_chief")
        cls.env.ref("base.user_admin").write({"group_ids": [Command.link(chief.id)]})
        cls.env["ir.config_parameter"].sudo().set_param("td.energy_control.remote_switching_enabled", "True")
        cls.env["ir.config_parameter"].sudo().set_param("td.energy_control.write_enabled", "True")
        cls.env["ir.config_parameter"].sudo().set_param("td.energy_control.automation_enabled", "True")

    # ------------------------------------------------------------------ серверна частина (V-35…V-45)

    def test_client_action(self):
        """V-35: клієнтська дія з тегом OWL-компонента й назвою."""
        action = self.env.ref("td_energy_control.action_td_energy_control")
        self.assertEqual(action._name, "ir.actions.client")
        self.assertEqual(action.tag, "td_energy_control.control")
        self.assertEqual(action.name, "Керування енергетикою заводу")

    def test_menus(self):
        """V-45 (розд. 3.3): батьки, послідовність, групи й дії меню «Керування», «Журнал команд», налаштувань."""
        for xmlid, (parent, sequence, group, action) in MENUS.items():
            menu = self.env.ref(f"td_energy_control.{xmlid}")
            self.assertEqual(menu.parent_id, self.env.ref(parent), xmlid)
            self.assertEqual(menu.sequence, sequence, xmlid)
            self.assertIn(self.env.ref(group), menu.group_ids, xmlid)
            self.assertEqual(menu.action, self.env.ref(f"td_energy_control.{action}"), xmlid)
        self.assertEqual(self.env.ref("td_energy_control.menu_td_energy_control").name, "Керування")
        self.assertEqual(self.env.ref("td_energy_control.menu_td_energy_action").name, "Журнал команд")

    def test_views_compile(self):
        """V-36…V-44: види збираються (arch → get_view) без помилок."""
        for model, view_type in VIEWS:
            result = self.env[model].get_view(view_type=view_type)
            self.assertTrue(result["arch"], f"{model}/{view_type}")

    def test_action_views(self):
        """V-41, V-42: журнал — list/form/pivot із пошуком; слоти розкладу — кнопка «Перебудувати план»."""
        action = self.env.ref("td_energy_control.action_td_energy_action")
        self.assertEqual(action.view_mode, "list,form,pivot")
        arch = self.env["td.energy.schedule.slot"].get_view(view_type="list")["arch"]
        self.assertIn("action_rebuild_plan", arch)
        search = self.env["td.energy.action"].get_view(view_type="search")["arch"]
        for name in ("mine", "awaiting_second", "errors", "auto", "today"):
            self.assertIn(f'name="{name}"', search)

    def test_settings_block(self):
        """V-44: у блоці td_energy налаштувань є розділи «Керування» з усіма td_energy_control_* полями."""
        arch = self.env["res.config.settings"].get_view(view_type="form")["arch"]
        for name in (
            "td_energy_control_write_enabled",
            "td_energy_control_automation_enabled",
            "td_energy_control_remote_switching_enabled",
            "td_energy_control_confirm_ttl_s",
            "td_energy_control_verify_timeout_s",
            "td_energy_control_export_advice_min",
        ):
            self.assertIn(name, arch)

    # ------------------------------------------------------------------ браузер (AC-294)

    def _state(self, mode, connected):
        state = self.env["td.energy.control.state"].get()
        state.sudo().with_context(td_energy_control_internal=True).write(
            {
                "engine_mode": mode,
                "heartbeat_at": fields.Datetime.now() + timedelta(hours=1)
                if connected
                else fields.Datetime.now() - timedelta(days=1),
            }
        )

    def _open_control(self, ready, body):
        self.browser_js(
            "/odoo/action-td_energy_control.action_td_energy_control",
            JS_HELPERS + f"run(async () => {{ {body} }});",
            ready=f"!!({ready})",
            login="admin",
            timeout=120,
        )

    def test_control_opens(self):
        """AC-294: экран відкривається без JS-помилок: h1, інформаційна смуга, чип зв'язку, 6 карток, 8 плиток."""
        self._state("auto", True)
        self._open_control(
            "document.querySelector('.o_td_en_control .o_td_en_h1')",
            """
            if ($('.o_td_en_h1').textContent.trim() !== 'Керування енергетикою заводу') { throw new Error("h1"); }
            if (!$('.o_td_en_info').textContent.includes('контролер ГРЩ і збирач сигналів')) { throw new Error("інформаційна смуга"); }
            await waitFor(() => $$('.o_td_en_sc').length === 6, "6 карток сценаріїв");
            await waitFor(() => $$('.o_td_en_cmd').length === 8, "8 плиток команд");
            if ($$('.o_td_en_shed_row').length < 1) { throw new Error("пріоритети"); }
            await waitFor(() => $$('.o_td_en_tl_row').length === 6, "6 рядків розкладу");
            const chip = $('.o_td_en_engine_chip');
            if (!chip.textContent.includes('на зв') || !chip.classList.contains('o_td_en_engine_chip--ok')) {
                throw new Error("чип зв'язку: " + chip.textContent);
            }
            """,
        )

    def test_engine_chip_paused(self):
        """AC-294: чип зв'язку, стан 2 — автоматику призупинено."""
        self._state("hold", True)
        self._open_control(
            "document.querySelector('.o_td_en_control .o_td_en_engine_chip')",
            """
            const chip = $('.o_td_en_engine_chip');
            if (!chip.textContent.includes('призупинено') || !chip.classList.contains('o_td_en_engine_chip--warn')) {
                throw new Error("чип: " + chip.textContent);
            }
            """,
        )

    def test_engine_chip_automation_off(self):
        """AC-294: автоматика вимкнена прапором (запобіжник 6) — чип «Автоматику призупинено», жовтий."""
        self._state("auto", True)
        self.env["ir.config_parameter"].sudo().set_param("td.energy_control.automation_enabled", "False")
        self._open_control(
            "document.querySelector('.o_td_en_control .o_td_en_engine_chip')",
            """
            const chip = $('.o_td_en_engine_chip');
            if (!chip.textContent.includes('призупинено') || !chip.classList.contains('o_td_en_engine_chip--warn')) {
                throw new Error("чип: " + chip.textContent);
            }
            """,
        )

    def test_engine_chip_offline(self):
        """AC-294: чип зв'язку, стан 3 — збирач не на зв'язку."""
        self._state("auto", False)
        self._open_control(
            "document.querySelector('.o_td_en_control .o_td_en_engine_chip')",
            """
            const chip = $('.o_td_en_engine_chip');
            if (!chip.textContent.includes('не на зв') || !chip.classList.contains('o_td_en_engine_chip--bad')) {
                throw new Error("чип: " + chip.textContent);
            }
            """,
        )

    def test_scenario_switch_opens_dialog(self):
        """AC-295 (браузер): клік по перемикачу відкриває діалог і не міняє стан без підтвердження."""
        self._state("auto", True)
        self._open_control(
            "document.querySelector('.o_td_en_control .o_td_en_sc')",
            """
            const sw = $('.o_td_en_sc .o_td_en_switch');
            const before = sw.getAttribute('aria-checked');
            sw.click();
            await waitFor(() => $('.o_td_en_cd [class*=o_td_en_cd_ok]'), "діалог підтвердження");
            if ($('.o_td_en_sc .o_td_en_switch').getAttribute('aria-checked') !== before) { throw new Error("стан змінено"); }
            $('.o_td_en_cd .o_td_en_cd_cancel').click();
            await waitFor(() => !$('.o_td_en_cd'), "закриття діалогу");
            """,
        )
