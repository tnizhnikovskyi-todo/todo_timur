"""Y-2: фільтр «Сьогодні» — київська доба сервера, а не `context_today()` браузера (UTC на тестовому стенді)."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo.tests import tagged

from .flow import YardFlowCase, freeze

KYIV = ZoneInfo("Europe/Kyiv")
# (UTC naive, київська доба): літо UTC+3, зима UTC+2; «вікно Y-2» — коли доба в Києві вже інша, ніж за UTC
CLOCKS = [
    (datetime(2026, 10, 14, 5, 0), date(2026, 10, 14)),
    (datetime(2026, 10, 14, 20, 59), date(2026, 10, 14)),
    (datetime(2026, 10, 14, 21, 0), date(2026, 10, 15)),
    (datetime(2026, 10, 14, 22, 30), date(2026, 10, 15)),
    (datetime(2026, 10, 14, 23, 59), date(2026, 10, 15)),
    (datetime(2026, 10, 15, 0, 0), date(2026, 10, 15)),
    (datetime(2026, 1, 14, 21, 59), date(2026, 1, 14)),
    (datetime(2026, 1, 14, 22, 0), date(2026, 1, 15)),
]


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardTodayFilter(YardFlowCase):
    def test_today_is_kyiv_day_at_any_hour(self):
        Visit = self.env["f3d.yard.visit"]
        for now, expected_day in CLOCKS:
            self.assertEqual(now.replace(tzinfo=timezone.utc).astimezone(KYIV).date(), expected_day)
            with freeze(now):
                visits = {
                    shift: self._visit(plate="АА%04dКТ" % (100 + i), arrived_at=now + timedelta(days=shift))
                    for i, shift in enumerate((-1, 0, 1))
                }
                domain = [("id", "in", [v.id for v in visits.values()])]
                self.assertEqual(visits[0].day, expected_day, now)
                self.assertEqual(Visit.search(domain + [("is_today", "=", True)]), visits[0], now)
                self.assertEqual(Visit.search(domain + [("is_today", "!=", True)]), visits[-1] | visits[1], now)
                self.assertEqual(Visit.search(domain + [("is_today", "=", False)]), visits[-1] | visits[1], now)
                self.assertEqual([v.is_today for v in visits.values()], [False, True, False], now)

    def test_booking_today_is_kyiv_day(self):
        Booking = self.env["f3d.yard.booking"]
        now = datetime(2026, 10, 14, 22, 30)  # 01:30 15.10 за Києвом, за UTC ще 14.10
        with freeze(now):
            today = self._booking(None, self.dock_t1, now + timedelta(hours=2), now + timedelta(hours=3))
            yesterday = self._booking(None, self.dock_t1, now - timedelta(hours=8), now - timedelta(hours=7))
            self.assertEqual((today.day, yesterday.day), (date(2026, 10, 15), date(2026, 10, 14)))
            domain = [("id", "in", (today | yesterday).ids)]
            self.assertEqual(Booking.search(domain + [("is_today", "=", True)]), today)
            self.assertEqual(Booking.search(domain + [("is_today", "!=", True)]), yesterday)

    def test_search_views_do_not_use_browser_date(self):
        for name in ("view_f3d_yard_visit_search", "view_f3d_yard_booking_search"):
            arch = self.env.ref("factory3d_yard." + name).arch_db
            self.assertNotIn("context_today", arch, name)
            self.assertIn("is_today", arch, name)
