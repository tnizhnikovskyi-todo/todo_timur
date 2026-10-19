"""W4-A: EnPI за добами (AC-18, AC-19, AC-21; AC-20 — після API-05, див. кінець файлу)."""

from datetime import timedelta

from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

PERIOD = (TODAY - timedelta(days=120), TODAY - timedelta(days=91))


@tagged(*TAGS)
class TestW4Enpi(TestW4Common):
    def _base(self, **kw):
        return self._approved_baseline(PERIOD, {"plate_m2": 4.1}, 1820.0, **kw)

    def _enpi_sql(self, base, day):
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT actual, expected, enpi, quality FROM td_energy_enpi WHERE baseline_id = %s AND day = %s",
            (base.id, day),
        )
        return self.env.cr.fetchone()

    def test_ac18_cron_rows(self):
        base = self._base()
        yesterday = TODAY - timedelta(days=1)
        self._daily(yesterday, qty=7000.0)
        self._driver_value("plate_m2", yesterday, 1000.0)
        d2 = TODAY - timedelta(days=2)  # немає значення драйвера
        self._daily(d2, qty=5000.0)
        d3 = TODAY - timedelta(days=3)  # неповна доба
        self._daily(d3, qty=6000.0, quality="partial")
        self._driver_value("plate_m2", d3, 1000.0)
        self.Enpi._cron_enpi()
        actual, expected, enpi, quality = self._enpi_sql(base, yesterday)
        self.assertAlmostEqual(expected, 1820.0 + 4100.0, places=2)
        self.assertAlmostEqual(enpi, 7000.0 / 5920.0, places=3)
        self.assertEqual((actual, quality), (7000.0, "ok"))
        row = self._enpi_sql(base, d2)
        self.assertEqual((row[0], row[1], row[2], row[3]), (5000.0, None, None, "no_driver"))
        self.assertEqual(self._enpi_sql(base, d3)[3], "partial")
        count = self.Enpi.search_count([])
        self.Enpi._cron_enpi()
        self.assertEqual(self.Enpi.search_count([]), count, "повтор ідемпотентний")
        self.assertEqual(
            self.Enpi.search([("baseline_id", "=", base.id), ("day", "=", yesterday)]).drivers, {"plate_m2": 1000.0}
        )

    def test_ac19_period_totals(self):
        base = self._base()
        days = [TODAY - timedelta(days=k) for k in range(1, 8)]
        for day in days:
            self._daily(day, qty=48150.0 / 7, import_qty=500.0, cost=4200.0)
            self._driver_value("plate_m2", day, 9000.0 / 7)
        self.Enpi.recompute(days[-1], days[0], baseline=base)
        totals = self.Enpi.period_totals(base, days[-1], days[0])
        self.assertAlmostEqual(totals["enpi"], 0.97, places=4)
        self.assertAlmostEqual(totals["saving_pct"], 3.0, places=1)
        self.assertAlmostEqual(totals["saving_qty"], 1490.0, delta=0.05)
        self.assertAlmostEqual(totals["coverage"], 1.0)
        self.assertNotIn("saving_cost", self.Enpi.with_user(self.u_view).period_totals(base, days[-1], days[0]))
        cost = self.Enpi.with_user(self.u_cost).period_totals(base, days[-1], days[0])
        self.assertAlmostEqual(cost["saving_cost"], 1490.0 * 8.4, delta=1.0)
        # покриття < 0,5 → enpi null
        low = self.Enpi.period_totals(base, days[-1], days[-1] + timedelta(days=29))
        self.assertIsNone(low["enpi"])
        self.assertAlmostEqual(low["coverage"], 7 / 30, places=3)

    def test_ac21_cron_scope_and_gaps(self):
        approved, draft = self._base(), self._baseline(PERIOD, {"plate_m2": 4.0}, method="manual", const_per_day=1.0)
        archived = self._baseline(PERIOD, {"plate_m2": 4.0}, method="manual", const_per_day=1.0)
        archived.write({"state": "archived"})
        for k in (1, 4):
            day = TODAY - timedelta(days=k)
            self._daily(day, qty=5000.0)
            self._driver_value("plate_m2", day, 900.0)
        self.Enpi._cron_enpi()
        self.assertEqual(self.Enpi.search_count([("baseline_id", "=", approved.id)]), 2, "вчора й пропуск")
        self.assertFalse(self.Enpi.search_count([("baseline_id", "in", (draft | archived).ids)]))

    def test_recompute_rights_and_range(self):
        base = self._base()
        from odoo.exceptions import AccessError

        with self.assertRaises(AccessError):
            self.Enpi.with_user(self.u_view).recompute(PERIOD[0], PERIOD[1], baseline=base)
        res = self.Enpi.with_user(self.u_eng).recompute(TODAY - timedelta(days=3), TODAY - timedelta(days=1))
        self.assertEqual(res["baselines"], 1)

    def test_area_scope_actual(self):
        area_base = self._approved_baseline(PERIOD, {"plate_m2": 1.0}, 100.0, scope="area", area="CUT")
        day = TODAY - timedelta(days=1)
        self._daily(day, qty=9999.0)
        self._daily(day, scope="node", node="SAW-1", qty=300.0)
        self._daily(day, scope="node", node="SAW-2", qty=200.0)
        self._daily(day, scope="node", node="EDGE-1", qty=77.0)
        self._driver_value("plate_m2", day, 400.0)
        self.Enpi.recompute(day, day, baseline=area_base)
        actual, expected, _enpi, _q = self._enpi_sql(area_base, day)
        self.assertEqual((actual, expected), (500.0, 500.0))

    def test_ac20_weekly_enpi(self):
        base = self._base()
        days = [TODAY - timedelta(days=k) for k in range(84)]
        for day in days:
            partial_today = day == TODAY  # неповна поточна доба: у точки тижнів не входить
            qty = 1000.0 if partial_today else 6800.0
            self._daily(day, qty=qty, import_qty=100.0, cost=840.0)
            self.Enpi.create({"baseline_id": base.id, "day": day, "actual": qty, "expected": 7100.0, "quality": "ok"})
        data = self.Api.with_user(self.u_cost).get_enpi()
        weeks = data["weeks"]
        self.assertEqual(len(weeks), 12)
        self.assertEqual([w["key"] for w in weeks], sorted(w["key"] for w in weeks), "за зростанням дат")
        self.assertEqual(weeks[-1]["key"], TODAY.isoformat())
        self.assertEqual(weeks[-2]["key"], (TODAY - timedelta(days=7)).isoformat())
        self.assertEqual((weeks[0]["label"], weeks[-1]["label"]), ("12 тижнів тому", "цей тиждень"))
        self.assertEqual({w["label"] for w in weeks[1:-1]}, {""})
        self.assertAlmostEqual(weeks[3]["expected_mwh"], 49.7)
        self.assertAlmostEqual(weeks[3]["actual_mwh"], 47.6)
        # останній тиждень (6 повних діб + неповна поточна) нормується до 7 діб: без хибного провалу
        self.assertAlmostEqual(weeks[-1]["expected_mwh"], 49.7)
        self.assertAlmostEqual(weeks[-1]["actual_mwh"], 47.6)
        self.assertEqual((data["y_min"], data["y_max"]), (45, 55))  # floor5(0,95·47,6), ceil5(1,05·49,7)
        self.assertAlmostEqual(data["enpi"], 6800 / 7100, places=4)
        self.assertAlmostEqual(data["saving_pct"], 4.2)
        self.assertAlmostEqual(data["saving_kwh"], 83 * 300.0)  # доби до вчора
        self.assertEqual(data["saving_uah"], round(83 * 300.0 * 8.4))
        view = self.Api.with_user(self.u_view).get_enpi()
        self.assertNotIn("saving_uah", view)
        self.assertAlmostEqual(view["enpi"], data["enpi"])

    def test_ac20_without_baseline(self):
        self._daily(TODAY - timedelta(days=2), qty=6800.0)
        data = self.Api.get_enpi()
        self.assertEqual(len(data["weeks"]), 12)
        self.assertIsNone(data["enpi"])
        self.assertIsNone(data["saving_pct"])
        self.assertIsNone(data["weeks"][-1]["expected_mwh"])
        self.assertAlmostEqual(data["weeks"][-1]["actual_mwh"], 6.8 * 7)  # одна повна доба нормується до тижня

    def test_ac20_partial_today_without_baseline(self):
        for k in range(1, 7):
            self._daily(TODAY - timedelta(days=k), qty=6800.0)
        self._daily(TODAY, qty=900.0)  # неповна доба
        last = self.Api.get_enpi()["weeks"][-1]
        self.assertAlmostEqual(last["actual_mwh"], 47.6)
