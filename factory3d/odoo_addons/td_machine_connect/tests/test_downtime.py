"""AC-10 (простій), AC-11…AC-16: простої, записи журналу часу, причини й підтвердження (R-05)."""

from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import D0, F3DMachineCase, at, kt


class DowntimeMixin:
    """Допоміжні методи для тестів простоїв (R-05…R-08)."""

    def downtimes(self, m=None):
        m = m or self.m_ua
        return self.env["td.downtime"].search([("machine_id", "=", m.id)], order="date_start, id")

    def records(self, dt):
        return self.env["mrp.workcenter.productivity"].search([("td_downtime_id", "=", dt.id)], order="date_start, id")

    def set_working(self, m, since="09:29"):
        log = self.make_log(m, "working", since)
        self.set_sql(
            m,
            state="working",
            state_since=kt(since),
            current_log_id=log.id,
            raw_state="WORKING",
            raw_mode="AUTOMATIC",
        )

    def start_wo(self, m, wc, t="09:29"):
        """Завдання стартує оператором (DEC-1: `button_start` + `td_employee_id`; `start_employee` у CE немає)."""
        mo = self.make_mo(wc)
        wo = mo.workorder_ids[:1]
        with at(t):
            wo.with_user(self.user_mrp).button_start()
        wo.td_employee_id = self.emp_ua
        self.set_sql(m, active_workorder_id=wo.id)
        return wo

    def loss(self, xmlid):
        return self.env.ref(xmlid)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestDowntime(DowntimeMixin, F3DMachineCase):
    def test_fault_blocks_wc(self):
        """AC-11: ERROR → простій fault, запис журналу часу «Поломка» блокує РЦ, таймер завдання закрито о ts."""
        m = self.m_ua
        self.set_working(m)
        wo = self.start_wo(m, self.wc_ua)
        timer = wo.time_ids[:1]
        self.assertFalse(timer.date_end)
        with at("09:42:03"):
            self.feed(self.ua(m, "09:42:00", state="ERROR"))
        self.assertEqual(m.state, "fault")
        dt = m.current_downtime_id
        self.assertEqual((dt.state_kind, dt.date_start, dt.reason_state), ("fault", kt("09:42"), "to_confirm"))
        rec = self.records(dt)
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec.loss_id, self.loss("mrp.block_reason1"))
        self.assertTrue(rec.td_auto)
        self.assertEqual((rec.td_source, rec.date_start), ("machine", kt("09:42")))
        self.assertEqual(rec.create_uid, self.env.ref("td_machine_connect.user_td_machine"))
        self.assertEqual(self.wc_ua.working_state, "blocked")
        self.assertEqual(timer.date_end, kt("09:42"))  # R-10 п. 1 (W3)

    def test_idle_no_timelog_until_close(self):
        """AC-12: поки простій `idle` триває — записів журналу часу немає; після — один закритий запис."""
        m = self.m_ua
        self.set_working(m)
        self.feed(self.ua(m, "10:05:00", state="READY"))
        self.tick("10:07:31")
        self.assertEqual(m.state, "idle")
        dt = m.current_downtime_id
        self.assertEqual(dt.date_start, kt("10:05"))
        self.assertFalse(self.records(dt))
        self.assertNotEqual(self.wc_ua.working_state, "blocked")
        self.feed(self.ua(m, "10:21:00", state="WORKING"))
        self.assertEqual(m.state, "working")
        self.assertFalse(m.current_downtime_id)
        self.assertEqual((dt.date_end, dt.ppt_min), (kt("10:21"), 16.0))
        rec = self.records(dt)
        self.assertEqual(len(rec), 1)
        self.assertEqual(
            (rec.loss_id, rec.date_start, rec.date_end, rec.td_auto),
            (self.env.ref("td_machine_connect.loss_unknown"), kt("10:05"), kt("10:21"), True),
        )

    def test_idle_lunch_and_after_shift(self):
        """AC-13: плановий час простою — лише в календарі; короткий поза зміною видаляється."""
        m = self.m_ua
        # SPEC AC-13 суперечить R-05 п. 4 (1,5 хв < micro_stop_s=120 → видалення): поріг знижено.
        m.micro_stop_s = 60
        with at("11:29:30"):
            self.feed(self.ua(m, "11:29:00", state="READY"))
        dt = m.current_downtime_id
        with at("12:01"):
            self.feed(self.ua(m, "12:00:30", state="WORKING"))
        self.assertEqual((dt.date_end, dt.ppt_min), (kt("12:00:30"), 1.5))
        self.assertTrue(dt.exists())
        self.assertEqual(len(self.records(dt)), 1)
        # 15:31–15:45: поза зміною → видалено, записів немає
        with at("15:32"):
            self.feed(self.ua(m, "15:31:00", state="READY"))
        self.tick("15:33:00")
        dt2 = m.current_downtime_id
        self.assertTrue(dt2)
        with at("15:46"):
            self.feed(self.ua(m, "15:45:00", state="WORKING"))
        self.assertFalse(dt2.exists())
        self.assertEqual(
            self.env["mrp.workcenter.productivity"].search_count(
                [("workcenter_id", "=", self.wc_ua.id), ("date_start", ">=", kt("15:00"))]
            ),
            0,
        )

    def test_day_boundary(self):
        """AC-14: крон о кінці планового часу закриває простій і відкриває новий з початку наступного дня."""
        m = self.m_ua
        with at("15:01"):
            self.feed(self.ua(m, "15:00:00", state="READY"))
        dt = m.current_downtime_id
        self.assertEqual(dt.date_start, kt("15:00"))
        self.tick("15:30:30")
        self.assertEqual((dt.date_end, dt.ppt_min), (kt("15:30"), 30.0))
        self.assertFalse(m.current_downtime_id)
        self.assertEqual(len(self.downtimes(m)), 1)
        self.assertEqual(m.state, "idle")
        d1 = D0 + timedelta(days=1)
        with at("07:00:30", day=d1):
            self.env["td.machine"]._cron_tick()
        new = m.current_downtime_id
        self.assertTrue(new)
        self.assertEqual((new.state_kind, new.date_start), ("idle", kt("07:00", d1)))
        self.assertEqual(len(self.downtimes(m)), 2)

    def test_nodata_closes_downtime(self):
        """AC-10 (частина про простій): stale й `q=bad` закривають відкритий простій о `now`/`ts`."""
        m = self.m_ua
        self.feed(self.ua(m, "10:00:00", state="READY"))
        dt = m.current_downtime_id
        self.assertTrue(dt)
        self.sig_ua_state._mark_stale("timeout")
        self.env.invalidate_all()
        self.assertEqual(m.state, "nodata")
        self.assertFalse(m.current_downtime_id)
        self.assertEqual((dt.date_end, dt.ppt_min), (kt("10:30"), 30.0))
        # q=bad
        with at("10:36"):
            self.feed(self.ua(m, "10:35:00", state="READY"))
        dt2 = m.current_downtime_id
        self.assertTrue(dt2)
        with at("10:51"):
            self.feed(self.ua(m, "10:50:00", state="READY", q="bad"))
        self.assertEqual(m.state, "nodata")
        self.assertEqual(dt2.date_end, kt("10:50"))

    def _fault(self, m):
        self.feed(self.ua(m, "09:42:00", state="ERROR"))
        return m.current_downtime_id

    def test_set_reason_rights(self):
        """AC-15: оператор вказує причину → to_confirm, машинні записи отримують її; без mrp — AccessError."""
        m = self.m_ua
        dt = self._fault(m)
        reason = self.loss("mrp.block_reason0")
        dt.with_user(self.user_mrp).action_set_reason(reason.id)
        self.assertEqual((dt.loss_id, dt.reason_source, dt.reason_state), (reason, "operator", "to_confirm"))
        self.assertEqual(self.records(dt).mapped("loss_id"), reason)
        with self.assertRaises(AccessError):
            dt.with_user(self.user_f3d).action_set_reason(reason.id)
        with self.assertRaises(UserError):
            dt.with_user(self.user_mrp).action_set_reason(self.loss("mrp.block_reason4").id)

    def test_confirm_rights(self):
        """AC-16: підтвердження лише з причиною; підтверджену змінює лише майстер."""
        m = self.m_ua
        dt = self._fault(m)
        # «Поломка» вже підказана автоматично; повернути «Не вказано» для перевірки
        dt._td_apply_reason(self.env.ref("td_machine_connect.loss_unknown"), "auto")
        with self.assertRaises(UserError):
            dt.with_user(self.user_mrp_manager).action_confirm()
        with self.assertRaises(AccessError):
            dt.with_user(self.user_mrp).action_confirm()
        dt.with_user(self.user_mrp).action_set_reason(self.loss("mrp.block_reason1").id)
        dt.with_user(self.user_mrp_manager).action_confirm()
        self.assertEqual(dt.reason_state, "confirmed")
        self.assertEqual(dt.confirmed_by, self.user_mrp_manager)
        with self.assertRaises(UserError):
            dt.with_user(self.user_mrp).action_set_reason(self.loss("mrp.block_reason0").id)
        dt.with_user(self.user_mrp_manager).action_set_reason(self.loss("mrp.block_reason0").id)
        self.assertEqual((dt.reason_source, dt.reason_state), ("master", "confirmed"))
