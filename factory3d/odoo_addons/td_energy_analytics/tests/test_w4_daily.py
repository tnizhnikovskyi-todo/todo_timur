"""W4-A: добові факти `td.energy.daily` (AC-08…AC-13)."""

from datetime import timedelta

from odoo.exceptions import AccessError, UserError

from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

D = TODAY - timedelta(days=3)  # середа 2026-10-14


@tagged(*TAGS)
class TestW4Daily(TestW4Common):
    def _plant(self, day=D):
        return self.Daily.search([("day", "=", day), ("scope", "=", "plant")])

    def _build(self, *days):
        return self.Daily._td_build_days(list(days or [D]))

    def _grid_day(self, day=D):
        """Фідери 600 кВт·год, 12 % слотів `missing`; вводи 500 (4 200 ₴, експорт 20); СЕС 120."""
        self._fill("PM-QF-1", day, {s: 12.5 for s in range(48)}, slots=range(50))
        self._fill("PM-QF-2", day, 0.0, slots=range(12), quality="missing")
        self._fill("PM-QF-2", day, 0.0, slots=range(12, 50))
        self._fill("PM-Q1", day, 10.0, slots=range(50), kwh_export=0.4)
        self._fill("SUN-1", day, 10.0, slots=range(12))
        self._fill("TEDOM-1", day, 0.0, slots=range(4))

    def test_ac08_plant_row(self):
        self._grid_day()
        res = self._build()
        self.assertEqual(res["days"], 1)
        plant = self._plant()
        self.assertEqual(len(plant), 1)
        self.assertAlmostEqual(plant.qty, 600.0, places=3)
        self.assertAlmostEqual(plant.import_qty, 500.0, places=3)
        self.assertAlmostEqual(plant.export_qty, 20.0, places=3)
        self.assertAlmostEqual(plant.gen_pv_qty, 120.0, places=3)
        self.assertAlmostEqual(plant.gen_chp_qty, 0.0, places=3)
        self.assertAlmostEqual(plant.cost, 4200.0, places=2)
        self.assertEqual(plant.quality, "partial")
        self.assertEqual(plant.resource_id, self.res_el)

    def test_ac08_quality_ok_below_threshold(self):
        self._fill("PM-QF-1", D, 1.0, slots=range(96))
        self._fill("PM-QF-2", D, 0.0, slots=range(9), quality="missing")  # 9 з 105 < 10 %
        self._fill("PM-QF-2", D, 0.0, slots=range(9, 18))
        self._build()
        self.assertEqual(self._plant().quality, "ok")

    def test_ac09_node_rows_and_area_snapshot(self):
        self._fill("PM-SAW-1", D, 2.0, slots=range(10))
        self._fill("PM-SAW-2", D, 3.0, slots=range(10))
        self._fill("PM-RV-ALL", D, 5.0, slots=range(10))
        saw1, rv = self._node("SAW-1"), self._node("RV-ALL")
        mo = self._mo(self._product("W4-DAILY-A", 1.0), 5)
        self._alloc(mo, saw1, D, kwh=15.0, minutes=120.0)
        self._alloc(None, saw1, D, kwh=4.0, minutes=0.0, kind="idle")
        self._build()
        rows = {r.node_id.code: r for r in self.Daily.search([("day", "=", D), ("scope", "=", "node")])}
        self.assertEqual(set(rows), {"SAW-1", "SAW-2", "RV-ALL"})
        self.assertAlmostEqual(rows["SAW-1"].qty, 20.0, places=3)
        self.assertAlmostEqual(rows["SAW-1"].cost, 168.0, places=2)
        self.assertEqual((rows["SAW-1"].area_id.code, rows["SAW-2"].area_id.code), ("CUT", "CUT"))
        self.assertEqual(rows["RV-ALL"].area_id.code, "HVAC")
        self.assertAlmostEqual(rows["SAW-1"].minutes, 120.0)
        self.assertAlmostEqual(rows["SAW-1"].idle_qty, 4.0)
        # зміна розмітки не чіпає збудовані доби, повторна побудова — чіпає
        saw1.area_id = self._area("EDGE")
        rows["SAW-1"].invalidate_recordset()
        self.assertEqual(rows["SAW-1"].area_id.code, "CUT")
        self._build()
        row = self.Daily.search([("day", "=", D), ("node_id", "=", saw1.id)])
        self.assertEqual(row.area_id.code, "EDGE")
        self.assertEqual(rv.area_id.code, "HVAC")

    def test_ac10_resource_rows(self):
        self._fill("PM-Q1", D, 10.0, slots=range(50))
        t0 = self._day0(D) + timedelta(hours=8)
        for i in range(2):
            self._res_interval("gas", t0 + timedelta(minutes=15 * i), 306.0, cost=6058.80)
        self._res_interval("heat", t0, 100.0, cost=50.0)
        self._res_interval("air", t0, 40.0, cost=7.0)
        self._build()
        by_res = {r.resource_id.code: r for r in self.Daily.search([("day", "=", D), ("scope", "=", "resource")])}
        self.assertTrue({"el", "gas", "heat", "air"} <= set(by_res), sorted(by_res))
        gas = by_res["gas"]
        self.assertAlmostEqual(gas.qty, 612.0, places=3)
        self.assertAlmostEqual(gas.cost, 12117.60, places=2)
        self.assertAlmostEqual(gas.co2_kg, 1199.52, places=2)
        self.assertAlmostEqual(by_res["heat"].cost, 50.0, places=2)
        self.assertAlmostEqual(by_res["el"].qty, self._plant().import_qty, places=3)
        self.assertAlmostEqual(by_res["el"].co2_kg, 500.0 * 0.37, places=2)

    def test_ac11_shifts_and_plate_split(self):
        self._calendar_two_shifts()
        # слоти: 27 = 06:45 (поза), 28 = 07:00 (з.1), 63 = 15:45 (з.1), 64 = 16:00 (з.2), 91 = 22:45 (з.2), 92 = 23:00
        self._fill(
            "PM-QF-1", D, {27: 1.0, 28: 2.0, 63: 4.0, 64: 8.0, 91: 16.0, 92: 32.0}, slots=[27, 28, 63, 64, 91, 92]
        )
        self._fill("PM-SAW-1", D, {28: 10.0, 64: 30.0}, slots=[28, 64])
        self._fill("PM-SLIDE-1", D, 0.0, slots=[28])
        self._direct("SAW-1")
        self._driver_value("plate_m2", D, 400.0)
        self._build()
        plant = self._plant()
        self.assertAlmostEqual(plant.shift1_qty, 6.0, places=3)
        self.assertAlmostEqual(plant.shift2_qty, 24.0, places=3)
        self.assertAlmostEqual(plant.off_qty, 33.0, places=3)
        self.assertAlmostEqual(plant.shift1_qty + plant.shift2_qty + plant.off_qty, plant.qty, places=3)
        self.assertAlmostEqual(plant.cost_s1, 6 * 8.4, places=2)
        self.assertAlmostEqual(plant.cost_s2, 24 * 8.4, places=2)
        self.assertAlmostEqual(plant.cost_off, 33 * 8.4, places=2)
        self.assertAlmostEqual(plant.direct_s1, 10.0, places=3)
        self.assertAlmostEqual(plant.direct_s2, 30.0, places=3)
        self.assertAlmostEqual(plant.direct_off, 0.0, places=3)
        self.assertAlmostEqual(plant.plate_s1, 100.0, places=3)
        self.assertAlmostEqual(plant.plate_s2, 300.0, places=3)
        self.assertAlmostEqual(plant.plate_s1 + plant.plate_s2 + plant.plate_off, 400.0, places=3)

    def test_ac11_no_direct_all_plate_to_shift1(self):
        self._calendar_two_shifts()
        day = D - timedelta(days=1)
        self._fill("PM-QF-1", day, 1.0, slots=[30])
        self._driver_value("plate_m2", day, 250.0)
        self._build(day)
        plant = self._plant(day)
        self.assertAlmostEqual(plant.plate_s1, 250.0, places=3)
        self.assertAlmostEqual(plant.plate_s2 + plant.plate_off, 0.0, places=3)

    def test_ac11_weekend_all_off(self):
        self._calendar_two_shifts()
        saturday = TODAY  # 2026-10-17
        self._fill("PM-QF-1", saturday, 2.0, slots=[40, 41])
        self._build(saturday)
        plant = self._plant(saturday)
        self.assertAlmostEqual(plant.off_qty, 4.0, places=3)
        self.assertAlmostEqual(plant.shift1_qty + plant.shift2_qty, 0.0, places=3)

    def test_ac12_idempotent_and_cron(self):
        self._param("catchup_days", 14)
        for back in (0, 1, 5, 20):
            self._fill("PM-QF-1", TODAY - timedelta(days=back), 3.0, slots=[10, 11])
        self.Daily._cron_daily()
        days = sorted({r.day for r in self.Daily.search([("scope", "=", "plant")])})
        self.assertEqual(days, [TODAY - timedelta(days=5), TODAY - timedelta(days=1), TODAY])
        count = self.Daily.search_count([])
        yesterday = TODAY - timedelta(days=1)
        self.env.cr.execute(
            "UPDATE td_energy_daily SET built_at = '2000-01-01' WHERE day = %s OR day = %s", (yesterday, TODAY)
        )
        self.Daily.invalidate_model()
        self.Daily._cron_daily()
        self.assertEqual(self.Daily.search_count([]), count, "повтор без дублів")
        self.assertEqual(self._plant(yesterday).built_at.year, 2000, "вчора після закриття не перераховується")
        self.assertEqual(self._plant(TODAY).built_at, self.now, "сьогодні — завжди")
        # місцевий час раніше `daily_close_h` — вчора перераховується
        self._param("daily_close_h", 15)
        self.Daily._cron_daily()
        self.assertEqual(self._plant(yesterday).built_at, self.now)
        # без `read_enabled` — нічого
        self.env.cr.execute("DELETE FROM td_energy_daily")
        self.Daily.invalidate_model()
        self.env["ir.config_parameter"].sudo().set_param("td.energy.read_enabled", "False")
        self.Daily._cron_daily()
        self.assertFalse(self.Daily.search_count([]))

    def test_ac12_catchup_depth(self):
        self._param("catchup_days", 3)
        for back in (2, 3, 4):
            self._fill("PM-QF-1", TODAY - timedelta(days=back), 3.0, slots=[10])
        self.Daily._cron_daily()
        days = {r.day for r in self.Daily.search([("scope", "=", "plant")])}
        self.assertEqual(days, {TODAY - timedelta(days=2), TODAY - timedelta(days=3)})

    def test_ac13_identity_and_rotate(self):
        self._grid_day()
        self._build()
        plant = self._plant()
        self.assertAlmostEqual(
            plant.qty,
            sum(self.env["td.energy.interval"].search([("day", "=", D), ("role", "=", "feeder")]).mapped("kwh")),
            places=3,
        )
        # ротація
        old, fresh = TODAY - timedelta(days=11), TODAY - timedelta(days=5)
        base = self._approved_baseline(
            (TODAY - timedelta(days=100), TODAY - timedelta(days=70)), {"plate_m2": 4.0}, 100.0
        )
        for day in (old, fresh):
            self._daily(day, qty=1.0)
            self.Enpi.create({"baseline_id": base.id, "day": day, "actual": 1.0, "expected": 1.0, "quality": "ok"})
            self._driver_value("plate_m2", day, 1.0)
        self.env["ir.config_parameter"].sudo().set_param("td.energy.keep_interval_days", "10")
        self.Daily._cron_rotate()
        self.assertFalse(self.Daily.search([("day", "=", old)]))
        self.assertTrue(self.Daily.search([("day", "=", fresh)]))
        self.assertFalse(self.Enpi.search([("day", "=", old)]))
        self.assertTrue(self.Enpi.search([("day", "=", fresh)]))
        self.assertFalse(self.DriverValue.search([("day", "=", old)]))
        self.assertTrue(self.DriverValue.search([("day", "=", fresh)]))

    def test_rebuild_action_limits_and_rights(self):
        self._grid_day()
        res = self.Daily.with_user(self.u_eng).action_rebuild(D, D)
        self.assertEqual((res["days"], res["rows"] > 0), (1, True))
        with self.assertRaisesRegex(UserError, "Не більше 400 діб"):
            self.Daily.with_user(self.u_eng).action_rebuild(TODAY - timedelta(days=400), TODAY)
        with self.assertRaises(AccessError):
            self.Daily.with_user(self.u_view).action_rebuild(D, D)
        with self.assertRaises(AccessError):
            self.Daily.with_user(self.u_view)._td_build_days([D])
