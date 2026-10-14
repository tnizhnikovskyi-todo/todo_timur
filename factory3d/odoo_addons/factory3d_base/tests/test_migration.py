from odoo.tests import tagged

from odoo.addons.factory3d_base.hooks import batches, uninstall_hook, x_fields

from .common import F3DCase

X_SPEC = x_fields.STOCK_PICKING_X_FIELDS


class MigrationCase(F3DCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        x_fields.restore_manual_fields(env, 'stock.picking', X_SPEC)
        cls.make_dock(cls, cls.dock_w1, 'west', 1, 0.0, 5.0)
        cls.dock_w1.f3d_code = 'DOCK-T1'
        cls.make_dock(cls, cls.dock_e1, 'east', 1, 150.0, 5.0)
        cls.dock_e1.f3d_code = 'DOCK-TE1'
        cls.eq.f3d_code = 'FL-T'
        Product = env['product.product'].create({'name': 'Товар-М'})
        in_type, out_type = cls.wh.in_type_id, cls.wh.out_type_id
        int_type = cls.wh.int_type_id
        cls.p1 = cls.make_picking(cls, in_type, Product)
        cls.p2 = cls.make_picking(cls, in_type, Product)
        cls.p3 = cls.make_picking(cls, out_type, Product)
        cls.p4 = cls.make_picking(cls, int_type, Product)
        cls.pickings = cls.p1 | cls.p2 | cls.p3 | cls.p4
        env.flush_all()
        for picking, state in ((cls.p1, 'done'), (cls.p2, 'done'), (cls.p3, 'assigned'), (cls.p4, 'done')):
            env.cr.execute("UPDATE stock_picking SET state=%s WHERE id=%s", (state, picking.id))
            env.cr.execute("UPDATE stock_move SET state=%s WHERE picking_id=%s", (state, picking.id))
        env.cr.execute("UPDATE stock_picking SET x_dock='DOCK-T1' WHERE id IN %s", ((cls.p1.id, cls.p2.id),))
        env.cr.execute("UPDATE stock_picking SET x_dock='DOCK-TE1', x_truck='TRUCK-OUT-T1' WHERE id=%s", (cls.p3.id,))
        env.cr.execute("UPDATE stock_picking SET x_vehicle='FL-T' WHERE id=%s", (cls.p4.id,))
        env['stock.picking'].invalidate_model()
        env['stock.move'].invalidate_model()
        cls.demo_view = env['ir.ui.view'].create({
            'name': 'demo dock', 'model': 'stock.picking', 'inherit_id': env.ref('stock.view_picking_form').id,
            'arch': '<field name="origin" position="after"><field name="x_dock"/></field>'})
        env['ir.model.data'].create({
            'module': 'factory3d', 'name': 'view_picking_form_dock', 'model': 'ir.ui.view',
            'res_id': cls.demo_view.id})

    def _field_names(self):
        return set(self.env['ir.model.fields'].search(
            [('model', '=', 'stock.picking'), ('name', 'in', ['x_dock', 'x_truck', 'x_vehicle'])]).mapped('name'))


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestBatchMigration(MigrationCase):

    def test_full_cycle_synthetic(self):  # AC-25…AC-28
        res = batches.migrate(self.env)
        self.assertEqual((res['batches_created'], res['batches_updated']), (4, 0))
        self.assertEqual((res['pickings_attached'], res['pickings_total_in_batches']), (4, 4))
        check = batches.verify(self.env)
        self.assertEqual(check, {'mismatches': [], 'moves_changed': 0})
        self.assertEqual(self.p3.batch_id.f3d_code, 'TRUCK-OUT-T1')
        self.assertEqual(self.p3.batch_id.f3d_truck, 'TRUCK-OUT-T1')
        self.assertEqual(self.p3.batch_id.dock_id, self.dock_e1)
        self.assertEqual(self.p1.batch_id.dock_id, self.dock_w1)
        self.assertFalse(self.p1.batch_id.f3d_code)
        self.assertEqual(self.p4.batch_id.f3d_vehicle_id, self.eq)
        self.assertFalse(self.p4.batch_id.dock_id)
        self.assertEqual(self.p1.batch_id.picking_type_id, self.p1.picking_type_id)
        dropped = x_fields.drop_demo(self.env, check['mismatches'])
        self.assertEqual((dropped['views_dropped'], dropped['fields_dropped']), (1, 3))
        self.assertFalse(self._field_names())
        self.assertFalse(self.demo_view.exists())

    def test_done_pickings_attached(self):
        batches.migrate(self.env)
        self.assertEqual({self.p1.batch_id.state, self.p2.batch_id.state, self.p4.batch_id.state}, {'done'})
        self.assertEqual(self.p3.batch_id.state, 'in_progress')
        self.assertEqual(len(self.p1.batch_id | self.p2.batch_id | self.p3.batch_id | self.p4.batch_id), 4)

    def test_moves_untouched(self):
        before = self.snapshot_moves(self.pickings)
        batches.migrate(self.env)
        self.assertEqual(before, self.snapshot_moves(self.pickings))
        self.assertEqual(batches.verify(self.env)['moves_changed'], 0)

    def test_rerun_idempotent(self):
        batches.migrate(self.env)
        count = self.env['stock.picking.batch'].search_count([])
        res = batches.migrate(self.env)
        self.assertEqual((res['batches_created'], res['pickings_attached']), (0, 0))
        self.assertEqual(self.env['stock.picking.batch'].search_count([]), count)

    def test_keep_x_fields(self):  # AC-29
        self.env['ir.config_parameter'].sudo().set_param('factory3d.base.keep_x_fields', 'True')
        batches.migrate(self.env)
        res = x_fields.drop_demo(self.env, [])
        self.assertEqual((res['views_dropped'], res['fields_dropped']), (0, 0))
        self.assertEqual(self._field_names(), {'x_dock', 'x_truck', 'x_vehicle'})

    def test_mismatch_blocks_drop(self):
        self.env.cr.execute("UPDATE stock_picking SET x_dock='DOCK-NOPE' WHERE id=%s", (self.p1.id,))
        batches.migrate(self.env)
        check = batches.verify(self.env)
        self.assertEqual(len(check['mismatches']), 1)
        self.assertIn('x_dock=DOCK-NOPE', check['mismatches'][0])
        x_fields.drop_demo(self.env, check['mismatches'])
        self.assertEqual(self._field_names(), {'x_dock', 'x_truck', 'x_vehicle'})

    def test_skipped_without_fields(self):
        x_fields.drop_demo(self.env, [])
        self.assertEqual(batches.migrate(self.env), {'skipped': True})
        self.assertEqual(x_fields.read_manual_field(self.env, 'stock.picking', 'x_dock'), {})


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestUninstall(MigrationCase):

    def test_restore_x_fields(self):  # AC-31, AC-48
        batches.migrate(self.env)
        x_fields.drop_demo(self.env, [])
        self.assertFalse(self._field_names())
        uninstall_hook(self.env)
        self.assertEqual(self._field_names(), {'x_dock', 'x_truck', 'x_vehicle'})
        read = x_fields.read_manual_field
        self.assertEqual(read(self.env, 'stock.picking', 'x_dock'),
                         {self.p1.id: 'DOCK-T1', self.p2.id: 'DOCK-T1', self.p3.id: 'DOCK-TE1'})
        self.assertEqual(read(self.env, 'stock.picking', 'x_truck'), {self.p3.id: 'TRUCK-OUT-T1'})
        self.assertEqual(read(self.env, 'stock.picking', 'x_vehicle'), {self.p4.id: 'FL-T'})
        self.assertFalse(self.env['ir.config_parameter'].sudo().search([('key', '=like', 'factory3d.base.%')]))
