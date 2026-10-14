from odoo.tests import tagged

from .common import F3DCase


class BatchCase(F3DCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env['product.product']
        cls.p_board = Product.create({'name': 'ДСП-Т', 'categ_id': cls.categ_boards.id})
        cls.p_hdf = Product.create({'name': 'ХДФ-Т', 'categ_id': cls.categ_hdf.id})
        cls.p_edge = Product.create({'name': 'Крайка-Т', 'categ_id': cls.categ_edge.id})
        cls.make_dock(cls, cls.dock_w1, 'west', 1, 0.0, 5.0)

    def _batch(self, products, **vals):
        picking = self.make_picking(self.wh.in_type_id, products)
        return picking, self.make_batch(
            picking, dock=self.dock_w1, picking_type_id=self.wh.in_type_id.id, **vals)


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestDockWarning(BatchCase):

    def test_warning_text(self):  # AC-22
        self.dock_w1.f3d_accepts = self.categ_boards
        self.dock_w1.f3d_code = 'DOCK-T1'
        _picking, batch = self._batch(self.p_edge)
        self.assertEqual(
            batch.f3d_dock_warning,
            'Ворота DOCK-T1 приймають: Плитні матеріали. У пакеті є: Крайка.')

    def test_child_category_ok(self):
        self.dock_w1.f3d_accepts = self.categ_boards
        _picking, batch = self._batch(self.p_hdf | self.p_board)
        self.assertFalse(batch.f3d_dock_warning)

    def test_no_categories(self):
        _picking, batch = self._batch(self.p_edge)
        self.assertFalse(batch.f3d_dock_warning)


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestPickingRelated(BatchCase):

    def test_related_fields(self):  # AC-51
        self.dock_w1.f3d_code = 'D-1'
        self.eq.f3d_code = 'FL-T'
        picking, batch = self._batch(
            self.p_board, f3d_code='TRUCK-T-1', f3d_truck='Фура плит (тест)', f3d_vehicle_id=self.eq.id)
        self.assertEqual(batch.f3d_dock_code, 'D-1')
        self.assertEqual(picking.f3d_dock_code, 'D-1')
        self.assertEqual(picking.f3d_dock_id, self.dock_w1)
        self.assertEqual(picking.f3d_truck_code, 'TRUCK-T-1')
        self.assertEqual(picking.f3d_truck, 'Фура плит (тест)')
        self.assertEqual(picking.f3d_vehicle_id.f3d_code, 'FL-T')
        alone = self.make_picking(self.wh.in_type_id, self.p_board)
        self.assertFalse(alone.f3d_dock_code)
        self.assertFalse(alone.f3d_truck_code)

    def test_search_read(self):
        self.dock_w1.f3d_code = 'D-1'
        self.eq.f3d_code = 'FL-T'
        picking, _batch = self._batch(
            self.p_board, f3d_code='TRUCK-T-1', f3d_truck='Фура', f3d_vehicle_id=self.eq.id)
        rows = self.env['stock.picking'].search_read(
            [('id', '=', picking.id)],
            ['f3d_dock_code', 'f3d_truck_code', 'f3d_truck', 'f3d_vehicle_id'])
        self.assertEqual(rows[0]['f3d_dock_code'], 'D-1')
        self.assertEqual(rows[0]['f3d_truck_code'], 'TRUCK-T-1')
        self.assertEqual(rows[0]['f3d_vehicle_id'][0], self.eq.id)
