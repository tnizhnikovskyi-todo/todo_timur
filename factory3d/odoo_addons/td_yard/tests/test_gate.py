from datetime import timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .flow import at, freeze
from .gate_case import GateCase

T = at(10, 0)


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardGate(GateCase):
    def test_seed_gates(self):  # AC-46
        gw, ge = self.gate_w, self.gate_e
        self.assertEqual((gw.direction, gw.side, gw.camera_code, gw.mode), ("in", "west", "CAM-05", "manual"))
        self.assertEqual((gw.pos_x, gw.pos_y), (-20.0, -30.0))
        self.assertEqual((ge.direction, ge.side, ge.camera_code), ("out", "east", "CAM-06"))
        with self.assertRaisesRegex(ValidationError, "CAM-05"):
            self.env["td.yard.gate"].create(
                {"td_code": "GATE-X", "name": "Дубль", "direction": "in", "side": "west", "camera_code": "CAM-05"}
            )

    def test_state_from_signals(self):  # AC-47
        gate = self.gate_w
        with freeze(T):
            self.put(gate, "state", 1, T)
            gate._f3d_yard_refresh_state()
            self.assertEqual(gate.state, "open")
            gate.invert_di = True
            gate._f3d_yard_refresh_state()
            self.assertEqual(gate.state, "closed")
            gate.invert_di = False
            self.put(gate, "state", 1, T, status="stale")
            gate._f3d_yard_refresh_state()
            self.assertEqual(gate.state, "unknown")
            self.put(gate, "state", 1, T)
            gate.last_error = "помилка"
            gate._f3d_yard_refresh_state()
            self.assertEqual(gate.state, "error")
            gate.last_error = False
            self.env["ir.config_parameter"].sudo().set_param("td.yard.read_enabled", "False")
            gate._f3d_yard_refresh_state()
            self.assertEqual(gate.state, "unknown")

    def _done_open_cmd(self, gate, done_at):
        cmd = (
            self.env["td.command"]
            .sudo()
            .create(
                {
                    "signal_id": self.sig(gate, "cmd_open").id,
                    "value": 1.0,
                    "requested_at": done_at,
                    "td_yard_gate_id": gate.id,
                    "td_yard_kind": "open",
                }
            )
        )
        cmd.write({"state": "done", "done_at": done_at})
        gate.write({"open_cmd_id": cmd.id, "last_command_id": cmd.id})
        return cmd

    def test_open_confirmation(self):  # AC-38
        gate = self.gate_w
        with freeze(T):
            self._done_open_cmd(gate, T)
        with freeze(T + timedelta(seconds=4)):
            self.put(gate, "state", 1, T + timedelta(seconds=4))
            gate._f3d_yard_refresh_state()
        self.assertEqual(gate.state, "open")
        self.assertFalse(gate.last_error)
        self.assertFalse(gate.open_cmd_id)
        # без підтвердження за open_timeout_s
        gate.write({"state": "closed", "opened_at": False})
        with freeze(T + timedelta(minutes=5)):
            self._done_open_cmd(gate, T + timedelta(minutes=5))
        with freeze(T + timedelta(minutes=5, seconds=11)):
            self.put(gate, "state", 0, T + timedelta(minutes=5, seconds=10))
            gate._f3d_yard_refresh_state()
        self.assertEqual(gate.state, "error")
        self.assertIn("Немає підтвердження відкриття за 10 с", gate.last_error)
        self.assertTrue(gate.activity_ids.filtered(lambda a: a.user_id == self.user_guard))
        gate.with_user(self.user_guard).action_reset_error()
        self.assertFalse(gate.last_error)
        self.assertNotEqual(gate.state, "error")
        # команда прострочена
        with freeze(T + timedelta(minutes=10)):
            cmd = self._done_open_cmd(gate, T + timedelta(minutes=10))
            cmd.write({"state": "expired"})
            self.put(gate, "state", 0, T + timedelta(minutes=10))
        with freeze(T + timedelta(minutes=10, seconds=1)):
            gate._f3d_yard_refresh_state()
        self.assertEqual(gate.state, "error")
        self.assertIn("не виконано", gate.last_error)

    def test_hold_and_release(self):  # AC-39
        gate = self.gate_w
        with freeze(T):
            self.put(gate, "state", 1, T)
            gate.with_user(self.user_guard).action_hold()
            self.assertEqual(gate.hold_until, T + timedelta(minutes=30))
            gate._f3d_yard_refresh_state()
            self.assertEqual(gate.state, "held")
        later = T + timedelta(minutes=31)
        with freeze(later):
            self.env["td.yard.visit"]._cron_queue()
        release = self.cmds(gate).filtered(lambda c: c.td_yard_kind == "release")
        self.assertEqual(len(release), 1)
        self.assertEqual(release.td_yard_reason, "auto_hold_max")
        self.assertFalse(gate.hold_until)
        # команди вимкнено: лише очищення й чаттер
        self.env["ir.config_parameter"].sudo().set_param("td.yard.write_enabled", "False")
        gate.hold_until = T
        before = len(self.cmds(gate))
        with freeze(later + timedelta(minutes=1)):
            self.env["td.yard.visit"]._cron_queue()
        self.assertEqual(len(self.cmds(gate)), before)
        self.assertFalse(gate.hold_until)
        self.assertTrue(any("Утримання знято" in (m.body or "") for m in gate.message_ids))

    def test_antipassback(self):  # AC-40
        gate = self.gate_w
        gate.write({"passes_day_start": 7, "admitted_today": 0})
        visit = self._visit(plate="АА1111КТ")
        visit._set_state("arrived")
        with freeze(T):
            visit.with_user(self.user_guard).action_admit(open_gate=False)
        self.assertEqual(gate.admitted_today, 1)
        gate._f3d_yard_on_readings([("passes", T, 8, 1)])
        self.assertEqual((gate.passes_today, gate.tailgate_today), (1, 0))
        gate._f3d_yard_on_readings([("passes", T + timedelta(seconds=10), 9, 1)])
        self.assertEqual((gate.passes_today, gate.tailgate_today), (2, 1))
        self.assertTrue(any("Проїзд без дозволу" in (m.body or "") for m in gate.message_ids))
        # антипрохід вимкнено
        self.env["ir.config_parameter"].sudo().set_param("td.yard.antipassback", "False")
        gate.write({"passes_day_start": 7, "admitted_today": 0, "passes_today": 0, "tailgate_today": 0})
        gate._f3d_yard_on_readings([("passes", T, 8, 1), ("passes", T, 9, 1)])
        self.assertEqual(gate.tailgate_today, 0)

    def test_loop_exit(self):  # AC-40
        for gate, expected in ((self.gate_e, "left"), (self.gate_w, "weighed")):
            visit = self._force(self._visit(plate="АА2222КТ"), "weighed")
            gate.write({"pending_visit_id": visit.id, "loop_occupied": False})
            gate._f3d_yard_on_readings([("loop", T, 1, 1), ("loop", T + timedelta(seconds=5), 0, 1)])
            self.assertEqual(visit.state, expected)
            self.assertFalse(gate.pending_visit_id)
            self.assertFalse(gate.loop_occupied)
