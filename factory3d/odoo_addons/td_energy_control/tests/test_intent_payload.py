"""AC-182 (форма payload), AC-188: інтент `td.command.payload` (API-26) і набір виду команд."""

import json
from pathlib import Path

from odoo.tests import tagged

from .common import TAGS, TestControlCommon

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"
INTENT_KINDS = ["qs_close", "qs_open", "bess_charge", "bess_discharge", "bess_stop", "chp_start", "chp_stop",
                "light_break", "light_restore", "vent_eco", "vent_restore", "air_setpoint"]  # fmt: skip


@tagged(*TAGS)
class TestIntentPayload(TestControlCommon):
    def test_payload_matches_contract(self):  # AC-182
        act = self.run_action("bess_charge", {"power_kw": 50, "until": "16:00"}, user=self.u_en1)
        payload = act.command_id.payload
        sample = json.loads((CONTRACTS / "api26_intent.json").read_text(encoding="utf-8"))
        self.assertEqual(set(payload), set(sample))
        self.assertEqual(set(payload["params"]), set(sample["params"]))
        self.assertEqual(payload["limits"], {"bess_kw_max": 200})
        self.assertEqual(payload["tz"], "Europe/Kyiv")
        self.assertEqual(payload["requested_by"], self.u_en1.login)
        self.assertRegex(payload["idem"], r"^[0-9a-f]{40}$")

    def test_only_intent_kinds_use_command(self):  # AC-188
        kinds_ = self.Kind.search([("executor", "=", "intent")]).mapped("code")
        self.assertEqual(sorted(kinds_), sorted(INTENT_KINDS))
        act = self.run_action("scenario_toggle", {"scenario": "chp", "enabled": True}, user=self.u_chief)
        self.assertFalse(act.command_id)
        self.assertEqual(self.env["td.command"].search_count([("energy_action_id", "=", act.id)]), 0)

    def test_payload_params_per_kind(self):
        self.assertEqual(self.run_action("light_break", user=self.u_en1).command_id.payload["params"],
                         {"level_pct": 50, "duration_min": 30, "scene_number": 3})  # fmt: skip
        self.assertEqual(self.run_action("vent_eco", user=self.u_en1).command_id.payload["params"],
                         {"vent_pct": 70, "duration_min": 120})  # fmt: skip
        self.assertEqual(self.run_action("air_setpoint", {"setpoint_bar": 6.5}, user=self.u_chief).command_id.payload["params"],
                         {"setpoint_bar": 6.5})  # fmt: skip
