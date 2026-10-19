from odoo.tests import tagged

from .flow import YardFlowCase, at


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardPicking(YardFlowCase):
    def test_expected_weight(self):  # AC-15
        batch = self._batch()
        visit = self._visit(batch_id=batch.id)
        picking = batch.picking_ids
        self.assertEqual(picking.td_expected_weight_kg, 11200.0)
        self.assertEqual(picking.td_visit_id, visit)
        self.assertEqual(visit.expected_kg, 11200.0)
        self.assertEqual(visit.weight_check, "none")
        moves = picking.move_ids
        moves[0].quantity = 72
        moves[1].quantity = 48
        moves.picked = True
        picking.with_context(cancel_backorder=True)._action_done()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.td_expected_weight_kg, 6720.0)

    def test_net_distribution_and_deviation(self):  # AC-18, AC-19
        batch = self._batch()
        picking = batch.picking_ids
        picking.user_id = self.env.user
        visit = self._visit(batch_id=batch.id)
        visit._td_yard_write_pickings(net=11520.0)
        self.assertEqual((picking.td_weight_check, picking.td_weight_deviation_pct), ("deviation", 2.86))
        visit._td_yard_write_pickings(net=11520.0)
        acts = picking.activity_ids.filtered(lambda a: a.summary == "Відхилення нетто")
        self.assertEqual(len(acts), 1)
        visit._td_yard_write_pickings(net=11300.0)
        self.assertEqual((picking.td_weight_check, picking.td_weight_deviation_pct), ("ok", 0.89))
        small = self._batch(lines=((6600, None),), product=self._product("T Один", 1.0, self.categ_hdf))
        v_small = self._visit(batch_id=small.id)
        v_small._td_yard_write_pickings(net=6750.0)
        self.assertEqual(
            (small.picking_ids.td_weight_check, small.picking_ids.td_weight_deviation_pct), ("deviation", 2.27)
        )

    def test_no_reference_and_shipping(self):  # AC-19
        batch = self._batch(code="outgoing", lines=((10, self.product_nw),))
        visit = self._visit(visit_type="outgoing", batch_id=batch.id)
        visit._td_yard_write_pickings(net=7380.0)
        picking = batch.picking_ids
        self.assertEqual(picking.td_weight_check, "no_reference")
        self.assertEqual(picking.shipping_weight, 7380.0)

    def test_two_pickings_split(self):  # AC-19
        prod = self._product("T Кг", 1.0, self.categ_hdf)
        batch = self._batch(lines=((8000, prod),))
        second = self._batch(lines=((4000, prod),))
        second.picking_ids.write({"batch_id": batch.id})
        visit = self._visit(batch_id=batch.id)
        visit._td_yard_write_pickings(net=12300.0)
        self.assertEqual(sorted(batch.picking_ids.mapped("td_net_weight_kg")), [4100.0, 8200.0])

    def test_auto_handling(self):  # AC-20
        batch = self._batch(lines=((10, None),))
        visit = self._visit(batch_id=batch.id)
        self._force(visit, "at_dock", at_dock_at=at(10))
        move = batch.picking_ids.move_ids
        move.with_context(f3d_yard_no_auto=True).quantity = 4
        self.assertEqual(visit.state, "at_dock")
        move.quantity = 12
        move.picked = True
        self.assertEqual(visit.state, "handling")
        self.assertTrue(visit.handling_start_at)
        batch.picking_ids._action_done()
        self.assertTrue(visit.handling_end_at)
        self.assertEqual(visit.state, "handling")

    def test_auto_handling_no_auto_done(self):  # AC-20
        batch = self._batch(lines=((10, None),))
        visit = self._visit(batch_id=batch.id)
        self._force(visit, "handling", at_dock_at=at(10), handling_start_at=at(10))
        batch.picking_ids.move_ids.quantity = 10
        batch.picking_ids.move_ids.picked = True
        batch.picking_ids.with_context(f3d_yard_no_auto=True)._action_done()
        self.assertFalse(visit.handling_end_at)
