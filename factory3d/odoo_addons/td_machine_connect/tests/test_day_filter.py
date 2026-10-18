"""Y-2: фільтри «Сьогодні»/«Цей тиждень»/«Цей місяць» зміни OEE — київська доба сервера, а не `context_today()` браузера."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from odoo.tests import tagged

from .common import F3DMachineCase

KYIV = ZoneInfo("Europe/Kyiv")
# (UTC naive): літо UTC+3, зима UTC+2; «вікно Y-2» — коли доба в Києві вже інша, ніж за UTC
CLOCKS = [
    datetime(2026, 10, 14, 20, 59),
    datetime(2026, 10, 14, 21, 0),  # 00:00 15.10 за Києвом
    datetime(2026, 10, 14, 23, 59),
    datetime(2026, 10, 31, 21, 30),  # 00:30 01.11 (перехід на зиму 25.10): інший місяць за Києвом
    datetime(2026, 1, 14, 22, 0),
]


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestOeeDayFilter(F3DMachineCase):
    def test_filters_follow_kyiv_day_at_any_hour(self):
        Shift = self.env["td.oee.shift"].sudo()
        for now in CLOCKS:
            today = now.replace(tzinfo=timezone.utc).astimezone(KYIV).date()
            week, month = today - timedelta(days=today.weekday()), today.replace(day=1)
            days = {
                today + timedelta(days=1),
                today,
                today - timedelta(days=1),
                week,
                week - timedelta(days=1),
                month,
                month - timedelta(days=1),
            }
            with freeze_time(now):
                rows = {d: Shift.create({"machine_id": self.m_saw.id, "date": d, "source": "machine"}) for d in days}
                all_rows = Shift.browse([r.id for r in rows.values()])
                base = [("id", "in", all_rows.ids)]
                pick = lambda pred: all_rows.filtered(lambda r: pred(r.date))  # noqa: E731
                self.assertEqual(Shift.search(base + [("is_today", "=", True)]), rows[today], now)
                self.assertEqual(Shift.search(base + [("is_today", "!=", True)]), all_rows - rows[today], now)
                self.assertEqual(Shift.search(base + [("is_this_week", "=", True)]), pick(lambda d: d >= week), now)
                self.assertEqual(Shift.search(base + [("is_this_week", "=", False)]), pick(lambda d: d < week), now)
                self.assertEqual(Shift.search(base + [("is_this_month", "=", True)]), pick(lambda d: d >= month), now)
                self.assertEqual(
                    sorted(all_rows.filtered("is_today").mapped("date")), [today], now
                )
                all_rows.unlink()

    def test_search_view_does_not_use_browser_date(self):
        arch = self.env.ref("td_machine_connect.view_td_oee_shift_search").arch_db
        self.assertNotIn("context_today", arch)
        self.assertIn("is_today", arch)
