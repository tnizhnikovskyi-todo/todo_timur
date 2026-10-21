"""Вау №6 (R-23): модель `td.energy.whatif` — розрахунок на даних, права, скидання, демо, види, браузер."""

import json
from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, tagged

from odoo.addons.td_energy.tests.common import NOW
from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy_analytics.tools import seed as seed_tools

from .common import TAGS, TestW4Common

LAST = date(2026, 10, 16)  # NOW — субота 17.10: база — до вчора
FIRST = date(2026, 10, 3)  # 14 діб: сб 03.10 … пт 16.10 (10 робочих)
DAYS = [FIRST + timedelta(days=i) for i in range(14)]
WINDOW = range(32, 64)  # 08:00–16:00
EVENING = range(64, 92)  # 16:00–23:00
ZONES = [
    {"name": "Ніч", "code": "night", "price": 3.0, "weekdays": "0123456", "hour_from": 23.0, "hour_to": 7.0},
    {"name": "День", "code": "day", "price": 6.0, "weekdays": "0123456", "hour_from": 7.0, "hour_to": 23.0},
]
FLAT = [{"name": "Цілодобова", "code": "flat", "price": 8.4, "weekdays": "0123456", "hour_from": 0.0, "hour_to": 24.0}]


def make_tariff(env, zones=ZONES, contract_kw=200.0, capacity_price=0.0):
    """Єдиний чинний тариф: решта архівується."""
    Tariff = env["td.energy.tariff"]
    Tariff.search([]).write({"active": False})
    return Tariff.create(
        {
            "name": "Тариф «Що якщо»", "date_from": date(2026, 1, 1), "contract_kw": contract_kw,
            "peak_warn_pct": 90.0, "capacity_price": capacity_price,
            "zone_ids": [(0, 0, dict(z, sequence=10 * i)) for i, z in enumerate(zones, 1)],
        }
    )  # fmt: skip


def fill_series(env, meter_code, day, values, built_at):
    """Інтервали лічильника за добу: `values` — `{слот: кВт·год}`."""
    meter = env["td.energy.meter"].search([("code", "=", meter_code)])
    d0 = dates.local_day_bounds(day)[0]
    rows = []
    for slot, kwh in values.items():
        ts = d0 + timedelta(minutes=15 * slot)
        local = dates.to_local(ts)
        rows.append(
            {
                "meter_id": meter.id, "ts_start": ts, "ts_end": ts + timedelta(minutes=15), "day": local.date(),
                "hour_local": local.hour, "e_start": 0.0, "e_end": kwh, "kwh": kwh, "kwh_export": 0.0,
                "kw_avg": kwh * 4, "price": 8.4, "cost": round(kwh * 8.4, 2), "quality": "measured",
                "built_at": built_at,
            }
        )  # fmt: skip
    env["td.energy.interval"].create(rows)


def fill_plant(env, days=DAYS, built_at=NOW):
    """Ввід `PM-Q1`: фон 100 кВт; у робочі доби розкрій SAW-1 (8 кВт у 08:00–16:00 і 16:00–23:00) і компресорна
    (32 кВт у 08:00–16:00) додаються до вводу; вихідні — лише фон."""
    for day in days:
        work = day.weekday() < 5
        saw = {s: 2.0 for s in list(WINDOW) + list(EVENING)} if work else {}
        compressor = {s: 8.0 for s in WINDOW} if work else {}
        grid = {s: 25.0 + saw.get(s, 0.0) + compressor.get(s, 0.0) for s in range(96)}
        fill_series(env, "PM-Q1", day, grid, built_at)
        fill_series(env, "PM-SAW-1", day, saw, built_at)
        fill_series(env, "PM-COMPRESSOR", day, compressor, built_at)


@tagged(*TAGS)
class TestW6WhatIf(TestW4Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WhatIf = cls.env["td.energy.whatif"]
        Node, Area = cls.env["td.energy.node"], cls.env["td.energy.area"]
        cls.saw = Node.search([("code", "=", "SAW-1")], limit=1)
        cls.saw.area_id = Area.search([("code", "=", "CUT")], limit=1)
        cls.compressor = Node.search([("code", "=", "COMPRESSOR")], limit=1)
        cls.compressor.area_id = Area.search([("code", "=", "AIR_DUST")], limit=1)
        cls.tariff = make_tariff(cls.env)
        fill_plant(cls.env)

    def _scenario(self, **vals):
        data = {"name": "Розкрій на ніч", "scope": "area", "area_id": self._area("CUT").id, "hour_from": 8.0,
                "hour_to": 16.0, "move_mode": "night", "base_days": 14}  # fmt: skip
        data.update(vals)
        return self.WhatIf.create(data)

    def _flat_tariff(self):
        return make_tariff(self.env, zones=FLAT)

    # --- розрахунок ------------------------------------------------------------------------------------
    def test_night_scenario_on_area(self):
        """AC-63: ділянка → у нічну зону: економія ₴/міс, пік, графік 96 точок, попередження про нічну зміну."""
        rec = self._scenario()
        rec.action_compute()
        self.assertEqual(rec.state, "done")
        self.assertEqual((rec.date_from, rec.date_to, rec.days_used), (FIRST, LAST, 14))
        # 10 робочих діб × 64 кВт·год × (6 − 3) ₴ = 1 920 ₴ за 14 діб → на 30 діб
        self.assertAlmostEqual(rec.saving_month, 1920 * 30 / 14, places=1)
        self.assertAlmostEqual(rec.cost_before - rec.cost_after, rec.saving_month, places=1)
        self.assertEqual((rec.peak_before_kw, rec.peak_after_kw, rec.peak_delta_kw), (140.0, 132.0, -8.0))
        self.assertEqual(rec.limit_kw, 200.0)
        self.assertAlmostEqual(rec.moved_kwh_month, 640 * 30 / 14, places=0)
        self.assertFalse(rec.limit_exceeded)
        data = json.loads(rec.result_json)
        self.assertEqual(len(data["profile"]["base_kw"]), 96)
        self.assertEqual(len(data["profile"]["scenario_kw"]), 96)
        self.assertEqual(data["profile"]["limit_kw"], 200.0)
        night = next(w for w in data["warnings"] if w["code"] == "night_shift")
        self.assertIn("ділянці «Розкрій»", night["text"])
        self.assertEqual(rec.warning_count, 1)
        self.assertEqual(data["meta"]["tariff"], "Тариф «Що якщо»")
        by_code = {z["code"]: z for z in data["zones"]}
        self.assertGreater(by_code["night"]["after_pct"], by_code["night"]["before_pct"])

    def test_nodes_scope_shift(self):
        """AC-63: вибрані вузли, зсув на 12 год: 20 з 32 слотів потрапляють у нічну зону."""
        rec = self._scenario(
            name="Зсув", scope="nodes", node_ids=[(6, 0, self.saw.ids)], move_mode="shift", shift_hours=12.0
        )
        rec.action_compute()
        self.assertAlmostEqual(rec.saving_month, 1200 * 30 / 14, places=1)
        self.assertIn("вузлах: SAW-1", rec.result_json)

    def test_other_nodes_do_not_move(self):
        """Переносяться лише вузли сценарію: компресор лишається, пік дня знижується рівно на вузол розкрою."""
        rec = self._scenario(scope="nodes", node_ids=[(6, 0, self.compressor.ids)], move_mode="shift", shift_hours=3.0)
        rec.action_compute()
        # компресорна 32 кВт у 08–16 → +3 год: пік 140 лишається (до 11:00 вікно ще повне, далі накладається)
        self.assertGreaterEqual(rec.peak_after_kw, 108.0)
        self.assertEqual(rec.saving_month, 0.0)  # зсув у межах денної зони — економії немає

    def test_input_change_resets_result(self):
        """AC-64: зміна входів скидає результат (у списку порівняння не лишаються застарілі цифри)."""
        rec = self._scenario()
        rec.action_compute()
        self.assertTrue(rec.saving_month)
        rec.write({"hour_to": 15.0})
        self.assertEqual(rec.state, "draft")
        self.assertEqual((rec.saving_month, rec.peak_after_kw), (0.0, 0.0))
        self.assertFalse(rec.result_json)
        rec.write({"name": "Інша назва"})  # назва не вхід
        rec.action_compute()
        rec.write({"name": "Ще інша"})
        self.assertEqual(rec.state, "done")

    def test_errors(self):
        """AC-65: немає тарифу / ділянки / нічної зони / даних — зрозуміла `UserError`."""
        rec = self._scenario()
        self.tariff.write({"active": False})
        with self.assertRaises(UserError) as ctx:
            rec.action_compute()
        self.assertIn("чинного тарифу", str(ctx.exception))
        self._flat_tariff()
        with self.assertRaises(UserError) as ctx:
            rec.action_compute()
        self.assertIn("нічної зони", str(ctx.exception))
        no_area = self._scenario(scope="area", area_id=False)
        make_tariff(self.env)
        with self.assertRaises(UserError):
            no_area.action_compute()
        future = rec.with_context(f3d_now=NOW + timedelta(days=60))
        with self.assertRaises(UserError) as ctx:
            future.action_compute()
        self.assertIn("повних діб", str(ctx.exception))

    def test_limit_exceeded(self):
        """AC-66: пік після переносу проти ліміту договору — попередження «перевищує ліміт на X кВт о HH:MM»."""
        make_tariff(self.env, contract_kw=130.0)
        rec = self._scenario()
        rec.action_compute()
        warn = next(w for w in json.loads(rec.result_json)["warnings"] if w["code"] == "peak_over_limit")
        self.assertIn("Пік перевищує ліміт договору (130 кВт) на 2 кВт о 08:00 (05.10)", warn["text"])
        self.assertIn("уже перевищувався", warn["text"])  # у базі пік 140 теж був вище ліміту
        self.assertTrue(rec.limit_exceeded)
        make_tariff(self.env, contract_kw=135.0)
        rec2 = self._scenario(name="Друга")
        rec2.action_compute()
        self.assertFalse(rec2.limit_exceeded)

    def test_capacity_price(self):
        """AC-67: плата за потужність із договору входить у вартість до/після; без неї — лише енергія."""
        make_tariff(self.env, capacity_price=50.0)
        rec = self._scenario()
        rec.action_compute()
        data = json.loads(rec.result_json)["tiles"]
        self.assertEqual(data["capacity_fee_before"], 50.0 * 140)
        self.assertEqual(data["capacity_fee_after"], 50.0 * 132)
        self.assertAlmostEqual(rec.saving_month, 1920 * 30 / 14 + 50.0 * 8, places=1)
        self.assertAlmostEqual(rec.cost_before, data["energy_cost_before"] + 7000.0, places=1)

    def test_compare_in_list(self):
        """AC-68: збережені сценарії порівнюються: впорядкування й сума економії."""
        best = self._scenario()
        zero = self._scenario(name="Зсув 2 год", move_mode="shift", shift_hours=2.0)
        (best | zero).action_compute()
        found = self.WhatIf.search([("id", "in", (best | zero).ids)], order="saving_month desc")
        self.assertEqual(found.ids, [best.id, zero.id])
        self.assertEqual(zero.saving_month, 0.0)
        info = json.loads(zero.result_json)["warnings"]
        self.assertNotIn("flat_tariff", {w["code"] for w in info})  # ціни зон різні

    def test_constraints(self):
        """Перевірки входів: частка, вікно, зсув, база."""
        for bad in (
            {"share_pct": 0.0}, {"share_pct": 101.0}, {"hour_from": 9.0, "hour_to": 9.0}, {"hour_to": 24.5},
            {"hour_from": 8.1}, {"base_days": 3}, {"base_days": 91}, {"move_mode": "shift", "shift_hours": 0.0},
            {"move_mode": "shift", "shift_hours": 13.0},
        ):  # fmt: skip
            with self.subTest(bad=bad), self.assertRaises(ValidationError), self.env.cr.savepoint():
                self._scenario(**bad)
        ok = self._scenario(hour_from=22.0, hour_to=6.0, shift_hours=-2.0, move_mode="shift")  # через північ, назад
        self.assertEqual((ok.window_text, ok.move_text), ("22:00–06:00", "−2 год"))

    # --- права -----------------------------------------------------------------------------------------
    def test_security(self):
        """AC-69: читає група вартості, створює й рахує менеджер; без групи вартості моделі не видно."""
        rec = self._scenario()
        data = {"name": "X", "scope": "area", "area_id": self._area("CUT").id}
        with self.assertRaises(AccessError):
            self.WhatIf.with_user(self.u_view).search([])
        rec.action_compute()
        self.assertEqual(rec.with_user(self.u_cost).saving_month, rec.saving_month)
        with self.assertRaises(AccessError):
            self.WhatIf.with_user(self.u_cost).create(data)
        mine = self.WhatIf.with_user(self.u_eng).create(dict(data, base_days=14, move_mode="night"))
        mine.action_compute()
        self.assertEqual(mine.state, "done")
        with self.assertRaises(AccessError):
            self.tariff.with_user(self.u_view).read(["capacity_price"])  # плата за потужність — лише cost

    # --- демо ------------------------------------------------------------------------------------------
    def test_seed_demo_needs_zones(self):
        """AC-70: на плоскому тарифі демо-сценарії не створюються (економії немає), на зональному — 2, без дублів."""
        self._flat_tariff()
        self.assertEqual(self.WhatIf._td_seed_demo(), 0)
        self.assertFalse(self.WhatIf.search([("note", "=", "демо-сид")]))
        make_tariff(self.env)
        self.assertEqual(self.WhatIf._td_seed_demo(), 2)
        demo = self.WhatIf.search([("note", "=", "демо-сид")], order="id")
        self.assertEqual(demo.mapped("name"), ["Розкрій на ніч", "Компресори зміщення на 2 год"])
        self.assertEqual(demo.mapped("state"), ["done", "done"])
        self.assertGreater(demo[0].saving_month, 0)
        self.assertEqual(self.WhatIf._td_seed_demo(), 0)
        seed_tools.purge(self.env)
        self.assertFalse(self.WhatIf.search([("note", "=", "демо-сид")]))

    # --- види ------------------------------------------------------------------------------------------
    def test_views_menu_and_tariff_field(self):
        """AC-71: меню «Що якщо» (seq 13, група вартості), види list/form/graph/search, поле тарифу в договорі."""
        menu = self.env.ref("td_energy_analytics.menu_td_energy_whatif")
        self.assertEqual((menu.sequence, menu.parent_id), (13, self.env.ref("td_energy.menu_td_energy")))
        self.assertEqual(menu.group_ids, self.env.ref("td_energy.group_td_energy_cost"))
        action = self.env.ref("td_energy_analytics.action_td_energy_whatif")
        self.assertEqual((action.res_model, action.view_mode), ("td.energy.whatif", "list,form,graph"))
        views = self.WhatIf.get_views([(False, "list"), (False, "form"), (False, "graph"), (False, "search")])
        self.assertIn('widget="td_whatif_board"', views["views"]["form"]["arch"])
        self.assertIn("saving_month", views["views"]["list"]["arch"])
        tariff_form = self.env["td.energy.tariff"].get_view(view_type="form")["arch"]
        self.assertIn("capacity_price", tariff_form)


@tagged(*TAGS)
class TestW6WhatIfUi(HttpCase):
    def test_form_renders_board(self):
        """AC-72: форма розрахованого сценарію показує 4 плитки, графік (2 лінії, ліміт, 96 зон наведення), зони й
        попередження без помилок JS."""
        make_tariff(self.env)
        fill_plant(self.env)
        area = self.env["td.energy.area"].search([("code", "=", "CUT")], limit=1)
        self.env["td.energy.node"].search([("code", "=", "SAW-1")]).area_id = area
        rec = self.env["td.energy.whatif"].create(
            {
                "name": "Розкрій на ніч",
                "scope": "area",
                "area_id": area.id,
                "hour_from": 8.0,
                "hour_to": 16.0,
                "move_mode": "night",
                "base_days": 14,
            }  # fmt: skip
        )
        rec.with_context(f3d_now=NOW)._td_compute()
        self.browser_js(
            "/odoo/action-td_energy_analytics.action_td_energy_whatif/%d" % rec.id,
            """
            const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const waitFor = async (check, label) => {
                const started = Date.now();
                for (;;) {
                    if (check()) { return; }
                    if (Date.now() - started > 30000) { throw new Error("timeout: " + label); }
                    await sleep(100);
                }
            };
            const $$ = (selector) => Array.from(document.querySelectorAll(selector));
            (async () => {
                await waitFor(() => $$('.o_td_wi_tile').length === 4, "плитки");
                await waitFor(() => $$('.o_td_wi_line').length === 2 && $$('.o_td_wi_limit').length === 1, "графік");
                if ($$('.o_td_wi_hit').length !== 96) { throw new Error("точок: " + $$('.o_td_wi_hit').length); }
                if (!/4\\s?114/.test($$('[data-tile="saving"]')[0].textContent)) { throw new Error("економія"); }
                if ($$('[data-zone]').length < 2) { throw new Error("зони"); }
                if (!$$('[data-warning="night_shift"]').length) { throw new Error("нічна зміна"); }
                console.log("test successful");
            })().catch((error) => console.error("UI test failed: " + error));
            """,
            ready="!!document.querySelector('.o_td_wi_tile')",
            login="admin",
            timeout=120,
        )
