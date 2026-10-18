import csv
import json
from datetime import timedelta
from pathlib import Path

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from ..tools import params as P
from .flow import at, freeze
from .gate_case import GateCase, capture_ms, lpr_event

T = at(12, 40)


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardCommands(GateCase):
    def _ready(self, gate, ts=T, photocell=0):
        self.put(gate, "photocell", photocell, ts)

    def test_write_disabled(self):  # AC-34
        P.set_param(self.env, "write_enabled", "False")
        with freeze(T), self.assertRaisesRegex(UserError, "factory3d.yard.write_enabled"):
            self.gate_w.with_user(self.user_guard).action_command("open")
        self.assertFalse(self.cmds())

    def test_command_fields_and_access(self):  # AC-35
        gate = self.gate_w
        with freeze(T):
            self._ready(gate)
            with self.assertRaises(AccessError):
                gate.with_user(self.user_reader).action_command("open")
            with self.assertRaises(AccessError):
                gate.with_user(self.user_guard).action_command("open", reason="auto_booking")
            cmd = gate.with_user(self.user_guard).action_command("open")
        self.assertEqual(cmd.signal_id, self.sig(gate, "cmd_open"))
        self.assertEqual((cmd.value, cmd.origin, cmd.state), (1.0, "yard", "queued"))
        self.assertEqual(cmd.expires_at, T + timedelta(seconds=30))
        self.assertEqual(cmd.requested_by, self.user_guard)
        self.assertEqual((cmd.f3d_yard_gate_id, cmd.f3d_yard_kind, cmd.f3d_yard_reason), (gate, "open", "manual"))
        self.assertEqual((gate.open_cmd_id, gate.admitted_today), (cmd, 1))
        with freeze(T + timedelta(seconds=60)):
            release = gate.with_user(self.user_guard).action_command("release")
        self.assertEqual((release.signal_id, release.value), (self.sig(gate, "cmd_hold"), 0.0))

    def test_command_checks(self):  # AC-36
        gate = self.gate_w
        with freeze(T):
            self._ready(gate, photocell=1)
            with self.assertRaisesRegex(UserError, "перешкода"):
                gate.with_user(self.user_guard).action_command("open")
            self._ready(gate, ts=T - timedelta(seconds=60))
            with self.assertRaisesRegex(UserError, "Немає свіжих даних"):
                gate.with_user(self.user_guard).action_command("open")
            self._ready(gate)
            self.env["f3d.command"].sudo().create(
                {
                    "signal_id": self.sig(gate, "cmd_open").id,
                    "value": 1.0,
                    "requested_at": T - timedelta(seconds=10),
                    "f3d_yard_gate_id": gate.id,
                    "f3d_yard_kind": "open",
                }
            )
            with self.assertRaisesRegex(UserError, "ще виконується"):
                gate.with_user(self.user_guard).action_command("open")
        with freeze(T + timedelta(minutes=5)):
            self._ready(gate, ts=T + timedelta(minutes=5))
            self.sig(gate, "cmd_open").sudo().write_enabled = False
            with self.assertRaisesRegex(UserError, "не налаштований"):
                gate.with_user(self.user_guard).action_command("open")

    def _planned(self, plate, start, dock=None):
        visit = self._visit(batch_id=self._batch().id, plate=plate)
        self._booking(visit, dock or self.dock_t1, start, start + timedelta(hours=1), confirm=True)
        return visit

    def _event(self, n, plate, ts, now, camera="CAM-05", **kw):
        with freeze(now):
            return self.recv(
                lpr_event(
                    n,
                    sensorProviderID=camera,
                    carID=str(n),
                    plateText=plate,
                    plateUnicode=None,
                    capture_timestamp=capture_ms(ts),
                    plateListDescription="",
                    **kw,
                )
            )

    def test_auto_open(self):  # AC-37
        gate, now = self.gate_w, T + timedelta(seconds=5)
        self._ready(gate, ts=now)
        visit = self._planned("АА7310КТ", at(13))
        # режим «ручний»: команди немає, сповіщення немає
        ev = self._event(1, "AA7310KT", T, now)
        self.assertEqual(ev.match_state, "matched")
        self.assertFalse(ev.kpp_alert)
        self.assertFalse(self.cmds())
        self.assertEqual(visit.state, "arrived")
        # авто: у вікні слоту
        gate.mode = "auto"
        visit2 = self._planned("АА7311КТ", at(13), self.dock_t2)
        self._event(2, "AA7311KT", T, now)
        cmd = self.cmds()
        self.assertEqual(len(cmd), 1)
        self.assertEqual((cmd.f3d_yard_reason, cmd.f3d_yard_visit_id), ("auto_booking", visit2))
        self.assertEqual(visit2.state, "queued")
        self.assertEqual(cmd.requested_by, self.env.ref("base.user_root"))
        # поза вікном слоту
        visit3 = self._planned("АА7312КТ", at(15))
        ev3 = self._event(3, "AA7312KT", at(11, 50), at(11, 50) + timedelta(seconds=5))
        self.assertEqual(visit3.state, "arrived")
        self.assertIn("Поза вікном слоту 14:00–17:00", ev3.note)
        self.assertTrue(ev3.kpp_alert)
        self.assertEqual(len(self.cmds()), 1)
        # запізнення події
        visit4 = self._planned("АА7313КТ", at(13), self.dock_t4)
        self.put(gate, "photocell", 0, T + timedelta(minutes=10))
        ev4 = self._event(4, "AA7313KT", T - timedelta(minutes=5), T + timedelta(minutes=10))
        self.assertIn("запізнилась", ev4.note)
        self.assertEqual(visit4.state, "arrived")

    def test_auto_exit(self):  # AC-37
        gate, now = self.gate_e, T + timedelta(seconds=5)
        gate.mode = "auto"
        self._ready(gate, ts=now)
        visit = self._force(self._visit(visit_type="outgoing", plate="АА4512КТ"), "weighed")
        ev = self._event(5, "AA4512KT", T, now, camera="CAM-06")
        self.assertEqual((ev.match_state, ev.direction, visit.gate_out_id), ("matched", "out", gate))
        cmd = self.cmds(gate)
        self.assertEqual((cmd.f3d_yard_reason, gate.pending_visit_id), ("auto_exit", visit))

    def test_signal_addresses(self):  # AC-88
        path = Path(__file__).resolve().parents[1] / "data" / "f3d_yard_signals.csv"
        with open(path, newline="", encoding="utf-8") as f:
            rows = {r["code"]: r for r in csv.DictReader(f)}

        def write(code):
            return json.loads(rows[code]["address"])["write"]

        for gate, op, cl, hold in (("GATE-W", 16, 18, 20), ("GATE-E", 17, 19, 21)):
            self.assertEqual(write("yard/gates/%s/cmd_open" % gate), {"fc": 5, "addr": op, "pulse_ms": 1500})
            self.assertEqual(write("yard/gates/%s/cmd_close" % gate), {"fc": 5, "addr": cl, "pulse_ms": 1500})
            self.assertEqual(write("yard/gates/%s/cmd_hold" % gate), {"fc": 5, "addr": hold})
        with freeze(T):
            cmd_e = self.gate_e.with_user(self.user_guard).action_command("hold")
            cmd_w = self.gate_w.with_user(self.user_guard).action_command("hold")
        self.assertEqual((cmd_e.signal_id, cmd_e.value), (self.sig(self.gate_e, "cmd_hold"), 1.0))
        self.assertEqual(cmd_w.signal_id, self.sig(self.gate_w, "cmd_hold"))
        self.assertNotEqual(cmd_e.signal_id, cmd_w.signal_id)
