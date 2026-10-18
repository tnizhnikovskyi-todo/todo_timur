import base64
from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools import params as P
from ..tools.plate import display_plate, normalize_plate
from .flow import at, freeze
from .gate_case import GateCase, capture_ms, lpr_event

NOW = datetime(2026, 10, 14, 5, 15, 10)
CAPTURE = datetime(2026, 10, 14, 5, 15, 5, 507000)
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2000


def b64(raw):
    return base64.b64encode(raw).decode()


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardLpr(GateCase):
    Event = None

    def setUp(self):
        super().setUp()
        self.Event = self.env["f3d.yard.lpr.event"]

    def _plain(self, n, plate, ts=None, **kw):
        ts = ts or at(12, 40)
        return lpr_event(
            n,
            carID=str(n),
            plateText=plate,
            plateUnicode=None,
            capture_timestamp=capture_ms(ts),
            plateListDescription=kw.pop("description", ""),
            **kw,
        )

    def _planned(self, plate, start=None, dock=None, batch=None):
        start = start or at(13)
        visit = self._visit(batch_id=(batch or self._batch()).id, plate=plate)
        self._booking(visit, dock or self.dock_t1, start, start + timedelta(hours=1), confirm=True)
        return visit

    def test_payload_to_event(self):  # AC-23
        with freeze(NOW):
            self.push(lpr_event())
            ev = self.Event.search([])
            self.assertEqual(len(ev), 1)
            self.assertEqual(
                (ev.camera_code, ev.gate_id, ev.direction, ev.car_state),
                ("CAM-05", self.gate_w, "in", "new"),
            )
            self.assertEqual((ev.plate_raw, ev.plate_unicode, ev.plate_norm), ("AA4512KT", "АА4512КТ", "AA4512KT"))
            self.assertEqual(ev.confidence, 0.912)
            self.assertEqual((ev.plate_list, ev.plate_list_mode), ("f3d_bookings", "allow"))
            self.assertEqual(ev.plate_list_description, "BATCH/OUT/00004 DOCK-E2 Меблі Дім (демо)")
            self.assertEqual(ev.dedup_key, "CAM-05|12891|2117398")
            self.assertEqual(ev.ts.replace(microsecond=0), CAPTURE.replace(microsecond=0))
            self.assertEqual(ev.match_state, "unmatched")
            future = self.recv(lpr_event(2, capture_timestamp="1792391105507"))
            self.assertEqual(future.ts, NOW)
            self.assertIn("Час камери відкинуто", future.note)
            no_ts = self.recv(lpr_event(3, capture_timestamp=None, datetime="20261014 051505507"))
            self.assertEqual(no_ts.ts, NOW)
            old = self.recv(lpr_event(4, capture_timestamp=capture_ms(NOW - timedelta(days=31))))
            self.assertEqual(old.ts, NOW)

    def test_dedup_and_update(self):  # AC-24
        with freeze(NOW):
            first = self.recv(lpr_event(1, plateConfidence="0.85"))
            again = self.recv(lpr_event(1, plateConfidence="0.85"))
            self.assertEqual(first, again)
            upd = self.recv(
                lpr_event(2, carState="update", plateConfidence="0.97", plateText="AA4513KT", plateUnicode=None)
            )
            self.assertEqual(upd, first)
            self.assertEqual((first.confidence, first.plate_norm), (0.97, "AA4513KT"))
            self.assertEqual(self.Event.search_count([]), 1)
            no_car = self.recv(lpr_event(7, carID=None, packetCounter=None))
            self.assertEqual(no_car.dedup_key, "evt|%s" % lpr_event(7)["event_id"])

    def test_lost_and_expire(self):  # AC-25
        with freeze(NOW):
            ev = self.recv(lpr_event(1))
            self.assertTrue(ev.kpp_alert)
            lost = self.recv(lpr_event(2, carState="lost"))
            self.assertEqual(lost, ev)
            self.assertEqual((ev.match_state, ev.kpp_alert), ("expired", False))
            self.assertTrue(ev.lost_at)
            self.assertEqual(self.Event.search_count([]), 1)
            alone = self.recv(lpr_event(3, carState="lost", carID="777"))
            self.assertEqual((alone.car_state, alone.match_state), ("lost", "ignored"))
            other = self.recv(lpr_event(4, carID="888"))
            self.assertTrue(other.kpp_alert)
        with freeze(NOW + timedelta(minutes=31)):
            self.env["f3d.yard.visit"]._cron_queue()
        self.assertEqual((other.match_state, other.kpp_alert), ("expired", False))

    def test_images(self):  # AC-26
        with freeze(NOW):
            ev = self.recv(
                lpr_event(1, imageArray=[b64(JPEG)], imagesURI=["https://10.90.2.5/a.jpg"], imageFile="/tmp/x.jpg")
            )
            att = ev.image_attachment_id
            self.assertEqual((att.mimetype, att.res_model, att.res_id), ("image/jpeg", ev._name, ev.id))
            self.assertEqual(ev.image_url, "https://10.90.2.5/a.jpg")
            big = self.recv(lpr_event(2, carID="2", imageArray=[b64(JPEG + b"0" * 1_500_000)]))
            self.assertFalse(big.image_attachment_id)
            self.assertIn("Знімок відхилено", big.note)
            text = self.recv(lpr_event(3, carID="3", imageArray=[b64(b"hello world")]))
            self.assertFalse(text.image_attachment_id)
            self.assertIn("Знімок відхилено", text.note)
            P.set_param(self.env, "lpr_store_images", "False")
            off = self.recv(lpr_event(4, carID="4", imageArray=[b64(JPEG)]))
            self.assertFalse(off.image_attachment_id)

    def test_normalize(self):  # AC-27
        for raw, norm in (
            ("АА 4512 КТ", "AA4512KT"),
            ("aa-4512-kt", "AA4512KT"),
            ("КА 0001 ВХ", "KA0001BX"),
            ("ВІ 7777 ЕН", "BI7777EH"),
            ("ЖЖ1234", "ЖЖ1234"),
            ("", ""),
        ):
            self.assertEqual(normalize_plate(raw), norm)
        self.assertEqual(display_plate("аа4512кт"), "АА 4512 КТ")
        self.assertEqual(display_plate("ЖЖ1234"), "ЖЖ1234")

    def test_match_by_plate(self):  # AC-28
        visit = self._planned("АА7310КТ")
        now = at(12, 40, 12) + timedelta(seconds=5)
        with freeze(now):
            ev = self.recv(self._plain(1, "AA7310KT"))
            self.assertEqual((ev.match_state, ev.visit_id), ("matched", visit))
            self.assertEqual((visit.state, visit.arrived_at, visit.gate_in_id), ("arrived", at(12, 40), self.gate_w))
            again = self.recv(self._plain(2, "AA7310KT"))
            self.assertIn("Повторне розпізнавання", again.note)
            self.assertEqual(visit.state, "arrived")
            far = self._planned("АА7320КТ", at(18), self.dock_t2)
            self.assertFalse(far.plate_norm == "")
            self.assertEqual(self.recv(self._plain(3, "AA7320KT")).match_state, "unmatched")
            handling = self._force(self._visit(visit_type="outgoing", plate="АА4512КТ"), "handling")
            out = self.recv(self._plain(4, "AA4512KT", sensorProviderID="CAM-06"))
            self.assertEqual((out.match_state, handling.gate_out_id), ("matched", self.gate_e))

    def test_match_by_documents(self):  # AC-29
        batch = self._batch()
        batch.name = "WH/IN/00131"
        visit = self._planned("", batch=batch)
        desc = "WH/IN/00131 DOCK-W2 Плитсервіс (демо)"
        now = at(12, 40, 12) + timedelta(seconds=5)
        with freeze(now):
            ev = self.recv(self._plain(1, "AA7310KT", description=desc))
            self.assertEqual((ev.match_state, ev.visit_id), ("matched", visit))
            self.assertEqual(visit.plate_norm, "AA7310KT")
            self.assertEqual(visit.state, "arrived")
            other = self._planned("ВХ1234ВХ", at(13), self.dock_t2, batch=self._batch())
            other.batch_id.name = "WH/IN/00132"
            ev2 = self.recv(self._plain(2, "AA9999KT", description="WH/IN/00132 DOCK-W2 X"))
            self.assertTrue(ev2.kpp_alert)
            self.assertIn("≠", ev2.note)
            self.assertFalse(self.cmds())
            dup1 = self._planned("АА5555КТ", at(13), self.dock_t4)
            dup2 = self._planned("АА5555КТ", at(15), self.dock_t1, batch=self._batch())
            dup2.batch_id.name = "WH/IN/00140"
            ev3 = self.recv(self._plain(3, "AA5555KT", description="WH/IN/00140 DOCK-W2 X"))
            self.assertEqual(ev3.visit_id, dup2)
            self.assertNotEqual(ev3.visit_id, dup1)

    def test_rejections(self):  # AC-30
        with freeze(NOW):
            low = self.recv(lpr_event(1, plateConfidence="0.62"))
            self.assertEqual((low.match_state, low.kpp_alert), ("low_confidence", True))
            self.assertIn("0.62", low.note)
            unknown = self.recv(lpr_event(2, sensorProviderID="CAM-99"))
            self.assertEqual(
                (unknown.match_state, unknown.gate_id.id, unknown.kpp_alert), ("unknown_camera", False, False)
            )
            visit = self._planned("АА7310КТ", NOW + timedelta(hours=1))
            self.gate_w.last_plate = "KEEP"
            P.set_param(self.env, "read_enabled", "False")
            ignored = self.recv(lpr_event(3, plateText="AA7310KT", plateUnicode="АА7310КТ", carID="3"))
            self.assertEqual(ignored.match_state, "ignored")
            self.assertEqual((self.gate_w.last_plate, visit.state), ("KEEP", "planned"))

    def test_unmatched_no_command(self):  # AC-31
        gate = self.gate_w
        gate.mode = "auto"
        with freeze(NOW):
            self.put(gate, "photocell", 0, NOW)
            ev = self.recv(lpr_event(1))
        self.assertEqual((ev.match_state, ev.kpp_alert), ("unmatched", True))
        self.assertFalse(self.cmds())

    def test_walk_in(self):  # AC-32
        with freeze(NOW):
            ev = self.recv(lpr_event(1))
            Wizard = self.env["f3d.yard.walkin.wizard"]
            guard = Wizard.with_user(self.user_guard).with_context(default_event_id=ev.id)
            for i in range(5):
                visit = self._visit(plate="АА10%02dКТ" % i)
                visit.write({"is_walk_in": True, "state": "arrived", "arrived_at": NOW})
            with self.assertRaisesRegex(UserError, r"\(5\)"):
                guard.create({}).action_create()
            disp = Wizard.with_user(self.user_dispatcher).with_context(default_event_id=ev.id)
            wiz = disp.create({})
            self.assertEqual((wiz.plate, wiz.gate_id), ("АА4512КТ", self.gate_w))
            wiz.action_create()
            visit = ev.visit_id
            self.assertEqual(
                (visit.state, visit.is_walk_in, ev.match_state, ev.kpp_alert), ("arrived", True, "handled", False)
            )
            P.set_param(self.env, "walk_in_allowed", "False")
            with self.assertRaisesRegex(UserError, "лише диспетчер"):
                guard.create({}).action_create()

    def test_reject(self):  # AC-33
        with freeze(NOW):
            ev = self.recv(lpr_event(1))
            wiz = (
                self.env["f3d.yard.reject.wizard"]
                .with_user(self.user_guard)
                .with_context(default_event_id=ev.id)
                .create({"reason": "Немає документів", "reason_code": "no_booking"})
            )
            wiz.action_confirm()
            visit = ev.visit_id
            self.assertEqual((visit.visit_type, visit.state, visit.is_walk_in), ("other", "rejected", True))
            self.assertEqual((ev.match_state, ev.kpp_alert), ("handled", False))
            planned = self._planned("АА7310КТ", NOW + timedelta(hours=2))
            self.env["f3d.yard.reject.wizard"].with_user(self.user_guard).with_context(
                default_visit_id=planned.id
            ).create({"reason": "x"}).action_confirm()
            self.assertEqual(planned.state, "rejected")
            self.assertTrue(all(b.state == "cancelled" for b in planned.booking_ids))
