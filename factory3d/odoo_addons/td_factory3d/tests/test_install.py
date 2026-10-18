from odoo.tests import tagged

from .common import F3DCase


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestInstall(F3DCase):

    def test_module_installed(self):
        mod = self.env['ir.module.module'].search([('name', '=', 'factory3d_base')])
        self.assertEqual(mod.state, 'installed')

    def test_groups_and_menus(self):
        user = self.env.ref('factory3d_base.group_f3d_user')
        manager = self.env.ref('factory3d_base.group_f3d_manager')
        admin = self.env.ref('factory3d_base.group_f3d_admin')
        self.assertIn(user, manager.implied_ids)
        self.assertIn(manager, admin.implied_ids)
        self.assertIn(user, self.user_reader.group_ids)
        self.assertIn(manager, self.user_manager.group_ids)
        for xmlid in ('menu_f3d_root', 'menu_f3d_plant', 'menu_f3d_config'):
            self.assertTrue(self.env.ref('factory3d_base.' + xmlid))
        self.assertEqual(self.env.ref('factory3d_base.menu_f3d_root').sequence, 75)
        self.assertEqual(
            self.env['ir.config_parameter'].sudo().get_param('factory3d.base.environment'), 'test')
