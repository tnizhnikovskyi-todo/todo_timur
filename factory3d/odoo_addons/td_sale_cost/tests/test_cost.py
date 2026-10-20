from odoo.tests import BaseCase, tagged

from odoo.addons.td_sale_cost.tools import cost


@tagged("post_install", "-at_install", "f3d", "f3d_sale_cost")
class TestCostTools(BaseCase):
    """R-01…R-06: чисті функції без ORM."""

    def test_total_none_is_no_data(self):
        self.assertIsNone(cost.total([None, None]))
        self.assertIsNone(cost.total([]))
        self.assertEqual(cost.total([None, 2.0, 3.0]), 5.0)
        self.assertEqual(cost.total([0.0]), 0.0)  # нуль — це дані
        self.assertEqual(cost.num(None), 0.0)

    def test_deviation_and_level(self):
        self.assertAlmostEqual(cost.deviation_pct(110.0, 100.0), 10.0)
        self.assertAlmostEqual(cost.deviation_pct(80.0, 100.0), -20.0)
        self.assertIsNone(cost.deviation_pct(5.0, 0.0))
        self.assertEqual(cost.level(103.0, 100.0), "ok")
        self.assertEqual(cost.level(110.0, 100.0), "warn")
        self.assertEqual(cost.level(120.0, 100.0), "alert")
        self.assertEqual(cost.level(50.0, 100.0), "ok")  # недовитрата — не тривога
        self.assertEqual(cost.level(0.0, 0.0), "none")
        self.assertEqual(cost.level(7.0, 0.0), "warn")  # факт без плану
        self.assertEqual(cost.level(110.0, 100.0, warn=20.0, alert=30.0), "ok")  # пороги з параметрів

    def test_margin(self):
        self.assertAlmostEqual(cost.margin_pct(1000.0, 700.0), 30.0)
        self.assertAlmostEqual(cost.margin_pct(1000.0, 1200.0), -20.0)
        self.assertIsNone(cost.margin_pct(0.0, 10.0))

    def test_progress_and_forecast(self):
        self.assertEqual(cost.fraction("done", 60, 0), 1.0)
        self.assertEqual(cost.fraction("progress", 60, 30), 0.5)
        self.assertEqual(cost.fraction("progress", 60, 90), 1.0)  # не більше 1
        self.assertEqual(cost.fraction("ready", 60, 0), 0.0)
        self.assertAlmostEqual(cost.progress([(60, 1.0), (180, 0.0)]), 0.25)
        self.assertIsNone(cost.progress([]))
        self.assertEqual(cost.forecast(80.0, 100.0, 40.0), 140.0)  # факт + решта плану
        self.assertEqual(cost.forecast(150.0, 100.0, 100.0), 150.0)
