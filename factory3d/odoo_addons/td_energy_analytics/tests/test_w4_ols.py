"""W4-A: регресія бази (AC-14, AC-15, AC-60): чиста `tools/ols.py` і `action_fit` моделі."""

import ast
import inspect
import math
import time
from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.td_energy_analytics.tools import ols
from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

FIRST = TODAY - timedelta(days=200)


@tagged(*TAGS)
class TestW4Ols(TestW4Common):
    def _series(self, n, func, drivers=("plate_m2",), first=FIRST, quality="ok"):
        """`n` діб: `func(i) → (x…, y)`; факт `plant` і значення драйверів."""
        for i in range(n):
            day = first + timedelta(days=i)
            *xs, y = func(i)
            self._daily(day, qty=y, quality=quality)
            for code, x in zip(drivers, xs, strict=True):
                self._driver_value(code, day, x)
        return (first, first + timedelta(days=n - 1))

    # --- чиста функція ----------------------------------------------------------------------------------
    def test_ac14_pure_one_driver(self):
        X = [[800.0 + 20 * i] for i in range(30)]
        y = [1820.0 + 4.1 * x[0] for x in X]
        const, coefs, r2, rmse = ols.fit(X, y)
        self.assertAlmostEqual(const, 1820.0, delta=0.001)
        self.assertAlmostEqual(coefs[0], 4.1, delta=1e-6)
        self.assertAlmostEqual(r2, 1.0, places=9)
        self.assertAlmostEqual(rmse, 0.0, places=6)

    def test_ac14_pure_two_drivers_and_k0(self):
        X = [[800.0 + 20 * i, float((i * 7) % 13)] for i in range(40)]
        y = [1500.0 + 4.0 * a + 35.0 * b for a, b in X]
        const, coefs, r2, _rmse = ols.fit(X, y)
        self.assertAlmostEqual(const, 1500.0, delta=0.001)
        self.assertAlmostEqual(coefs[0], 4.0, delta=1e-6)
        self.assertAlmostEqual(coefs[1], 35.0, delta=1e-6)
        self.assertAlmostEqual(r2, 1.0, places=9)
        const, coefs, r2, rmse = ols.fit([], [10.0, 20.0, 30.0])
        self.assertEqual((const, coefs, r2), (20.0, [], 0.0))
        self.assertAlmostEqual(rmse, math.sqrt(200.0 / 3))

    def test_ac15_pure_singular(self):
        X = [[800.0 + 20 * i, 2 * (800.0 + 20 * i)] for i in range(30)]
        with self.assertRaises(ols.SingularError):
            ols.fit(X, [float(i) for i in range(30)])
        with self.assertRaises(ols.SingularError):  # сталий драйвер
            ols.fit([[5.0] for _ in range(30)], [float(i) for i in range(30)])

    def test_ac60_pure_python_and_speed(self):
        imported = set()
        for node in ast.walk(ast.parse(inspect.getsource(ols))):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertFalse(imported & {"numpy", "scipy", "pandas"}, imported)
        X = [[800.0 + (i * 37) % 400, float((i * 7) % 53), float((i * 11) % 29)] for i in range(400)]
        y = [100.0 + 3.0 * a + 2.0 * b + 5.0 * c + (i % 5) for i, (a, b, c) in enumerate(X)]
        started = time.monotonic()
        ols.fit(X, y)
        self.assertLess(time.monotonic() - started, 0.1)

    # --- модель -----------------------------------------------------------------------------------------
    def test_ac14_model_fit_one_driver(self):
        period = self._series(30, lambda i: (800.0 + 20 * i, 1820.0 + 4.1 * (800.0 + 20 * i)))
        base = self._baseline(period, {"plate_m2": 0.0})
        self.assertTrue(base.name)
        base.with_user(self.u_eng).action_fit()
        self.assertAlmostEqual(base.const_per_day, 1820.0, delta=0.001)
        self.assertAlmostEqual(base.line_ids.coef, 4.1, delta=1e-6)
        self.assertAlmostEqual(base.r2, 1.0, places=6)
        self.assertAlmostEqual(base.rmse, 0.0, places=2)
        self.assertEqual(base.n_days, 30)
        self.assertTrue(base.fitted_at)
        self.assertFalse(base.warning)
        self.assertAlmostEqual(base.expected({"plate_m2": 1000.0}), 1820.0 + 4100.0, places=2)
        self.assertIsNone(base.expected({}))

    def test_ac14_model_two_drivers(self):
        period = self._series(
            40,
            lambda i: (800.0 + 20 * i, float((i * 7) % 13), 1500.0 + 4.0 * (800.0 + 20 * i) + 35.0 * ((i * 7) % 13)),
            drivers=("plate_m2", "hdd"),
        )
        base = self._baseline(period, {"plate_m2": 0.0, "hdd": 0.0})
        base.action_fit()
        self.assertAlmostEqual(base.const_per_day, 1500.0, delta=0.001)
        coefs = {line.driver_id.code: line.coef for line in base.line_ids}
        self.assertAlmostEqual(coefs["plate_m2"], 4.0, delta=1e-6)
        self.assertAlmostEqual(coefs["hdd"], 35.0, delta=1e-6)

    def test_ac14_model_k0_mean(self):
        period = self._series(30, lambda i: (1000.0 + i,), drivers=())
        base = self._baseline(period, {})
        base.action_fit()
        self.assertAlmostEqual(base.const_per_day, 1000.0 + 14.5, places=3)
        self.assertAlmostEqual(base.r2, 0.0)

    def test_ac15_not_enough_days(self):
        period = self._series(25, lambda i: (800.0 + 20 * i, 2000.0 + 3 * i))
        base = self._baseline((period[0], period[0] + timedelta(days=29)), {"plate_m2": 0.0})
        with self.assertRaisesRegex(UserError, r"Замало даних для моделі бази: потрібно ≥ 30 діб, є 25\."):
            base.action_fit()
        self.assertEqual(base.state, "draft")

    def test_ac15_partial_days_are_skipped(self):
        period = self._series(30, lambda i: (800.0 + 20 * i, 2000.0 + 3 * i))
        self.Daily.search([("day", "in", [FIRST, FIRST + timedelta(days=1)])]).write({"quality": "partial"})
        base = self._baseline(period, {"plate_m2": 0.0})
        with self.assertRaisesRegex(UserError, "є 28"):
            base.action_fit()

    def test_ac15_dependent_drivers(self):
        twice = self.Driver.create({"code": "plate2", "name": "2×плит", "source_kind": "manual"})
        for i in range(40):
            day = FIRST + timedelta(days=i)
            self._daily(day, qty=1000.0 + i * i)
            self._driver_value("plate_m2", day, 800.0 + 20 * i)
            self._driver_value("plate2", day, 2 * (800.0 + 20 * i), quality="manual")
        base = self._baseline((FIRST, FIRST + timedelta(days=39)), {"plate_m2": 0.0, "plate2": 0.0})
        self.assertTrue(twice)
        with self.assertRaisesRegex(UserError, "Драйвери лінійно залежні або сталі"):
            base.action_fit()

    def test_ac15_four_drivers_rejected(self):
        extra = [self.Driver.create({"code": "x%d" % i, "name": "x", "source_kind": "manual"}) for i in range(3)]
        coefs = {"plate_m2": 0.0, "hdd": 0.0, **{d.code: 0.0 for d in extra}}
        with self.assertRaisesRegex(ValidationError, "Не більше 3 драйверів"):
            self._baseline((FIRST, FIRST + timedelta(days=39)), coefs)

    def test_fit_rights_and_state(self):
        period = self._series(30, lambda i: (800.0 + 20 * i, 2000.0 + 3 * i))
        base = self._baseline(period, {"plate_m2": 0.0})
        with self.assertRaises(AccessError):
            base.with_user(self.u_view).action_fit()
        base.action_fit()
        base.write({"state": "archived"})
        with self.assertRaisesRegex(UserError, "лише чернетку"):
            base.action_fit()

    def test_negative_coefficient_warning(self):
        period = self._series(30, lambda i: (800.0 + 20 * i, 5000.0 - 2.0 * (800.0 + 20 * i)))
        base = self._baseline(period, {"plate_m2": 0.0})
        base.action_fit()
        self.assertIn("Від'ємний коефіцієнт plate_m2", base.warning)
