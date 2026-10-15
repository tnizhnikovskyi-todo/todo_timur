from odoo.tests import tagged

from .common import AccessCase


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestAccessInstall(AccessCase):

    def test_module_installed(self):
        mod = self.env['ir.module.module'].search([('name', '=', 'factory3d_access')])
        self.assertEqual(mod.state, 'installed')

    def test_groups(self):
        sec = self.env.ref('factory3d_access.group_f3d_access_security')
        adm = self.env.ref('factory3d_access.group_f3d_access_admin')
        f3d_admin = self.env.ref('factory3d_base.group_f3d_admin')
        self.assertIn(self.env.ref('factory3d_base.group_f3d_user'), sec.implied_ids)
        self.assertIn(sec, adm.implied_ids)
        self.assertIn(adm, f3d_admin.implied_ids)

    def test_params(self):
        ICP = self.env['ir.config_parameter'].sudo()
        self.assertEqual(ICP.get_param('factory3d.access.write_enabled'), 'False')
        self.assertEqual(ICP.get_param('factory3d.access.page_size'), '500')
        self.assertEqual(ICP.get_param('factory3d.access.migration_state'), 'pending')

    def test_menu(self):
        menu = self.env.ref('factory3d_access.menu_f3d_access')
        self.assertEqual(menu.name, 'Доступ')
        self.assertEqual(menu.parent_id, self.env.ref('factory3d_base.menu_f3d_root'))

    def test_network_blocked(self):
        import requests
        with self.assertRaises(AssertionError):
            requests.Session().request('GET', 'http://127.0.0.1:1/')

    def test_fixtures(self):
        self.assertEqual(len(self.fixture_rows('users', 'UserCollection')), 36)
        self.assertEqual(len(self.fixture_rows('devices', 'DeviceCollection')), 5)
        self.assertEqual(len(self.fixture_rows('doors', 'DoorCollection')), 5)
