from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestInstall(TransactionCase):
    """AC-01: після встановлення є групи, довідник, параметри, меню й клієнтська дія."""

    def test_groups_terms_params_menus(self):
        env = self.env
        privilege = env.ref('factory3d_constructor.privilege_f3d_constructor')
        self.assertEqual(len(env['res.groups'].search([('privilege_id', '=', privilege.id)])), 4)
        self.assertEqual(env['f3d.term'].search_count([]), 12)
        keys = env['ir.config_parameter'].sudo().search([('key', '=like', 'factory3d.constructor.%')]).mapped('key')
        self.assertGreaterEqual(len(keys), 7)  # 6 з params.xml + publish_enabled з хука (seed_report — після seed)
        plan = env.ref('factory3d_constructor.menu_f3d_constructor_plan')
        main = env.ref('factory3d_constructor.menu_f3d_constructor')
        root = env.ref('factory3d_base.menu_f3d_root')
        self.assertEqual((main.sequence, plan.sequence), (12, 14))
        self.assertEqual((main.parent_id, plan.parent_id), (root, root))
        self.assertEqual(env.ref('factory3d_constructor.action_f3d_constructor').tag, 'f3d_constructor')
