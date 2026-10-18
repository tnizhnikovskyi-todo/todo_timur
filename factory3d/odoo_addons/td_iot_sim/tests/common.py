from unittest import mock

from odoo.tests import TransactionCase, new_test_user

TAG_ARGS = ('post_install', '-at_install', 'f3d', 'f3d_iot_sim')
SIM_URL = 'http://sim.test:8090'
SIM_TOKEN = 'secret-sim-token'


class FakeResponse:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data if data is not None else {}

    def json(self):
        return self._data


class SimCase(TransactionCase):
    """Спільні фікстури: параметри сервісу + мок HTTP /sim/v1 (requests.Session.request)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base_user = 'base.group_user'
        cls.user_reader = new_test_user(
            cls.env, login='f3d_sim_reader', groups=f'{base_user},factory3d_base.group_f3d_user')
        cls.user_manager = new_test_user(
            cls.env, login='f3d_sim_manager', groups=f'{base_user},factory3d_base.group_f3d_manager')
        cls.user_admin = new_test_user(
            cls.env, login='f3d_sim_admin', groups=f'{base_user},factory3d_base.group_f3d_admin')

    def setUp(self):
        super().setUp()
        self.responses = {}  # (METHOD, '/path') -> (status, json) | Exception
        self.calls = []
        patcher = mock.patch('requests.Session.request', side_effect=self._fake_request)
        self.request_mock = patcher.start()
        self.addCleanup(patcher.stop)
        self.set_params(url=SIM_URL, token=SIM_TOKEN, read_enabled='True', write_enabled='True',
                        level0_enabled='True', level0_after_min='5')
        self.panel = self.env['f3d.sim.panel'].get_panel()

    def set_params(self, **kwargs):
        for key, value in kwargs.items():
            self.env['ir.config_parameter'].sudo().set_param('factory3d.iot_sim.' + key, value)

    def respond(self, method, path, status=200, data=None):
        self.responses[(method, path)] = (status, data)

    def _fake_request(self, method, url, **kwargs):
        path = url.split('/sim/v1', 1)[1]
        self.calls.append({'method': method, 'path': path, 'json': kwargs.get('json'),
                           'headers': kwargs.get('headers') or {}})
        item = self.responses.get((method, path), (200, {}))
        if isinstance(item, Exception):
            raise item
        status, data = item
        if isinstance(status, Exception):
            raise status
        return FakeResponse(status, data)

    def make_device(self, code, **vals):
        vals.setdefault('name', code)
        return self.env['f3d.sim.device'].create(dict(vals, code=code))
