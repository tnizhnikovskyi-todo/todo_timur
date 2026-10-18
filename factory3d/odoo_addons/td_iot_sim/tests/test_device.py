from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TAG_ARGS, SimCase


@tagged(*TAG_ARGS)
class TestDevice(SimCase):

    def setUp(self):
        super().setUp()
        self.cnc = self.make_device('CNC-T2', protocol='P-01', driver='opcua_ww')
        self.lsz = self.make_device('FA-CUT-T', protocol='P-09', driver='passive', params={'lsz': 12})

    def _fault(self, device, reason):
        wiz = self.env['f3d.sim.fault.wizard'].create({'device_id': device.id, 'reason': reason})
        return wiz.action_confirm()

    def test_fault_wizard_calls_api(self):
        self.respond('POST', '/device/CNC-T2/fault', 200, {})
        self._fault(self.cnc, 'spindle')
        self.assertEqual(self.cnc.state, 'fault')
        self.assertEqual(self.calls[-1]['json'], {'reason': 'spindle'})
        event = self.env['f3d.sim.event'].search([('kind', '=', 'command'), ('device_code', '=', 'CNC-T2')])
        self.assertTrue(event)
        self.assertNotIn('secret-sim-token', str(event.payload))

    def test_clear(self):
        self.respond('POST', '/device/CNC-T2/fault', 200, {})
        self.respond('POST', '/device/CNC-T2/clear', 200, {})
        self._fault(self.cnc, 'generic')
        self.cnc.action_clear()
        self.assertEqual(self.cnc.state, 'ok')
        self.assertFalse(self.cnc.fault_reason)

    def test_code_regex(self):
        with self.assertRaises(ValidationError):
            self.make_device('cnc 2')

    def test_unit_unique(self):
        self.make_device('PM-A', protocol='P-05', driver='modbus_pm5560', unit_id=201)
        with self.assertRaises(ValidationError):
            self.make_device('PM-B', protocol='P-05', driver='modbus_pm5560', unit_id=201)
        with self.assertRaises(ValidationError):
            self.make_device('PM-C', protocol='P-05', driver='modbus_pm5560', unit_id=300)
        # I/O-модулі ADAM: кілька пристроїв на одному unit — дозволено
        self.make_device('IO-A', protocol='P-02', driver='modbus_adam6050', unit_id=80)
        self.make_device('IO-B', protocol='P-02', driver='modbus_adam6050', unit_id=80)

    def test_reason_loop_only_lsz(self):
        with self.assertRaises(ValidationError):
            self._fault(self.cnc, 'loop')
        self.respond('POST', '/device/FA-CUT-T/fault', 200, {})
        self._fault(self.lsz, 'loop')
        self.assertEqual(self.calls[-1]['json'], {'reason': 'loop'})

    def test_equipment_link_by_code(self):
        eq = self.env['maintenance.equipment'].create({'name': 'Фреза-Т', 'f3d_code': 'CNC-T2'})
        self.assertEqual(eq.f3d_sim_device_id, self.cnc)
        self.respond('POST', '/device/CNC-T2/fault', 200, {})
        self._fault(self.cnc, 'generic')
        self.assertEqual(eq.f3d_sim_state, 'fault')
        self.assertEqual(self.cnc.display_name, 'CNC-T2 — CNC-T2')
