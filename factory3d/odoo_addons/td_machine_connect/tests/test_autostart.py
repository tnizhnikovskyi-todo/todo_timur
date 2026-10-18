"""AC-25…AC-32, AC-101: автостарт завдань (R-09), «Надіслати на верстат» (M-13)."""

from unittest import mock

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import F3DMachineCase, at, kt


def job(wo):
    return "WO%05d" % wo.id


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestAutostart(F3DMachineCase):
    def setUp(self):
        super().setUp()
        self.enable_autostart()
        self.bot = self.env.ref("td_machine_connect.user_td_machine")

    def wo_of(self, wc, **kw):
        return self.make_mo(wc, **kw).workorder_ids[:1]

    def work(self, m, t, **kw):
        sec = "%s:05" % t if t.count(":") == 1 else t
        with at(sec):
            return self.feed(self.ua(m, t, state="WORKING", mode="AUTOMATIC", **kw))

    def no_job_acts(self, m):
        return self.acts(m).filtered(lambda a: "працює без завдання" in a.summary)

    def test_start_by_job(self):
        """AC-25: WORKING + job → завдання стартувало, таймер від технічного користувача з `date_start = t`."""
        m, wo = self.m_ua, self.wo_of(self.wc_ua)
        self.work(m, "09:55", job=job(wo))
        self.assertEqual(wo.state, "progress")
        timers = wo.time_ids
        self.assertEqual(len(timers), 1)
        self.assertFalse(timers.date_end)
        self.assertEqual((timers.user_id, timers.create_uid), (self.bot, self.bot))
        self.assertEqual(timers.date_start, kt("09:55"))
        self.assertEqual(wo.td_employee_id, self.emp_ua)
        self.assertTrue(wo.td_auto_started)
        self.assertEqual(m.active_workorder_id, wo)
        self.assertEqual(m.current_log_id.workorder_id, wo)
        self.assertTrue(any("стартував верстат UA-T" in (msg.body or "") for msg in wo.production_id.message_ids))

    def test_single_ready_io(self):
        """AC-26 (1): I/O без сигналу завдання, одне `ready` → старт."""
        m, wo = self.m_io, self.wo_of(self.wc_io)
        with at("09:55:05"):
            self.feed(self.io(m, "09:55:00", run=True))
        self.assertEqual((wo.state, m.active_workorder_id), ("progress", wo))
        self.assertFalse(m.no_job_since)

    def test_two_ready_no_start_activity(self):
        """AC-26 (2): два `ready` → старту немає, `no_job_since`, одна діяльність після 15 хв."""
        m = self.m_io
        wos = self.wo_of(self.wc_io) | self.wo_of(self.wc_io)
        with at("09:55:05"):
            self.feed(self.io(m, "09:55:00", run=True))
        self.assertEqual(wos.mapped("state"), ["ready", "ready"])
        self.assertEqual(m.no_job_since, kt("09:55"))
        self.tick("10:05:00")
        self.assertFalse(self.no_job_acts(m))
        self.tick("10:10:30")
        self.assertEqual(len(self.no_job_acts(m)), 1)
        self.tick("10:12:00")
        self.assertEqual(len(self.no_job_acts(m)), 1)
        self.assertTrue(m.no_job_notified)

    def test_job_mode_requires_job(self):
        """AC-27: режим `job` і `job="-"` → старту немає навіть за одного `ready`."""
        m, wo = self.m_saw, self.wo_of(self.wc_saw)
        self.assertEqual(m.auto_start_mode, "job")
        self.work(m, "09:55", job="-")
        self.assertEqual((m.state, wo.state), ("working", "ready"))
        self.assertFalse(wo.time_ids)

    def test_unknown_job_activity(self):
        """AC-28: завдання не знайдено / іншого РЦ → старту немає, діяльність (одна на текст)."""
        m = self.m_ua
        wo = self.wo_of(self.wc_ua)
        other = self.wo_of(self.wc_io)
        self.work(m, "09:55", job="WO99999")
        summary = "Завдання верстата «WO99999» не знайдено в Odoo"
        self.assertEqual(len(self.acts(m, summary)), 1)
        self.assertEqual(wo.state, "ready")
        with at("10:00:05"):
            m._f3d_autostart(kt("10:00"), text="WO99999")
        self.assertEqual(len(self.acts(m, summary)), 1)
        with at("10:01:05"):
            m._f3d_autostart(kt("10:01"), text=job(other))
        self.assertEqual(other.state, "ready")
        self.assertEqual(len(self.acts(m, "Завдання верстата «%s» не знайдено в Odoo" % job(other))), 1)
        self.assertFalse(m.active_workorder_id)

    def test_idempotent(self):
        """AC-29: той самий пакет двічі й ще раз з новим `ts` → один таймер, один виклик старту."""
        m, wo = self.m_ua, self.wo_of(self.wc_ua)
        model = type(self.env["td.machine"])
        orig = model._f3d_start_wo
        with mock.patch.object(model, "_f3d_start_wo", autospec=True, side_effect=orig) as start:
            self.work(m, "09:55", job=job(wo))
            self.work(m, "09:55", job=job(wo))
            self.work(m, "09:56", job=job(wo))
            m._f3d_autostart(kt("09:57"), text=job(wo))
        self.assertEqual(start.call_count, 1)
        self.assertEqual(len(wo.time_ids.filtered(lambda t: not t.date_end)), 1)
        self.assertEqual(len(wo.time_ids), 1)

    def test_blocked_wc_unblocked(self):
        """AC-30: РЦ `blocked` записом оператора → запис закрито `ts`, завдання стартувало."""
        m, wo = self.m_ua, self.wo_of(self.wc_ua)
        rec = (
            self.env["mrp.workcenter.productivity"]
            .with_user(self.user_mrp)
            .create(
                {
                    "workcenter_id": self.wc_ua.id,
                    "loss_id": self.env.ref("mrp.block_reason1").id,
                    "date_start": kt("09:40"),
                }
            )
        )
        self.assertEqual(self.wc_ua.working_state, "blocked")
        self.work(m, "09:55", job=job(wo))
        self.assertEqual(rec.date_end, kt("09:55"))
        self.assertEqual(wo.state, "progress")

    def test_employee_order(self):
        """AC-31: порядок вибору працівника (б) > (в) > (г) > (ґ), недозволені пропускаються, (д) без працівника."""
        m, wo = self.m_ua, self.wo_of(self.wc_ua)
        model = type(m)
        ua, saw, io, x = self.emp_ua, self.emp_saw, self.emp_io, self.emp_x
        m.employee_id = io
        self.assertEqual(m._f3d_pick_employee(wo), ua)  # (в) OP-UA-T
        with mock.patch.object(model, "_f3d_wc_employees", return_value=saw | x):
            self.assertEqual(m._f3d_pick_employee(wo), saw)  # (в), (г) недозволені → (ґ)
            m.employee_id = x
            self.assertEqual(m._f3d_pick_employee(wo), x)  # (г)
        with mock.patch.object(model, "_f3d_wc_employees", return_value=ua | x):
            self.assertEqual(m._f3d_pick_employee(wo), ua)  # (в) краще за (г)
        record = (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .create(
                {
                    "workcenter_id": self.wc_ua.id,
                    "workorder_id": wo.id,
                    "loss_id": self.env.ref("mrp.block_reason7").id,
                    "date_start": kt("08:00"),
                    "date_end": kt("08:30"),
                    "user_id": self.user_mrp.id,
                }
            )
        )
        wo.td_employee_id = saw
        self.assertEqual(m._f3d_pick_employee(wo), saw)  # (б) працівник сьогоднішнього запису
        with mock.patch.object(model, "_f3d_wc_employees", return_value=ua | x):
            self.assertEqual(m._f3d_pick_employee(wo), ua)  # (б) недозволений → (в)
        wo.td_employee_id = False
        record.unlink()
        m.employee_id = False
        with mock.patch.object(type(self.env["hr.employee"]), "search_f3d", return_value=self.env["hr.employee"]):
            self.assertFalse(m._f3d_pick_employee(wo))  # (д)

    def test_employee_fields_enterprise(self):
        """AC-31 (Enterprise): недозволений OP-код пропускається за `wc.employee_ids` (лише з `mrp_workorder`)."""
        if "employee_ids" not in self.env["mrp.workcenter"]._fields:
            self.skipTest("немає mrp.workcenter.employee_ids (Enterprise mrp_workorder)")
        self.wc_ua.employee_ids = self.emp_saw | self.emp_x
        wo = self.wo_of(self.wc_ua)
        self.assertEqual(self.m_ua._f3d_pick_employee(wo), self.emp_saw)

    def test_disabled(self):
        """AC-32: автостарт вимкнено — завдання не стартувало; `read_enabled=False` — стан не змінюється."""
        m, wo = self.m_ua, self.wo_of(self.wc_ua)
        self._icp().set_param("td.machine_connect.auto_start_enabled", "False")
        written = wo.write_date
        self.work(m, "09:55", job=job(wo))
        self.assertEqual(m.state, "working")
        self.assertEqual((wo.state, wo.write_date, len(wo.time_ids)), ("ready", written, 0))
        self._icp().set_param("td.machine_connect.read_enabled", "False")
        with at("10:00:05"):
            self.feed(self.ua(m, "10:00:00", state="ERROR"))
        self.assertEqual(m.state, "working")

    def test_send_to_machine(self):
        """AC-101: «Надіслати на верстат» — команда `Store`, чатер, обмеження."""
        self.enable_write()
        mo = self.make_mo(self.wc_ua, qty=14, name="WH/MO/T0002")
        wo = mo.workorder_ids[:1]
        wo.with_user(self.user_mrp).action_f3d_send_to_machine()
        cmd = self.env["td.command"].search([("td_machine_id", "=", self.m_ua.id)])
        self.assertEqual(len(cmd), 1)
        self.assertEqual(cmd.signal_id, self.sig_ua_cmd)
        self.assertEqual(cmd.origin, "machine_connect")
        self.assertEqual(cmd.text, "Store;%s;14;WH/MO/T0002;5" % job(wo))
        if "payload" in cmd._fields:
            self.assertEqual(
                cmd.payload,
                {"method": "Store", "job": job(wo), "qty": 14, "ref": "WH/MO/T0002", "priority": 5},
            )
        self.assertTrue(any("поставлено в чергу верстата UA-T" in (msg.body or "") for msg in mo.message_ids))
        self.cmd_done(cmd, data={"ReturnStatus": 0})
        self.assertTrue(
            any("Команда" in (msg.body or "") and "ReturnStatus" in (msg.body or "") for msg in self.m_ua.message_ids)
        )
        # завдання в роботі
        wo.write({"state": "progress"})
        with self.assertRaises(UserError):
            wo.with_user(self.user_mrp).action_f3d_send_to_machine()
        # РЦ без OPC UA JobManagement
        wo_io = self.wo_of(self.wc_io)
        with self.assertRaisesRegex(UserError, "не приймає завдань з Odoo"):
            wo_io.with_user(self.user_mrp).action_f3d_send_to_machine()
        # запис вимкнено
        wo2 = self.wo_of(self.wc_ua)
        self._icp().set_param("td.machine_connect.write_enabled", "False")
        with self.assertRaisesRegex(UserError, "write_enabled"):
            wo2.with_user(self.user_mrp).action_f3d_send_to_machine()
