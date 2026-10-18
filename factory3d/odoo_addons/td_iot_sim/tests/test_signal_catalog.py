import os
import tempfile

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TAG_ARGS, SimCase


@tagged(*TAG_ARGS)
class TestSignalCatalog(SimCase):

    def test_csv_loaded_1168(self):
        Signal = self.env['f3d.sim.signal']
        self.assertEqual(Signal.search_count([]), 1168)
        self.assertEqual(Signal.search_count([('protocol', '=', 'none')]), 151)
        self.assertFalse(Signal.search([('device_id', '=', False)]))

    def test_mock_signals_have_level0(self):
        mock_signals = self.env['f3d.sim.signal'].search([('origin', '=', 'mock')])
        self.assertEqual(len(mock_signals), 196)
        self.assertTrue(all(s.level0_code == s.code for s in mock_signals))

    def test_unknown_device_creates_passive(self):
        path = os.path.join(tempfile.mkdtemp(), 'cat.csv')
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write('n,code,device,protocol,address,dtype,unit,scale,nominal,thresholds,model,status\n'
                     '1,equipment/ZZ-UNKNOWN/x,ZZ-UNKNOWN,P-07,Modbus u99 fc3 pdu1 u16,U16,bar,×1,5,—,R-08,новий\n')
        with self.assertLogs('odoo.addons.factory3d_iot_sim.models.sim_signal', 'WARNING'):
            self.env['f3d.sim.signal']._load_catalog(path)
        device = self.env['f3d.sim.device'].search([('code', '=', 'ZZ-UNKNOWN')])
        self.assertEqual(device.driver, 'passive')
        self.assertEqual(device.state, 'passive')
        # повторне завантаження — без дублікатів
        self.env['f3d.sim.signal']._load_catalog(path)
        self.assertEqual(self.env['f3d.sim.signal'].search_count([('code', '=', 'equipment/ZZ-UNKNOWN/x')]), 1)

    def test_computed_protocol_none(self):
        signal = self.env['f3d.sim.signal'].search([('protocol', '=', 'none')], limit=1)
        with self.assertRaisesRegex(UserError, 'модуль-власник'):
            signal.action_read_now()
        self.assertEqual(self.calls, [])

    def test_read_now_updates_last_value(self):
        signal = self.env['f3d.sim.signal'].search([('protocol', '!=', 'none')], limit=1)
        self.respond('GET', '/signals/%s' % signal.code, 200,
                     {'value': 12.5, 'status': 'warn', 'ts': '2026-10-13T20:05:11+03:00'})
        signal.action_read_now()
        self.assertEqual(signal.last_value, 12.5)
        self.assertEqual(signal.last_status, 'warn')
