import re

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .flow import YardFlowCase, at, freeze


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardVisit(YardFlowCase):
    def test_create_defaults(self):  # AC-01
        visit = self._visit(visit_type="outgoing", plate=" аа 4512 кт ")
        self.assertRegex(visit.name, r"^YV/\d{4}/\d{5}$")
        self.assertEqual(visit.side, "east")
        self.assertEqual(visit.weighing_policy, "in_out")
        self.assertEqual(visit.plate, "АА 4512 КТ")
        self.assertEqual(visit.plate_norm, "AA4512KT")
        self.assertEqual(visit.plate_display, "АА 4512 КТ")
        self.assertEqual(self._visit(visit_type="other").side, "west")
        for bad in ("A", "AA#12"):
            with self.assertRaises(ValidationError):
                self._visit(plate=bad)

    def test_state_chain(self):  # AC-02
        batch = self._batch()
        visit = self._visit(batch_id=batch.id)
        self._booking(visit, self.dock_t1, at(13), at(14), confirm=True)
        self.assertEqual(visit.state, "planned")
        t = [at(12, 0), at(12, 10), at(12, 20), at(12, 30), at(12, 40), at(12, 50)]
        visit.action_arrive(ts=t[0])
        with freeze(t[1]):
            visit.action_admit()
        with freeze(t[2]):
            visit.action_call_to_dock()
        with freeze(t[3]):
            visit.action_start_handling()
        visit._set_state("weighed", ts=t[4])
        visit.action_leave(ts=t[5])
        self.assertEqual(visit.state, "left")
        self.assertEqual(
            [
                visit.arrived_at,
                visit.admitted_at,
                visit.at_dock_at,
                visit.handling_start_at,
                visit.weighed_out_at,
                visit.left_at,
            ],
            t,
        )
        self.assertEqual(visit.planned_at is not False, True)
        with self.assertRaisesRegex(UserError, "неможливий"):
            visit.action_arrive(ts=at(15))
        self.assertEqual(visit.arrived_at, t[0])
        with self.assertRaisesRegex(UserError, "неможливий"):
            self._visit().action_leave()

    def test_durations(self):  # AC-03
        visit = self._visit()
        self._booking(visit, self.dock_t1, at(9, 30), at(10, 30), confirm=True)
        visit.write(
            {
                "arrived_at": at(9, 10),
                "at_dock_at": at(9, 30),
                "handling_end_at": at(10, 50),
                "weighed_out_at": at(11, 0),
                "left_at": at(11, 5),
            }
        )
        self.assertEqual((visit.wait_min, visit.dock_min, visit.total_min, visit.late_min), (20.0, 80.0, 115.0, -20.0))
        visit.left_at = False
        self.assertFalse(visit.total_min)

    def test_permissions(self):  # AC-21
        visit = self._visit(plate="AA1111AA")
        visit._set_state("arrived")
        with self.assertRaises(AccessError):
            visit.with_user(self.user_reader).action_admit()
        stock_user = new_test_user(self.env, "yard_stock", groups="td_factory3d.group_td_user,stock.group_stock_user")
        with self.assertRaises(AccessError):
            visit.with_user(stock_user).action_admit()
        visit.with_user(self.user_guard).action_admit()
        self.assertEqual(visit.state, "queued")
        visit.with_user(stock_user).action_start_handling()
        self.assertEqual(visit.state, "handling")
        visit.with_user(self.user_guard).action_leave()
        self.assertEqual(visit.state, "left")
        draft = self._visit()
        with self.assertRaises(AccessError):
            draft.with_user(self.user_guard).action_cancel()
        draft.with_user(self.user_dispatcher).action_cancel()
        self.assertEqual(draft.state, "cancelled")
        arrived = self._visit()
        arrived._set_state("arrived")
        Wizard = self.env["td.yard.reject.wizard"].with_user(self.user_guard)
        Wizard.create({"visit_id": arrived.id, "reason": "x"}).action_confirm()
        self.assertEqual(arrived.state, "rejected")

    def test_unlink_reject_constraints(self):  # AC-22
        for state in ("draft", "planned", "cancelled"):
            visit = self._visit()
            self._force(visit, state)
            visit.unlink()
        arrived = self._visit()
        arrived._set_state("arrived")
        with self.assertRaises(UserError):
            arrived.unlink()
        visit = self._visit()
        booking = self._booking(visit, self.dock_t1, at(13), at(14))
        wizard = self.env["td.yard.reject.wizard"].create(
            {"visit_id": visit.id, "reason_code": "no_booking", "reason": "немає документів"}
        )
        wizard.action_confirm()
        self.assertEqual(visit.state, "rejected")
        self.assertEqual(visit.reject_reason, "Немає бронювання: немає документів")
        self.assertEqual(booking.state, "cancelled")
        batch = self._batch()
        self._visit(batch_id=batch.id)
        with self.assertRaisesRegex(ValidationError, "уже має активний рейс"):
            self._visit(batch_id=batch.id)
        with self.assertRaisesRegex(ValidationError, "не збігається"):
            self._visit(visit_type="outgoing", batch_id=self._batch().id)
        self.assertTrue(re.match(r"^YV/", visit.name))

    def test_change_batch_locked(self):
        visit = self._visit()
        self._force(visit, "queued")
        with self.assertRaisesRegex(UserError, "лише до пропуску"):
            visit.visit_type = "outgoing"

    def test_driver_onchange(self):  # AC-16 (onchange)
        carrier = self.env["res.partner"].create({"name": "Перевізник", "is_company": True, "td_is_carrier": True})
        driver = self.env["res.partner"].create(
            {
                "name": "Водій",
                "phone": "+380501112233",
                "td_is_driver": True,
                "td_carrier_id": carrier.id,
                "td_driver_doc": "ААА123456",
                "td_default_plate": "ВІ 7777 ЕН",
            }
        )
        visit = self.env["td.yard.visit"].new({"driver_id": driver.id})
        visit._onchange_driver_id()
        self.assertEqual(
            (visit.driver_phone, visit.driver_doc, visit.carrier_id, visit.plate),
            ("+380501112233", "ААА123456", carrier, "ВІ 7777 ЕН"),
        )
        with self.assertRaises(AccessError):
            driver.with_user(self.user_reader).read(["td_driver_doc"])
        for pl in ("A", "AA#1"):
            with self.assertRaises(ValidationError):
                driver.td_default_plate = pl

    def test_partner_visit_count(self):  # AC-16
        partner = self.env["res.partner"].create({"name": "Усі ролі", "is_company": True})
        self._visit(partner_id=partner.id)
        self._visit(carrier_id=partner.id)
        self._visit(driver_id=partner.id)
        self._visit()
        self.assertEqual(partner.td_visit_count, 3)
        self.assertEqual(partner.action_f3d_view_visits()["res_model"], "td.yard.visit")
        self.assertTrue(fields.Datetime.now())
