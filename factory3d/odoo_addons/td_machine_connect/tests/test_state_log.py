"""AC-04…AC-08: журнал станів, мікрозупинки, відкладені переходи, сигнал machine_state."""

from odoo.tests import tagged

from .common import F3DMachineCase


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestStateLog(F3DMachineCase):
    def _set_state(self, m, state, since, raw_state="READY"):
        log = self.make_log(m, state, since)
        self.set_sql(
            m, state=state, state_since=self.kt(since), current_log_id=log.id, raw_state=raw_state, raw_mode="AUTOMATIC"
        )
        return log

    def _logs(self, m):
        return self.env["f3d.machine.state.log"].search([("machine_id", "=", m.id)], order="date_start, id")

    def test_transition_closes_and_opens(self):
        m = self.m_ua
        old = self._set_state(m, "idle", "09:50")
        self.feed(self.ua(m, "09:55:00", state="WORKING", mode="AUTOMATIC"))
        self.assertEqual(old.date_end, self.kt("09:55"))
        self.assertEqual(old.duration_min, 5.0)
        self.assertEqual(old.in_ppt_min, 5.0)
        self.assertEqual(m.state, "working")
        self.assertEqual(m.state_since, self.kt("09:55"))
        new = m.current_log_id
        self.assertEqual((new.state, new.date_start, new.source), ("working", self.kt("09:55"), "machine"))
        self.assertEqual(new.raw, "WORKING/AUTOMATIC")
        self.assertEqual(
            self.env["f3d.machine.state.log"].search_count([("machine_id", "=", m.id), ("date_end", "=", False)]), 1
        )
        logs = self._logs(m)
        for prev, nxt in zip(logs, logs[1:], strict=False):
            self.assertLessEqual(prev.date_end, nxt.date_start)

    def test_micro_stop_absorbed(self):
        m = self.m_ua
        self._set_state(m, "working", "09:55", raw_state="WORKING")
        count = len(self._logs(m))
        self.feed(self.ua(m, "10:02:00", state="READY"))
        self.assertEqual(m.pending_state, "idle")
        self.feed(self.ua(m, "10:03:10", state="WORKING"))
        self.assertEqual(m.state, "working")
        self.assertFalse(m.pending_state)
        self.assertEqual(len(self._logs(m)), count)

    def test_pending_committed_by_cron(self):
        m = self.m_ua
        old = self._set_state(m, "working", "09:55", raw_state="WORKING")
        self.feed(self.ua(m, "10:05:00", state="READY"))
        self.tick("10:06:50")
        self.assertEqual(m.state, "working")
        self.tick("10:07:31")
        self.env.invalidate_all()
        self.assertEqual(m.state, "idle")
        self.assertEqual(m.state_since, self.kt("10:05"))
        self.assertEqual(old.date_end, self.kt("10:05"))
        self.assertFalse(m.pending_state)

    def test_late_reading_ignored(self):
        m = self.m_ua
        self._set_state(m, "working", "10:00", raw_state="WORKING")
        self.set_sql(m, pieces_last=10, pieces_ts=self.kt("09:30"))
        self.feed(self.ua(m, "09:59:00", state="READY", pieces=13))
        self.assertEqual(m.state, "working")
        self.assertEqual(m.raw_state, "WORKING")
        self.assertEqual(m.pieces_last, 13)
        self.assertEqual(m.current_log_id.pieces, 3)

    def test_machine_state_signal(self):
        m = self.m_ua
        self._set_state(m, "idle", "09:50")
        self.feed(self.ua(m, "09:55:00", state="WORKING", mode="AUTOMATIC"))
        self.assertEqual(self.sig_ua_mstate.last_text, "working")
        reading = self.env["f3d.reading"].search([("signal_id", "=", self.sig_ua_mstate.id)])
        self.assertEqual(reading.mapped("src"), ["module"])

    def test_collector_cannot_feed_derived(self):
        res = self.feed([self.rk(self.sig_ua_mstate, "working", None, "10:00:00")])
        self.assertEqual([r["reason"] for r in res["rejected"]], ["foreign_signal"])

    def test_stale_and_bad_do_not_break_log(self):
        m = self.m_ua
        self._set_state(m, "working", "09:55", raw_state="WORKING")
        self.sig_ua_state._mark_stale("timeout")
        self.env.invalidate_all()
        self.assertEqual(m.state, "nodata")
        self.assertEqual(m.current_log_id.state, "nodata")
        self.assertEqual(
            self.env["f3d.machine.state.log"].search_count([("machine_id", "=", m.id), ("date_end", "=", False)]), 1
        )
