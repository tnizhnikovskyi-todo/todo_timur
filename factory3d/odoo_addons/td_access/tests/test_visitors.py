from datetime import datetime, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from ..tools import params as P
from .common import AccessCase, FakeBioStar, freeze_time


class VisitorCase(AccessCase):

    def _visitor(self, uid='V-T1', **kw):
        vals = {'name': 'Гість', 'host_employee_id': self.emp_a.id, 'server_id': self.server.id,
                'date_from': datetime(2026, 10, 12, 3, 0), 'date_to': datetime(2026, 10, 12, 13, 0)}
        if uid:
            vals['biostar_user_id'] = uid
        vals.update(kw)
        return self.env['td.access.visitor'].create(vals)

    def _pool(self, number='555'):
        return self.env['td.access.card'].create({
            'number': number, 'server_id': self.server.id, 'holder_type': 'pool'})

    def _pass(self, base, at, user='V-T1', where='in', tna=''):
        return self.feed(self.prow(base, at, 4102, user, where=where, tna=tna))

    def _fake(self, enabled):
        P.set_param(self.env, 'write_enabled', 'True' if enabled else 'False')
        fake = FakeBioStar()
        fake.write_enabled = enabled
        return fake


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestVisitors(VisitorCase):

    def test_lifecycle(self):  # AC-44
        pool = self._pool()
        visitor = self._visitor(uid=False)
        visitor.action_expect()
        self.assertEqual(visitor.state, 'expected')
        self.assertEqual((pool.holder_type, pool.state, pool.visitor_id, visitor.card_id), ('visitor', 'active',
                                                                                          visitor, pool))
        visitor.biostar_user_id = 'V-T1'
        self.assertEqual((visitor.link_id.match, visitor.link_id.visitor_id), ('visitor', visitor))
        ev = self._pass(1, '2026-10-12T03:52:00.00Z', tna='1')
        self.assertEqual((ev.visitor_id, ev.attendance_action), (visitor, 'not_employee'))
        self.assertEqual((visitor.state, visitor.arrived_at, visitor.present, visitor.zone_id),
                         ('on_site', datetime(2026, 10, 12, 3, 52), True, self.z['Z-ASM']))
        self.assertEqual(ev.presence_changed, True)
        self._pass(2, '2026-10-12T12:40:00.00Z', tna='2')
        self.assertEqual((visitor.state, visitor.left_at, visitor.present, visitor.zone_id),
                         ('left', datetime(2026, 10, 12, 12, 40), False, self.env['td.zone']))
        visitor.action_close()
        self.assertEqual((visitor.state, pool.state, pool.holder_type), ('closed', 'returned', 'pool'))
        self.assertFalse(visitor.link_id.active)

    def test_reentry_after_left(self):
        visitor = self._visitor(state='left', present=False)
        self._pass(1, '2026-10-12T12:50:00.00Z', tna='1')
        self.assertEqual(visitor.state, 'on_site')
        late = self._visitor('V-T9', state='left', date_to=datetime(2026, 10, 12, 8, 0),
                             date_from=datetime(2026, 10, 12, 3, 0))
        ev = self._pass(2, '2026-10-12T12:50:00.00Z', user='V-T9', tna='1')
        self.assertEqual(late.state, 'left')
        self.assertIn('Вийшов', ev.error_message)

    def test_no_attendance_and_violation(self):  # AC-45
        visitor = self._visitor(state='expected')
        self._pass(1, '2026-10-12T03:52:00.00Z', tna='1')
        visitor.allowed_zone_ids = self.z['Z-OFFICE']
        count = self.env['hr.attendance'].search_count([])
        ev = self._pass(2, '2026-10-12T04:10:00.00Z', where='elec')
        self.assertEqual((ev.zone_violation, ev.attendance_action), (True, 'not_employee'))
        self.assertEqual(visitor.violation_count, 1)
        self.assertEqual((visitor.zone_id, visitor.zone_door_id), (self.z['Z-ELEC'], self.door_elec))
        self.assertEqual(self.env['hr.attendance'].search_count([]), count)
        visitor.allowed_zone_ids = False
        ev = self._pass(3, '2026-10-12T04:20:00.00Z', where='chg')
        self.assertFalse(ev.zone_violation)

    def test_closed_pass_logged(self):  # AC-45
        visitor = self._visitor(state='closed')
        ev = self._pass(1, '2026-10-12T03:52:00.00Z', tna='1')
        self.assertEqual(visitor.state, 'closed')
        self.assertEqual(ev.error_message, 'Відвідувач у стані «Закрито»: прохід лише зафіксовано')
        self.assertFalse(visitor.present)

    def test_biostar_user_create(self):  # AC-46
        fake = self._fake(True)
        visitor = self._visitor(uid=False)
        with self.patch_client(fake):
            visitor.action_expect()
        uid = 'V-%d' % visitor.id
        self.assertEqual(visitor.biostar_user_id, uid)
        self.assertIn(('create_user', uid, 'Гість', visitor.date_from, visitor.date_to + timedelta(hours=1), '1'),
                      fake.calls)
        self.assertEqual((visitor.link_id.biostar_user_id, visitor.link_id.match, visitor.sync_state),
                         (uid, 'visitor', 'synced'))

    def test_biostar_user_405(self):  # AC-46
        fake = self._fake(True)
        fake.write_status = 405
        visitor = self._visitor(uid=False)
        with self.patch_client(fake):
            visitor.action_expect()
        self.assertEqual(visitor.sync_state, 'error')
        self.assertIn('405', visitor.sync_error)

    def test_biostar_user_exists_is_ok(self):
        from ..tools.biostar_client import BioStarError
        fake = self._fake(True)
        fake.fail_always = BioStarError(200, '1', 'User already exist')
        visitor = self._visitor(uid=False)
        with self.patch_client(fake):
            visitor.action_expect()
        self.assertEqual(visitor.sync_state, 'synced')

    def test_biostar_user_write_disabled(self):  # AC-46
        fake = self._fake(False)
        visitor = self._visitor(uid=False)
        with self.patch_client(fake):
            visitor.action_expect()
        self.assertEqual((visitor.sync_state, visitor.biostar_user_id), ('local', False))
        self.assertEqual(fake.calls, [])

    def test_cron_user_sync(self):
        fake = self._fake(True)
        fake.write_status = 405
        visitor = self._visitor(uid=False, state='expected', sync_state='error')
        fake.write_status = None
        with self.patch_client(fake):
            self.env['td.access.visitor']._cron_user_sync()
        self.assertEqual(visitor.sync_state, 'synced')
        fake2 = self._fake(False)
        other = self._visitor(uid=False, state='expected', sync_state='error')
        with self.patch_client(fake2):
            self.env['td.access.visitor']._cron_user_sync()
        self.assertEqual((other.sync_state, fake2.calls), ('error', []))

    def test_manual_user_conflict(self):  # AC-46
        visitor = self._visitor(uid=False)
        with self.assertRaisesRegex(ValidationError, 'належить працівнику'):
            visitor.biostar_user_id = 'TSTA1'
        with self.assertRaisesRegex(ValidationError, 'належить працівнику'):
            self._visitor('TSTB2')
        with self.assertRaisesRegex(ValidationError, '1–64'):
            visitor.biostar_user_id = 'bad id'

    def test_register_from_yard(self):  # AC-47
        self._pool('600')
        self._pool('555')
        vals = {'name': 'Водій', 'host_employee_id': self.emp_a.id, 'origin': 'yard', 'origin_ref': 'YV/2026/0012'}
        visitor = self.env['td.access.visitor'].with_user(self.user_security).f3d_visitor_register(vals)
        self.assertEqual((visitor.state, visitor.card_id.number, visitor.origin), ('expected', '555', 'yard'))
        self.assertEqual(visitor.card_id.state, 'active')

    def test_register_no_card(self):  # AC-47
        visitor = self.env['td.access.visitor'].f3d_visitor_register(
            {'name': 'Водій', 'host_employee_id': self.emp_a.id})
        self.assertEqual(visitor.state, 'expected')
        self.assertFalse(visitor.card_id)
        self.assertIn('Вільних карток у пулі немає', visitor.message_ids[:1].body)

    def test_dates_and_unlink(self):  # AC-48
        base = datetime(2026, 10, 12, 3, 0)
        with self.assertRaisesRegex(ValidationError, 'пізніше'):
            self._visitor(date_to=base)
        with self.assertRaisesRegex(ValidationError, '7 діб'):
            self._visitor(date_to=base + timedelta(days=8))
        visitor = self.env['td.access.visitor'].create({
            'name': 'Без кінця', 'host_employee_id': self.emp_a.id, 'date_from': base})
        self.assertEqual(visitor.date_to, base + timedelta(hours=8))
        expected = self._visitor(state='expected')
        with self.assertRaisesRegex(UserError, 'Видалити можна лише'):
            expected.unlink()
        draft = self._visitor('V-D1')
        draft.unlink()
        self.assertFalse(draft.exists())

    def test_cancel_returns_card(self):
        pool = self._pool()
        visitor = self._visitor(uid=False)
        visitor.action_expect()
        visitor.action_cancel()
        self.assertEqual((visitor.state, pool.state, pool.holder_type), ('cancelled', 'returned', 'pool'))
        visitor.unlink()

    def test_security_user_flow(self):
        self._pool()
        visitor = self._visitor(uid=False).with_user(self.user_security)
        visitor.action_expect()
        visitor.action_arrive()
        self.assertEqual(visitor.state, 'on_site')
        visitor.action_leave()
        visitor.action_close()
        self.assertEqual(visitor.state, 'closed')
        with self.assertRaises(AccessError):
            self._visitor('V-X1').with_user(self.user_hr).action_expect()
        with self.assertRaises(AccessError):
            self.env['td.access.visitor'].with_user(self.user_f3d).search([])


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestVisitorPresence(VisitorCase):

    def _enter_cut(self):
        self.feed(self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'),
                  self.prow(2, '2026-10-12T03:53:00.00Z', 4102, 'TSTB2', tna='1'))
        self.emp_b._td_access_set({'td_access_zone_id': self.z['Z-CUT'].id})
        self.emp_c.sudo().td_home_zone_id = self.z['Z-CUT']
        return self._visitor(state='on_site', present=True, zone_id=self.z['Z-CUT'].id,
                             arrived_at=datetime(2026, 10, 12, 3, 55))

    def test_people_now(self):  # AC-29
        visitor = self._enter_cut()
        zone = self.z['Z-CUT']
        self.assertEqual(zone.td_people_now, 3)
        self.assertEqual(zone.td_people_employee_ids, self.emp_a | self.emp_b)
        self.assertEqual(zone.td_people_visitor_ids, visitor)
        action = zone.action_view_people()
        self.assertEqual((action['res_model'], action['domain']), ('td.access.presence', [('zone_id', '=', zone.id)]))

    def test_presence_view_rows(self):  # AC-30
        visitor = self._enter_cut()
        Presence = self.env['td.access.presence']
        rows = Presence.with_user(self.user_security).search_read([('zone_id', '=', self.z['Z-CUT'].id)])
        self.assertEqual(len(rows), 3)
        self.assertEqual(sorted(r['id'] % 2 for r in rows), [0, 0, 1])
        row = next(r for r in rows if r['id'] % 2)
        self.assertEqual((row['code'], row['visitor_id'][0], row['person_type']),
                         ('V-%d' % visitor.id, visitor.id, 'visitor'))
        self.assertNotIn(self.emp_c.id, [r['employee_id'][0] for r in rows if r['employee_id']])
        with self.assertRaises(AccessError):
            Presence.with_user(self.user_f3d).search_read([])
        self.assertEqual(Presence.browse(row['id']).with_user(self.user_security).action_open_person()['res_model'],
                         'td.access.visitor')

    def test_on_site_at(self):  # AC-35 (відвідувачі)
        visitor = self._visitor()
        self._pass(1, '2026-10-12T03:40:00.00Z', tna='1')
        self._pass(2, '2026-10-12T04:30:00.00Z', tna='2')
        Event = self.env['td.access.event']
        self.assertEqual(Event.f3d_on_site_at(datetime(2026, 10, 12, 4, 0))['visitors'], visitor)
        self.assertFalse(Event.f3d_on_site_at(datetime(2026, 10, 12, 4, 40))['visitors'])
        manual = self._visitor('V-M1', state='on_site', present=True, arrived_at=datetime(2026, 10, 12, 3, 0))
        self.assertIn(manual, Event.f3d_on_site_at(datetime(2026, 10, 12, 4, 40))['visitors'])

    def test_dwell(self):  # R-17 для відвідувача
        visitor = self._visitor(state='expected')
        self._pass(1, '2026-10-12T03:52:00.00Z', tna='1')
        self._pass(2, '2026-10-12T06:51:00.00Z', where='elec')
        self.assertEqual((visitor.zone_id, visitor.zone_door_id), (self.z['Z-ELEC'], self.door_elec))
        with freeze_time('2026-10-12 07:20:00'):
            self.env['td.access.event']._cron_zone_dwell()
        self.assertEqual(visitor.zone_id, self.z['Z-ELEC'])
        with freeze_time('2026-10-12 07:25:00'):
            self.env['td.access.event']._cron_zone_dwell()
        self.assertEqual(visitor.zone_id, self.door_elec.zone_from_id)
        self.assertFalse(visitor.zone_door_id)

    def test_housekeeping(self):  # AC-38
        now = datetime(2026, 10, 12, 10, 0)
        P.set_param(self.env, 'keep_days', '90')
        self.feed(self.prow(1, '2026-07-13T03:52:00.00Z', 4102, 'TSTB2', tna='1'),
                  self.prow(2, '2026-07-15T03:52:00.00Z', 4102, 'TSTB2', tna='2'), at='2026-10-12 10:00:00')
        expiring = self._visitor('V-E1', state='expected', date_from=now - timedelta(hours=6),
                                 date_to=now - timedelta(hours=2))
        card = self.env['td.access.card'].create({
            'number': '901', 'server_id': self.server.id, 'holder_type': 'visitor', 'visitor_id': expiring.id,
            'state': 'active'})
        expiring.card_id = card
        recent = self._visitor('V-R1', state='closed', date_from=now - timedelta(days=2),
                               date_to=now - timedelta(days=1))
        old_card = self.env['td.access.card'].create({
            'number': '902', 'server_id': self.server.id, 'holder_type': 'pool', 'visitor_id': recent.id,
            'state': 'returned', 'returned_at': now - timedelta(days=91)})
        old = self._visitor('V-O1', state='closed', date_from=now - timedelta(days=92, hours=1),
                            date_to=now - timedelta(days=91))
        fake = FakeBioStar()
        with self.patch_client(fake), freeze_time(now):
            self.env['td.access.event']._cron_housekeeping()
        ids = self.env['td.access.event'].search([]).mapped('biostar_id')
        self.assertNotIn('1', ids)
        self.assertIn('2', ids)
        self.assertEqual((expiring.state, expiring.overdue, expiring.present), ('closed', True, False))
        self.assertEqual((card.state, card.holder_type), ('returned', 'pool'))
        self.assertEqual(fake.search_calls[-1]['since'], now - timedelta(hours=24))
        self.assertFalse(old_card.visitor_id)
        self.assertEqual(old_card.state, 'returned')
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestVisitorToday(VisitorCase):

    def test_today_filter_kyiv_day(self):
        """Фільтр «Сьогодні» — `is_today` за київською добою сервера (без datetime.time.min/max у домені)."""
        # 12.10.2026 23:30 за Києвом (UTC+3): доба = [11.10 21:00, 12.10 21:00) UTC
        inside = self._visitor('V-D1', date_from=datetime(2026, 10, 12, 8, 0), date_to=datetime(2026, 10, 12, 12, 0))
        spanning = self._visitor('V-D2', date_from=datetime(2026, 10, 11, 12, 0), date_to=datetime(2026, 10, 12, 1, 0))
        yesterday = self._visitor('V-D3', date_from=datetime(2026, 10, 11, 6, 0), date_to=datetime(2026, 10, 11, 20, 59))
        tomorrow = self._visitor('V-D4', date_from=datetime(2026, 10, 12, 21, 0), date_to=datetime(2026, 10, 13, 5, 0))
        visitors = inside | spanning | yesterday | tomorrow
        domain = [('id', 'in', visitors.ids)]
        with freeze_time(datetime(2026, 10, 12, 20, 30)):
            today = self.env['td.access.visitor'].search(domain + [('is_today', '=', True)])
            other = self.env['td.access.visitor'].search(domain + [('is_today', '!=', True)])
            self.assertEqual(visitors.mapped('is_today'), [True, True, False, False])
        self.assertEqual(today, inside | spanning)
        self.assertEqual(other, yesterday | tomorrow)
        with freeze_time(datetime(2026, 10, 12, 21, 30)):  # вже 13.10 за Києвом
            self.assertEqual(self.env['td.access.visitor'].search(domain + [('is_today', '=', True)]),
                             tomorrow)
        arch = self.env.ref('td_access.view_td_access_visitor_search').arch
        self.assertIn("is_today", arch)
        self.assertNotIn("time.max", arch)
        self.assertNotIn("time.min", arch)
