from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import TAG_ARGS, SimCase


@tagged(*TAG_ARGS)
class TestScenarioRun(SimCase):

    def test_scenarios_loaded(self):
        self.assertEqual(self.env['f3d.sim.scenario'].search_count([]), 15)

    def test_run_wizard_creates_run(self):
        scenario = self.env.ref('factory3d_iot_sim.scenario_filter_clogged')
        device = self.env['f3d.sim.device'].search([('code', '=', 'RV-05')]) or self.make_device('RV-05')
        self.respond('POST', '/scenario/filter_clogged/start', 201, {'id': 'r-01J', 'state': 'running'})
        wiz = self.env['f3d.sim.run.wizard'].with_context(default_scenario_id=scenario.id).create(
            {'scenario_id': scenario.id, 'device_id': device.id, 'params_text': '{"ramp_min": 2}'})
        action = wiz.action_confirm()
        run = self.env['f3d.sim.run'].browse(action['res_id'])
        self.assertEqual(run.state, 'running')
        self.assertEqual(run.sim_run_id, 'r-01J')
        self.assertTrue(run.name.startswith('RUN/'))
        body = self.calls[-1]['json']
        self.assertEqual(body['params']['device'], 'RV-05')
        self.assertEqual(body['run_ref'], run.name)
        event = self.env['f3d.sim.event'].search([('kind', '=', 'command'), ('run_id', '=', run.id)])
        self.assertTrue(event)
        self.assertNotIn('secret-sim-token', str(event.payload))

    def test_wizard_default_params(self):
        scenario = self.env.ref('factory3d_iot_sim.scenario_blackout')
        defaults = self.env['f3d.sim.run.wizard'].with_context(default_scenario_id=scenario.id).default_get(
            ['scenario_id', 'params_text'])
        self.assertIn('restore_delay_s', defaults['params_text'])

    def test_run_failed_on_service_error(self):
        scenario = self.env.ref('factory3d_iot_sim.scenario_spark')
        self.respond('POST', '/scenario/spark/start', 409, {'detail': 'конфлікт'})
        run = self.env['f3d.sim.run']._create_and_start(scenario, {})
        self.assertEqual(run.state, 'failed')
        self.assertIn('конфлікт', run.message)

    def test_validate_params(self):
        Run = self.env['f3d.sim.run']
        schema = {'properties': {'device': {'type': 'string'}, 'n': {'type': 'integer', 'minimum': 1, 'maximum': 5},
                                 'k': {'type': 'string', 'enum': ['a', 'b']}}, 'required': ['device']}
        self.assertTrue(Run._validate_params(schema, {'device': 'X', 'n': 3, 'k': 'a'}))
        for bad in ({}, {'device': 1}, {'device': 'X', 'n': 9}, {'device': 'X', 'n': 0},
                    {'device': 'X', 'k': 'z'}, {'device': 'X', 'n': True}):
            with self.assertRaises(ValidationError, msg=str(bad)):
                Run._validate_params(schema, bad)

    def test_write_disabled_blocks_start(self):
        self.set_params(write_enabled='False')
        scenario = self.env.ref('factory3d_iot_sim.scenario_spark')
        with self.assertRaisesRegex(UserError, 'стоп-краном'):
            self.env['f3d.sim.run']._create_and_start(scenario, {})

    def test_stop(self):
        scenario = self.env.ref('factory3d_iot_sim.scenario_spark')
        self.respond('POST', '/scenario/spark/start', 201, {'id': 'r-9'})
        run = self.env['f3d.sim.run']._create_and_start(scenario, {})
        self.respond('POST', '/scenario/spark/stop', 200, {'id': 'r-9', 'state': 'stopped'})
        run.action_stop()
        self.assertEqual(run.state, 'stopped')
        self.assertTrue(run.stop_ts)
        self.assertEqual(self.calls[-1]['json'], {'run_id': 'r-9'})
        self.respond('POST', '/scenario/spark/stop', 200, {'id': 'r-9', 'state': 'stopping'})
        run.state = 'running'
        run.action_stop()
        self.assertEqual(run.state, 'stopping')
