from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSiteLayer(F3DConstructorCase):
    """AC-04 (ORM-частина), AC-07, AC-08, AC-09, AC-17, AC-18."""

    def test_ac04_blank_site(self):
        site = self.site
        self.assertEqual((site.building_length_m, site.building_width_m, site.building_height_m), (60, 30, 8))
        layers = site.layer_ids.sorted('sequence')
        self.assertEqual(len(layers), 5)
        self.assertEqual(layers.mapped('elevation_m'), [0.0, 0.0, 0.0, 6.0, 0.0])
        self.assertEqual(len(site.check_config_ids), 7)
        self.assertEqual(site.slot_count, 0)
        self.assertFalse(site.has_changes)
        self.assertEqual(
            self.layers['storage'].edit_group_ids,
            self.env.ref('factory3d_constructor.group_f3d_constructor_storekeeper'),
        )
        self.assertTrue(self.env.ref('factory3d_constructor.variant_generic_machine').exists())
        modes = {c.check_key: c.mode for c in site.check_config_ids}
        self.assertEqual({k for k, m in modes.items() if m == 'block'}, {'fits', 'collide', 'aisles_free', 'fire'})

    def test_ac07_multicompany_rules(self):
        company2 = self.env['res.company'].create({'name': "Друга компанія"})
        site2 = (
            self.env['f3d.site']
            .with_context(f3d_blank=True)
            .create({'name': "Чужа", 'code': 'OTH', 'company_id': company2.id})
        )
        manager = self.u_manager.with_company(self.company)
        self.assertEqual(
            self.env['f3d.site'].with_user(manager).search([('id', 'in', (self.site | site2).ids)]), self.site
        )
        with self.assertRaises(AccessError):
            self.env['f3d.layer'].with_user(manager).create(
                {'site_id': site2.id, 'name': "Підсаджений", 'kind': 'custom'}
            )
        with self.assertRaises(AccessError):
            site2.with_user(manager).name  # noqa: B018 - читання чужої площадки

    def test_ac08_layer_fields_and_validation(self):
        layer = self.env['f3d.layer'].create(
            {
                'site_id': self.site.id,
                'name': "Антресоль",
                'kind': 'custom',
                'elevation_m': 3.6,
                'grid_step_m': 0.25,
                'aisle_width_m': 3.5,
                'color': '#112233',
                'opacity': 0.4,
                'bounds': [[0, 0], [10, 0], [10, 10], [0, 10]],
                'edit_group_ids': [
                    Command.set([self.env.ref('factory3d_constructor.group_f3d_constructor_storekeeper').id])
                ],
                'allowed_slot_type_ids': [Command.set(self.env['f3d.term'].search([('key', '=', 'pallet_rack')]).ids)],
            }
        )
        self.assertEqual((layer.elevation_m, layer.grid_step_m, layer.color), (3.6, 0.25, '#112233'))
        self.assertEqual(len(layer.bounds), 4)
        for bad in (
            {'grid_step_m': 0},
            {'color': 'red'},
            {'bounds': [[0, 0], [1, 1]]},
            {'opacity': 1.5},
            {'bounds': [[0, 0], [10, 10], [10, 0], [0, 10]]},  # самоперетин
            {'edit_group_ids': [Command.set([self.env.ref('base.group_user').id])]},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                layer.write(bad)

    def test_ac09_custom_layer_cells_z0(self):
        layer = self.env['f3d.layer'].create(
            {'site_id': self.site.id, 'name': "Антресоль офісу", 'kind': 'custom', 'elevation_m': 3.6}
        )
        slot = self.env['f3d.slot'].create(
            {
                'layer_id': layer.id,
                'template': 'shelf',
                'code_prefix': 'ANT-S1',
                'x_m': 10,
                'y_m': 10,
                'params': {'sections': 2, 'shelves': 3, 'cell_w': 0.9, 'cell_d': 0.4, 'cell_h': 0.4},
            }
        )
        cells = {c['code']: c for c in slot._f3d_cells()}
        self.assertAlmostEqual(cells['ANT-S1-S01-L1']['z0'], 3.6)
        self.assertAlmostEqual(cells['ANT-S1-S01-L3']['z0'], 3.6 + 2 * 0.4)

    def test_json_schemas(self):
        layer = self.layers['production']
        layer.write({'aisles': [{'id': 'a1', 'name': "Прохід", 'x0': 0, 'y0': 0, 'x1': 10, 'y1': 3, 'junk': 1}]})
        self.assertNotIn('junk', layer.aisles[0])  # невідомі ключі відкидаються (R-22)
        with self.assertRaises(ValidationError):
            layer.write({'aisles': [{'id': 'a1', 'name': "X", 'x0': 5, 'y0': 0, 'x1': 1, 'y1': 3}]})
        with self.assertRaises(ValidationError):
            layer.write({'fire_paths': [{'id': 'f1', 'kind': 'door', 'name': "X", 'x0': 0, 'y0': 0, 'x1': 1, 'y1': 1}]})
        with self.assertRaises(ValidationError):
            layer.write({'utilities': [{'id': 'u1', 'kind': 'steam', 'name': "X", 'x': 1, 'y': 1}]})

    def test_layer_unlink_guard(self):
        layer = self.layers['storage']
        self.make_slot()
        with self.assertRaises(Exception) as ctx:
            layer.unlink()
        self.assertIn("Шар не порожній", str(ctx.exception))

    def test_ac17_ac18_underlay(self):
        layer = self.layers['storage']
        att = self.env['ir.attachment'].create(
            {'name': 'plan.dxf', 'raw': b'0\nEOF\n', 'res_model': 'f3d.layer', 'res_id': layer.id}
        )
        layer.underlay_attachment_id = att
        self.assertEqual((layer.underlay_format, layer.underlay_status), ('dxf', 'ready'))
        att2 = self.env['ir.attachment'].create(
            {'name': 'plan.dwg', 'raw': b'AC1015', 'res_model': 'f3d.layer', 'res_id': layer.id}
        )
        layer.underlay_attachment_id = att2
        self.assertEqual((layer.underlay_format, layer.underlay_status), ('dwg', 'pending_conversion'))
        layer.underlay_attachment_id = False
        self.assertEqual(layer.underlay_status, 'none')
