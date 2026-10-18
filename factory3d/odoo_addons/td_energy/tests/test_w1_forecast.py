"""W1-A: AC-114, AC-115 — профіль доби 15 хв і прогноз до кінця доби (R-28)."""

from datetime import datetime, timedelta

from odoo.tests import tagged

from .common import TAGS, TestW1Common


@tagged(*TAGS)
class TestW1Forecast(TestW1Common):
    def today_feeder(self, kwh=25.0, slots=range(57)):
        """Факт сьогодні (слоти 0…56): PM-QF-2 по 25 кВт·год (100 кВт)."""
        day0 = datetime(2026, 10, 16, 21, 0)
        for s in slots:
            self.interval("PM-QF-2", day0 + timedelta(minutes=15 * s), kwh)

    def profile(self):
        return self.env["td.energy.dashboard"].with_user(self.u_view).get_pult(parts=["profile"])

    def test_profile_and_forecast(self):  # AC-114
        self.fixture_grid()
        self.today_feeder()
        self.typical("PM-QF-2", days=8)
        data = self.profile()
        profile = data["profile"]
        self.assertEqual((profile["step_min"], profile["now_slot"], profile["forecast_days_used"]), (15, 57, 8))
        for key in ("cons", "grid", "pv", "cons_fc", "grid_fc"):
            self.assertEqual(len(profile[key]), 96, key)
        self.assertEqual(profile["cons"][:57], [100.0] * 57)
        self.assertEqual(profile["cons"][57], 667.0)  # слот «зараз» — живі значення
        self.assertTrue(all(v is None for v in profile["cons"][58:]))
        self.assertTrue(all(v is None for v in profile["cons_fc"][:57]))
        self.assertEqual(profile["cons_fc"][57], 667.0)  # перша прогнозна точка = поточна
        self.assertEqual(profile["cons_fc"][58:], [100.0] * 38)
        self.assertEqual(profile["grid_fc"][57], 358.0)
        self.assertEqual(profile["grid_fc"][58:], [100.0] * 38)  # без СЕС: grid_fc = cons_fc
        self.assertEqual(data["foot"]["forecast_kwh"], 950)  # 38 · 100 кВт · 0,25 (+0 імпорту: інтервалів вводів немає)

    def test_pv_scaling_and_no_history(self):  # AC-115
        self.fixture_grid()
        self.today_feeder()
        self.typical("PM-QF-2", days=3)
        slots = range(30, 71)
        self.typical("SUN-1", days=3, kwh=10.0, slots=slots)  # типова СЕС 40 кВт
        day0 = datetime(2026, 10, 16, 21, 0)
        for s in range(30, 57):
            self.interval("SUN-1", day0 + timedelta(minutes=15 * s), 6.0)  # факт: 60 % типового
        profile = self.profile()["profile"]
        self.assertEqual(profile["pv"][30], 24.0)
        self.assertEqual(profile["grid_fc"][60], round(100.0 - 40.0 * 0.6, 1))  # pv_fc = typical · 0,6
        self.assertEqual(profile["grid_fc"][80], 100.0)  # типової СЕС там немає
        for s in range(30, 57):  # факт 20 % → clamp до 0,3
            self.env["td.energy.interval"].search(
                [("meter_id.code", "=", "SUN-1"), ("ts_start", "=", day0 + timedelta(minutes=15 * s))]
            ).kwh = 2.0
        clamped = self.profile()["profile"]
        self.assertEqual(clamped["grid_fc"][60], round(100.0 - 40.0 * 0.3, 1))
        # менше 3 днів історії → прогноз недоступний
        self.env["td.energy.interval"].search(
            [("meter_id.code", "=", "PM-QF-2"), ("ts_start", "<", datetime(2026, 10, 9))]
        ).unlink()
        none = self.profile()
        self.assertTrue(all(v is None for v in none["profile"]["cons_fc"] + none["profile"]["grid_fc"]))
        self.assertLess(none["profile"]["forecast_days_used"], 3)
        self.assertIsNone(none["foot"]["forecast_kwh"])
