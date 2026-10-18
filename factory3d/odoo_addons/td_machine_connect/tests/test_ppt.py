"""AC-09, AC-10: плановий час (R-26), stale/bad → nodata (R-03)."""

from datetime import date, datetime

from odoo.tests import tagged

from ..tools import ppt
from .common import F3DMachineCase


def utc(day, h, m=0):
    return datetime(day.year, day.month, day.day, h, m)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestPpt(F3DMachineCase):
    def test_ppt_monday(self):
        d = date(2026, 10, 12)
        res = ppt.ppt_intervals(self.env, self.wc_ua, utc(date(2026, 10, 11), 21), utc(d, 21))
        self.assertEqual(res, [(utc(d, 4), utc(d, 8, 30)), (utc(d, 9), utc(d, 12, 30))])
        self.assertEqual(ppt.total_min(res), 480)

    def test_ppt_dst(self):
        d = date(2026, 10, 26)
        res = ppt.ppt_intervals(self.env, self.wc_ua, utc(date(2026, 10, 25), 21), utc(d, 22))
        self.assertEqual(res, [(utc(d, 5), utc(d, 9, 30)), (utc(d, 10), utc(d, 13, 30))])
        self.assertEqual(ppt.total_min(res), 480)

    def test_ppt_saturday(self):
        d = date(2026, 10, 17)
        self.assertEqual(ppt.ppt_intervals(self.env, self.wc_ua, utc(date(2026, 10, 16), 21), utc(d, 21)), [])

    def test_leave_subtracted(self):
        d = date(2026, 10, 12)
        Leave = self.env["resource.calendar.leaves"]
        Leave.create(
            {
                "name": "Відсутність",
                "calendar_id": self.cal.id,
                "resource_id": self.wc_ua.resource_id.id,
                "date_from": utc(d, 7),
                "date_to": utc(d, 8),
                "time_type": "leave",
            }
        )
        Leave.create(
            {
                "name": "Слот завдання",
                "calendar_id": self.cal.id,
                "resource_id": self.wc_ua.resource_id.id,
                "date_from": utc(d, 10),
                "date_to": utc(d, 11),
                "time_type": "other",
            }
        )
        res = ppt.ppt_intervals(self.env, self.wc_ua, utc(date(2026, 10, 11), 21), utc(d, 21))
        self.assertEqual(res, [(utc(d, 4), utc(d, 7)), (utc(d, 8), utc(d, 8, 30)), (utc(d, 9), utc(d, 12, 30))])

    def test_pure_helpers(self):
        a = [(1, 5), (4, 8), (10, 12)]
        self.assertEqual(ppt.union(a), [(1, 8), (10, 12)])
        self.assertEqual(ppt.clip(a, 2, 11), [(2, 8), (10, 11)])
        self.assertEqual(ppt.minus([(0, 10)], [(2, 3), (5, 20)]), [(0, 2), (3, 5)])

    def test_stale_to_nodata(self):
        m = self.m_ua
        log = self.make_log(m, "working", "09:55")
        self.set_sql(m, state="working", state_since=self.kt("09:55"), current_log_id=log.id, raw_state="WORKING")
        self.sig_ua_state._mark_stale("timeout")
        self.env.invalidate_all()
        self.assertEqual(m.state, "nodata")
        self.assertEqual(log.date_end, self.kt("10:30"))

    def test_bad_quality_nodata(self):
        m = self.m_ua
        log = self.make_log(m, "working", "09:55")
        self.set_sql(m, state="working", state_since=self.kt("09:55"), current_log_id=log.id, raw_state="WORKING")
        self.feed(self.ua(m, "10:10:00", state="WORKING", q="bad"))
        self.assertEqual(m.state, "nodata")
        self.assertEqual(log.date_end, self.kt("10:10"))
