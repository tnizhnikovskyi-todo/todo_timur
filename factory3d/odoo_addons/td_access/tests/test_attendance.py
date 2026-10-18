from datetime import date, datetime

from odoo.tests import tagged

from ..tools import params as P
from ..tools.dates import fmt_bs_dt, local_date, parse_bs_dt, schedule_end_utc, to_local_str
from .common import AccessCase, FakeBioStar, freeze_time


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestAttendance(AccessCase):

    def _open_manual(self, emp, check_in):
        return self.env['hr.attendance'].sudo().create({'employee_id': emp.id, 'check_in': check_in})

    def test_check_in(self):
        fake = FakeBioStar(events=[self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1')])
        self.poll('2026-10-12 03:53:00', fake)
        att = self.attendances(self.emp_a)
        ev = self.env['td.access.event'].search([('biostar_id', '=', '1')])
        self.assertEqual(len(att), 1)
        self.assertEqual((att.check_in, att.check_out, att.in_mode), (datetime(2026, 10, 12, 3, 52), False, 'biostar'))
        self.assertEqual((att.td_in_event_id, att.td_in_device_id), (ev, self.device_acr_in))
        self.assertEqual(att.date, date(2026, 10, 12))
        self.assertEqual((ev.attendance_action, ev.process_state, ev.direction, ev.door_id, ev.is_perimeter),
                         ('checked_in', 'done', 'in', self.door_turn_1, True))
        self.assertEqual(ev.attendance_id, att)

    def test_attach_demo(self):
        manual = self._open_manual(self.emp_a, '2026-10-12 03:52:00')
        ev = self.feed(self.prow(1, '2026-10-12T03:52:10.00Z', 4102, 'TSTA1', tna='1'))
        self.assertEqual(self.attendances(self.emp_a), manual)
        self.assertEqual((ev.attendance_action, manual.in_mode, manual.check_in),
                         ('attached', 'manual', datetime(2026, 10, 12, 3, 52)))
        self.assertEqual(manual.td_in_event_id, ev)

    def test_duplicate_apb(self):
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'))
        dup = self.feed(self.prow(2, '2026-10-12T03:55:00.00Z', 4102, 'TSTA1', tna='1'))
        att = self.attendances(self.emp_a)
        self.assertEqual(len(att), 1)
        self.assertEqual((dup.attendance_action, dup.apb_suspect, dup.attendance_id), ('duplicate', True, att))
        # ручна відмітка, людина вже на території, вхід за межами dup_window_min -> duplicate
        manual = self._open_manual(self.emp_b, '2026-10-12 03:52:00')
        self.emp_b._f3d_access_set({'td_access_present': True, 'td_access_last_in': '2026-10-12 03:52:00'})
        ev = self.feed(self.prow(3, '2026-10-12T04:20:00.00Z', 4102, 'TSTB2', tna='1'))
        self.assertEqual((ev.attendance_action, ev.apb_suspect), ('duplicate', True))
        self.assertEqual(self.attendances(self.emp_b), manual)

    def test_check_out(self):
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'))
        out = self.feed(self.prow(2, '2026-10-12T12:42:05.00Z', 4102, 'TSTA1', tna='2'))
        att = self.attendances(self.emp_a)
        self.assertEqual((att.check_out, att.out_mode), (datetime(2026, 10, 12, 12, 42, 5), 'biostar'))
        self.assertEqual((att.td_out_event_id, att.td_out_device_id), (out, self.device_acr_in))
        self.assertEqual((out.attendance_action, out.direction), ('checked_out', 'out'))

    def _day(self, emp, user, base):
        rows = [self.prow(base + 1, '2026-10-12T03:52:00.00Z', 4102, user, tna='1'),
                self.prow(base + 2, '2026-10-12T08:31:00.00Z', 4102, user, tna='2'),
                self.prow(base + 3, '2026-10-12T08:58:00.00Z', 4102, user, tna='1'),
                self.prow(base + 4, '2026-10-12T12:42:00.00Z', 4102, user, tna='2')]
        return self.feed(*rows)

    def test_lunch_merge_off_on(self):
        self._day(self.emp_a, 'TSTA1', 0)
        att = self.attendances(self.emp_a)
        self.assertEqual([(a.check_in, a.check_out) for a in att],
                         [(datetime(2026, 10, 12, 3, 52), datetime(2026, 10, 12, 8, 31)),
                          (datetime(2026, 10, 12, 8, 58), datetime(2026, 10, 12, 12, 42))])
        P.set_param(self.env, 'merge_gap_min', '45')
        evs = self._day(self.emp_b, 'TSTB2', 10)
        att = self.attendances(self.emp_b)
        self.assertEqual(len(att), 1)
        self.assertEqual((att.check_in, att.check_out, att.out_mode),
                         (datetime(2026, 10, 12, 3, 52), datetime(2026, 10, 12, 12, 42), 'biostar'))
        self.assertEqual(evs.filtered(lambda e: e.biostar_id == '13').attendance_action, 'merged')

    def test_stale_close_table(self):
        Link = self.env['td.access.user.link'].sudo()
        for emp, user in ((self.emp_c, 'TSTC'), (self.emp_d, 'TSTD')):
            Link.create({'server_id': self.server.id, 'biostar_user_id': user, 'employee_id': emp.id})
        cases = ((self.emp_a, '2026-10-12 03:52:00', '2026-10-12 12:30:00'),
                 (self.emp_b, '2026-10-26 05:01:00', '2026-10-26 13:30:00'),
                 (self.emp_c, '2026-10-12 13:10:00', '2026-10-12 14:10:00'),
                 (self.emp_d, '2026-10-17 06:00:00', '2026-10-17 07:00:00'))
        atts = []
        for emp, check_in, _out in cases:
            atts.append(self._open_manual(emp, check_in))
            emp._f3d_access_set({'td_access_present': True, 'td_access_last_in': check_in})
        with self.patch_client(FakeBioStar()), freeze_time('2026-10-28 02:00:00'):
            self.env['td.access.event']._cron_housekeeping()
        for (emp, _in, out), att in zip(cases, atts, strict=True):
            with self.subTest(emp=emp.name):
                self.assertEqual(att.check_out, datetime.fromisoformat(out))
                self.assertEqual((att.out_mode, att.td_closed_by_rule), ('technical', True))
                self.assertTrue(any('Закрито правилом СКУД' in (m.body or '') for m in att.message_ids))
                self.assertFalse(emp.td_access_present)

    def test_stale_close_disabled(self):
        self.env['td.access.user.link'].sudo().create({
            'server_id': self.server.id, 'biostar_user_id': 'TSTC', 'employee_id': self.emp_c.id})
        att = self._open_manual(self.emp_c, '2026-10-12 03:52:00')
        P.set_param(self.env, 'stale_close_enabled', 'False')
        with self.patch_client(FakeBioStar()), freeze_time('2026-10-28 02:00:00'):
            self.env['td.access.event']._cron_housekeeping()
        self.assertFalse(att.check_out)

    def test_out_without_open(self):
        ev = self.feed(self.prow(1, '2026-10-12T12:42:00.00Z', 4102, 'TSTA1', tna='2'))
        self.assertEqual((ev.attendance_action, ev.apb_suspect), ('no_open', True))
        self.assertFalse(self.attendances(self.emp_a))
        self.assertFalse(self.emp_a.td_access_present)

    def test_out_before_in(self):
        att = self._open_manual(self.emp_a, '2026-10-12 10:00:00')
        ev = self.feed(self.prow(1, '2026-10-12T09:00:00.00Z', 4102, 'TSTA1', tna='2'))
        self.assertEqual(ev.attendance_action, 'no_open')
        self.assertEqual(ev.error_message, 'Вихід раніше за вхід відмітки')
        self.assertFalse(att.check_out)

    def test_internal_door_no_attendance(self):
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'))
        ev = self.feed(self.prow(2, '2026-10-12T06:51:00.00Z', 4102, 'TSTA1', where='elec'))
        att = self.attendances(self.emp_a)
        self.assertEqual((len(att), bool(att.check_out), ev.attendance_action), (1, False, 'none'))
        self.assertEqual(self.emp_a.td_access_zone_id, self.z['Z-ELEC'])

    def test_night_and_long(self):
        self.feed(self.prow(1, '2026-10-12T19:00:00.00Z', 4102, 'TSTA1', tna='1'))
        out = self.feed(self.prow(2, '2026-10-13T03:00:00.00Z', 4102, 'TSTA1', tna='2'), at='2026-10-13 04:00:00')
        att = self.attendances(self.emp_a)
        self.assertEqual((out.attendance_action, att.worked_hours), ('checked_out', 8.0))
        self.feed(self.prow(3, '2026-10-12T03:52:00.00Z', 4102, 'TSTB2', tna='1'))
        late = self.feed(self.prow(4, '2026-10-13T12:40:00.00Z', 4102, 'TSTB2', tna='2'), at='2026-10-13 13:00:00')
        att = self.attendances(self.emp_b)
        self.assertEqual((att.check_out, att.td_closed_by_rule), (datetime(2026, 10, 12, 12, 30), True))
        self.assertEqual(late.attendance_action, 'no_open')

    def test_dates_helpers(self):
        for text in ('2026-10-12T03:52:10.00Z', '2026-10-12T03:52:10.000Z', '2026-10-12T03:52:10Z',
                     '2026-10-12T03:52:10+00:00'):
            self.assertEqual(parse_bs_dt(text), datetime(2026, 10, 12, 3, 52, 10))
        with self.assertRaises(ValueError):
            parse_bs_dt('x')
        self.assertEqual(str(local_date(datetime(2026, 10, 12, 21, 30))), '2026-10-13')
        self.assertEqual(to_local_str(datetime(2026, 10, 25, 1, 30)), '2026-10-25 03:30:00')
        self.assertEqual(schedule_end_utc(date(2026, 10, 12), 15.5, 'Europe/Kyiv'), datetime(2026, 10, 12, 12, 30))
        self.assertEqual(schedule_end_utc(date(2026, 10, 26), 15.5, 'Europe/Kyiv'), datetime(2026, 10, 26, 13, 30))
        self.assertEqual(fmt_bs_dt(datetime(2026, 10, 12, 3, 52, 10)), '2026-10-12T03:52:10.000Z')
