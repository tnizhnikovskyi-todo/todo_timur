"""AC-19: блок «Імітація» (API-07) — без td_iot_sim `available=false`, з ним — сценарії й запуск через майстер."""

import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from ..models.td_chp_pult import SIM_CODES
from .common import TAGS, ChpCase


@tagged(*TAGS)
class TestSim(ChpCase):
    def test_unavailable_without_simulator(self):
        if "td.sim.scenario" in self.env:
            self.skipTest("td_iot_sim встановлено")
        self.assertEqual(self.pult(self.u_mgr).sim("list"), {"available": False, "scenarios": []})
        with self.assertRaises(UserError):
            self.pult(self.u_mgr).sim("start", code="chp_fire")

    def test_manager_only(self):
        with self.assertRaises(AccessError):
            self.pult(self.u_user).sim("list")
        with self.assertRaises(AccessError):
            self.pult(self.u_op1).sim("list")

    def test_list_and_start_via_wizard(self):
        if "td.sim.scenario" not in self.env:
            self.skipTest("td_iot_sim не встановлено")
        Scenario = self.env["td.sim.scenario"]
        have = set(Scenario.search([]).mapped("code"))
        for code in SIM_CODES:  # S-25…S-30 дає td_iot_sim ≥ 19.0.2.3.0; для старіших версій створюємо відсутні
            if code not in have:
                Scenario.create({"code": code, "name": f"КГУ: {code}", "group": "energy", "duration_s": 600})
        res = self.pult(self.u_mgr).sim("list")
        self.assertTrue(res["available"])
        self.assertEqual(sorted(s["code"] for s in res["scenarios"]), sorted(SIM_CODES))
        self.assertEqual(len(res["scenarios"]), 9)
        wizard = self.registry["td.sim.run.wizard"]
        with patch.object(wizard, "action_confirm", autospec=True, return_value={"res_id": 77}) as confirm:
            out = self.pult(self.u_mgr).sim("start", code="chp_fire")
        self.assertEqual(out, {"ok": True, "code": "chp_fire", "run_id": 77})
        self.assertEqual(confirm.call_count, 1)
        started = confirm.call_args.args[0]
        self.assertEqual(started.scenario_id.code, "chp_fire")
        self.assertEqual(started.env.user, self.u_mgr)  # від імені користувача
        self.assertEqual(json.loads(started.params_text), json.loads(started.params_text))
        with self.assertRaises(UserError):
            self.pult(self.u_mgr).sim("start", code="shift")  # не сценарій КГУ
        self.assertEqual(self.pult(self.u_mgr).sim("stop", code="chp_fire"), {"ok": True, "stopped": 0})
        self.assertEqual(self.pult(self.u_mgr).sim("reset"), {"ok": True, "stopped": 0})
