from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools.biostar_client import BioStarAuthError
from .common import AccessCase, FakeBioStar


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
