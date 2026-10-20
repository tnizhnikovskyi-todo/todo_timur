from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestInstall(TransactionCase):
    """AC-01: після встановлення є групи, довідник, параметри, меню й клієнтська дія."""

    def test_groups_terms_params_menus(self):
        env = self.env
        privilege = env.ref('td_constructor.privilege_td_constructor')
        self.assertEqual(len(env['res.groups'].search([('privilege_id', '=', privilege.id)])), 4)
        self.assertEqual(env['td.term'].search_count([]), 27)  # 13 (+ floor_spot, S1) + 14 довідників зони (S2)
        keys = env['ir.config_parameter'].sudo().search([('key', '=like', 'td.constructor.%')]).mapped('key')
        self.assertEqual(len(keys), 14)  # 12 з params.xml (6 + 6 волн 1–2) + publish_enabled і seed_report з хука
        plan = env.ref('td_constructor.menu_td_constructor_plan')
        main = env.ref('td_constructor.menu_td_constructor')
        root = env.ref('td_factory3d.menu_td_root')
        help_menu = env.ref('td_constructor.menu_td_constructor_help')
        self.assertEqual(plan.sequence, 70)
        self.assertEqual(plan.parent_id, root)
        # «Конструктор» й «Інструкція» — перші пункти «Планування»
        self.assertEqual((main.parent_id, main.sequence), (plan, 1))
        self.assertEqual((help_menu.parent_id, help_menu.sequence), (plan, 2))
        self.assertLess(
            max(main.sequence, help_menu.sequence), min((plan.child_id - main - help_menu).mapped('sequence'))
        )
        self.assertEqual(env.ref('td_constructor.action_td_constructor').tag, 'f3d_constructor')

    def test_uninstall_hook_keeps_business_records(self):
        from .. import hooks

        locations = self.env['stock.location'].search_count([])
        hooks.uninstall_hook(self.env)
        self.assertFalse(self.env['ir.config_parameter'].sudo().search([('key', '=like', 'td.constructor.%')]))
        self.assertEqual(self.env['stock.location'].search_count([]), locations)
        self.assertTrue(self.env['td.site'].search_count([]))
