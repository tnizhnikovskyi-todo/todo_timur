"""AC-17…AC-20: злиття записів оператора з простоєм верстата (R-06)."""

from odoo.tests import tagged

from .common import F3DMachineCase, kt
from .test_downtime import DowntimeMixin


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestMerge(DowntimeMixin, F3DMachineCase):
    def _operator_block(self, user, xmlid, t=None):
        vals = {"workcenter_id": self.wc_ua.id, "loss_id": self.env.ref(xmlid).id}
        if t:
            vals["date_start"] = kt(t)
        return self.env["mrp.workcenter.productivity"].with_user(user).create(vals)

    def test_operator_block_during_fault(self):
        """AC-17: запис оператора під час аварії прив'язується, машинний запис закривається на його початку."""
        m = self.m_ua
        self.feed(self.ua(m, "09:42:00", state="ERROR"))
        dt = m.current_downtime_id
        machine_rec = self.records(dt)
        self.assertEqual(len(machine_rec), 1)
        rec = self._operator_block(self.user_mrp, "mrp.block_reason1", "09:50")
        self.assertEqual((rec.f3d_downtime_id, rec.f3d_source), (dt, "operator"))
        self.assertEqual(machine_rec.date_end, rec.date_start)
        self.assertTrue(machine_rec.exists() and rec.exists())
        self.assertEqual((dt.reason_source, dt.reason_state), ("operator", "to_confirm"))
        # перекриттів немає
        recs = self.records(dt)
        for prev, nxt in zip(recs, recs[1:], strict=False):
            self.assertLessEqual(prev.date_end or kt("23:00"), nxt.date_start)
        master_rec = self._operator_block(self.user_mrp_manager, "mrp.block_reason0", "09:55")
        self.assertEqual(master_rec.f3d_source, "master")
        self.assertEqual(dt.reason_state, "confirmed")

    def test_operator_block_before_stop(self):
        """AC-18: оператор заблокував РЦ під час роботи; READY → простій отримав причину оператора."""
        m = self.m_ua
        self.set_working(m)
        rec = self._operator_block(self.user_mrp, "mrp.block_reason0", "10:00")
        self.assertFalse(rec.f3d_downtime_id)
        self.feed(self.ua(m, "10:05:00", state="READY"))
        self.tick("10:07:31")
        dt = m.current_downtime_id
        self.assertEqual(m.state, "idle")
        self.assertEqual(rec.f3d_downtime_id, dt)
        self.assertEqual(
            (dt.loss_id, dt.reason_source, dt.reason_state),
            (self.env.ref("mrp.block_reason0"), "operator", "to_confirm"),
        )

    def test_working_closes_operator_record(self):
        """AC-19: WORKING закриває прив'язаний запис оператора, РЦ розблоковано."""
        m = self.m_ua
        self.feed(self.ua(m, "10:00:00", state="READY"))
        dt = m.current_downtime_id
        rec = self._operator_block(self.user_mrp, "mrp.block_reason0", "10:05")
        self.assertEqual(rec.f3d_downtime_id, dt)
        self.assertEqual(self.wc_ua.working_state, "blocked")
        self.feed(self.ua(m, "10:20:00", state="WORKING"))
        self.assertEqual(rec.date_end, kt("10:20"))
        self.assertNotEqual(self.wc_ua.working_state, "blocked")
        self.assertTrue(rec.exists())
        machine_rec = self.records(dt).filtered("f3d_auto")
        self.assertEqual((machine_rec.date_start, machine_rec.date_end), (kt("10:00"), kt("10:05")))

    def test_unblock_reopens_fault_record(self):
        """AC-20: «Розблокувати» під час аварії → на такті відкривається запис «Аварія триває»."""
        m = self.m_ua
        self.feed(self.ua(m, "09:42:00", state="ERROR"))
        self.assertEqual(self.wc_ua.working_state, "blocked")
        self.wc_ua.unblock()
        self.env.invalidate_all()
        self.assertNotEqual(self.wc_ua.working_state, "blocked")
        self.tick("10:30:30")
        dt = m.current_downtime_id
        opened = self.records(dt).filtered(lambda r: not r.date_end)
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened.description, "Аварія триває")
        self.assertTrue(opened.f3d_auto)
        self.assertEqual(self.wc_ua.working_state, "blocked")

    def test_working_operator_record_closed_by_cron(self):
        """R-06 п. 3: верстат працює ≥ micro_stop_s після запису оператора → запис закрито кроном."""
        m = self.m_ua
        self.set_working(m)
        rec = self._operator_block(self.user_mrp, "mrp.block_reason0", "10:00")
        self.tick("10:01:00")
        self.assertFalse(rec.date_end)
        self.tick("10:02:30")
        self.assertEqual(rec.date_end, kt("10:02:30"))
        self.assertIn("верстат працює", rec.description)
