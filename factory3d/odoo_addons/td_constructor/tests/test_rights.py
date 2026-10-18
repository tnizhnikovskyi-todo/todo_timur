from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestRights(F3DConstructorCase):
    """AC-43…AC-47 (ORM-частина) і §13.3: права ролей поверх ACL, ir.rule і серверної перевірки R-11."""

    def _slot_vals(self, kind, prefix, template='pallet_rack'):
        params = {'bays': 2, 'levels': 1} if template == 'pallet_rack' else {'length': 3.0, 'width': 1.5}
        return {
            'layer_id': self.layers[kind].id,
            'template': template,
            'code_prefix': prefix,
            'x_m': 20.0,
            'y_m': 10.0,
            'params': params,
        }

    def test_ac43_storekeeper_vs_technologist_layers(self):
        Slot = self.env['td.slot'].with_user(self.u_store)
        slot = Slot.create(self._slot_vals('storage', 'ST-1'))
        slot.write({'x_m': 31.0})
        with self.assertRaises(AccessError) as ctx:
            Slot.create(self._slot_vals('production', 'PR-1', 'machine_spot'))
        self.assertIn("Шар «Виробництво» редагує: Конструктор: технолог.", str(ctx.exception))
        placement = self.make_placement()
        with self.assertRaises(AccessError):
            placement.with_user(self.u_store).write({'x_m': 5.0})

    def test_ac44_technologist_and_engineer(self):
        Placement = self.env['td.placement'].with_user(self.u_tech)
        placement = Placement.create(
            {
                'layer_id': self.layers['production'].id,
                'variant_id': self.variant.id,
                'code': 'T-1',
                'name': "Станок",
                'x_m': 10.0,
                'y_m': 10.0,
            }
        )
        placement.write({'x_m': 11.0})
        self.variant.with_user(self.u_tech).write({'note': "оновлено технологом"})
        layer = self.layers['engineering'].with_user(self.u_eng)
        layer.write(
            {
                'utilities': [{'id': 'p1', 'kind': 'panel', 'name': "ГРЩ", 'x': 1, 'y': 1}],
                'aisles': [{'id': 'a1', 'name': "П", 'x0': 0, 'y0': 0, 'x1': 5, 'y1': 2}],
            }
        )
        self.assertEqual(len(layer.utilities), 1)
        with self.assertRaises(AccessError):
            layer.write({'elevation_m': 7.0})
        with self.assertRaises(AccessError):
            layer.write({'edit_group_ids': [(5, 0, 0)]})
        with self.assertRaises(AccessError):
            self.env['td.layer'].with_user(self.u_eng).create(
                {'site_id': self.site.id, 'name': "Новий", 'kind': 'custom'}
            )

    def test_ac45_layer_without_groups_is_manager_only(self):
        vals = self._slot_vals('building', 'BL-1', 'zone')
        vals['params'] = {'polygon': [[0, 0], [5, 0], [5, 5]]}
        for user in (self.u_store, self.u_tech, self.u_eng):
            with self.subTest(user=user.login), self.assertRaises(AccessError) as ctx:
                self.env['td.slot'].with_user(user).create(dict(vals))
            self.assertIn("менеджер", str(ctx.exception))
        slot = self.env['td.slot'].with_user(self.u_manager).create(vals)
        self.assertTrue(slot.exists())

    def test_ac46_move_between_layers_needs_both(self):
        slot = self.env['td.slot'].with_user(self.u_store).create(self._slot_vals('storage', 'MV-1'))
        with self.assertRaises(AccessError):
            slot.write({'layer_id': self.layers['production'].id})

    def test_ac47_plain_user_read_only(self):
        slot = self.make_slot()
        plain = self.u_plain
        self.assertTrue(self.env['td.slot'].with_user(plain).search([('id', '=', slot.id)]))
        with self.assertRaises(AccessError):
            self.env['td.slot'].with_user(plain).create(self._slot_vals('storage', 'PL-1'))
        with self.assertRaises(AccessError):
            slot.with_user(plain).write({'x_m': 1.0})
        with self.assertRaises(AccessError):
            self.env['td.layer'].with_user(plain).create({'site_id': self.site.id, 'name': "X", 'kind': 'custom'})

    def test_manager_only_actions(self):
        with self.assertRaises(AccessError):
            self.site.with_user(self.u_tech).action_publish_wizard()
        with self.assertRaises(AccessError):
            self.site.check_config_ids[:1].with_user(self.u_tech).write({'mode': 'warn'})
        self.site.check_config_ids[:1].with_user(self.u_manager).write({'mode': 'warn'})

    def test_injection_in_codes(self):
        from odoo.exceptions import ValidationError

        for bad in ("'; DROP TABLE x;--", "ab cd", "ЖК-1", "../x", "a-b", "-A", "A-", "A" * 33):
            with self.subTest(code=bad), self.assertRaises(ValidationError):
                self.make_placement(code=bad)
        for bad in ("'; DROP", "x y", "Ж", "A" * 23):
            with self.subTest(prefix=bad), self.assertRaises(ValidationError):
                self.make_slot(prefix=bad)
