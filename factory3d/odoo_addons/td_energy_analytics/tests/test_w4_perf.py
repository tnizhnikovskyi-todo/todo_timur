"""W4-A: продуктивність (AC-56…AC-58, ТП-01…ТП-03). 400 діб історії генеруються SQL-ом (≈ 2,2 млн 15-хв інтервалів),
далі — штатна побудова фактів `_td_build_days`; ТП-04 (сид) — у `test_w4_seed` і на стенді."""

import json
import statistics
import time
from datetime import timedelta

from odoo.tests import tagged

from odoo.addons.td_energy.tools import dates

from .common import TAGS, TODAY, TestW4Common

DAYS = 400
GEN_SQL = """
INSERT INTO td_energy_interval (meter_id, node_id, role, ts_start, ts_end, day, hour_local, e_start, e_end, kwh,
    kwh_export, kw_avg, price, cost, quality, built_at, is_backfill)
SELECT m.id, m.node_id, m.role, g.ts, g.ts + interval '15 minutes',
       (g.ts AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv')::date,
       EXTRACT(HOUR FROM g.ts AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv')::int,
       0, v.kwh, v.kwh, 0, v.kwh * 4, 8.4, round((v.kwh * 8.4)::numeric, 2), 'measured', %(now)s, true
  FROM td_energy_meter m
 CROSS JOIN generate_series(%(start)s::timestamp, %(end)s::timestamp, interval '15 minutes') AS g(ts)
 CROSS JOIN LATERAL (
     SELECT (CASE m.role WHEN 'consumer' THEN 1.5 WHEN 'feeder' THEN 25 ELSE 40 END)
            * (0.6 + 0.4 * sin(EXTRACT(HOUR FROM g.ts) / 24.0 * 6.2831))
            * (1 + (EXTRACT(ISODOW FROM g.ts) < 6)::int) AS kwh) v
 WHERE m.role IN ('incomer', 'feeder', 'consumer')
ON CONFLICT DO NOTHING
"""
DRIVER_SQL = """
INSERT INTO td_energy_driver_value (driver_id, day, value, quality, source_note)
SELECT d.id, g.day::date, CASE d.code WHEN 'plate_m2' THEN 800 + 400 * abs(sin(EXTRACT(DOY FROM g.day)))
                                      ELSE 9 + 8 * sin(EXTRACT(DOY FROM g.day) / 58.0) END,
       'estimated', 'perf'
  FROM td_energy_driver d CROSS JOIN generate_series(%s::date, %s::date, interval '1 day') AS g(day)
 WHERE d.code IN ('plate_m2', 'hdd', 'perf_x')
ON CONFLICT DO NOTHING
"""


@tagged(*TAGS)
class TestW4Perf(TestW4Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cr = cls.env.cr
        cls.first = TODAY - timedelta(days=DAYS)
        cls.last = TODAY - timedelta(days=1)
        d0, d1 = dates.local_day_bounds(cls.first)[0], dates.local_day_bounds(TODAY)[0]
        cr.execute(GEN_SQL, {"now": cls.now, "start": d0, "end": d1 - timedelta(minutes=15)})
        cls.Driver.create({"code": "perf_x", "name": "Третій драйвер", "source_kind": "manual"})
        cr.execute(DRIVER_SQL, (cls.first, cls.last))
        cls.days = [cls.first + timedelta(days=i) for i in range(DAYS)]
        started = time.monotonic()
        cls.build_stats = cls.Daily._td_build_days(cls.days)
        cls.build_seconds = time.monotonic() - started
        cls.base = cls.Baseline.create(
            {
                "resource_id": cls.res_el.id, "period_from": cls.first, "period_to": cls.first + timedelta(days=239),
                "method": "manual", "const_per_day": 4000.0, "r2": 0.9,
                "line_ids": [(0, 0, {"driver_id": cls.plate.id, "coef": 4.0})],
            }
        )  # fmt: skip
        cls.base.action_approve()
        cls.Budget.create({"month": TODAY.replace(day=1), "amount_uah": 1950000.0}).action_approve()
        cls.Daily.invalidate_model()

    def _median(self, func, runs=10):
        func()  # прогрів кешів (групи, параметри)
        times = []
        for _ in range(runs):
            started = time.monotonic()
            func()
            times.append(time.monotonic() - started)
        return statistics.median(times)

    # --- ТП-01 / AC-56 ----------------------------------------------------------------------------------
    def test_tp01_dashboard_speed_and_queries(self):
        api = self.Api.with_user(self.u_cost)
        month = self._median(lambda: api.get_dashboard("m", "area", None))
        self.assertLess(month, 0.6, "get_dashboard('m'): %.3f с" % month)
        year = self._median(lambda: api.get_dashboard("y", "area", None))
        self.assertLess(year, 1.5, "get_dashboard('y'): %.3f с" % year)
        heat = self._median(lambda: api.get_heatmap("y"))
        self.assertLess(heat, 0.4, "теплокарта: %.3f с" % heat)
        for period in ("m", "y"):
            before = self.env.cr.sql_log_count
            api.get_dashboard(period, "area", None)
            queries = self.env.cr.sql_log_count - before
            self.assertLessEqual(queries, 60, "SQL у get_dashboard(%r): %s" % (period, queries))

    def test_tp01_all_dims_year(self):
        api = self.Api.with_user(self.u_cost)
        for dim in ("area", "eq", "mo", "prod", "shift"):
            started = time.monotonic()
            data = api.get_dashboard("y", dim, ["cut"])
            self.assertNotIn("error", data["cut"], dim)
            self.assertLess(time.monotonic() - started, 1.5, dim)

    # --- ТП-02 / AC-57 ----------------------------------------------------------------------------------
    def test_tp02_build_times(self):
        self.assertEqual(self.build_stats["days"], DAYS)
        self.assertLess(self.build_seconds, 300.0, "400 діб: %.1f с" % self.build_seconds)
        day = self.days[200]
        started = time.monotonic()
        self.Daily._td_build_days([day])
        self.assertLess(time.monotonic() - started, 3.0)

    # --- ТП-03 / AC-57 ----------------------------------------------------------------------------------
    def test_tp03_fit_and_rotate(self):
        draft = self._baseline(
            (self.first, self.first + timedelta(days=299)), {"plate_m2": 0.0, "hdd": 0.0, "perf_x": 0.0}
        )
        started = time.monotonic()
        draft.action_fit()
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual(draft.n_days, 300)
        self.env.cr.execute("UPDATE ir_config_parameter SET value = '120' WHERE key = 'td.energy.keep_interval_days'")
        started = time.monotonic()
        self.Daily._cron_rotate()
        self.assertLess(time.monotonic() - started, 30.0)
        self.assertFalse(self.Daily.search_count([("day", "<", TODAY - timedelta(days=121))]))
        self.assertTrue(self.Daily.search_count([("day", ">=", TODAY - timedelta(days=119))]))

    # --- AC-58 -------------------------------------------------------------------------------------------
    def test_ac58_volumes_and_payload(self):
        rows = self.Daily.search_count([])
        self.assertGreater(rows, 40 * DAYS)
        self.assertLessEqual(rows, 22000)
        self.assertLessEqual(self.Enpi.search_count([]), 1200)
        payload = self.Api.with_user(self.u_cost).get_dashboard("y", "area", None)
        self.assertLessEqual(len(json.dumps(payload)), 60 * 1024)
