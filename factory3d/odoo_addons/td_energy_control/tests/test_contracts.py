"""Заморозка контрактів C-38…C-47: набір ключів реальних відповідей = `contracts/*.json`."""

import json
from pathlib import Path

from odoo.tests import tagged

from ..tools import config_builder
from .common import TAGS, TestControlCommon

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"


def load(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def shape(obj, depth=2):
    """Набір ключів до глибини `depth` (списки — за першим елементом)."""
    if isinstance(obj, dict) and depth:
        return {k: shape(v, depth - 1) for k, v in obj.items()}
    if isinstance(obj, list) and obj and depth:
        return [shape(obj[0], depth - 1)]
    return None


@tagged(*TAGS)
class TestContracts(TestControlCommon):
    def test_get_control(self):
        got, want = self.ctl(self.u_en1).get_control(), load("api16_get_control.json")
        self.assertEqual(set(got), set(want))
        for key in ("meta", "engine"):
            self.assertEqual(set(got[key]), set(want[key]), key)
        self.assertEqual(set(got["scenarios"]), set(want["scenarios"]))
        self.assertEqual(set(got["scenarios"]["items"][0]), set(want["scenarios"]["items"][0]))
        self.assertEqual(set(got["shed"]), set(want["shed"]))
        self.assertEqual(set(got["shed"]["items"][0]), set(want["shed"]["items"][0]))
        self.assertEqual(set(got["commands"][0]), set(want["commands"][0]))
        self.assertEqual(set(got["schedule"]), set(want["schedule"]))
        self.assertEqual(set(got["schedule"]["rows"][0]), set(want["schedule"]["rows"][0]))
        self.assertEqual(set(got["journal"][0]) if got["journal"] else set(want["journal"][0]), set(want["journal"][0]))

    def test_prepare_confirm_action(self):
        prep = self.ctl(self.u_en1).prepare("qs_close")
        self.assertEqual(set(prep), set(load("api17_prepare.json")))
        self.assertEqual(set(prep["checks"][0]), set(load("api17_prepare.json")["checks"][0]))
        res = self.ctl(self.u_en1).confirm(prep["token"])
        self.assertEqual(set(res), set(load("api18_confirm.json")))
        self.assertEqual(set(self.ctl(self.u_en1).get_action(prep["action_id"])), set(load("api22_get_action.json")))
        self.assertEqual(set(self.ctl(self.u_en1).get_schedule()), set(load("api23_get_schedule.json")))
        journal = self.ctl(self.u_en1).get_journal()
        self.assertEqual(set(journal), {"items", "more"})
        self.assertEqual(set(journal["items"][0]), set(load("api28_journal.json")["items"][0]))
        node = self.ctl(self.u_en1).get_node_actions("QS")
        self.assertEqual(set(node[0]), set(load("api27_node_actions.json")[0]))
        self.assertEqual(self.ctl(self.u_en1).get_node_actions("T1"), [])

    def test_config(self):
        got, want = config_builder.build(self.env), load("api24_config.json")
        self.assertEqual(set(got), set(want) - {"etag"})
        for key in ("flags", "engine", "plant", "signals", "inputs", "limits"):
            self.assertEqual(set(got[key]), set(want[key]), key)
        self.assertEqual(set(got["scenarios"]), set(want["scenarios"]))
        self.assertEqual(set(got["shed"][0]), set(want["shed"][0]))
        self.assertEqual(set(got["slots"][0]) if got["slots"] else set(want["slots"][0]), set(want["slots"][0]))
        self.assertEqual(set(got["tariff"]), set(want["tariff"]))
        self.assertEqual(set(got["bms"]), set(want["bms"]))
        self.assertEqual(
            set(got["bms"]["night"]["vent"][0]) - {"sp_night_signal"},
            set(want["bms"]["night"]["vent"][0]) - {"sp_night_signal"},
        )
        for key, sc in want["scenarios"].items():
            self.assertLessEqual(set(sc["params"]), set(got["scenarios"][key]["params"]), key)
        self.assertEqual(set(got["scenarios"]["night"]["params"]), set(want["scenarios"]["night"]["params"]))

    def test_registers_match_signals(self):  # C-47
        regs = {r["code"]: r for r in load("c47_registers.json")["registers"]}
        Signal = self.env["td.signal"].sudo()
        self.assertEqual(len(regs), 28)
        for code, reg in regs.items():
            sig = Signal.search([("code", "=", code)])
            self.assertEqual(sig.address["addr"], reg["hr"], code)
            self.assertEqual(bool(sig.address.get("write")), reg["rw"] in ("W", "RW"), code)

    def test_state_request_shape(self):
        want = load("api25_state_request.json")
        res = self.State._td_report(want)
        self.assertEqual(set(res), set(load("api25_state_response.json")))

    def test_pending_shape(self):
        act = self.run_action("qs_close", user=self.u_en1)
        pend = self.ctl(self.u_en2).get_control()["pending"]
        self.assertEqual(set(pend[0]), set(load("api16_get_control.json")["pending"][0]))
        self.assertEqual(pend[0]["id"], act.id)

    def test_advice_contract(self):  # C-38
        want = load("c38_advice_actions.json")
        for action in want["actions"]:
            self.assertEqual(set(action), {"code", "label", "kind", "class", "params"})
        self.assertEqual(
            set(want["intent_aliases"]),
            {"vent_night_mode", "air_pressure_setpoint", "pv_self_consumption", "heat_schedule_shift"},
        )
