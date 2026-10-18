from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from ..tools import params as P
from .flow import YardFlowCase, at, freeze


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardBooking(YardFlowCase):
    def test_confirm_syncs_batch(self):  # AC-04
        batch = self._batch(dock=self.dock_t1, start=at(10), end=at(11))
        visit = self._visit(batch_id=batch.id)
        booking = self._booking(visit, self.dock_t2, at(13), at(14))
        booking.action_confirm()
        self.assertEqual((batch.dock_id, batch.scheduled_date, batch.end_date), (self.dock_t2, at(13), at(14)))
        self.assertEqual(visit.state, "planned")
        Batch = self.env.registry["stock.picking.batch"]
        with patch.object(Batch, "write", autospec=True) as mocked:
            booking._sync_batch()
        mocked.assert_not_called()
        # пакет done не змінюється
        done = self._batch(dock=self.dock_t1, start=at(10), end=at(11))
        picking = done.picking_ids
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking._action_done()
        self.assertEqual(done.state, "done")
        visit2 = self._visit(batch_id=done.id)
        self._booking(visit2, self.dock_t4, at(15), at(16), confirm=True)
        self.assertEqual(done.dock_id, self.dock_t1)

    def test_batch_write_syncs_booking(self):  # AC-05
        batch = self._batch(dock=self.dock_t1, start=at(10), end=at(11))
        visit = self._visit(batch_id=batch.id)
        booking = self._booking(visit, self.dock_t1, at(10), at(11), confirm=True)
        batch.write({"scheduled_date": at(11), "end_date": at(12)})
        self.assertEqual((booking.slot_start, booking.slot_end), (at(11), at(12)))
        other = self._visit()
        self._booking(other, self.dock_t1, at(14), at(15), confirm=True)
        with self.assertRaises(ValidationError):
            batch.write({"scheduled_date": at(14, 30), "end_date": at(15, 30)})
        batch.invalidate_recordset()
        booking.invalidate_recordset()
        self.assertEqual(batch.scheduled_date, at(11))
        self.assertEqual(booking.slot_start, at(11))

    def test_cancel_reset(self):  # AC-06
        batch = self._batch(dock=self.dock_t1, start=at(10), end=at(11))
        visit = self._visit(batch_id=batch.id)
        booking = self._booking(visit, self.dock_t2, at(13), at(14), confirm=True)
        booking.action_cancel()
        self.assertEqual((booking.state, visit.state), ("cancelled", "draft"))
        self.assertEqual(batch.dock_id, self.dock_t2)
        booking.action_reset()
        self.assertEqual(booking.state, "requested")

    def test_overlap_and_buffer(self):  # AC-07, AC-08
        first = self._booking(self._visit(), self.dock_t1, at(13), at(14), confirm=True)
        self.assertEqual(first.name, "DOCK-T1 · 12.10 13:00–14:00")
        clash = self._booking(self._visit(), self.dock_t1, at(13, 30), at(14, 30))
        with self.assertRaisesRegex(ValidationError, "^Ворота DOCK-T1 уже заброньовані"):
            clash.action_confirm()
        clash.state = "requested"  # тестовий savepoint не відкочує кеш невдалого підтвердження
        self.assertIn("Перетин із запитом", first.warning or "")
        touch = self._booking(self._visit(), self.dock_t1, at(14), at(15))
        self.assertIn("Між слотами 0 хв (буфер 15 хв)", touch.warning)
        touch.action_confirm()
        self.assertEqual(touch.state, "confirmed")
        free = self._booking(self._visit(), self.dock_t1, at(15, 15), at(16, 15))
        self.assertFalse(free.warning)

    def test_calendar_and_sides(self):  # AC-09
        att = []
        for day in range(5):
            att += [
                Command.create({"name": "Р", "dayofweek": str(day), "hour_from": 7.0, "hour_to": 11.5}),
                Command.create({"name": "О", "dayofweek": str(day), "hour_from": 12.0, "hour_to": 15.5}),
            ]
        cal = self.env["resource.calendar"].create(
            {"name": "Зміна 1 (07:00–15:30)", "attendance_ids": [Command.clear()] + att}
        )
        P.set_param(self.env, "calendar_id", cal.id)
        late = self._booking(self._visit(), self.dock_t1, at(15), at(16))
        self.assertEqual(late.warning, "Слот поза зміною «Зміна 1 (07:00–15:30)» (07:00–15:30).")
        sat = self._booking(self._visit(), self.dock_t1, at(10, day=17), at(11, day=17))
        self.assertIn("День без зміни", sat.warning)
        P.set_param(self.env, "enforce_calendar", "True")
        with self.assertRaisesRegex(ValidationError, "Слот поза зміною"):
            late.action_confirm()
        P.set_param(self.env, "enforce_calendar", "False")
        with self.assertRaisesRegex(ValidationError, "на стороні"):
            self._booking(self._visit(visit_type="incoming"), self.dock_t3, at(8), at(9))
        batch = self._batch()
        with self.assertRaisesRegex(ValidationError, "не належать типу операцій"):
            self._booking(self._visit(batch_id=batch.id), self.dock_t5, at(8), at(9))
        with self.assertRaisesRegex(ValidationError, "довший за 24"):
            self._booking(self._visit(), self.dock_t1, at(8), at(8, day=14))

    def test_category_warning(self):  # AC-10
        self.dock_t1.td_accepts = [Command.set(self.categ_plates.ids)]
        edge = self._visit(batch_id=self._batch(product=self._product("T Крайка", 1.0, self.categ_edge)).id)
        booking = self._booking(edge, self.dock_t1, at(8), at(9))
        self.assertIn("Ворота DOCK-T1 приймають: Плитні матеріали. У рейсі є: Крайка.", booking.warning)
        booking.action_confirm()
        self.assertEqual(booking.state, "confirmed")
        hdf = self._visit(batch_id=self._batch().id)
        booking2 = self._booking(hdf, self.dock_t1, at(10), at(11))
        self.assertFalse(booking2.warning)

    def _queue_fixture(self):
        t = at(12, 50)
        v1 = self._visit(plate="V1")
        self._force(v1, "queued", arrived_at=at(12, 20))
        v2 = self._visit(plate="V2")
        self._booking(v2, self.dock_t2, at(13), at(14), confirm=True)
        self._force(v2, "queued", arrived_at=at(12, 40))
        v3 = self._visit(plate="V3")
        self._booking(v3, self.dock_t4, at(14), at(15), confirm=True)
        self._force(v3, "queued", arrived_at=at(12, 30))
        v4 = self._visit(plate="V4", priority="1")
        self._force(v4, "queued", arrived_at=at(12, 45))
        return t, v1, v2, v3, v4

    def test_queue_and_call(self):  # AC-11, AC-12, AC-13
        t, v1, v2, v3, v4 = self._queue_fixture()
        Visit = self.env["td.yard.visit"]
        with freeze(t):
            self.assertEqual(Visit._f3d_yard_queue("west"), v4 + v2 + v1 + v3)
            self.assertEqual(Visit._f3d_yard_queue("west", self.dock_t2), v4 + v2 + v1)
            called = Visit._f3d_yard_call_next(self.dock_t2)
            self.assertEqual(called, v2)
            self.assertEqual((v2.state, v4.state), ("at_dock", "queued"))
            self.assertEqual(v2.dock_id, self.dock_t2)
            v1.action_call_to_dock()
            self.assertEqual(v1.state, "at_dock")
            self.assertTrue(v1.dock_id.td_side == "west")
            booking = v1.booking_id
            self.assertEqual(
                (booking.source, booking.state, booking.slot_start, booking.slot_end),
                ("walk_in", "confirmed", t, at(13, 50)),
            )
            with self.assertRaisesRegex(UserError, "зайняті рейсом"):
                v4.action_call_to_dock(self.dock_t2)
            fresh = self._visit()
            fresh._set_state("arrived")
            with self.assertRaisesRegex(UserError, "лише фуру в черзі"):
                fresh.action_call_to_dock()

    def test_no_free_docks(self):  # AC-12
        t = at(12, 50)
        for dock in (self.dock_t1, self.dock_t2, self.dock_t4):
            holder = self._visit()
            self._booking(holder, dock, at(12), at(13), confirm=True)
            self._force(holder, "at_dock")
        visit = self._visit(batch_id=self._batch().id)
        self._force(visit, "queued", arrived_at=t)
        with freeze(t), self.assertRaisesRegex(UserError, "Немає вільних воріт"):
            visit.action_call_to_dock()

    def test_auto_call_next(self):  # AC-13
        t = at(12, 50)
        holder = self._visit()
        self._booking(holder, self.dock_t2, at(12), at(12, 40), confirm=True)
        self._force(holder, "handling", at_dock_at=at(12), handling_start_at=at(12, 5))
        nxt = self._visit()
        self._force(nxt, "queued", arrived_at=at(12, 30))
        with freeze(t):
            holder.action_leave()
        self.assertEqual(nxt.state, "queued")
        P.set_param(self.env, "auto_call_next", "True")
        holder2 = self._visit()
        self._booking(holder2, self.dock_t2, at(12, 41), at(12, 50), confirm=True)
        self._force(holder2, "handling", at_dock_at=at(12, 41))
        with freeze(t):
            holder2.action_leave()
        self.assertEqual((nxt.state, nxt.dock_id), ("at_dock", self.dock_t2))

    def test_create_visit_from_batch(self):  # AC-14
        company = self.env["res.partner"].create({"name": "Плитсервіс (демо)", "is_company": True})
        contact = self.env["res.partner"].create({"name": "Контакт", "parent_id": company.id})
        batch = self._batch(partner=contact, dock=self.dock_t1, start=at(10), end=at(11))
        self.user_dispatcher.write({"group_ids": [Command.link(self.env.ref("stock.group_stock_manager").id)]})
        action = batch.with_user(self.user_dispatcher).action_f3d_create_visit()
        visit = self.env["td.yard.visit"].browse(action["res_id"])
        self.assertEqual((visit.visit_type, visit.partner_id, visit.batch_id), ("incoming", company, batch))
        self.assertEqual(
            (
                visit.booking_ids.state,
                visit.booking_ids.dock_id,
                visit.booking_ids.slot_start,
                visit.booking_ids.slot_end,
            ),
            ("requested", self.dock_t1, at(10), at(11)),
        )
        self.assertEqual(batch.action_f3d_create_visit()["res_id"], visit.id)
        rows = self.env["stock.picking.batch"].search_read([("id", "=", batch.id)], ["td_visit_id", "td_plate"])
        self.assertEqual(rows[0]["td_visit_id"][0], visit.id)
        with self.assertRaises(UserError):
            self._batch(code="internal").action_f3d_create_visit()
