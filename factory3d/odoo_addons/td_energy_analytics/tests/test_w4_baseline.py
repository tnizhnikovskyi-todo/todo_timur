"""W4-A: модель бази: затвердження й архівація (AC-16, AC-17)."""

from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

FIRST = TODAY - timedelta(days=100)
PERIOD = (FIRST, FIRST + timedelta(days=29))


@tagged(*TAGS)
class TestW4Baseline(TestW4Common):
    def _fitted(self, period=PERIOD, **vals):
        for i in range((period[1] - period[0]).days + 1):
            day = period[0] + timedelta(days=i)
            self._daily(day, qty=1820.0 + 4.1 * (800.0 + 20 * i), import_qty=100.0, cost=840.0)
            self._driver_value("plate_m2", day, 800.0 + 20 * i)
        base = self._baseline(period, {"plate_m2": 0.0}, **vals)
        base.action_fit()
        return base

    def test_ac16_approve_rights_and_thresholds(self):
        base = self._fitted()
        for user in (self.u_view, self.u_eng):
            with self.assertRaises(AccessError):
                base.with_user(user).action_approve()
        base.r2 = 0.3
        with self.assertRaisesRegex(UserError, "Модель не може бути затверджена"):
            base.with_user(self.u_chief).action_approve()
        base.r2 = 0.95
        base.line_ids.coef = -1.0
        with self.assertRaisesRegex(UserError, "Модель не може бути затверджена"):
            base.with_user(self.u_chief).action_approve()
        base.action_fit()
        base.with_user(self.u_chief).action_approve()
        self.assertEqual((base.state, base.approved_by), ("approved", self.u_chief))
        self.assertTrue(base.approved_at)

    def test_ac16_one_approved_per_pair_and_enpi_recompute(self):
        first = self._fitted()
        first.with_user(self.u_chief).action_approve()
        self.assertTrue(self.Enpi.search_count([("baseline_id", "=", first.id)]), "EnPI пораховано при затвердженні")
        second = self._baseline(PERIOD, {"plate_m2": 0.0}, method="manual", const_per_day=1000.0)
        second.line_ids.coef = 3.0
        second.with_user(self.u_chief).action_approve()
        self.assertEqual((first.state, second.state), ("archived", "approved"))
        self.assertEqual(
            self.Baseline.search_count([("state", "=", "approved"), ("resource_id", "=", self.res_el.id)]), 1
        )
        # інша пара (газ) не архівує
        gas = self._baseline(PERIOD, {"hdd": 0.0}, resource="gas", method="manual", const_per_day=10.0)
        gas.line_ids.coef = 2.0
        gas.with_user(self.u_chief).action_approve()
        self.assertEqual((second.state, gas.state), ("approved", "approved"))
        # прямий запис `approved` менеджером — заборонений; другий approved у парі — теж
        third = self._baseline(PERIOD, {"plate_m2": 0.0}, method="manual")
        with self.assertRaises(AccessError):
            third.with_user(self.u_eng).write({"state": "approved"})
        with self.assertRaises(ValidationError):
            third.write({"state": "approved"})

    def test_ac16_manual_skips_r2(self):
        base = self._baseline(PERIOD, {"plate_m2": 4.0}, method="manual", const_per_day=1800.0)
        self.assertEqual(base.r2, 0.0)
        base.with_user(self.u_chief).action_approve()
        self.assertEqual(base.state, "approved")

    def test_ac16_archive_and_back_to_draft(self):
        base = self._fitted()
        base.with_user(self.u_chief).action_approve()
        self.assertTrue(self.Enpi.search_count([("baseline_id", "=", base.id)]))
        with self.assertRaises(AccessError):
            base.with_user(self.u_eng).action_to_draft()
        base.with_user(self.u_chief).action_to_draft()
        self.assertEqual(base.state, "draft")
        self.assertFalse(self.Enpi.search_count([("baseline_id", "=", base.id)]), "EnPI бази скинуто")
        base.with_user(self.u_chief).action_approve()
        base.with_user(self.u_chief).action_archive()
        self.assertEqual(base.state, "archived")

    def test_constraints(self):
        with self.assertRaisesRegex(ValidationError, "ділянку"):
            self._baseline(PERIOD, {}, scope="area")
        with self.assertRaisesRegex(ValidationError, "лише електрики та газу|електрики та газу"):
            self._baseline(PERIOD, {}, resource="heat")
        with self.assertRaisesRegex(ValidationError, "не коротшим"):
            self._baseline((FIRST, FIRST + timedelta(days=10)), {})
        self.assertIn("Електрика", self._baseline(PERIOD, {}).name)

    def test_ac17_gas_baseline_hdd(self):
        for i in range(40):
            day = FIRST + timedelta(days=i)
            hdd = float((i * 5) % 17)
            self._daily(day, scope="resource", resource="gas", qty=120.0 + 25.0 * hdd, cost=1000.0)
            self._daily(day, qty=3000.0)
            self._driver_value("hdd", day, hdd)
        base = self._baseline((FIRST, FIRST + timedelta(days=39)), {"hdd": 0.0}, resource="gas")
        base.action_fit()
        self.assertAlmostEqual(base.const_per_day, 120.0, delta=0.001)
        self.assertAlmostEqual(base.line_ids.coef, 25.0, delta=1e-6)
        self.assertAlmostEqual(base.expected({"hdd": 11.0}), 395.0, places=2)
        base.with_user(self.u_chief).action_approve()
        self.assertEqual(base.state, "approved")
        series = base._td_expected_series(FIRST, FIRST + timedelta(days=1))
        self.assertAlmostEqual(series[FIRST], 120.0, places=2)
