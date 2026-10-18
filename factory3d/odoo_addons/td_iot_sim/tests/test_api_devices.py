from odoo import fields
from odoo.tests import HttpCase, tagged

TOKEN = 'export-token-for-tests'
AUTH = {'Authorization': 'Bearer ' + TOKEN}


@tagged('post_install', '-at_install', 'f3d', 'f3d_iot_sim')
class TestApiDevices(HttpCase):

    def _set_token(self, value):
        self.env['ir.config_parameter'].sudo().set_param('td.iot_sim.export_token', value)

    def test_devices_401_503_200_304(self):
        self._set_token('')
        self.assertEqual(self.url_open('/f3d/sim/devices').status_code, 503)
        self._set_token(TOKEN)
        self.assertEqual(self.url_open('/f3d/sim/devices').status_code, 401)
        self.assertEqual(self.url_open('/f3d/sim/devices', headers={'Authorization': 'Bearer bad'}).status_code, 401)
        resp = self.url_open('/f3d/sim/devices', headers=AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/json', resp.headers['Content-Type'])
        data = resp.json()
        self.assertEqual(data['version'], 1)
        for key in ('devices', 'zones', 'docks', 'shifts', 'employees', 'bookings'):
            self.assertIn(key, data)
        etag = resp.headers['ETag']
        again = self.url_open('/f3d/sim/devices', headers=dict(AUTH, **{'If-None-Match': etag}))
        self.assertEqual(again.status_code, 304)

    def test_devices_content(self):
        self._set_token(TOKEN)
        device = self.env['td.sim.device'].create({
            'code': 'API-T1', 'name': 'API тест', 'protocol': 'P-01', 'driver': 'opcua_ww'})
        self.env['td.sim.signal'].create({
            'code': 'workcenters/API-T1/state', 'device_id': device.id, 'protocol': 'P-01',
            'address': 'ns=2;s=API-T1.State', 'dtype': 'enum', 'origin': 'new', 'kind': 'state'})
        data = self.url_open('/f3d/sim/devices?protocol=P-01', headers=AUTH).json()
        found = [d for d in data['devices'] if d['code'] == 'API-T1']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['signals'][0]['code'], 'workcenters/API-T1/state')
        self.assertTrue(all(d['protocol'] == 'P-01' for d in data['devices']))

    def test_events_post_dedup(self):
        self._set_token(TOKEN)
        scenario = self.env.ref('td_iot_sim.scenario_spark')
        run = self.env['td.sim.run'].create({'scenario_id': scenario.id, 'state': 'running'})
        body = {'events': [
            {'ts': '2026-10-13T20:05:11+03:00', 'kind': 'info', 'device': 'RV-05', 'message': 'Фільтр 285 Па',
             'payload': {'event_id': 'uuid-1'}},
            {'ts': '2026-10-13T20:06:11+03:00', 'kind': 'scenario', 'run_ref': run.name, 'message': 'done',
             'payload': {'event_id': 'uuid-2', 'state': 'done'}},
        ]}
        resp = self.url_open('/f3d/sim/events', json=body, headers=AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'accepted': 2, 'rejected': []})
        run.invalidate_recordset()
        self.assertEqual(run.state, 'done')
        self.assertEqual(self.env['td.sim.event'].search_count([('run_id', '=', run.id)]), 1)
        again = self.url_open('/f3d/sim/events', json=body, headers=AUTH).json()
        self.assertEqual(again['accepted'], 0)
        self.assertEqual({r['reason'] for r in again['rejected']}, {'duplicate'})
        bad = self.url_open('/f3d/sim/events', data='{not json', headers=dict(AUTH, **{'Content-Type': 'application/json'}))
        self.assertEqual(bad.status_code, 400)
        too_many = {'events': [{'ts': '2026-10-13T20:05:11Z', 'kind': 'info', 'message': 'x'}] * 101}
        self.assertEqual(self.url_open('/f3d/sim/events', json=too_many, headers=AUTH).status_code, 413)
        self.assertEqual(self.url_open('/f3d/sim/events', json=body).status_code, 401)

    def test_health(self):
        resp = self.url_open('/f3d/sim/health')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['module'], 'td_iot_sim')
        self.assertEqual(data['version'], '19.0.2.0.0')
        self.assertEqual(data['signals'], self.env['td.sim.signal'].search_count([]))
        self.assertEqual(data['devices'], self.env['td.sim.device'].search_count([]))

    def test_bookings_truck_plate(self):
        self._set_token(TOKEN)
        wh = self.env['stock.warehouse'].search([], limit=1)
        dock = self.env['stock.location'].create({
            'name': 'Док-API-Т', 'usage': 'internal', 'location_id': wh.view_location_id.id,
            'barcode': 'DOCK-API-T'})
        dock.write({'td_kind': 'dock', 'td_side': 'east', 'td_dock_no': 9, 'td_x': 10.0, 'td_y': 5.0,
                    'td_code': 'DOCK-E9'})
        batch = self.env['stock.picking.batch'].create({
            'picking_type_id': wh.out_type_id.id, 'dock_id': dock.id, 'td_code': 'TRUCK-OUT-1',
            'scheduled_date': fields.Datetime.now()})
        data = self.url_open('/f3d/sim/devices', headers=AUTH).json()
        booking = [b for b in data['bookings'] if b['batch'] == batch.name]
        self.assertEqual(len(booking), 1)
        self.assertEqual(booking[0]['truck'], 'TRUCK-OUT-1')
        self.assertEqual(booking[0]['dock'], 'DOCK-E9')
        self.assertEqual(booking[0]['plate'], None)
        self.assertEqual(booking[0]['type'], 'outgoing')
        self.assertIn('DOCK-E9', [d['code'] for d in data['docks']])
