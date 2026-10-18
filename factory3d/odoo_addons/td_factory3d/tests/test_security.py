from odoo.exceptions import AccessError, ValidationError
from odoo.tests import new_test_user, tagged

from odoo.addons.td_factory3d.hooks import x_fields

from .common import F3DCase

MENUS = {  # xml-id: (sequence, parent, group)
    'menu_td_root': (75, None, 'group_td_user'),
    'menu_td_plant': (20, 'menu_td_root', 'group_td_user'),
    'menu_td_zone': (10, 'menu_td_plant', 'group_td_user'),
    'menu_td_dock': (20, 'menu_td_plant', 'group_td_user'),
    'menu_td_equipment': (30, 'menu_td_plant', 'group_td_user'),
    'menu_td_passport': (40, 'menu_td_plant', 'group_td_user'),
    'menu_td_config': (99, 'menu_td_root', 'group_td_manager'),
    'menu_td_config_spec': (20, 'menu_td_config', 'group_td_manager'),
    'menu_td_config_source': (21, 'menu_td_config', 'group_td_manager'),
    'menu_td_config_params': (95, 'menu_td_config', 'group_td_admin'),
    'menu_td_config_migration': (96, 'menu_td_config', 'group_td_admin'),
}


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestGroups(F3DCase):

    def test_groups_chain(self):  # AC-41
        ref = self.env.ref
        user, manager, admin = (ref('td_factory3d.group_td_' + n) for n in ('user', 'manager', 'admin'))
        self.assertIn(user, manager.implied_ids)
        self.assertIn(manager, admin.implied_ids)
        self.assertIn(admin, ref('base.group_system').implied_ids)
        self.assertIn(user, ref('stock.group_stock_user').implied_ids)
        self.assertIn(user, ref('mrp.group_mrp_user').implied_ids)
        self.assertEqual(user.privilege_id, ref('td_factory3d.privilege_td'))
        self.assertEqual(user.privilege_id.name, 'Завод 3D')

    def test_menus(self):  # AC-44
        for xmlid, (seq, parent, group) in MENUS.items():
            menu = self.env.ref('td_factory3d.' + xmlid)
            self.assertEqual(menu.sequence, seq, xmlid)
            self.assertEqual(menu.parent_id, self.env.ref('td_factory3d.' + parent) if parent
                             else self.env['ir.ui.menu'], xmlid)
            self.assertEqual(menu.group_ids, self.env.ref('td_factory3d.' + group), xmlid)

    def test_access_reader_manager(self):  # AC-42
        zone = self.make_zone('ACC-1')
        Zone = self.env['td.zone']
        self.assertTrue(Zone.with_user(self.user_reader).search([('id', '=', zone.id)]))
        for model in ('td.zone', 'td.equipment.passport', 'td.equipment.spec', 'td.equipment.source'):
            self.env[model].with_user(self.user_reader).check_access('read')
            for mode in ('write', 'create', 'unlink'):
                with self.assertRaises(AccessError, msg=f'{model} {mode}'):
                    self.env[model].with_user(self.user_reader).check_access(mode)
                self.env[model].with_user(self.user_manager).check_access(mode)
        with self.assertRaises(AccessError):
            zone.with_user(self.user_reader).write({'name': 'X'})
        zone.with_user(self.user_manager).write({'name': 'Ok'})

    def test_no_group_denied(self):  # §13.3
        user = self.env['res.users'].create({'name': 'Plain', 'login': 'f3d_plain',
                                             'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['td.zone'].with_user(user).search([])

    def test_code_write_rights(self):  # AC-43
        loc = self.loc_in
        with self.assertRaises(AccessError):
            loc.with_user(self.user_stock_mgr).write({'td_code': 'X-1'})
        with self.assertRaises(AccessError):
            self.env['stock.location'].with_user(self.user_stock_mgr).create(
                {'name': 'Нова-Х', 'usage': 'internal', 'td_code': 'X-2'})
        loc.with_user(self.user_stock_mgr).write({'name': 'Нова'})
        self.assertEqual(loc.name, 'Нова')
        both = new_test_user(self.env, login='f3d_stock_f3d_mgr', groups='base.group_user,'
                             'stock.group_stock_manager,td_factory3d.group_td_manager')
        loc.with_user(both).write({'td_code': 'X-1'})
        self.assertEqual(loc.td_code, 'X-1')

    def test_zone_company_rule(self):  # AC-45
        company_b = self.env['res.company'].create({'name': 'Компанія Б'})
        zone_b = self.make_zone('CMP-B', company_id=company_b.id)
        zone_a = self.make_zone('CMP-A')
        Zone = self.env['td.zone'].with_user(self.user_reader)
        found = Zone.search([('id', 'in', (zone_b | zone_a).ids)])
        self.assertEqual(found, zone_a)  # company_id обов'язкове: зон без компанії немає
        user_b = self.user_reader.copy({'login': 'f3d_reader_b', 'company_id': company_b.id,
                                        'company_ids': [(6, 0, [company_b.id])]})
        found_b = self.env['td.zone'].with_user(user_b).search([('id', 'in', (zone_b | zone_a).ids)])
        self.assertEqual(found_b, zone_b)

    def test_run_migration_rights(self):  # AC-50
        Mixin = self.env['td.scene.mixin']
        with self.assertRaises(AccessError):
            Mixin.with_user(self.user_manager).f3d_run_migration()
        action = Mixin.with_user(self.user_admin).f3d_run_migration()
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'display_notification')

    def test_code_injection_rejected(self):  # §13.3
        with self.assertRaises(ValidationError):
            self.make_zone("'; DROP TABLE --")

    def test_manual_field_name_validated(self):  # §13.3
        with self.assertRaises(ValueError):
            x_fields.read_manual_field(self.env, 'stock.picking', 'x_dock; DROP')

    def test_polygon_injection_rejected(self):  # §13.3
        with self.assertRaises(ValidationError):
            self.make_zone('INJ-1', polygon='{"__class__": "x"}')
