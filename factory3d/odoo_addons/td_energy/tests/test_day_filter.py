"""Y-2: фільтри «Сьогодні»/«Вчора»/«7 днів» — київська доба сервера, а не `context_today()` браузера."""

from datetime import date, datetime, time

from odoo.tests import tagged

from .common import TAGS, F3DEnergyCase

# (UTC naive, київська доба): літо UTC+3, зима UTC+2; «вікно Y-2» — коли доба в Києві вже інша, ніж за UTC
CLOCKS = [
    (datetime(2026, 10, 14, 5, 0), date(2026, 10, 14)),
    (datetime(2026, 10, 14, 20, 59), date(2026, 10, 14)),
    (datetime(2026, 10, 14, 21, 0), date(2026, 10, 15)),
    (datetime(2026, 10, 14, 23, 59), date(2026, 10, 15)),
    (datetime(2026, 1, 14, 21, 59), date(2026, 1, 14)),
    (datetime(2026, 1, 14, 22, 0), date(2026, 1, 15)),
]
VIEWS = ("view_f3d_energy_alloc_search", "view_f3d_energy_interval_search", "view_f3d_energy_balance_search")


@tagged(*TAGS)
class TestEnergyDayFilter(F3DEnergyCase):
    def _rows(self, today):
        """Рядки балансу за днями today−8 … today+1 (унікальність — година)."""
        node = self.env["f3d.energy.node"].search([], limit=1)
        self.assertTrue(node)
        rows = {}
        for back in range(-1, 9):
            day = date.fromordinal(today.toordinal() - back)
            rows[back] = self.env["f3d.energy.balance"].create(
                {
                    "node_id": node.id,
                    "hour": datetime.combine(date(2000, 1, 1 + (back + 1)), time(12, 0)),
                    "day": day,
                    "state": "ok",
                }
            )
        return rows

    def test_filters_follow_kyiv_day_at_any_hour(self):
        Balance = self.env["f3d.energy.balance"]
        for now, today in CLOCKS:
            rows = self._rows(today)  # rows[back] — доба today − back
            all_rows = Balance.browse([r.id for r in rows.values()])
            last_7d = Balance.browse([rows[back].id for back in range(0, 8)])
            at = Balance.with_context(f3d_now=now)
            base = [("id", "in", all_rows.ids)]
            self.assertEqual(at.search(base + [("is_today", "=", True)]), rows[0], now)
            self.assertEqual(at.search(base + [("is_today", "!=", True)]), all_rows - rows[0], now)
            self.assertEqual(at.search(base + [("is_yesterday", "=", True)]), rows[1], now)
            self.assertEqual(at.search(base + [("is_last_7d", "=", True)]), last_7d, now)
            self.assertEqual(at.search(base + [("is_last_7d", "=", False)]), rows[-1] | rows[8], now)
            self.assertEqual(
                [at.browse(rows[b].id).is_today for b in (1, 0, -1)], [False, True, False], now
            )
            all_rows.unlink()

    def test_search_views_do_not_use_browser_date(self):
        for name in VIEWS:
            arch = self.env.ref("factory3d_energy." + name).arch_db
            self.assertNotIn("context_today", arch, name)
            self.assertIn("is_today", arch, name)
