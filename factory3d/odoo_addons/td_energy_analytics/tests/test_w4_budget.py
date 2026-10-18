"""W4-A: бюджет енергії й прогноз (AC-22, AC-23, AC-24)."""

from datetime import date, timedelta

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tools import mute_logger

from odoo.addons.td_energy_analytics.tools import budget as budget_tools
from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

OCT = date(2026, 10, 1)
TYPICAL = {0: 62000.0, 1: 62000.0, 2: 62000.0, 3: 62000.0, 4: 62000.0, 5: 60000.0, 6: 38000.0}


@tagged(*TAGS)
class TestW4Budget(TestW4Common):
    def _fixture_1710(self):
        """Факт 1–16.10 = 1 036 000, сьогодні 60 000, типові доби (8 тижнів) пн–пт 62 000, сб 60 000, нд 38 000."""
        start = TODAY - timedelta(days=56)
        costs = {}
        for i in range(56):
            day = start + timedelta(days=i)
            costs[day] = TYPICAL[day.weekday()]
        # +96 000 на пн–чт 5–8.10; те саме віднімаємо в ті самі дні тижня раніше: середні типових діб не змінюються
        for k, day in enumerate((date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8))):
            costs[day] += 24000.0
            costs[date(2026, 9, 21) + timedelta(days=k)] -= 24000.0
        costs[TODAY] = 60000.0
        for day, cost in costs.items():
            self._daily(day, scope="resource", resource="el", cost=cost, qty=1.0)
        self._daily(TODAY - timedelta(days=60), scope="resource", resource="heat", cost=999999.0)  # поза вікном
        return costs

    def test_ac22_basics(self):
        with self.assertRaises(ValidationError):
            self._budget(date(2026, 10, 2), 1000.0, approve=False)
        with self.assertRaises(ValidationError):
            self._budget(OCT, 0.0, approve=False)
        budget = self._budget(OCT, 1950000.0, approve=False)
        self.assertEqual(budget.state, "draft")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.Budget.create({"month": OCT, "amount_uah": 5.0})
        gas = self._budget(OCT, 100.0, resource=self.res_gas, approve=False)  # інший ресурс — інша пара
        self.assertTrue(gas)
        # draft не враховується; затверджує лише головний
        self.assertIsNone(self.Budget.get_status("2026-10"))
        for user in (self.u_eng, self.u_cost, self.u_view):
            with self.assertRaises(AccessError):
                budget.with_user(user).action_approve()
        budget.with_user(self.u_chief).action_approve()
        self.assertEqual((budget.state, budget.approved_by), ("approved", self.u_chief))
        # правка суми затвердженого — лише головний; скидає в чернетку
        with self.assertRaises(AccessError):
            budget.with_user(self.u_eng).write({"amount_uah": 2000000.0})
        budget.with_user(self.u_chief).write({"amount_uah": 2000000.0})
        self.assertEqual(budget.state, "draft")

    def test_ac22_access(self):
        budget = self._budget(OCT, 1950000.0)
        self.assertEqual(self.Budget.with_user(self.u_cost).search([("id", "=", budget.id)]), budget)
        with self.assertRaises(AccessError):
            self.Budget.with_user(self.u_view).search([])
        with self.assertRaises(AccessError):
            self.Budget.with_user(self.u_plain).get_status("2026-10")

    def test_ac23_forecast_1710(self):
        self._fixture_1710()
        self._budget(OCT, 1950000.0)
        res = self.Budget.with_user(self.u_cost).get_status("2026-10")
        self.assertEqual(res["month"], "2026-10")
        self.assertEqual(res["month_label"], "жовтень")
        self.assertAlmostEqual(res["plan_uah"], 1950000.0)
        self.assertAlmostEqual(res["fact_uah"], 1096000.0)
        self.assertEqual((res["fact_pct"], res["month_share_pct"]), (56, 55))
        self.assertAlmostEqual(res["forecast_uah"], 1912000.0)
        self.assertEqual(res["delta_pct"], -2)
        self.assertEqual(
            res["text"],
            "Факт на 17.10 — 1 096 000 ₴ (56 % при 55 % місяця) · прогноз 1 912 000 ₴, на 2 % нижче бюджету",
        )
        self.assertEqual(self.Budget.get_status()["month"], "2026-10", "за замовчуванням — поточний місяць")
        # без групи вартості блок відсутній
        self.assertIsNone(self.Budget.with_user(self.u_view).get_status("2026-10"))

    def test_ac23_pure_function(self):
        actual = {OCT + timedelta(days=i): 1036000.0 / 16 for i in range(16)}
        actual[TODAY] = 60000.0
        typical = [TYPICAL[w] for w in range(7)]
        res = budget_tools.status(1950000.0, OCT, TODAY, actual, typical)
        self.assertAlmostEqual(res["forecast"], 1036000.0 + 60000.0 + 2 * 38000.0 + 10 * 62000.0 + 2 * 60000.0)
        self.assertEqual((res["fact_pct"], res["month_share"], res["delta_pct"]), (56, 55, -2))

    def test_ac24_edge_cases(self):
        # немає даних → прогнозу немає
        self._budget(OCT, 1000000.0)
        res = self.Budget.with_user(self.u_cost).get_status("2026-10")
        self.assertEqual((res["fact_uah"], res["forecast_uah"], res["delta_pct"]), (0.0, None, None))
        self.assertNotIn("прогноз", res["text"])
        # зразків дня тижня < 3 → середнє всіх діб вікна
        typical = budget_tools.typical_by_weekday(
            {TODAY - timedelta(days=1): 100.0, TODAY - timedelta(days=2): 300.0}, TODAY, 8, 3
        )
        self.assertEqual(typical, [200.0] * 7)
        self.assertIsNone(budget_tools.typical_by_weekday({}, TODAY, 8, 3))
        # перший день місяця
        first = budget_tools.status(100.0, OCT, OCT, {OCT: 5.0}, [10.0] * 7)
        self.assertAlmostEqual(first["forecast"], 10.0 * 31)
        self.assertEqual(first["month_share"], 3)
        # останній день місяця: факт перевищує типову добу → прогноз = факт
        last = date(2026, 10, 31)
        actual = {OCT + timedelta(days=i): 10.0 for i in range(31)}
        end = budget_tools.status(300.0, OCT, last, {**actual, last: 50.0}, [10.0] * 7)
        self.assertAlmostEqual(end["forecast"], end["fact"])
        # минулий місяць: прогноз = факт
        past = budget_tools.status(300.0, date(2026, 9, 1), TODAY, {date(2026, 9, 5): 7.0}, None)
        self.assertEqual((past["forecast"], past["fact"]), (7.0, 7.0))
        # «відповідає бюджету»
        same = budget_tools.status(100.0, OCT, last, {last: 100.0}, [1.0] * 7)
        self.assertIn("відповідає бюджету", same["text"])

    def test_ac24_resource_budget_gas(self):
        for k in range(1, 4):
            self._daily(TODAY - timedelta(days=k), scope="resource", resource="gas", cost=1000.0)
            self._daily(TODAY - timedelta(days=k), scope="resource", resource="el", cost=50000.0)
        self._budget(OCT, 40000.0, resource=self.res_gas)
        res = self.Budget.with_user(self.u_cost).get_status("2026-10", resource_code="gas")
        self.assertAlmostEqual(res["fact_uah"], 3000.0)
        self.assertIsNone(self.Budget.with_user(self.u_cost).get_status("2026-10"), "загального бюджету немає")

    def test_ac53_weeks_param_changes_typical(self):
        self._fixture_1710()
        self._budget(OCT, 1950000.0)
        base = self.Budget.with_user(self.u_cost).get_status("2026-10")["forecast_uah"]
        self._param("forecast_weeks", 2)
        short = self.Budget.with_user(self.u_cost).get_status("2026-10")["forecast_uah"]
        self.assertNotEqual(base, short)
