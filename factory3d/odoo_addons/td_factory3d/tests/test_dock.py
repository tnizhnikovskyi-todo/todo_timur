from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.td_factory3d.hooks import docks

from .common import F3DCase


@tagged("post_install", "-at_install", "f3d", "f3d_base")
class TestDockConstraints(F3DCase):
    def test_requires_side_no(self):  # AC-20
        with self.assertRaisesRegex(ValidationError, "Для воріт задайте сторону й номер"):
            self.dock_w1.td_kind = "dock"
        self.make_dock(self.dock_w1, "west", 1, 0.0, 5.0)
        self.assertEqual(self.dock_w1.td_kind, "dock")

    def test_unique_side_no(self):
        self.make_dock(self.dock_w1, "west", 1, 0.0, 5.0)
        with self.assertRaisesRegex(ValidationError, "уже існують"):
            self.make_dock(self.dock_e1, "west", 1, 0.0, 15.0)

    def test_kind_mismatch(self):
        with self.assertRaisesRegex(ValidationError, "лише для виду «Ворота»"):
            self.loc_in.td_dock_no = 2

    def test_kind_zone_forbidden(self):
        with self.assertRaisesRegex(ValidationError, "Місце зберігання може бути лише"):
            self.loc_in.td_kind = "zone"

    def test_coords_bounds(self):  # AC-23
        with self.assertRaises(ValidationError):
            self.make_dock(self.dock_w1, "west", 1, 151.0, 5.0)
        with self.assertRaises(ValidationError):
            self.make_dock(self.dock_e1, "east", 1, 150.0, -1.0)

    def test_capacity_default(self):
        self.assertEqual(self.loc_in.td_kind, "location")
        self.assertEqual(self.loc_in.td_capacity, 0)


@tagged("post_install", "-at_install", "f3d", "f3d_base")
class TestRegister(F3DCase):
    def test_register_west_east(self):  # AC-21
        self.make_dock(self.dock_w1, "west", 1, 0.0, 5.0)
        self.make_dock(self.dock_e1, "east", 1, 150.0, 5.0)
        in_type, out_type = self.wh.in_type_id, self.wh.out_type_id
        self.assertTrue(in_type.dispatch_management)
        self.assertIn(self.dock_w1, in_type.dock_ids)
        self.assertNotIn(self.dock_w1, out_type.dock_ids)
        self.assertIn(self.dock_e1, out_type.dock_ids)
        self.assertEqual(self.dock_w1.td_dock_picking_type_ids, in_type)

    def test_register_idempotent(self):
        self.make_dock(self.dock_w1, "west", 1, 0.0, 5.0)
        ptype = self.dock_w1.f3d_register_dock()
        self.dock_w1.f3d_register_dock()
        self.assertEqual(ptype, self.wh.in_type_id)
        self.assertEqual(self.wh.in_type_id.dock_ids.ids.count(self.dock_w1.id), 1)

    def test_hook_docks_on_synthetic(self):  # AC-11
        rows = [
            {
                "code": "DOCK-W1",
                "side": "west",
                "no": "1",
                "barcode": "UNLOAD-T1",
                "alias": "UNLOAD-T1",
                "x": "0.0",
                "y": "5.0",
                "accepts": "Плитні матеріали",
                "zone": "Z-RCV-1",
            },
            {
                "code": "DOCK-E1",
                "side": "east",
                "no": "1",
                "barcode": "DOCK-TE1",
                "alias": "",
                "x": "150.0",
                "y": "5.0",
                "accepts": "",
                "zone": "Z-OUT-1",
            },
            {
                "code": "DOCK-W9",
                "side": "west",
                "no": "9",
                "barcode": "NOPE",
                "alias": "",
                "x": "0.0",
                "y": "9.0",
                "accepts": "",
                "zone": "",
            },
        ]
        with self.with_data_file("scene_docks.csv", rows):
            res = docks.register(self.env)
        self.assertEqual(res["docks"], 2)
        self.assertEqual(self.dock_w1.td_code, "DOCK-W1")
        self.assertEqual(self.dock_w1.td_alias, "UNLOAD-T1")
        self.assertEqual(self.dock_w1.barcode, "UNLOAD-T1")
        self.assertEqual(self.dock_w1.td_accepts, self.categ_boards)
        self.assertEqual(self.wh.in_type_id.dock_ids, self.dock_w1)
        self.assertEqual(self.wh.out_type_id.dock_ids, self.dock_e1)
        with self.with_data_file("scene_docks.csv", rows):
            again = docks.register(self.env)
        self.assertEqual(again, res)
