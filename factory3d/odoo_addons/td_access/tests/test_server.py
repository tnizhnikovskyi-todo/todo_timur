from datetime import datetime, timedelta
from unittest import mock

from psycopg2 import IntegrityError
from psycopg2 import errors as pg_errors

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools import params as P
from ..tools.biostar_client import BioStarAuthError, BioStarError
from .common import AccessCase, FakeBioStar, freeze_time


class ServerCase(AccessCase):

    @classmethod
    def _set_env(cls, value):
        cls.env['ir.config_parameter'].sudo().set_param('factory3d.base.environment', value)

    def _new_server(self, **vals):
        return self.env['f3d.access.server'].create(dict({'name': 'Т', 'url': 'https://iot-sim:8443'}, **vals))


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestServerConstraints(ServerCase):

    def test_url_rules(self):
        self._set_env('test')
        for bad in ('ftp://x', 'https://iot-sim:8443/api?x=1', 'javascript:alert(1)'):
            with self.assertRaises(ValidationError, msg=bad):
                self._new_server(url=bad)
        self.assertEqual(self._new_server(url='https://iot-sim:8443/').url, 'https://iot-sim:8443')
        self.assertTrue(self._new_server(url='http://iot-sim:8081', verify_ssl=False))

    def test_verify_ssl_env(self):
        self._set_env('prod')
        with self.assertRaises(ValidationError) as cm:
            self._new_server(verify_ssl=False)
        self.assertIn('лише в тестовому середовищі', str(cm.exception))
        with self.assertRaises(ValidationError) as cm:
            self._new_server(url='http://iot-sim:8081')
        self.assertIn('HTTP без TLS', str(cm.exception))
        self.assertTrue(self._new_server())

    def test_timeouts(self):
        for field in ('timeout_connect_s', 'timeout_read_s'):
            for value in (0, 1000):
                with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
                    self._new_server(**{field: value})


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestConnection(ServerCase):

    def _fake(self):
        return FakeBioStar(users=self.fixture_rows('users', 'UserCollection'),
                           devices=self.fixture_rows('devices', 'DeviceCollection'))

    def test_ok_separate_session(self):
        self.env['ir.config_parameter'].sudo().set_param('factory3d.access.read_enabled', 'False')
        fake = self._fake()
        server = self.server
        with self.patch_client(fake):
            res = server.with_user(self.user_f3d_admin).action_test_connection()
        self.assertEqual([c[0] for c in fake.calls], ['login', 'list_users_total', 'list_devices', 'logout'])
        self.assertEqual(res['params']['type'], 'success')
        self.assertIn('користувачів 36, пристроїв 5', res['params']['message'])
        self.assertEqual((server.state, server.users_total, server.devices_total), ('online', 36, 5))
        self.assertFalse(server.sudo().session_id)

    def test_auth_fail_no_secret(self):
        fake = self._fake()
        fake.login_error = BioStarAuthError(401, '101', 'Failed to login for invalid username or password')
        server = self.server
        with self.patch_client(fake), self.assertLogs('odoo.addons.factory3d_access', 'DEBUG') as logs:
            res = server.with_user(self.user_f3d_admin).action_test_connection()
        self.assertEqual(res['params']['type'], 'danger')
        self.assertEqual((server.state, server.error_count), ('error', 1))
        self.assertIn('101', server.last_error)
        self.assertNotIn('test-pass', server.last_error)
        self.assertTrue(server.next_try_at)
        self.assertFalse([line for line in logs.output if 'test-pass' in line])

    def test_requires_f3d_admin(self):
        with self.patch_client(self._fake()), self.assertRaises(AccessError):
            self.server.with_user(self.user_admin).action_test_connection()

    def test_backoff_values(self):
        server = self.server
        seen = []
        for _i in range(6):
            server._mark_error(Exception('x'))
            seen.append(int((server.next_try_at - server.last_error_ts).total_seconds()))
        self.assertEqual(seen, [60, 120, 240, 480, 600, 600])
        server._mark_ok()
        self.assertEqual((server.state, server.error_count, bool(server.next_try_at)), ('online', 0, False))


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestCodeValidation(ServerCase):

    def _device(self, **vals):
        return self.env['f3d.access.device'].create(dict(
            {'name': 'Д', 'code': 'ACR-NEW', 'server_id': self.server.id}, **vals))

    def _door(self, **vals):
        return self.env['f3d.access.door'].create(dict(
            {'name': 'Дв', 'code': 'DOOR-NEW', 'server_id': self.server.id}, **vals))

    def test_device_codes(self):
        for code, bsid in (('acr-x', False), ('ACR-NEW', '53 9')):
            with self.assertRaises(ValidationError):
                self._device(code=code, biostar_id=bsid)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self._device(code='ACR-IN')
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self._device(biostar_id='5390001')
        self.assertTrue(self._device(biostar_id='5390099'))

    def test_door_rules(self):
        with self.assertRaises(ValidationError):
            self._door(zone_from_id=self.z['Z-KPP'].id)
        with self.assertRaises(ValidationError):
            self._door(is_perimeter=True)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self._door(dwell_min=2000)
        other = self.env['f3d.access.server'].create({'name': 'Інший', 'url': 'https://other:8443'})
        foreign = self.env['f3d.access.device'].create({'name': 'Ч', 'code': 'ACR-FOR', 'server_id': other.id})
        with self.assertRaises(ValidationError):
            self._door(entry_device_id=foreign.id)
        door = self._door(zone_from_id=self.z['Z-KPP'].id, zone_to_id=self.z['Z-ASM'].id, is_perimeter=True)
        self.assertTrue(door)

    def test_door_write_guard(self):
        door = self.door_turn_1
        door.with_user(self.user_security).write({'alarm': False})
        with self.assertRaises(AccessError):
            door.with_user(self.user_security).write({'dwell_min': 5})
        door.with_user(self.user_admin).write({'dwell_min': 5})
        self.assertEqual(door.dwell_min, 5)

    def test_door_state_rules(self):
        from datetime import datetime
        door = self.door_elec
        t = datetime(2026, 10, 12, 3, 52, 10)
        door._f3d_set_state('unlocked', t)
        door._f3d_set_state('forced', t.replace(second=12), alarm=True, reason='forced')
        self.assertEqual((door.state, door.alarm, door.alarm_reason), ('forced', True, 'forced'))
        door._f3d_set_state('open', t.replace(second=5))  # запізніла — ігнорується
        self.assertEqual(door.state, 'forced')
        door._f3d_set_state('closed', t.replace(second=20))
        self.assertEqual((door.state, door.alarm), ('closed', False))
        door._f3d_set_state(None, t.replace(second=30), alarm=True, reason='fire')
        self.assertEqual((door.state, door.alarm_reason), ('closed', 'fire'))
        door._f3d_set_state('closed', t.replace(second=40))
        self.assertTrue(door.alarm)  # пожежну знімає лише охорона
        door.with_user(self.user_security).action_ack_alarm()
        self.assertFalse(door.alarm)


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestPoll(ServerCase):

    def _rows(self, *stamps, code=20480):
        return [self.make_row(i + 1, '2026-10-12T%s.00Z' % st, code) for i, st in enumerate(stamps)]

    def _four(self):
        return self._rows('06:58:20', '06:58:40', '06:59:00', '06:59:10')

    def _events(self):
        return self.env['f3d.access.event'].search([('server_id', '=', self.server.id)])

    def test_window_first_and_next(self):
        fake = FakeBioStar(events=self._four())
        self.poll('2026-10-12 07:00:30', fake)
        self.assertEqual(fake.search_calls[0]['since'], datetime(2026, 10, 11, 7, 0, 30))
        self.assertEqual(fake.search_calls[0]['until'], datetime(2026, 10, 12, 7, 5, 30))
        self.assertEqual(self.server.last_event_ts, datetime(2026, 10, 12, 6, 59, 10))
        self.poll('2026-10-12 07:01:30', fake)
        self.assertEqual(fake.search_calls[-1]['since'], datetime(2026, 10, 12, 6, 57, 10))

    def test_future_row_cursor(self):
        fake = FakeBioStar(events=self._rows('06:59:10') + [
            self.prow(2, '2026-10-12T07:03:00.00Z', 4102, 'TSTA1', tna='1')])
        self.poll('2026-10-12 07:00:30', fake)
        future = self._events().filtered(lambda e: e.biostar_id == '2')
        self.assertEqual((future.attendance_action, future.process_state), ('future', 'new'))
        self.assertEqual(self.server.last_event_ts, datetime(2026, 10, 12, 7, 0, 30))

    def test_dedup(self):
        fake = FakeBioStar(events=self._four())
        self.poll('2026-10-12 07:00:30', fake)
        self.poll('2026-10-12 07:01:30', fake)
        self.assertEqual(len(self._events()), 4)
        self.assertEqual((self.server.last_poll_new, self.server.last_poll_rows), (0, 4))
        res = self.env['f3d.access.event']._f3d_ingest_rows(self.server, fake.events)
        self.assertEqual((res['created'], res['duplicates'], res['invalid']), (0, 4, 0))
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            self.env['f3d.access.event'].create({
                'server_id': self.server.id, 'biostar_id': '1', 'ts': '2026-10-12 06:58:20', 'code': 20480,
                'event_type': 'door'})

    def test_backoff_sequence(self):
        fake = FakeBioStar(events=self._four())
        self.poll('2026-10-12 07:00:30', fake)
        cursor = self.server.last_event_ts
        fake.fail_always = BioStarError(None, None, 'ConnectionError: refused')
        server = self.server
        now = datetime(2026, 10, 12, 7, 10, 0)
        pauses = []
        for _ in range(6):
            with self.patch_client(fake), freeze_time(now):
                server._cron_poll()
            pauses.append((server.error_count, (server.next_try_at - now).total_seconds()))
            now = server.next_try_at + timedelta(seconds=1)
        self.assertEqual(pauses, [(1, 60), (2, 120), (3, 240), (4, 480), (5, 600), (6, 600)])
        calls = len(fake.calls)
        with self.patch_client(fake), freeze_time(server.next_try_at - timedelta(seconds=5)):
            server._cron_poll()
        self.assertEqual(len(fake.calls), calls)
        self.assertEqual(server.last_event_ts, cursor)

    def test_recovery_after_outage(self):
        fake = FakeBioStar(events=self._four())
        self.poll('2026-10-12 07:00:30', fake)
        cursor = self.server.last_event_ts
        fake.fail_always = BioStarError(None, None, 'ConnectionError: refused')
        with self.patch_client(fake), freeze_time('2026-10-12 07:02:00'):
            self.server._cron_poll()
        self.assertEqual(self.server.state, 'error')
        fake.fail_always = None
        fake.events += [self.make_row(10 + i, '2026-10-12T07:%02d:00.00Z' % (1 + i), 20480) for i in range(12)]
        with self.patch_client(fake), freeze_time('2026-10-12 07:20:00'):
            self.server._cron_poll()
        self.assertEqual((self.server.state, self.server.error_count), ('online', 0))
        self.assertEqual(fake.search_calls[-1]['since'], cursor - timedelta(seconds=120))
        self.assertEqual(len(self._events()), 16)

    def test_max_pages_more(self):
        P.set_param(self.env, 'page_size', '2')
        P.set_param(self.env, 'max_pages_per_run', '2')
        stamps = ['05:%02d:00' % (5 * i) for i in range(7)]
        fake = FakeBioStar(events=self._rows(*stamps))
        self.poll('2026-10-12 06:00:00', fake)
        self.assertEqual(len(self._events()), 4)
        self.assertTrue(self.server.last_poll_more)
        self.assertEqual(self.server.last_event_ts, datetime(2026, 10, 12, 5, 15))
        self.poll('2026-10-12 06:00:30', fake)
        self.assertEqual(len(self._events()), 7)

    def test_pagination_offsets(self):
        P.set_param(self.env, 'page_size', '2')
        fake = FakeBioStar(events=self._rows('05:00:00', '05:05:00', '05:10:00', '05:15:00', '05:20:00'))
        self.poll('2026-10-12 06:00:00', fake)
        self.assertEqual([(c['offset'], c['limit']) for c in fake.search_calls], [(0, 2), (2, 2), (4, 2)])
        self.assertEqual(len(self._events()), 5)

    def test_lock_skip(self):
        cr = self.env.cr
        original = cr.execute

        def execute(query, params=None, *args, **kwargs):
            if 'FOR UPDATE NOWAIT' in str(query):
                raise pg_errors.LockNotAvailable('locked')
            return original(query, params, *args, **kwargs)

        fake = FakeBioStar(events=self._four())
        with mock.patch.object(cr, 'execute', side_effect=execute), self.patch_client(fake):
            res = self.server._poll()
        self.assertEqual(res, {'skipped': True})
        self.assertEqual(fake.search_calls, [])


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestCommitGuard(AccessCase):
    """Регресія D-1: у Odoo 19 немає Registry.in_test_mode(); крони не мають падати."""

    def test_may_commit_no_attribute_error(self):
        server = self.server.with_context(f3d_no_commit=False)
        self.assertFalse(server._may_commit())

    def test_gc_without_no_commit(self):
        Event = self.env['f3d.access.event'].with_context(f3d_no_commit=False)
        self.assertEqual(Event._gc(90), 0)
