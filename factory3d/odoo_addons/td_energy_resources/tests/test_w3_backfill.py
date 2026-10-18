"""W3-A: AC-46…AC-48, AC-61 — генератор історії ресурсів (R-22, API-08)."""

import hashlib
import math
import time
from datetime import datetime, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import SLOT, TAGS, TestW3Common

UNTIL = datetime(2026, 10, 12, 21, 0)  # вівторок 00:00 Київ (13.10)


@tagged(*TAGS)
class TestW3Backfill(TestW3Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Interval = cls.env["td.energy.interval"]
        cls.Meter = cls.env["td.energy.meter"]

    def n_meters(self):
        """Лічильники backfill: 16 ресурсних + 2 реактивні вводи + теплові (їх створює міст td_energy_resources_bms)."""
        return 18 + self.Meter.search_count([("resource_id.code", "=", "heat"), ("active", "=", True)])

    def electric(self, days, seed=1):
        return self.Interval._td_backfill(days=days, until=UNTIL, seed=seed, with_balance=False, with_events=False)

    def backfill(self, days, seed=1, **kw):
        kw.setdefault("until", UNTIL)
        return self.ResInterval._td_backfill(days=days, seed=seed, **kw)

    def digest(self):
        self.env.cr.execute(
            "SELECT m.code, r.metric, r.ts_start, r.qty, r.cost FROM td_energy_res_interval r"
            " JOIN td_energy_meter m ON m.id = r.meter_id ORDER BY 1, 2, 3"
        )
        return hashlib.sha256(repr(self.env.cr.fetchall()).encode()).hexdigest()

    def test_rows_and_quality(self):  # AC-46
        self.electric(2)
        stats = self.backfill(2)
        n = self.n_meters()
        self.assertEqual((stats["meters"], stats["slots"], stats["rows"], stats["skipped"]), (n, 192, n * 192, 0))
        self.assertEqual(stats["since"], "2026-10-10 21:00:00")
        self.assertEqual(self.ResInterval.search_count([]), n * 192)
        self.assertEqual(self.ResInterval.search_count([("is_backfill", "=", False)]), 0)
        estimated = self.ResInterval.search([("quality", "=", "estimated")]).mapped("meter_id")
        self.assertTrue(estimated)
        self.assertEqual(set(estimated.mapped("mode")), {"estimate"})
        measured = self.ResInterval.search([("quality", "=", "measured")]).mapped("meter_id")
        self.assertFalse(set(measured.mapped("mode")) & {"estimate"})
        self.assertEqual(self.ResInterval.search_count([("metric", "=", "react")]), 2 * 192)
        self.assertEqual(self.ResInterval.search_count([("quality", "=", "missing")]), 0)
        last = UNTIL - SLOT
        starts = set(self.Meter.search([("resource_id.code", "!=", "el")]).mapped("res_last_interval_start"))
        self.assertEqual(starts, {last})

    def test_properties_and_determinism(self):  # AC-47
        self.electric(7)
        stats = self.backfill(7)
        self.assertEqual(stats["rows"], self.n_meters() * 7 * 96)
        cr = self.env.cr

        def total(code):
            cr.execute(
                "SELECT COALESCE(SUM(r.qty), 0) FROM td_energy_res_interval r"
                " JOIN td_energy_meter m ON m.id = r.meter_id WHERE m.code = %s AND r.metric = 'main'",
                (code,),
            )
            return cr.fetchone()[0]

        main = total("GM-MAIN")
        branches = sum(total(c) for c in ("GM-BOILER", "GM-CHP", "GM-DRY1", "GM-CANTEEN"))
        self.assertGreater(main, 0)
        self.assertLessEqual(abs(main - branches) / main, 0.03)
        cr.execute(
            """SELECT MIN(r.rate_avg) FROM td_energy_res_interval r JOIN td_energy_meter m ON m.id = r.meter_id
                WHERE m.code = 'AM-MAIN' AND r.hour_local < 5"""
        )
        self.assertAlmostEqual(cr.fetchone()[0], 1.6, delta=0.2)
        cr.execute(
            """SELECT r.day, SUM(r.qty), (SELECT SUM(i.kwh) FROM td_energy_interval i
                    JOIN td_energy_meter c ON c.id = i.meter_id WHERE c.code = 'PM-COMPRESSOR' AND i.day = r.day)
                 FROM td_energy_res_interval r JOIN td_energy_meter m ON m.id = r.meter_id
                WHERE m.code = 'AM-MAIN' GROUP BY r.day ORDER BY r.day"""
        )
        rows = [(a, b) for _d, a, b in cr.fetchall() if b]
        self.assertGreaterEqual(len(rows), 6)
        self.assertGreaterEqual(self.pearson([a for a, _b in rows], [b for _a, b in rows]), 0.9)
        first = self.digest()
        again = self.backfill(7)  # ідемпотентність
        self.assertEqual((again["rows"], again["skipped"]), (0, stats["rows"]))
        purged = self.backfill(7, purge=True)
        self.assertEqual(purged["purged_rows"], stats["rows"])
        self.assertEqual(self.ResInterval.search_count([]), 0)
        self.backfill(7)
        self.assertEqual(self.digest(), first)  # однаковий seed — однаковий набір

    @staticmethod
    def pearson(xs, ys):
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
        sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
        sy = math.sqrt(sum((y - my) ** 2 for y in ys))
        return cov / (sx * sy) if sx and sy else 0.0

    def test_purge_keeps_live(self):  # AC-47: purge не чіпає is_backfill = False
        self.electric(1)
        self.backfill(1)
        meter = self.Meter.search([("code", "=", "GM-MAIN")])
        self.env.cr.execute(
            "UPDATE td_energy_res_interval SET is_backfill = false WHERE meter_id = %s AND ts_start = %s",
            (meter.id, UNTIL - SLOT),
        )
        self.backfill(1, purge=True)
        self.assertEqual([r[0] for r in self.rows(meter)], [UNTIL - SLOT])

    def test_live_not_overwritten(self):  # AC-48
        meter = self.Meter.search([("code", "=", "GM-MAIN")])
        other = self.Meter.search([("code", "=", "WM-MAIN")])
        live_ts = UNTIL + SLOT
        self.res_interval(meter, live_ts, 7.0)  # живий слот після `until`
        self.res_interval(other, UNTIL - SLOT, 5.0)  # живий слот усередині історії
        self.env.cr.execute(
            "UPDATE td_energy_meter SET res_last_interval_start = %s WHERE id = %s", (live_ts, meter.id)
        )
        meter.invalidate_recordset()
        self.electric(1)
        stats = self.backfill(1)
        self.assertEqual(stats["skipped"], 1)  # слот WM-MAIN уже зайнятий живим рядком
        self.assertEqual(self.rows(meter)[-1][:2], (live_ts, 7.0))
        self.assertEqual(meter.res_last_interval_start, live_ts)  # не зменшується
        self.env.cr.execute("SELECT MAX(ts_start) FROM td_energy_res_interval WHERE is_backfill")
        self.assertLess(self.env.cr.fetchone()[0], UNTIL)  # слоти ≥ until не створюються
        self.assertEqual([r for r in self.rows(other) if r[0] == UNTIL - SLOT][0][1], 5.0)
        self.assertEqual([r for r in self.rows(other) if r[0] == UNTIL - SLOT][0][7], False)

    def test_access_and_limits(self):  # API-08
        with self.assertRaises(AccessError):
            self.ResInterval.with_user(self.u_eng)._td_backfill(days=1, until=UNTIL)
        for days in (0, 401):
            with self.assertRaises(UserError):
                self.backfill(days)
        self.ResInterval.with_user(self.u_admin)._td_backfill(days=1, until=UNTIL, seed=3)
        # фільтр ресурсів: лише вода
        self.ResInterval.search([]).unlink()
        stats = self.backfill(1, resources=["water"])
        self.assertEqual(stats["meters"], 5)
        self.assertEqual(self.ResInterval.search_count([]), 5 * 96)
        self.assertEqual(self.ResInterval.search_count([("resource_id.code", "!=", "water")]), 0)

    def test_without_electric_data(self):  # попередження, оцінні слоти — missing; вимірювані генеруються
        stats = self.backfill(1)
        self.assertEqual(stats["rows"], self.n_meters() * 96)
        missing = self.ResInterval.search([("quality", "=", "missing")]).mapped("meter_id")
        self.assertIn("AM-EDGE1", missing.mapped("code"))
        self.assertIn("PM-Q1", missing.mapped("code"))
        self.assertNotIn("GM-MAIN", missing.mapped("code"))

    def test_performance(self):  # AC-61, ТП-04: 90 діб
        started = time.monotonic()
        stats = self.backfill(90)
        self.assertLess(time.monotonic() - started, 60.0)
        self.assertEqual(stats["rows"], self.n_meters() * 90 * 96)
        self.assertIn("seconds", stats)
        self.assertEqual(stats["since"], (UNTIL - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S"))
