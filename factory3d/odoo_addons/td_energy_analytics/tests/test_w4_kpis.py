"""W4-A: періоди (R-01) і KPI екрана (AC-25…AC-32)."""

import json
from datetime import date, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy_analytics.tools import heatmap as heatmap_tools
from odoo.addons.td_energy_analytics.tools import periods
from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common


@tagged(*TAGS)
class TestW4Kpis(TestW4Common):
    def _kpis(self, period="m", user=None):
        api = self.Api.with_user(user or self.u_cost)
        return {k["id"]: k for k in api.get_kpis(period)}

    # --- AC-25 ------------------------------------------------------------------------------------------
    def test_ac25_windows_and_buckets(self):
        self.assertEqual(periods.window("w", TODAY), (date(2026, 10, 11), TODAY))
        self.assertEqual(periods.window("m", TODAY), (date(2026, 9, 18), TODAY))
        self.assertEqual(periods.window("q", TODAY), (date(2026, 7, 19), TODAY))
        self.assertEqual(periods.window("y", TODAY), (date(2025, 11, 1), TODAY))
        w = periods.buckets("w", TODAY)
        self.assertEqual([b["label"] for b in w], ["нд", "пн", "вт", "ср", "чт", "пт", "сб"])
        m = periods.buckets("m", TODAY)
        self.assertEqual(len(m), 30)
        self.assertEqual([b["label"] for b in m[:11]], ["18", "", "", "", "", "23", "", "", "", "", "28"])
        self.assertEqual(m[0]["key"], "2026-09-18")
        q = periods.buckets("q", TODAY)
        self.assertEqual(len(q), 13)
        self.assertEqual((q[0]["date_from"], q[0]["date_to"]), (date(2026, 7, 19), date(2026, 7, 25)))
        self.assertEqual((q[-1]["date_from"], q[-1]["date_to"]), (date(2026, 10, 11), TODAY))
        self.assertEqual([b["label"] for b in q[:4]], ["т1", "", "т3", ""])
        y = periods.buckets("y", TODAY)
        self.assertEqual(len(y), 12)
        self.assertEqual((y[0]["date_from"], y[0]["date_to"]), (date(2025, 11, 1), date(2025, 11, 30)))
        self.assertEqual((y[-1]["date_from"], y[-1]["date_to"]), (date(2026, 10, 1), TODAY))
        self.assertEqual([b["label"] for b in y[:3]], ["лис", "гру", "січ"])
        self.assertEqual(sum(1 for _ in periods.weeks(TODAY)), 12)

    def test_ac25_unknown_period_and_access(self):
        with self.assertRaisesRegex(UserError, "Невідомий період: x"):
            self.Api.get_kpis("x")
        with self.assertRaisesRegex(UserError, "Невідомий розріз: z"):
            self.Api.get_dashboard("m", "z")
        with self.assertRaisesRegex(AccessError, "Немає доступу до Енергетики"):
            self.Api.with_user(self.u_plain).get_kpis("m")

    # --- макет 17.10 -------------------------------------------------------------------------------------
    def test_ac26_el(self):
        self._mockup_1710()
        el = self._kpis()["el"]
        self.assertEqual((el["value"], el["unit"], el["tone"]), (186400, "кВт·год", "good"))
        self.assertAlmostEqual(el["delta_pct"], -6.0)
        self.assertEqual(el["note"], "−6 % до бази")
        self.assertEqual(set(el), {"id", "label", "value", "unit", "delta_pct", "note", "tone"})

    def test_ac26_without_baseline(self):
        self._daily(TODAY, qty=1000.0)
        el = self._kpis()["el"]
        self.assertEqual(
            (el["value"], el["delta_pct"], el["note"], el["tone"]), (1000, None, "База не задана", "neutral")
        )

    def test_ac27_gas(self):
        self._mockup_1710()
        gas = self._kpis()["gas"]
        self.assertEqual((gas["value"], gas["tone"]), (18400, "bad"))
        self.assertAlmostEqual(gas["delta_pct"], 2.0)
        self.assertEqual(gas["note"], "+2 % до бази · похолодання")
        # тепліше: HDD вікна -15 % до бази
        for rec in self.DriverValue.search(
            [("driver_id", "=", self.hdd.id), ("day", ">=", TODAY - timedelta(days=29))]
        ):
            rec.value = 7.9 * 0.85
        self.assertEqual(self._kpis()["gas"]["note"], "+2 % до бази · тепліше")
        for rec in self.DriverValue.search(
            [("driver_id", "=", self.hdd.id), ("day", ">=", TODAY - timedelta(days=29))]
        ):
            rec.value = 7.9 * 1.05
        self.assertEqual(self._kpis()["gas"]["note"], "+2 % до бази")

    def test_ac27_no_gas_baseline(self):
        self._daily(TODAY, qty=1.0)
        self._daily(TODAY, scope="resource", resource="gas", qty=100.0, cost=10.0)
        gas = self._kpis()["gas"]
        self.assertEqual((gas["value"], gas["delta_pct"], gas["note"]), (100, None, "База не задана"))

    def test_ac28_cost(self):
        self._mockup_1710()
        cost = self._kpis()["cost"]
        self.assertEqual((cost["value"], cost["unit"], cost["tone"]), (1937880, "₴", "neutral"))
        self.assertEqual(cost["note"], "електрика 81 % · газ 19 %")
        self.assertIsNone(cost["delta_pct"])
        self.assertNotIn("cost", self._kpis(user=self.u_view))
        self.assertEqual(list(self._kpis(user=self.u_view)), ["el", "gas", "spec", "cogs", "selfgen", "co2"])

    def test_ac29_spec(self):
        self._mockup_1710()
        spec = self._kpis()["spec"]
        self.assertAlmostEqual(spec["value"], 4.85)
        self.assertAlmostEqual(spec["delta_pct"], -5.9)
        self.assertEqual(spec["note"], "база 5,16 · −6 %")
        self.assertEqual((spec["unit"], spec["tone"]), ("кВт·год/м² плити", "good"))
        self.DriverValue.search([("driver_id", "=", self.plate.id)]).write({"value": 0.0})
        self.assertIsNone(self._kpis()["spec"]["value"])

    def test_ac30_cogs(self):
        self._mockup_1710()
        cogs = self._kpis()["cogs"]
        self.assertAlmostEqual(cogs["value"], 6.8)
        self.assertEqual((cogs["note"], cogs["tone"]), ("база 7,3 %", "good"))
        self.env.cr.execute("UPDATE stock_move SET value = 0")
        self.env["stock.move"].invalidate_model()
        self.assertEqual((self._kpis()["cogs"]["value"], self._kpis()["cogs"]["note"]), (None, "—"))

    def test_ac31_selfgen(self):
        self._mockup_1710()
        selfgen = self._kpis()["selfgen"]
        self.assertEqual((selfgen["value"], selfgen["unit"], selfgen["tone"]), (18, "%", "good"))
        self.assertEqual(selfgen["note"], "СЕС 41 000 кВт·год")

    def test_ac32_co2(self):
        self._mockup_1710()
        co2 = self._kpis()["co2"]
        self.assertEqual((co2["value"], co2["unit"]), (93, "т"))
        self.assertEqual(co2["note"], "мережа 57 т · газ 36 т за період")

    def test_kpi_order_and_period_window(self):
        self._mockup_1710()
        self.assertEqual(list(self._kpis()), ["el", "gas", "cost", "spec", "cogs", "selfgen", "co2"])
        week = self._kpis("w")["el"]["value"]
        self.assertEqual(week, round(186400 / 30 * 7))

    # --- API-01 ------------------------------------------------------------------------------------------
    def test_dashboard_parts_meta_and_errors(self):
        el, _gas = self._mockup_1710()
        full = self.Api.with_user(self.u_cost).get_dashboard("m", "area", None)
        self.assertEqual(list(full), ["meta", "kpis", "stack", "heatmap", "enpi", "budget", "cut", "opps"])
        meta = full["meta"]
        self.assertEqual(
            (meta["period"], meta["period_label"], meta["date_from"], meta["date_to"]),
            ("m", "30 днів", "2026-09-18", "2026-10-17"),
        )
        self.assertEqual(meta["now_local"], "14:20")
        self.assertEqual(meta["baseline"]["id"], el.id)
        self.assertEqual(meta["baseline"]["coefs"], [{"driver": "plate_m2", "coef": 4.1}])
        self.assertEqual((meta["baseline"]["label"], meta["baseline"]["state"]), ("2025", "approved"))
        self.assertTrue(meta["subtitle"].endswith("база для порівняння — 2025"))
        self.assertEqual(meta["capabilities"], {"cost": True, "plan": False, "report": True})
        self.assertEqual((meta["refresh_s"], meta["data_quality"]), (300, {"days": 30, "partial_days": 0}))
        self.assertIsNone(full["budget"])
        part = self.Api.get_dashboard("w", "eq", ["kpis", "nope"])
        self.assertEqual(set(part), {"meta", "kpis"})
        self.assertTrue(self.Api.with_user(self.u_eng).get_dashboard("m", "area", [])["meta"]["capabilities"]["plan"])
        self.assertLess(len(json.dumps(self.Api.get_dashboard("y", "area", None))), 61440)

    def test_dashboard_part_error_is_isolated(self):
        self._daily(TODAY, qty=100.0)
        with patch.object(heatmap_tools, "build_heatmap", side_effect=RuntimeError("boom")):
            data = self.Api.get_dashboard("m", "area", ["kpis", "heatmap", "stack"])
        self.assertEqual(data["heatmap"], {"error": "boom"})
        self.assertEqual(len(data["kpis"]), 7)
        self.assertEqual(len(data["stack"]["bars"]), 30)

    def test_dashboard_all_dims_and_periods(self):
        self._mockup_1710()
        for period in ("w", "m", "q", "y"):
            for dim in ("area", "eq", "mo", "prod", "shift"):
                data = self.Api.with_user(self.u_cost).get_dashboard(period, dim, ["cut", "kpis"])
                self.assertEqual(data["cut"]["dim"], dim, (period, dim))
                self.assertNotIn("error", data["cut"], (period, dim))
