"""AC-33…AC-38: лічильник деталей, автозавершення, неповна партія, пауза й відновлення (R-10…R-12)."""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import F3DMachineCase, at, kt


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestCounterFinish(F3DMachineCase):
    def setUp(self):
        super().setUp()
        self.enable_autostart()
        self.m = self.m_ua
        self.wo = self.make_mo(self.wc_ua, qty=14).workorder_ids[:1]
        self.job = "WO%05d" % self.wo.id
        with at("09:55:05"):
            self.feed(self.ua(self.m, "09:55:00", state="WORKING", mode="AUTOMATIC", job=self.job, pieces=0))
        self.assertEqual(self.wo.state, "progress")

    def pieces(self, t, value, **kw):
        with at(t + ":05"):
            return self.feed(self.ua(self.m, t + ":00", pieces=value, **kw))

    def test_counter_reset_and_jump(self):
        """AC-33: 0→1→5, скидання 5→0→2, стрибок 2→1500 ігнорується з WARNING."""
        for t, value in (("10:00", 1), ("10:05", 5), ("10:10", 0), ("10:15", 2)):
            self.pieces(t, value)
        with self.assertLogs("odoo.addons.td_machine_connect", "WARNING"):
            self.pieces("10:20", 1500)
        self.assertEqual(self.wo.td_qty_counted, 7)
        self.assertEqual(self.m.current_log_id.pieces, 7)

    def test_live_sync(self):
        """AC-34: режим `live`, `qty_sync_s=300`: синхронізація не частіше 5 хв; `finish` — 0 до завершення."""
        self._icp().set_param("td.machine_connect.qty_sync_mode", "live")
        self._icp().set_param("td.machine_connect.qty_sync_s", "300")
        self.pieces("10:00", 3)
        self.assertEqual(self.wo.qty_produced, 3)
        self.pieces("10:01", 5)
        self.assertEqual(self.wo.qty_produced, 3)
        with at("10:05:06"):
            self.feed(self.ua(self.m, "10:05:01", pieces=6))
        self.assertEqual((self.wo.qty_produced, self.wo.td_qty_counted), (6, 6))

    def test_finish_mode_keeps_qty(self):
        self.pieces("10:00", 5)
        self.assertEqual((self.wo.qty_produced, self.wo.td_qty_counted), (0, 5))

    def test_finish_by_job_change(self):
        """AC-35: `counted=14`, `job → "-"` → `done`, `qty_produced=14`, активне завдання знято."""
        mo = self.wo.production_id
        self.pieces("10:00", 14)
        self.assertEqual(self.wo.state, "progress")
        with at("10:25:50"):
            self.feed(self.ua(self.m, "10:25:48", job="-"))
        self.assertEqual((self.wo.state, self.wo.qty_produced), ("done", 14))
        self.assertFalse(self.m.active_workorder_id)
        self.assertFalse(self.wo.time_ids.filtered(lambda t: not t.date_end))
        self.assertTrue(any("завершив верстат UA-T" in (msg.body or "") for msg in mo.message_ids))
        self.assertEqual(mo.product_qty, 14)

    def test_partial_hold(self):
        """AC-35: `counted=12` → неповна партія: позначка, таймер закрито, діяльність, `progress`, план не змінено."""
        mo = self.wo.production_id
        self.pieces("10:00", 12)
        with at("10:25:50"):
            self.feed(self.ua(self.m, "10:25:48", job="-"))
        self.assertTrue(self.wo.td_partial_hold)
        self.assertEqual(self.wo.state, "progress")
        self.assertFalse(self.wo.time_ids.filtered(lambda t: not t.date_end))
        self.assertEqual(mo.product_qty, 14)
        self.assertEqual(len(self.acts(mo, None).filtered(lambda a: a.summary.startswith("Неповна партія на UA-T"))), 1)
        self.assertFalse(self.m.active_workorder_id)

    def test_io_finish_after_idle(self):
        """AC-36: I/O, `counted ≥ remaining`, `stop` з `t` → о `t+59` ще ні, о `t+61` — `done`."""
        m = self.m_io
        wo = self.make_mo(self.wc_io, qty=8).workorder_ids[:1]
        with at("10:31:05"):
            self.feed(self.io(m, "10:31:00", run=True, pieces=0))
        self.assertEqual(wo.state, "progress")
        with at("10:35:05"):
            self.feed(self.io(m, "10:35:00", pieces=8))
        self.assertEqual(wo.td_qty_counted, 8)
        with at("10:40:00"):
            self.feed(self.io(m, "10:40:00", run=False))
        self.tick("10:40:59")
        self.assertEqual(wo.state, "progress")
        self.tick("10:41:01")
        self.assertEqual((wo.state, wo.qty_produced), ("done", 8))

    def test_finish_partial_rights(self):
        """AC-37: `action_f3d_finish_partial` — лише майстер; `qty_produced = counted`."""
        self.pieces("10:00", 12)
        with at("10:25:50"):
            self.feed(self.ua(self.m, "10:25:48", job="-"))
        wo = self.wo
        with self.assertRaises(AccessError):
            wo.with_user(self.user_mrp).action_f3d_finish_partial()
        wo.with_user(self.user_mrp_manager).action_f3d_finish_partial()
        self.assertEqual((wo.qty_produced, wo.state, wo.td_partial_hold), (12, "done", False))

    def test_clear_hold(self):
        self.pieces("10:00", 12)
        with at("10:25:50"):
            self.feed(self.ua(self.m, "10:25:48", job="-"))
        self.wo.with_user(self.user_mrp_manager).action_f3d_clear_hold()
        self.assertFalse(self.wo.td_partial_hold)

    def test_autopause_resume(self):
        """AC-38: ERROR → таймер закрито одразу; WORKING → новий таймер; `idle` → пауза кроном; `setup` не зупиняє."""
        m, wo = self.m, self.wo
        m.micro_stop_s = 0
        with at("10:12:03"):
            self.feed(self.ua(m, "10:12:00", state="ERROR"))
        first = wo.time_ids
        self.assertEqual(len(first), 1)
        self.assertEqual(first.date_end, kt("10:12"))
        self.assertTrue(m.wo_paused)
        self.assertEqual(wo.state, "progress")
        with at("10:30:02"):
            self.feed(self.ua(m, "10:30:00", state="WORKING"))
        opened = wo.time_ids.filtered(lambda t: not t.date_end)
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened.date_start, kt("10:30"))
        self.assertEqual(wo.td_employee_id, self.emp_ua)
        self.assertFalse(m.wo_paused)
        with at("10:40:02"):
            self.feed(self.ua(m, "10:40:00", state="READY", mode="AUTOMATIC"))
        self.assertEqual(m.state, "idle")
        self.tick("10:45:00")
        self.assertFalse(opened.date_end)
        self.tick("10:50:30")
        self.assertEqual(opened.date_end, kt("10:40"))
        self.assertTrue(m.wo_paused)
        # відновлення і налагодження
        with at("10:55:02"):
            self.feed(self.ua(m, "10:55:00", state="WORKING"))
        opened = wo.time_ids.filtered(lambda t: not t.date_end)
        self.assertEqual(len(opened), 1)
        with at("11:00:02"):
            self.feed(self.ua(m, "11:00:00", state="READY", mode="SETUP"))
        self.assertEqual(m.state, "setup")
        self.tick("11:20:00")
        self.assertFalse(opened.date_end)
