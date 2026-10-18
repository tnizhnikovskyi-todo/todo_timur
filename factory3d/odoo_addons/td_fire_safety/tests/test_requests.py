"""AC-32 (M-14, R-22): заявки ТО за сигналами пожежної безпеки."""
from odoo.tests import tagged

from .common import FireCase


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestRequests(FireCase):

    CODE = 'fire/groups/FA-CUT/state'

    def requests(self):
        sig = self.env['td.signal'].search([('code', '=', self.CODE)])
        return self.env['maintenance.request'].search([('td_signal_id', '=', sig.id)])

    def test_zone_fault_request_linked(self):
        self.push_text(self.CODE, 'fault', self.at(0))
        request = self.requests()
        self.assertEqual(len(request), 1)
        self.assertEqual(request.td_fire_zone_id, self.z_cut)
        event = self.ev('fault', object_code='FA-CUT')
        self.assertEqual(request.td_fire_event_id, event)
        self.assertEqual(event.request_id, request)
        self.assertEqual(request.maintenance_team_id, self.team)
        self.assertIn('Пожежна безпека: зона FA-CUT (Розкрій).', request.description)
        self.assertEqual(request.action_f3d_fire_open_zone()['res_id'], self.z_cut.id)

    def test_no_duplicate(self):
        self.push_text(self.CODE, 'fault', self.at(0))
        self.push_text(self.CODE, 'tamper', self.at(30))
        self.push_text(self.CODE, 'fault', self.at(60))
        self.assertEqual(len(self.requests()), 1)

    def test_team_param_overrides(self):
        other = self.env['maintenance.team'].create({'name': 'Інша команда'})
        self.equipment['FA-CUT'].maintenance_team_id = other
        self.push_text(self.CODE, 'fault', self.at(0))
        self.assertEqual(self.requests().maintenance_team_id, self.team)
