"""W4-A: демо-сид «Аналітики» (AC-54, AC-55). Електричний backfill робиться один раз на клас."""

import hashlib
from datetime import timedelta

from odoo.exceptions import AccessError, UserError

from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

DAYS = 90


@tagged(*TAGS)
class TestW4Seed(TestW4Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls._mk_user("w4_seed_admin", ["td_factory3d.group_td_admin"])
        cls.Interval = cls.env["td.energy.interval"]
        cls.Interval._td_backfill(days=DAYS, with_balance=False, with_events=False)

    def _seed(self, days=DAYS, **kw):
        return self.Api.with_user(self.admin)._td_seed_demo(days=days, **kw)

    def _digest(self):
        rows = self._rows(
            "td_energy_driver_value", "source_note = %s ORDER BY driver_id, day", ("демо-сид",), "driver_id, day, value"
        )
        return hashlib.sha256(repr(rows).encode()).hexdigest(), len(rows)

    def test_ac54_seed_90_days(self):
        stats = self._seed()
        self.assertEqual(
            set(stats), {"days", "products", "mos", "workorders", "alloc_rows", "baselines", "budgets", "seconds"}
        )
        self.assertEqual(
            (stats["days"], stats["products"], stats["baselines"]), (DAYS, 5, 1 + int(stats["baselines"] > 1))
        )
        yesterday = TODAY - timedelta(days=1)
        first = yesterday - timedelta(days=DAYS - 1)
        # драйвери: plate_m2 за всі доби, у робочі дні > 0
        values = {v.day: v.value for v in self.DriverValue.search([("driver_id", "=", self.plate.id)])}
        self.assertTrue(all(first + timedelta(days=i) in values for i in range(DAYS)))
        weekdays = [d for d in values if d.weekday() < 5 and first <= d <= yesterday]
        self.assertTrue(all(values[d] > 0 for d in weekdays))
        # МО: ≥ 3 у робочі доби, наряди, розподіл
        orders = self.env["mrp.production"].search([("origin", "=", "td_energy_seed")])
        self.assertEqual(len(orders), stats["mos"])
        per_day = {}
        for mo in orders:
            per_day[mo.date_finished.date()] = per_day.get(mo.date_finished.date(), 0) + 1
        self.assertTrue(per_day)
        self.assertGreaterEqual(min(per_day.values()), 3)
        self.assertGreater(stats["alloc_rows"], 0)
        self.assertTrue(self.env["td.energy.alloc"].search_count([("production_id", "in", orders.ids)]))
        # база й EnPI
        base = self.Baseline.search([("state", "=", "approved"), ("resource_id", "=", self.res_el.id)])
        self.assertEqual(len(base), 1)
        self.assertGreaterEqual(base.r2, 0.9)
        enpi = self.Api.with_user(self.admin).get_enpi()
        self.assertTrue(0.92 <= enpi["enpi"] <= 0.96, enpi["enpi"])
        # бюджети: поточний і 3 попередні
        budgets = self.Budget.search([("note", "=", "демо-сид")])
        self.assertEqual((len(budgets), set(budgets.mapped("state"))), (4, {"approved"}))
        # цілісність: розрив стовпців, розподіл ≤ споживання заводу
        self.assertLessEqual(abs(self.Api._td_stack_gap_pct("y")), 3.0)
        self.env.flush_all()
        self.env.cr.execute(
            """SELECT a.day, SUM(a.kwh), MAX(d.qty) FROM td_energy_alloc a
                 JOIN td_energy_daily d ON d.day = a.day AND d.scope = 'plant'
                WHERE a.production_id = ANY(%s) GROUP BY a.day""",
            (orders.ids,),
        )
        for _day, alloc, plant in self.env.cr.fetchall():
            self.assertLessEqual(alloc, plant)
        # екран працює на сидованих даних
        data = self.Api.with_user(self.admin).get_dashboard("m", "area", None)
        self.assertEqual(len(data["kpis"]), 7)
        self.assertEqual(len(data["stack"]["bars"]), 30)
        self.assertTrue(data["cut"]["rows"])

    def test_ac55_idempotent_deterministic_purge(self):
        manual = self.Driver.create({"code": "units", "name": "Одиниці", "source_kind": "manual"})
        kept = self.DriverValue.create({"driver_id": manual.id, "day": TODAY - timedelta(days=2), "value": 7.0})
        self._seed(days=30)
        mos = self.env["mrp.production"].search_count([("origin", "=", "td_energy_seed")])
        digest = self._digest()
        self.assertGreater(mos, 0)
        self._seed(days=30)
        self.assertEqual(self.env["mrp.production"].search_count([("origin", "=", "td_energy_seed")]), mos)
        self.assertEqual(self._digest(), digest, "той самий seed — той самий набір значень драйверів")
        self.assertEqual(self.Baseline.search_count([("note", "=", "демо-сид")]), 1)
        stats = self._seed(purge=True)
        self.assertEqual(stats["mos"], mos)
        self.assertFalse(self.env["mrp.production"].search_count([("origin", "=", "td_energy_seed")]))
        self.assertEqual(self._digest()[1], 0)
        self.assertFalse(self.Baseline.search_count([("note", "=", "демо-сид")]))
        self.assertFalse(self.Budget.search_count([("note", "=", "демо-сид")]))
        self.assertTrue(kept.exists(), "ручні значення драйверів не чіпаємо")

    def test_ac55_rights_and_prerequisites(self):
        with self.assertRaisesRegex(AccessError, "лише адміністратор"):
            self.Api.with_user(self.u_eng)._td_seed_demo(days=30)
        self.env.cr.execute("DELETE FROM td_energy_interval")
        self.Interval.invalidate_model()
        with self.assertRaisesRegex(UserError, "_td_backfill"):
            self._seed(days=30)
