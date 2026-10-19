from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged

from ..models.td_access_event import F3dAccessEvent
from .common import AccessCase, FakeBioStar, freeze_time


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestPresence(AccessCase):

    def _enter(self, base, user='TSTA1', at='2026-10-12T03:52:00.00Z'):
        return self.feed(self.prow(base, at, 4102, user, tna='1'))

    def test_home_zone_and_fallback(self):
        ev_a = self._enter(1)
        ev_b = self._enter(2, 'TSTB2')
        ts = datetime(2026, 10, 12, 3, 52)
        a, b = self.emp_a, self.emp_b
        self.assertEqual((a.td_access_present, a.td_access_zone_id, a.td_access_zone_since, a.td_access_last_in),
                         (True, self.z['Z-CUT'], ts, ts))
        self.assertEqual(b.td_access_zone_id, self.z['Z-ASM'])
        self.assertTrue(ev_a.presence_changed and ev_b.presence_changed)

    def test_exit_clears(self):
        self._enter(1)
        self.feed(self.prow(2, '2026-10-12T12:42:00.00Z', 4102, 'TSTA1', tna='2'))
        a = self.emp_a
        self.assertEqual((a.td_access_present, a.td_access_zone_id, a.td_access_last_out),
                         (False, self.env['td.zone'], datetime(2026, 10, 12, 12, 42)))

    def test_internal_zone_and_dwell(self):
        self._enter(1)
        self.feed(self.prow(2, '2026-10-12T06:51:00.00Z', 4102, 'TSTA1', where='elec'))
        a = self.emp_a
        self.assertEqual((a.td_access_zone_id, a.td_access_zone_door_id), (self.z['Z-ELEC'], self.door_elec))
        Event = self.env['td.access.event']
        with freeze_time('2026-10-12 07:20:00'):
            Event._cron_zone_dwell()
        self.assertEqual(a.td_access_zone_id, self.z['Z-ELEC'])
        with freeze_time('2026-10-12 07:21:01'):
            Event._cron_zone_dwell()
        self.assertEqual((a.td_access_zone_id, a.td_access_zone_door_id),
                         (self.z['Z-CUT'], self.env['td.access.door']))

    def test_dwell_zero(self):
        self.door_elec.sudo().write({'dwell_min': 0})
        self._enter(1)
        self.feed(self.prow(2, '2026-10-12T06:51:00.00Z', 4102, 'TSTA1', where='elec'))
        with freeze_time('2026-10-12 09:00:00'):
            self.env['td.access.event']._cron_zone_dwell()
        self.assertEqual(self.emp_a.td_access_zone_id, self.z['Z-ELEC'])

    def test_internal_without_entry(self):
        ev = self.feed(self.prow(1, '2026-10-12T07:20:00.00Z', 4102, 'TSTB2', where='paint'))
        b = self.emp_b
        self.assertEqual((b.td_access_present, b.td_access_zone_id, ev.apb_suspect),
                         (True, self.z['Z-FAC'], True))

    def test_people_now(self):
        self._enter(1)
        self._enter(2, 'TSTB2')
        self.emp_c.sudo().td_home_zone_id = self.z['Z-CUT']
        self.emp_b._td_access_set({'td_access_zone_id': self.z['Z-CUT'].id})
        zone = self.z['Z-CUT']
        self.assertEqual(zone.td_people_now, 2)
        self.assertEqual(zone.td_people_employee_ids, self.emp_a | self.emp_b)
        action = zone.action_view_people()
        self.assertEqual((action['res_model'], action['domain']), ('td.access.presence', [('zone_id', '=', zone.id)]))

    def test_presence_view_rows(self):
        self._enter(1)
        self._enter(2, 'TSTB2')
        self.emp_b._td_access_set({'td_access_zone_id': self.z['Z-CUT'].id})
        Presence = self.env['td.access.presence']
        ids = (self.emp_a | self.emp_b | self.emp_c).ids
        rows = Presence.with_user(self.user_security).search_read([('employee_id', 'in', ids)])
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r['id'] % 2 == 0 for r in rows))
        self.assertNotIn(self.emp_c.id, [r['employee_id'][0] for r in rows])
        with self.assertRaises(AccessError):
            Presence.with_user(self.user_f3d).search_read([])

    def test_on_site_at(self):
        self.feed(self.prow(1, '2026-10-12T03:40:00.00Z', 4102, 'TSTA1', tna='1'),
                  self.prow(2, '2026-10-12T03:45:00.00Z', 4102, 'TSTB2', tna='1'),
                  self.prow(3, '2026-10-12T03:50:00.00Z', 4102, 'OPTSTC', tna='1'),
                  self.prow(4, '2026-10-12T04:30:00.00Z', 4102, 'OPTSTC', tna='2'),
                  self.prow(5, '2026-10-09T03:40:00.00Z', 4102, 'OPTSTD', tna='1'))
        Event = self.env['td.access.event']
        for ts, expect in (('2026-10-12 03:45:00', self.emp_a | self.emp_b),
                           ('2026-10-12 04:00:00', self.emp_a | self.emp_b | self.emp_c),
                           ('2026-10-12 04:40:00', self.emp_a | self.emp_b)):
            res = Event.f3d_on_site_at(datetime.fromisoformat(ts))
            self.assertEqual(res['employees'], expect, ts)
            self.assertEqual(set(res), {'employees', 'visitors', 'ts'})

    def test_passes_between(self):
        self.feed(self.prow(1, '2026-10-12T03:50:00.00Z', 4102, 'TSTA1', tna='1'),
                  self.prow(2, '2026-10-12T04:00:00.00Z', 4102, 'TSTB2', tna='1'),
                  self.prow(3, '2026-10-12T05:00:00.00Z', 4102, 'TSTB2', tna='2'),
                  self.prow(4, '2026-10-12T05:30:00.00Z', 4102, 'TSTA1', tna='2'),
                  self.prow(5, '2026-10-12T04:30:00.00Z', 4102, 'TSTB2', where='elec'))
        Event = self.env['td.access.event']
        t0, t1 = datetime(2026, 10, 12, 3, 0), datetime(2026, 10, 12, 6, 0)
        outs = Event.f3d_passes_between(t0, t1, ['TURN-1'], 'out')
        self.assertEqual(outs.mapped('biostar_id'), ['3', '4'])
        self.assertEqual(Event.f3d_passes_between(t0, t1).mapped('biostar_id'), ['1', '2', '5', '3', '4'])

    def test_drill(self):
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'))
        with patch.object(F3dAccessEvent, '_td_drill_active', return_value=True):
            out = self.feed(self.prow(2, '2026-10-12T09:00:00.00Z', 4102, 'TSTA1', tna='2'))
            self.assertEqual(out.attendance_action, 'drill')
            att = self.attendances(self.emp_a)
            self.assertFalse(att.check_out)
            self.assertFalse(self.emp_a.td_access_present)
            back = self.feed(self.prow(3, '2026-10-12T09:20:00.00Z', 4102, 'TSTA1', tna='1'))
            self.assertEqual(back.attendance_action, 'drill')
            self.assertEqual(len(self.attendances(self.emp_a)), 1)
            self.assertTrue(self.emp_a.td_access_present)

    def test_fire_source_dicts(self):
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'))
        source = self.env['td.fire.passage.source.access']
        at = datetime(2026, 10, 12, 7, 0)
        self.assertEqual(source._td_on_site(at), [{'employee_id': self.emp_a.id,
                                                    'since': datetime(2026, 10, 12, 3, 52), 'point': 'TURN-1'}])
        rows = source._td_passages(datetime(2026, 10, 12, 3, 0), at)
        self.assertEqual(rows, [{'employee_id': self.emp_a.id, 'ts': datetime(2026, 10, 12, 3, 52),
                                 'point': 'TURN-1', 'direction': 'in'}])
        self.assertFalse(source._td_drill_active(at))

    def test_housekeeping(self):
        now = datetime(2026, 10, 12, 10, 0)
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'),
                  self.prow(2, '2026-07-13T03:52:00.00Z', 4102, 'TSTB2', tna='1'),  # now - 91 доба
                  self.prow(3, '2026-07-15T03:52:00.00Z', 4102, 'TSTB2', tna='2'),  # now - 89 діб
                  at='2026-10-12 10:00:00')
        fake = FakeBioStar()
        with self.patch_client(fake), freeze_time(now):
            self.env['td.access.event']._cron_housekeeping()
        ids = self.env['td.access.event'].search([]).mapped('biostar_id')
        self.assertNotIn('2', ids)
        self.assertIn('3', ids)
        self.assertEqual(fake.search_calls[-1]['since'], now - timedelta(hours=24))
