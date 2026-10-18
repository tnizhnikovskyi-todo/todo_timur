from odoo.tests import tagged

from .common import F3DCase


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestInstall(F3DCase):

    def test_module_installed(self):
        mod = self.env['ir.module.module'].search([('name', '=', 'td_factory3d')])
        self.assertEqual(mod.state, 'installed')

    def test_groups_and_menus(self):
        user = self.env.ref('td_factory3d.group_td_user')
        manager = self.env.ref('td_factory3d.group_td_manager')
        admin = self.env.ref('td_factory3d.group_td_admin')
        self.assertIn(user, manager.implied_ids)
        self.assertIn(manager, admin.implied_ids)
        self.assertIn(user, self.user_reader.group_ids)
        self.assertIn(manager, self.user_manager.group_ids)
        for xmlid in ('menu_td_root', 'menu_td_plant', 'menu_td_config'):
            self.assertTrue(self.env.ref('td_factory3d.' + xmlid))
        self.assertEqual(self.env.ref('td_factory3d.menu_td_root').sequence, 75)
        self.assertEqual(
            self.env['ir.config_parameter'].sudo().get_param('td.base.environment'), 'test')
