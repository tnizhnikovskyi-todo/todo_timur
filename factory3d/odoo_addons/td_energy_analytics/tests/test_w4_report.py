"""W4-B: PDF-звіти й майстри (AC-44, AC-46, AC-47; M-13, M-16, R-18, R-19).

PDF формує `wkhtmltopdf`, якого в тестовому середовищі може не бути, тому перевіряється HTML (`_render_qweb_html`) і
дія `ir.actions.report`. Час — ключ контексту `f3d_now` (за замовчуванням субота 17.10.2026 14:20 Київ).
"""

import html as html_lib
import re
from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

MANAGEMENT = "td_energy_analytics.report_management_document"
SHIFT = "td_energy_analytics.report_shift_document"
MONDAY = date(2026, 10, 19)


def _text(markup):
    """Видимий текст HTML: без тегів, стилів, з нормалізованими пробілами (в т. ч. нерозривними)."""
    markup = re.sub(r"<style.*?</style>", " ", markup, flags=re.S)
    markup = re.sub(r"<[^>]+>", " ", markup)
    return re.sub(r"\s+", " ", html_lib.unescape(markup)).strip()


@tagged(*TAGS)
class TestW4Report(TestW4Common):
    # --- допоміжні -----------------------------------------------------------------------------------------
    def _wizard(self, user, kind="management", **vals):
        return self.env["td.energy.report.wizard"].with_user(user).create({"kind": kind, **vals})

    def _render(self, user, report, wizard):
        markup, kind = self.env["ir.actions.report"].with_user(user)._render_qweb_html(report, wizard.ids)
        self.assertEqual(kind, "html")
        return markup.decode()

    def _management(self, user, **vals):
        return self._render(user, MANAGEMENT, self._wizard(user, "management", **vals))

    def _fixture_30d(self, full_enpi=True):
        """«Макет 17.10» + бюджет жовтня + вузол ділянки + резерви (R-18); `full_enpi` — EnPI на все вікно 12 тижнів
        (покриття ≥ 50 %, R-05), інакше лише 30 діб макета (покриття 36 %: «Недостатньо даних»)."""
        el, _gas = self._mockup_1710()
        if full_enpi:
            for day in self._days(TODAY - timedelta(days=83), 54):
                self.Enpi.create(
                    {"baseline_id": el.id, "day": day, "actual": 6000.0, "expected": 6000.0 / 0.94, "quality": "ok"}
                )
        self._budget(date(2026, 10, 1), 1950000.0)
        self._daily(TODAY, scope="node", node="SAW-1", qty=100.0, cost=840.0)
        self._opps()

    def _opps(self):
        rule = self.env.ref("td_energy_resources.rule_vent_offshift")
        Opp = self.env["td.energy.opportunity"]
        recs = Opp
        for i, saving in enumerate((15500.0, 12000.0, 5500.0, 3000.0)):
            recs |= Opp.create(
                {
                    "rule_id": rule.id, "dedup_key": "w4b:%d" % i, "title": "Резерв %d" % i, "text": "Текст %d" % i,
                    "est_saving_month": saving, "est_qty_month": 100.0,
                    "actions": [{"code": "night_mode", "label": "Сценарій BMS", "kind": "control",
                                 "params": {"intent": "vent_night_mode"}}],
                }
            )  # fmt: skip
        recs[0].with_user(self.u_eng).action_plan_toggle()
        return recs

    # --- AC-44: звіт для керівництва ----------------------------------------------------------------------
    def test_ac44_management_report(self):
        self._fixture_30d()
        wizard = self._wizard(self.u_cost, "management", period="m")
        markup = self._render(self.u_cost, MANAGEMENT, wizard)
        text = _text(markup)
        self.assertIn("Звіт для керівництва · Енергетика", text)
        self.assertIn("18.09.2026 – 17.10.2026 · 30 днів", text)
        self.assertIn("Автор: %s" % self.u_cost.name, text)
        self.assertIn("Сформовано: 17.10.2026 14:20", text)
        # 2. таблиця 7 KPI
        self.assertEqual(len(re.findall(r'data-kpi="', markup)), 7)
        self.assertIn("Підсумки періоду", text)
        self.assertIn("186 400", text)
        self.assertIn("−6 % до бази", text)
        self.assertIn("1 937 880", text)
        # 3. EnPI, параметри моделі бази
        self.assertIn("EnPI проти бази (ISO 50001)", text)
        self.assertIn("EnPI 0,94 · економія 6 % до бази", text)
        self.assertIn("1 820 кВт·год/добу + 4,1 × Площа плит (м²)", text)
        self.assertIn("R² 0,93", text)
        self.assertIn("01.11.2025 – 30.11.2025", text)
        self.assertRegex(markup, r'<path(?=[^>]*stroke="#714B67")[^>]*\sd="M[^"]+"')
        # 4. бюджет (cost)
        self.assertIn("Бюджет енергії · жовтень", text)
        self.assertIn("1 950 000", text)
        # 5. ділянки, 6. топ-5 обладнання, 7. резерви, 8. примітки
        self.assertIn("Енергія за ділянками", text)
        self.assertIn("Розкрій", text)
        self.assertIn("Найбільші споживачі", text)
        self.assertIn("Резерви економії", text)
        self.assertIn("У плані: 15 500 ₴/міс з 36 000 ₴/міс", text)
        self.assertIn("Резерв 0", text)
        self.assertIn("Примітки", text)

    def test_ac44_enpi_coverage_note(self):
        """База є, але EnPI за 12 тижнів покриває < 50 % вікна: замість «База не задана» — «Недостатньо даних»."""
        self._fixture_30d(full_enpi=False)
        text = _text(self._management(self.u_cost, period="m"))
        self.assertIn("Недостатньо даних для розрахунку EnPI", text)
        self.assertNotIn("База не задана", text)
        self.assertIn("1 820 кВт·год/добу", text)

    def test_ac44_paper_format(self):
        report = self.env.ref("td_energy_analytics.report_td_energy_management")
        self.assertEqual((report.model, report.report_type), ("td.energy.report.wizard", "qweb-pdf"))
        self.assertEqual(report.report_name, MANAGEMENT)
        self.assertTrue(report.print_report_name.startswith("'Енергетика_звіт_%s'"))
        paper = report.paperformat_id
        self.assertEqual((paper.format, paper.orientation), ("A4", "Portrait"))
        self.assertEqual((paper.margin_top, paper.margin_bottom, paper.margin_left, paper.margin_right), (12,) * 4)
        shift = self.env.ref("td_energy_analytics.report_td_energy_shift")
        self.assertEqual((shift.report_name, shift.paperformat_id), (SHIFT, paper))

    def test_ac44_without_cost_group(self):
        """Без групи вартості: немає ₴-колонок, блоку бюджету, KPI «Вартість» і сум резервів."""
        self._fixture_30d()
        markup = self._management(self.u_view, period="m")
        text = _text(markup)
        self.assertEqual(len(re.findall(r'data-kpi="', markup)), 6)
        self.assertNotIn('data-kpi="cost"', markup)
        self.assertNotIn("₴", text)
        self.assertNotIn("Бюджет енергії", text)
        self.assertIn("186 400", text)
        self.assertIn("Резерв 0", text)

    def test_ac44_empty_data_renders(self):
        """Без даних, бази й бюджету звіт будується з приміткою «База не задана»; без виключень."""
        markup = self._management(self.u_cost, period="w")
        text = _text(markup)
        self.assertIn("База не задана", text)
        self.assertIn("Модель бази не задана або не затверджена", text)
        self.assertIn("Бюджет енергії на поточний місяць не затверджено.", text)
        self.assertIn("За період немає добових даних по вузлах", text)

    def test_ac44_periods(self):
        self._fixture_30d()
        for period, label in (("w", "7 днів"), ("m", "30 днів"), ("q", "13 тижнів"), ("y", "12 місяців")):
            text = _text(self._management(self.u_cost, period=period))
            self.assertIn(label, text, period)

    def test_ac44_report_values_use_api(self):
        """R-18: `get_dashboard(period, "area", parts)` + `get_cut("eq", period)` — з правами користувача."""
        self._fixture_30d()
        model = self.env["report.td_energy_analytics.report_management_document"].with_user(self.u_cost)
        values = model._get_report_values(self._wizard(self.u_cost, "management", period="q").ids)
        data = values["reports"][values["doc_ids"][0]]
        self.assertTrue(data["cost"])
        self.assertEqual([k["id"] for k in data["kpis"]], ["el", "gas", "cost", "spec", "cogs", "selfgen", "co2"])
        self.assertLessEqual(len(data["equipment"]["rows"]), 5)
        self.assertEqual(data["budget"]["month"], "жовтень")

    # --- AC-46: звіт за зміну -------------------------------------------------------------------------------
    def test_ac46_pick_shift(self):
        """R-19: поточна зміна (з початку до «зараз»), остання завершена, зміна за назвою."""
        self._calendar_two_shifts()
        model = self.env["report.td_energy_analytics.report_shift_document"]
        # субота: змін немає — остання завершена — «Зміна 2» п'ятниці 16.10
        info = model._td_pick_shift()
        self.assertEqual((info["name"], info["day"], info["current"]), ("Зміна 2", date(2026, 10, 16), False))
        self.assertEqual(
            (info["start"], info["end"]), (self._local(date(2026, 10, 16), 16), self._local(date(2026, 10, 16), 23))
        )
        # понеділок 10:00 — триває «Зміна 1», вікно до «зараз»
        now = self._local(MONDAY, 10)
        info = model.with_context(f3d_now=now)._td_pick_shift()
        self.assertEqual((info["name"], info["current"]), ("Зміна 1", True))
        self.assertEqual(
            (info["start"], info["end"], info["full_end"]), (self._local(MONDAY, 7), now, self._local(MONDAY, 16))
        )
        # понеділок 23:30 — завершилась «Зміна 2» цього дня
        info = model.with_context(f3d_now=self._local(MONDAY, 23, 30))._td_pick_shift()
        self.assertEqual((info["name"], info["day"], info["current"]), ("Зміна 2", MONDAY, False))
        # понеділок 06:00 — сьогодні ще нічого не завершилось: «Зміна 2» п'ятниці (вихідні — без змін)
        info = model.with_context(f3d_now=self._local(MONDAY, 6))._td_pick_shift()
        self.assertEqual((info["name"], info["day"]), ("Зміна 2", date(2026, 10, 16)))
        # за назвою й датою
        info = model._td_pick_shift(MONDAY, "Зміна 1")
        self.assertEqual((info["name"], info["day"], info["start"]), ("Зміна 1", MONDAY, self._local(MONDAY, 7)))
        self.assertFalse(info["current"])
        with self.assertRaisesRegex(UserError, "Зміни «Нічна»"):
            model._td_pick_shift(MONDAY, "Нічна")

    def _shift_fixture(self):
        """«Зміна 2» п'ятниці 16.10 (слоти 64…91): 28 × 10 кВт·год + пік 40 у слоті 70; 4 попередні зміни по 280."""
        friday = date(2026, 10, 16)
        self._fill("PM-QF-1", friday, {70: 40.0, **{s: 10.0 for s in range(64, 92) if s != 70}}, slots=range(64, 92))
        self._fill("PM-Q1", friday, 12.0, slots=range(64, 92))
        for back in range(1, 5):
            self._fill("PM-QF-1", friday - timedelta(days=back), 10.0, slots=range(64, 92))
        ts = self._local(friday, 17, 10)
        self.Event._f3d_log(
            "warn", "threshold", "SAW-1", "Тест: перевищення порогу.", ts=ts, title="Перевищення порогу"
        )
        self.Event._f3d_log("info", "peak", "SAW-1", "Тест: інформація.", ts=ts + timedelta(minutes=5))
        # поза вікном зміни — не враховується
        self.Event._f3d_log("bad", "threshold", "SAW-1", "Тест: ранок.", ts=self._local(friday, 9))
        self.env["td.energy.outage.plan"].create(
            {
                "node_id": self._node("SAW-1").id,
                "start": self._local(friday, 18),
                "end": self._local(friday, 19),
            }
        )
        self.env["td.energy.outage.plan"].create(
            {"node_id": self._node("EDGE-1").id, "start": self._local(friday, 8), "end": self._local(friday, 9)}
        )
        self._opps()
        return friday

    def test_ac46_shift_report(self):
        self._calendar_two_shifts()
        self._shift_fixture()
        wizard = self._wizard(self.u_cost, "shift")
        text = _text(self._render(self.u_cost, SHIFT, wizard))
        self.assertIn("Звіт за зміну · Енергетика · Зміна 2", text)
        self.assertIn("пт 16.10.2026, 16:00–23:00 · завершена", text)
        self.assertIn("Споживання (фідери) 310 кВт·год", text)
        self.assertIn("Надходження з мережі (вводи) 336 кВт·год", text)
        self.assertIn("Пік потужності (15-хвилинний інтервал) 160 кВт о 17:30", text)
        self.assertIn("Вартість 2 604 ₴", text)
        self.assertIn("(середнє останніх 4 змін: 280 кВт·год)", text)
        self.assertIn("+11 %", text)
        # події: 1 «Увага», 1 «Інформація»; подія вікна — із назвою; ранкова подія не враховується
        self.assertIn("Інформація: 1 Увага: 1 Аварія: 0", text)
        self.assertIn("Перевищення порогу", text)
        self.assertNotIn("ранок", text)
        # відключення, що перетинають вікно: лише друге (18:00–19:00)
        self.assertIn("18:00–19:00", text)
        self.assertNotIn("08:00–09:00", text)
        # обходи — лише з td_energy_mobile
        if "td.energy.round" not in self.env:
            self.assertNotIn("Обходи", text)
        # три найбільші резерви, за ₴/міс
        self.assertIn("Резерв 0", text)
        self.assertIn("Резерв 1", text)
        self.assertIn("Резерв 2", text)
        self.assertNotIn("Резерв 3", text)
        self.assertLess(text.index("Резерв 0"), text.index("Резерв 1"))
        self.assertIn("15 500", text)

    def test_ac46_shift_report_without_cost(self):
        self._calendar_two_shifts()
        self._shift_fixture()
        text = _text(self._render(self.u_view, SHIFT, self._wizard(self.u_view, "shift")))
        self.assertIn("Споживання (фідери) 310 кВт·год", text)
        self.assertNotIn("₴", text)
        self.assertNotIn("Вартість", text)

    def test_ac46_current_shift_and_named(self):
        """Поточна зміна — з початку до «зараз»; типова — той самий відрізок від початку; зміна за назвою й датою."""
        self._calendar_two_shifts()
        self._fill("PM-QF-1", MONDAY, 10.0, slots=range(28, 64))
        for back in (3, 4, 5, 6, 7):  # пт, чт, ср, вт, пн попереднього тижня (суб і нд — без змін)
            self._fill("PM-QF-1", MONDAY - timedelta(days=back), 5.0, slots=range(28, 64))
        now = self._local(MONDAY, 10)  # 3 год = 12 слотів від 07:00 (28…39)
        env = self.env(context=dict(self.env.context, f3d_now=now))
        wizard = env["td.energy.report.wizard"].with_user(self.u_cost).create({"kind": "shift"})
        text = _text(env["ir.actions.report"].with_user(self.u_cost)._render_qweb_html(SHIFT, wizard.ids)[0].decode())
        self.assertIn("Зміна 1", text)
        self.assertIn("триває, дані до 10:00", text)
        self.assertIn("Споживання (фідери) 120 кВт·год", text)  # 12 слотів × 10
        self.assertIn("(середнє останніх 4 змін: 60 кВт·год)", text)  # 12 слотів × 5 у кожній з 4 змін
        self.assertIn("+100 %", text)
        named = (
            env["td.energy.report.wizard"]
            .with_user(self.u_cost)
            .create({"kind": "shift", "shift_name": "Зміна 1", "shift_date": MONDAY})
        )
        text = _text(env["ir.actions.report"].with_user(self.u_cost)._render_qweb_html(SHIFT, named.ids)[0].decode())
        self.assertIn("пн 19.10.2026, 07:00–16:00 · триває", text)

    def test_ac46_server_action_and_hook(self):
        """V-13: серверна дія повертає `report_action`; хук Пульту (C-02) вказує на її xml-id."""
        action = self.env.ref("td_energy_analytics.action_td_energy_shift_report")
        self.assertEqual(action._name, "ir.actions.server")
        self.assertIn("create_and_print('shift')", action.code)
        result = action.with_user(self.u_view).run()
        self.assertEqual(result["type"], "ir.actions.report")
        self.assertEqual(result["report_name"], SHIFT)
        wizard = self.env["td.energy.report.wizard"].sudo().browse(result["context"]["active_ids"])
        self.assertEqual((wizard.kind, wizard.create_uid), ("shift", self.u_view))
        self.assertEqual(
            self.env["td.energy.dashboard"]._td_report_action(), "td_energy_analytics.action_td_energy_shift_report"
        )
        meta = self.env["td.energy.dashboard"].with_user(self.u_view).get_pult(parts=["kpis"])["meta"]
        self.assertEqual(meta["report_action"], "td_energy_analytics.action_td_energy_shift_report")
        self.assertIs(meta["capabilities"]["report"], True)

    # --- AC-47: права, види звіту ---------------------------------------------------------------------------
    def test_ac47_create_and_print(self):
        Wizard = self.env["td.energy.report.wizard"]
        for kind, name in (("management", MANAGEMENT), ("shift", SHIFT)):
            result = Wizard.with_user(self.u_view).create_and_print(kind, "q" if kind == "management" else None)
            self.assertEqual(
                (result["type"], result["report_type"], result["report_name"]), ("ir.actions.report", "qweb-pdf", name)
            )
            wizard = Wizard.sudo().browse(result["context"]["active_ids"])
            self.assertEqual((wizard.kind, wizard.create_uid), (kind, self.u_view))
        self.assertEqual(Wizard.sudo().search([("kind", "=", "management")], order="id desc", limit=1).period, "q")
        named = Wizard.with_user(self.u_view).create_and_print("shift", None, "Зміна 2")
        self.assertEqual(Wizard.sudo().browse(named["context"]["active_ids"]).shift_name, "Зміна 2")

    def test_ac47_admin_gets_report_not_layout_wizard(self):
        """Адміністратору (макет документа не задано) Odoo за замовчуванням підсовує майстер макета — тут його немає."""
        admin = self.env.ref("base.user_admin")
        self.env.company.external_report_layout_id = False
        for kind, name in (("management", MANAGEMENT), ("shift", SHIFT)):
            result = self.env["td.energy.report.wizard"].with_user(admin).create_and_print(kind)
            self.assertEqual((result["type"], result["report_name"]), ("ir.actions.report", name))
        action = self.env.ref("td_energy_analytics.action_td_energy_shift_report").with_user(admin).run()
        self.assertEqual(action["type"], "ir.actions.report")

    def test_ac47_errors(self):
        Wizard = self.env["td.energy.report.wizard"]
        with self.assertRaisesRegex(UserError, r"Невідомий вид звіту: x\."):
            Wizard.with_user(self.u_view).create_and_print("x")
        with self.assertRaisesRegex(UserError, "Невідомий період: z"):
            Wizard.with_user(self.u_view).create_and_print("management", "z")
        for kind in ("management", "shift"):
            with self.assertRaises(AccessError):
                Wizard.with_user(self.u_plain).create_and_print(kind)

    def test_ac47_open_form_print(self):
        wizard = self._wizard(self.u_view, "management", period="y")
        action = wizard.action_print()
        self.assertEqual(action["report_name"], MANAGEMENT)
        self.assertEqual(action["context"]["active_ids"], wizard.ids)
        wizard.kind = "shift"
        self.assertEqual(wizard.action_print()["report_name"], SHIFT)

    # --- M-16: майстер перерахунку ----------------------------------------------------------------------------
    def test_rebuild_wizard(self):
        self._fill("PM-QF-1", TODAY, 10.0, slots=range(40))
        self._fill("PM-Q1", TODAY, 12.0, slots=range(40))
        Wizard = self.env["td.energy.daily.rebuild.wizard"]
        wizard = Wizard.with_user(self.u_eng).create({"date_from": TODAY, "date_to": TODAY})
        result = wizard.action_rebuild()
        self.assertEqual(
            (result["tag"], result["params"]["next"]), ("display_notification", {"type": "ir.actions.act_window_close"})
        )
        self.assertRegex(result["params"]["message"], r"Перераховано діб: 1, рядків фактів: \d+")
        plant = self.Daily.search([("day", "=", TODAY), ("scope", "=", "plant")])
        self.assertEqual(len(plant), 1)
        self.assertAlmostEqual(plant.qty, 400.0, places=2)
        self.assertEqual(wizard.date_from, TODAY)

    def test_rebuild_wizard_rules(self):
        Wizard = self.env["td.energy.daily.rebuild.wizard"]
        default = Wizard.with_user(self.u_eng).default_get(["date_from", "date_to"])
        self.assertEqual((default["date_to"], default["date_from"]), (TODAY, TODAY - timedelta(days=6)))
        long = Wizard.with_user(self.u_eng).create({"date_from": TODAY - timedelta(days=400), "date_to": TODAY})
        with self.assertRaisesRegex(UserError, "Не більше 400 діб"):
            long.action_rebuild()
        back = Wizard.with_user(self.u_eng).create({"date_from": TODAY, "date_to": TODAY - timedelta(days=1)})
        with self.assertRaisesRegex(UserError, "Кінець діапазону раніше початку"):
            back.action_rebuild()
        with self.assertRaises(AccessError):  # права на майстер — лише «Енергетик»
            Wizard.with_user(self.u_view).create({"date_from": TODAY, "date_to": TODAY})
        with self.assertRaises(AccessError):
            Wizard.with_user(self.u_plain).create({"date_from": TODAY, "date_to": TODAY})
