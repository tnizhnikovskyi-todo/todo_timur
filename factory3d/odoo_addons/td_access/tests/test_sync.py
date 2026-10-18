from odoo.tests import tagged

from ..tools.biostar_client import BioStarError
from .common import AccessCase, FakeBioStar


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestSync(AccessCase):

    def _dev_rows(self, extra=True):
        rows = self.fixture_rows('devices', 'DeviceCollection')
        if extra:
            rows.append({'id': '5390006', 'name': 'Новий', 'device_type_id': {'name': 'BioLite N2'},
                         'status': '1', 'ip': '192.168.10.16'})
        return rows

    def test_sync_devices(self):
        fake = FakeBioStar(devices=self._dev_rows())
        with self.patch_client(fake):
            res = self.server._sync_devices()
        self.assertEqual((res['devices_total'], res['devices_created']), (6, 1))
        self.assertEqual(self.device_acr_srv.status, 'offline')
        self.assertEqual(self.device_acr_in.status, 'online')
        self.assertEqual(self.device_acr_in.device_type, 'BioEntry W3')
        self.assertEqual(self.device_acr_in.name, 'Вхід персоналу (прохідна)')
        new = self.env['f3d.access.device'].search([('code', '=', 'BS-5390006')])
        self.assertEqual((new.direction, bool(new.zone_id), new.biostar_id), ('in', False, '5390006'))
        self.assertEqual(self.server.devices_total, 6)
        self.assertEqual(self.server.state, 'online')

    def test_device_fail_unknown(self):
        fake = FakeBioStar(devices=self._dev_rows())
        fake.fail_always = BioStarError(None, None, 'ConnectionError: refused')
        with self.patch_client(fake):
            self.server._sync_devices()
            self.server._sync_devices()
        self.assertEqual(self.device_acr_in.sync_fail_count, 2)
        self.assertEqual(self.device_acr_in.status, 'unknown')
        self.assertEqual(self.server.state, 'error')

    def test_sync_doors_new(self):
        doors = self.fixture_rows('doors', 'DoorCollection')
        doors[0]['open_duration'] = '5'
        doors.append({'id': '6', 'name': 'Нові двері', 'entry_device_id': {'id': '5390006'}, 'open_duration': '3'})
        fake = FakeBioStar(devices=self._dev_rows(), doors=doors)
        zones = {d.code: (d.zone_from_id, d.zone_to_id) for d in self.server.door_ids}
        with self.patch_client(fake):
            res = self.server._sync_devices()
        self.assertEqual((res['doors_total'], res['doors_created']), (6, 1))
        self.assertEqual(self.door_turn_1.open_duration_s, 5)
        for door in self.server.door_ids.filtered(lambda d: d.code in zones):
            self.assertEqual((door.zone_from_id, door.zone_to_id), zones[door.code])
        new = self.env['f3d.access.door'].search([('code', '=', 'BSD-6')])
        self.assertEqual(new.entry_device_id.code, 'BS-5390006')
        self.assertFalse(new.zone_to_id)
        self.assertEqual(self.server.doors_without_zone, 1)

    def _users(self):
        return [
            {'user_id': 'TSTA1', 'name': 'Тест А', 'user_group_id': {'id': '2', 'name': 'Виробництво'},
             'disabled': 'false', 'card_count': '1', 'face_count': '1', 'photo': 'iVBORw0KGgo',
             'start_datetime': '2001-01-01T00:00:00.00Z', 'expiry_datetime': '2030-12-31T23:59:00.00Z'},
            {'user_id': 'OPTSTC', 'name': 'Інше ім\'я', 'disabled': 'false', 'card_count': '0', 'face_count': '0'},
            {'user_id': 'ALIAS1', 'name': 'Тест Г', 'disabled': 'true', 'card_count': '0', 'face_count': '0'},
            {'user_id': '1', 'name': 'Administrator', 'disabled': 'false', 'card_count': '0', 'face_count': '0'},
            {'user_id': 'ZZZ9', 'name': self.emp_a.name, 'disabled': 'false', 'card_count': '0',
             'face_count': '0'},
        ]

    def _sync_users(self, users=None):
        self.link_b.unlink()  # TSTB2 не повертається — перевіряємо лише OLD9
        old = self.env['f3d.access.user.link'].create({'server_id': self.server.id, 'biostar_user_id': 'OLD9'})
        with self.patch_client(FakeBioStar(users=users or self._users())):
            return old, self.server._sync_users()

    def test_sync_users_matching(self):
        old, res = self._sync_users()
        Link = self.env['f3d.access.user.link']

        def link(uid):
            return Link.search([('server_id', '=', self.server.id), ('biostar_user_id', '=', uid)])

        self.assertEqual((link('TSTA1').employee_id, link('TSTA1').match), (self.emp_a, 'barcode'))
        self.assertTrue(link('TSTA1').has_face)
        self.assertEqual((link('OPTSTC').employee_id, link('OPTSTC').match), (self.emp_c, 'code'))
        self.assertEqual((link('ALIAS1').employee_id, link('ALIAS1').match), (self.emp_d, 'alias'))
        self.assertTrue(link('ALIAS1').disabled)
        self.assertEqual(link('TSTA1').user_group, 'Виробництво')
        self.assertEqual(link('1').match, 'none')
        self.assertFalse(old.in_biostar)
        self.assertEqual(res['total'], 5)
        self.assertEqual((res['unlinked'], res['missing'], res['created']), (2, 1, 4))
        self.assertEqual((self.server.users_total, self.server.state), (5, 'online'))
        self.assertEqual(self.server.unlinked_count, 2)

    def test_no_name_match(self):
        _old, _res = self._sync_users()
        link = self.env['f3d.access.user.link'].search([('biostar_user_id', '=', 'ZZZ9')])
        self.assertEqual((link.match, bool(link.employee_id)), ('none', False))

    def test_biometrics_not_stored(self):
        self._sync_users()
        for rec in self.env['f3d.access.user.link'].search([]):
            for name in rec._fields:
                value = rec[name]
                if isinstance(value, str):
                    self.assertNotIn('iVBOR', value, name)

    def test_missing_users(self):
        _old, res = self._sync_users(users=self._users()[:1])
        self.assertEqual(res['missing'], 1)
        self.assertFalse(self.env['f3d.access.user.link'].search([('biostar_user_id', '=', 'OLD9')]).in_biostar)
        # користувач повернувся — прапорець знову піднімається
        with self.patch_client(FakeBioStar(users=self._users() + [{'user_id': 'OLD9', 'name': 'Повернувся'}])):
            self.server._sync_users()
        self.assertTrue(self.env['f3d.access.user.link'].search([('biostar_user_id', '=', 'OLD9')]).in_biostar)

    def test_manual_match_survives(self):
        link = self.env['f3d.access.user.link'].create({'server_id': self.server.id, 'biostar_user_id': 'ZZZ9'})
        link.write({'employee_id': self.emp_c.id})
        self.assertEqual(link.match, 'manual')
        with self.patch_client(FakeBioStar(users=self._users())):
            self.server._sync_users()
        self.assertEqual((link.match, link.employee_id), ('manual', self.emp_c))
