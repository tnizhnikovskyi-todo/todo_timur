from odoo.tests import tagged

from .common import TAG_ARGS, SimCase


@tagged(*TAG_ARGS)
class TestScenarioEvacuation(SimCase):
    def test_scenario_record(self):
        scenario = self.env.ref("td_iot_sim.scenario_fire_evacuation")
        self.assertEqual((scenario.code, scenario.group, scenario.duration_s), ("fire_evacuation", "safety", 300))
        props = scenario.params_schema["properties"]
        self.assertTrue({"zone", "stuck", "wrong_exit_pct", "speed_mps", "return_people"} <= set(props))
        self.assertEqual(scenario.params_default["stuck"], 1)
        self.assertEqual(self.env["td.sim.scenario"].search([("code", "=", "fire_evacuation")]), scenario)
