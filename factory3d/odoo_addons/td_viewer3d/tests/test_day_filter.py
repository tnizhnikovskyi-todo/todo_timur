"""Y-2: фільтри «Сьогодні»/«Цей тиждень» журналу знімків — київська доба сервера, а не `context_today()` браузера."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from odoo.tests import tagged

from .common import F3dViewerBase

KYIV = ZoneInfo("Europe/Kyiv")
# (UTC naive): літо UTC+3, зима UTC+2; «вікно Y-2» — коли доба в Києві вже інша, ніж за UTC
CLOCKS = [
    datetime(2026, 10, 14, 20, 59),
    datetime(2026, 10, 14, 21, 0),  # 00:00 15.10 за Києвом
    datetime(2026, 10, 14, 23, 59),
    datetime(2026, 10, 18, 21, 30),  # 00:30 пн 19.10 за Києвом (UTC+3), а за UTC ще неділя: інший тиждень
    datetime(2026, 1, 14, 22, 0),
]


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestSnapshotDayFilter(F3dViewerBase):
    def test_filters_follow_kyiv_day_at_any_hour(self):
        Snap = self.env["td.viewer.snapshot"].sudo()
        self.set_param("demo_clock", "")
        for now in CLOCKS:
            today = now.replace(tzinfo=timezone.utc).astimezone(KYIV).date()
            week = today - timedelta(days=today.weekday())
            with freeze_time(now):
                snaps = {}
                for shift in (-8, -1, 0, 1):
                    ts = now + timedelta(days=shift)
                    snaps[shift] = Snap.create(
                        {"ts": ts, "kind": "manual", "payload_file": Snap._pack({"meta": {"schema": "1.1"}})}
                    )
                all_snaps = Snap.browse([s.id for s in snaps.values()])
                base = [("id", "in", all_snaps.ids)]
                self.assertEqual(snaps[0].shift_date, today, now)
                self.assertEqual(Snap.search(base + [("is_today", "=", True)]), snaps[0], now)
                self.assertEqual(Snap.search(base + [("is_today", "!=", True)]), all_snaps - snaps[0], now)
                self.assertEqual(Snap.search(base + [("is_today", "=", False)]), all_snaps - snaps[0], now)
                in_week = all_snaps.filtered(lambda s, week=week: s.shift_date >= week)
                self.assertEqual(Snap.search(base + [("is_this_week", "=", True)]), in_week, now)
                self.assertEqual(Snap.search(base + [("is_this_week", "=", False)]), all_snaps - in_week, now)
                self.assertEqual(all_snaps.filtered("is_today"), snaps[0], now)

    def test_today_follows_demo_clock(self):
        """R-21: під `demo_clock` «сьогодні» — доба годинника, як у shift_date знімка `_take`."""
        Snap = self.env["td.viewer.snapshot"].sudo()
        Snap.search([]).unlink()
        self.set_param("demo_clock", "2020-01-12 10:30")
        snap = Snap._take("manual")
        self.assertEqual(Snap.search([("is_today", "=", True)]), snap)

    def test_search_view_does_not_use_browser_date(self):
        arch = self.env.ref("td_viewer3d.view_td_viewer_snapshot_search").arch_db
        self.assertNotIn("context_today", arch)
        self.assertIn("is_today", arch)
        self.assertIn("is_this_week", arch)
