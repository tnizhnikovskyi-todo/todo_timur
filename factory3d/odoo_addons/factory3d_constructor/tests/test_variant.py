from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestVariant(F3DConstructorCase):
    """AC-19, AC-20, AC-21."""

    def test_ac19_passport_variants_and_categories(self):
        passport = self.env['f3d.equipment.passport'].create({'role': 'test_other', 'manufacturer': "T", 'model': "M"})
        self.assertEqual(passport.f3d_category, 'other')
        variant = self.env['f3d.equipment.variant'].create(
            {'passport_id': passport.id, 'name': "V1", 'length_mm': 1000, 'width_mm': 500, 'height_mm': 800}
        )
        self.assertEqual(passport.variant_ids, variant)
        self.assertEqual(passport.variant_count, 1)
        self.assertEqual(passport.action_view_variants()['res_model'], 'f3d.equipment.variant')

    def test_ac20_fields_and_validation(self):
        variant = self.variant
        variant.write(
            {
                'length_mm': 4000,
                'width_mm': 1200,
                'height_mm': 1600,
                'service_front_mm': 1000,
                'service_back_mm': 500,
                'service_left_mm': 300,
                'service_right_mm': 300,
                'front_side': 'n',
                'anchor': 'front',
                'rotation_mode': 'h',
                'power_kw': 11,
                'panel': "ГРЩ-1",
                'weight_kg': 2400,
                'utilities': [
                    {'kind': 'electric', 'x_mm': -1800, 'y_mm': 0, 'z_mm': 500},
                    {'kind': 'air', 'x_mm': 1800, 'y_mm': 0, 'z_mm': 400},
                ],
                'allowed_layer_kind_ids': [(6, 0, self.env['f3d.term'].search([('key', '=', 'production')]).ids)],
                'allowed_slot_type_ids': [(6, 0, self.env['f3d.term'].search([('key', '=', 'machine_spot')]).ids)],
            }
        )
        self.assertEqual(len(variant.utilities), 2)
        for bad in (
            {'length_mm': 0},
            {'service_left_mm': -1},
            {'utilities': [{'kind': 'steam', 'x_mm': 0, 'y_mm': 0, 'z_mm': 0}]},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                variant.write(bad)

    def test_ac21_inherit_from_passport_and_floor_load(self):
        passport = self.env['f3d.equipment.passport'].create(
            {
                'role': 'test_inherit',
                'manufacturer': "T",
                'model': "Станок",
                'f3d_category': 'machine',
                'dim_l_mm': 4000,
                'dim_w_mm': 1200,
                'dim_h_mm': 1600,
                'power_kw': 11,
            }
        )
        variant = self.env['f3d.equipment.variant'].create(
            {'passport_id': passport.id, 'name': "Авто", 'weight_kg': 2400}
        )
        self.assertEqual(
            (variant.length_mm, variant.width_mm, variant.height_mm, variant.power_kw), (4000, 1200, 1600, 11)
        )
        self.assertAlmostEqual(variant.floor_load_kn_m2, 2400 * 9.80665 / 1000 / 4.8, places=2)
        self.assertAlmostEqual(variant.floor_load_kn_m2, 4.90, places=2)
        variant.floor_load_kn_m2 = 7.5
        self.assertEqual(variant.floor_load_kn_m2, 7.5)  # ручне значення зберігається
        # R-23: за категорією machine варіант дозволений на шарі «Виробництво», create_workcenter = True
        self.assertEqual(variant.allowed_layer_kind_ids.mapped('key'), ['production'])
        self.assertTrue(variant.create_workcenter)

    def test_unlink_guard(self):
        self.make_placement()
        with self.assertRaises(Exception) as ctx:
            self.variant.unlink()
        self.assertIn("використовується", str(ctx.exception))
