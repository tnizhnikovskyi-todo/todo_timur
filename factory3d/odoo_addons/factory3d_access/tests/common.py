import json
from contextlib import contextmanager
from unittest import mock

from odoo.tests import TransactionCase, new_test_user
from odoo.tools import file_open

from ..tools import params as P
from ..tools.biostar_client import BioStarError, BioStarWriteDisabled
from ..tools.dates import parse_bs_dt


def load_fixture(name):
    """Ответ BioStar (P-10) из tests/fixtures/<name>.json."""
    with file_open(f'factory3d_access/tests/fixtures/{name}.json') as fh:
        return json.load(fh)


def fixture_rows(name, collection):
    """Строки коллекции фикстуры: fixture_rows('users', 'UserCollection')."""
    return load_fixture(name)[collection]['rows']


class FakeBioStar:
    """Підміна BioStarClient (SPEC §13.1): ті самі сигнатури, без мережі."""

    def __init__(self, users=None, devices=None, doors=None, events=None):
        self.users = list(users or [])
        self.devices = list(devices or [])
        self.doors = list(doors or [])
        self.events = list(events or [])
        self.calls = []
        self.search_calls = []
        self.session_id = None
        self.fail_always = None
        self.fail_times = 0
        self.login_error = None
        self.write_enabled = False
        self.write_status = None
        self.next_card_id = '9'

    def _tick(self, name, *args):
        self.calls.append((name,) + args)
        if self.fail_always is not None:
            raise self.fail_always
        if self.fail_times > 0:
            self.fail_times -= 1
            raise BioStarError(None, None, 'ConnectionError: refused')

    def _write_guard(self):
        if not self.write_enabled:
            raise BioStarWriteDisabled(None, None, 'Запис у BioStar вимкнено стоп-краном')
        if self.write_status == 405:
            raise BioStarError(405, None, 'Метод не підтримується сервером BioStar (405)')

    def login(self):
        self.calls.append(('login',))
        if self.login_error is not None:
            raise self.login_error
        if self.fail_always is not None:
            raise self.fail_always
        self.session_id = 'fake-session'
        return self.session_id

    def logout(self):
        self.calls.append(('logout',))
        self.session_id = None

    def list_users(self, limit=100):
        self._tick('list_users', limit)
        yield from self.users

    def list_users_total(self):
        self._tick('list_users_total')
        return len(self.users)

    def list_devices(self):
        self._tick('list_devices')
        return list(self.devices)

    def list_doors(self):
        self._tick('list_doors')
        return list(self.doors)

    def search_events(self, since, until, limit, offset=None, hint=None):
        self._tick('search_events', since, until, limit, offset, hint)
        self.search_calls.append({'since': since, 'until': until, 'limit': limit, 'offset': offset, 'hint': hint})
        rows = sorted((r for r in self.events if since <= parse_bs_dt(r['datetime']) <= until),
                      key=lambda r: parse_bs_dt(r['datetime']))
        total = len(rows)
        if hint is not None:
            ids = [r.get('hint') for r in rows]
            start = ids.index(hint) + 1 if hint in ids else 0
        else:
            start = offset or 0
        return rows[start:start + limit], total

    def create_card(self, card_id, card_type_id):
        self._tick('create_card', card_id, card_type_id)
        self._write_guard()
        return self.next_card_id

    def update_user_cards(self, user_id, cards):
        self._tick('update_user_cards', user_id, cards)
        self._write_guard()

    def create_user(self, user_id, name, start_dt, expiry_dt, user_group_id):
        self._tick('create_user', user_id, name)
        self._write_guard()


def make_row(id, dt, code, user=None, device='5390001', door='1', tna=''):  # noqa: A002
    """Рядок EventCollection (SPEC §7.2); `door_id` — список."""
    row = {'id': str(id), 'datetime': dt, 'server_datetime': dt, 'event_type_id': {'code': str(code)},
           'device_id': {'id': str(device)}, 'tna_key': tna, 'hint': 'H%s' % id}
    if user is not None:
        row['user_id'] = {'user_id': str(user)}
    if door is not None:
        row['door_id'] = [{'id': str(door)}]
    return row


class AccessCase(TransactionCase):
    """Общая база тестов factory3d_access: сеть запрещена (SPEC §13.1, DoD §14)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, f3d_no_commit=True))
        patcher = mock.patch(
            'requests.Session.request',
            side_effect=AssertionError('Сетевой вызов в юнит-тесте запрещён'))
        patcher.start()
        cls.addClassCleanup(patcher.stop)
        for key, value in (('read_enabled', 'True'), ('write_enabled', 'False'), ('biostar_password', 'test-pass'),
                           ('merge_gap_min', '0'), ('dup_window_min', '20'), ('keep_raw', 'False'),
                           ('publish_signals', 'True')):
            P.set_param(cls.env, key, value)
        zones = 'Z-KPP Z-ASM Z-CUT Z-FG Z-ELEC Z-POST Z-CHG Z-FAC Z-MAINT Z-HW Z-OFFICE'.split()
        cls.z = {c: cls.env.ref('factory3d_base.zone_' + c.lower().replace('-', '_')) for c in zones}
        cls.server = cls.env.ref('factory3d_access.server_biostar_sim')
        for code in ('acr_in', 'acr_elec', 'acr_chg', 'acr_paint', 'acr_srv'):
            setattr(cls, 'device_' + code, cls.env.ref('factory3d_access.device_' + code))
        for code in ('turn_1', 'elec', 'chg', 'paint', 'srv'):
            setattr(cls, 'door_' + code, cls.env.ref('factory3d_access.door_' + code))
        Employee = cls.env['hr.employee'].sudo()
        cls.emp_a = Employee.create({'name': 'Тест А', 'barcode': 'TSTA1', 'f3d_code': 'OP-TST-A'})
        cls.emp_b = Employee.create({'name': 'Тест Б', 'barcode': 'TSTB2', 'f3d_code': 'OP-TST-B'})
        cls.emp_c = Employee.create({'name': 'Тест В', 'f3d_code': 'OP-TST-C'})
        cls.emp_d = Employee.create({'name': 'Тест Г', 'f3d_code': 'OP-TST-D', 'f3d_alias': 'ALIAS1'})
        Link = cls.env['f3d.access.user.link'].sudo()
        cls.link_a = Link.create({'server_id': cls.server.id, 'biostar_user_id': 'TSTA1',
                                  'employee_id': cls.emp_a.id, 'match': 'barcode'})
        cls.link_b = Link.create({'server_id': cls.server.id, 'biostar_user_id': 'TSTB2',
                                  'employee_id': cls.emp_b.id, 'match': 'barcode'})
        cls.user_plain = new_test_user(cls.env, 'f3d_plain', groups='base.group_user')
        cls.user_f3d = new_test_user(cls.env, 'f3d_user', groups='base.group_user,factory3d_base.group_f3d_user')
        cls.user_security = new_test_user(
            cls.env, 'f3d_security', groups='base.group_user,factory3d_access.group_f3d_access_security')
        cls.user_admin = new_test_user(
            cls.env, 'f3d_acc_admin', groups='base.group_user,factory3d_access.group_f3d_access_admin')
        cls.user_hr = new_test_user(
            cls.env, 'f3d_hr', groups='base.group_user,hr_attendance.group_hr_attendance_user')
        cls.user_f3d_admin = new_test_user(
            cls.env, 'f3d_f3d_admin', groups='base.group_user,factory3d_base.group_f3d_admin')

    @contextmanager
    def patch_client(self, fake):
        with mock.patch.object(type(self.env['f3d.access.server']), '_get_client', lambda srv: fake):
            yield fake

    make_row = staticmethod(make_row)
    load_fixture = staticmethod(load_fixture)
    fixture_rows = staticmethod(fixture_rows)
