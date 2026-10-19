import datetime

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.tools.safe_eval import datetime as safe_datetime, safe_eval
from lxml import etree

from ..tools.event_codes import classify
from .common import AccessCase, FakeBioStar, freeze_time


@tagged("post_install", "-at_install", "f3d", "f3d_access")
class TestClassify(AccessCase):
    def test_table(self):
        table = {
            4102: ("pass", "card", False),
            4100: ("pass", "id_face", False),
            4865: ("pass", "finger", False),
            4867: ("pass", "face", False),
            5120: ("fail", False, False),
            4352: ("fail", False, False),
            6400: ("denied", False, "other"),
            6401: ("denied", False, "access_group"),
            6405: ("denied", False, "apb"),
            6406: ("denied", False, "timed_apb"),
            20480: ("door", False, False),
            20992: ("door", False, False),
            21248: ("door", False, False),
            26368: ("alarm", False, False),
            4608: ("alarm", False, False),
            12544: ("system", False, False),
            15104: ("system", False, False),
            8192: ("system", False, False),
            0: ("other", False, False),
        }
        for code, (etype, cred, deny) in table.items():
            with self.subTest(code=code):
                cls = classify(code)
                self.assertEqual((cls["event_type"], cls["credential"], cls["deny_reason"]), (etype, cred, deny))
        self.assertEqual(classify(20480)["door_state"], "unlocked")
        self.assertEqual(classify(21504)["alarm_reason"], "forced")
        self.assertEqual(classify(21760)["alarm_reason"], "held")
        self.assertEqual(classify(26368)["alarm_reason"], "fire")


@tagged("post_install", "-at_install", "f3d", "f3d_access")
class TestJournal(AccessCase):
    def _filter_domains(self):
        arch = etree.fromstring(self.env.ref("td_access.view_td_access_event_search").arch)
        ctx = {"datetime": safe_datetime, "context_today": datetime.date.today}
        return {f.get("name"): safe_eval(f.get("domain"), ctx) for f in arch.iter("filter") if f.get("domain")}

    def test_late_event(self):
        self.feed(
            self.prow(1, "2026-10-12T03:52:00.00Z", 4102, "TSTA1", tna="1"),
            self.prow(2, "2026-10-12T12:42:00.00Z", 4102, "TSTA1", tna="2"),
        )
        late = self.feed(self.prow(3, "2026-10-12T10:00:00.00Z", 4102, "TSTA1", tna="1"))
        self.assertEqual((late.attendance_action, late.process_state), ("late", "done"))
        att = self.attendances(self.emp_a)
        self.assertEqual(len(att), 1)
        self.assertTrue(att.check_out)
        self.assertFalse(self.emp_a.td_access_present)

    def test_future_then_processed(self):
        rows = [self.prow(1, "2026-10-12T03:53:00.00Z", 4102, "TSTA1", tna="1")]
        fake = FakeBioStar(events=rows)
        self.poll("2026-10-12 03:50:00", fake)
        ev = self.env["td.access.event"].search([("biostar_id", "=", "1")])
        self.assertEqual((ev.attendance_action, ev.process_state), ("future", "new"))
        self.assertFalse(self.attendances(self.emp_a))
        self.poll("2026-10-12 03:54:00", fake)
        self.assertEqual(ev.attendance_action, "checked_in")
        self.assertEqual(self.attendances(self.emp_a).check_in, datetime.datetime(2026, 10, 12, 3, 53))

    def test_filters_denied_apb(self):
        self.feed(
            self.prow(1, "2026-10-12T03:52:00.00Z", 4102, "TSTA1", tna="1"),
            self.prow(2, "2026-10-12T03:55:00.00Z", 4102, "TSTA1", tna="1"),
            self.prow(3, "2026-10-12T04:00:00.00Z", 6405, "TSTB2", tna="1"),
            self.prow(4, "2026-10-12T04:01:00.00Z", 6401, "TSTB2", tna="1"),
            self.prow(5, "2026-10-12T04:02:00.00Z", 5120, "TSTB2", tna="1"),
        )
        doms = self._filter_domains()
        Event = self.env["td.access.event"]
        self.assertEqual(Event.search_count(doms["filter_denied"]), 3)
        self.assertEqual(Event.search_count(doms["filter_apb"]), 2)
        self.assertFalse(self.attendances(self.emp_b))

    def test_unknown_user(self):
        ev = self.feed(self.prow(1, "2026-10-12T08:05:00.00Z", 4102, "1", where="srv"))
        self.assertTrue(ev.unknown_user)
        link = self.env["td.access.user.link"].search([("biostar_user_id", "=", "1")])
        self.assertEqual(link.match, "none")
        self.assertEqual(self.env["td.access.event"].search_count(self._filter_domains()["filter_unknown"]), 1)
        self.assertEqual(self.env["hr.attendance"].search_count([("in_mode", "=", "biostar")]), 0)

    def test_immediate_match(self):
        ev = self.feed(self.prow(1, "2026-10-12T03:52:00.00Z", 4102, "OPTSTC", tna="1"))
        link = self.env["td.access.user.link"].search([("biostar_user_id", "=", "OPTSTC")])
        self.assertEqual((link.match, link.employee_id), ("code", self.emp_c))
        self.assertEqual((ev.employee_id, ev.attendance_action), (self.emp_c, "checked_in"))
        self.assertFalse(ev.unknown_user)

    def test_door_states(self):
        door = self.door_turn_1
        self.assertEqual(door.state, "unknown")
        self.feed(
            self.prow(1, "2026-10-12T03:52:00.00Z", 20480, None), self.prow(2, "2026-10-12T03:52:01.00Z", 20992, None)
        )
        self.assertEqual(door.state, "open")
        self.feed(self.prow(3, "2026-10-12T03:52:06.00Z", 21248, None))
        self.assertEqual(door.state, "closed")
        self.feed(self.prow(4, "2026-10-12T03:52:01.00Z", 20992, None))
        self.assertEqual(door.state, "closed")
        self.feed(self.prow(5, "2026-10-12T03:53:00.00Z", 21504, None))
        self.assertEqual((door.state, door.alarm, door.alarm_reason), ("forced", True, "forced"))
        self.feed(self.prow(6, "2026-10-12T03:53:30.00Z", 21248, None))
        self.assertEqual((door.state, door.alarm), ("closed", False))

    def test_fire_alarm_all_doors(self):
        row = self.make_row(1, "2026-10-12T09:00:00.00Z", 26368, device="5390001", door=None)
        self.feed(row)
        doors = self.env["td.access.door"].search([("server_id", "=", self.server.id)])
        self.assertEqual(len(doors), 5)
        self.assertTrue(all(d.alarm and d.alarm_reason == "fire" for d in doors))

    def test_ack_alarm_rights(self):
        self.door_turn_1.sudo().write({"alarm": True, "alarm_reason": "fire"})
        self.door_turn_1.with_user(self.user_security).action_ack_alarm()
        self.assertFalse(self.door_turn_1.alarm)
        with self.assertRaises(AccessError):
            self.door_turn_1.with_user(self.user_security).write({"name": "X"})

    @mute_logger("odoo.addons.td_access.models.td_access_event")
    def test_validation_error_isolated(self):
        self.env["hr.attendance"].sudo().create(
            {"employee_id": self.emp_a.id, "check_in": "2026-10-12 03:00:00", "check_out": "2026-10-12 05:00:00"}
        )
        evs = self.feed(
            self.prow(1, "2026-10-12T04:00:00.00Z", 4102, "TSTA1", tna="1"),
            self.prow(2, "2026-10-12T04:05:00.00Z", 4102, "TSTB2", tna="1"),
        )
        ev_a, ev_b = evs.sorted("biostar_id")
        self.assertEqual(ev_a.process_state, "error")
        self.assertIn("Cannot create new attendance record", ev_a.error_message)
        self.assertEqual(ev_b.process_state, "done")

    @mute_logger("odoo.addons.td_access.models.td_access_event")
    def test_reprocess_wizard(self):
        manual = (
            self.env["hr.attendance"]
            .sudo()
            .create(
                {"employee_id": self.emp_a.id, "check_in": "2026-10-12 03:00:00", "check_out": "2026-10-12 05:00:00"}
            )
        )
        ev = self.feed(self.prow(1, "2026-10-12T04:00:00.00Z", 4102, "TSTA1", tna="1"))
        self.assertEqual(ev.process_state, "error")
        manual.unlink()
        wiz = self.env["td.access.event.reprocess.wizard"].create(
            {
                "mode": "reprocess",
                "server_id": self.server.id,
                "only_errors": True,
                "date_from": "2026-10-12 00:00:00",
                "date_to": "2026-10-12 23:00:00",
            }
        )
        with freeze_time("2026-10-12 23:30:00"):
            wiz.action_run()
        self.assertEqual((ev.process_state, ev.attendance_action), ("done", "checked_in"))
        self.assertIn("Оброблено", wiz.result)
        self.assertEqual(len(self.attendances(self.emp_a)), 1)
        # повторна обробка «done» не множить відмітки
        ev.action_reprocess()
        self.assertEqual(len(self.attendances(self.emp_a)), 1)

    def test_repoll_wizard(self):
        fake = FakeBioStar(events=[self.prow(1, "2026-10-12T03:52:00.00Z", 4102, "TSTA1", tna="1")])
        vals = {
            "mode": "repoll",
            "server_id": self.server.id,
            "date_from": "2026-10-12 00:00:00",
            "date_to": "2026-10-12 23:00:00",
        }
        from ..tools import params as P

        P.set_param(self.env, "read_enabled", "False")
        with self.patch_client(fake), self.assertRaises(UserError):
            self.env["td.access.event.reprocess.wizard"].create(vals).action_run()
        P.set_param(self.env, "read_enabled", "True")
        with self.patch_client(fake), freeze_time("2026-10-12 23:30:00"):
            wiz = self.env["td.access.event.reprocess.wizard"].create(vals)
            wiz.action_run()
        self.assertEqual(fake.search_calls[-1]["since"], wiz.date_from)
        self.assertEqual(fake.search_calls[-1]["until"], wiz.date_to)
        self.assertEqual(self.env["td.access.event"].search_count([("biostar_id", "=", "1")]), 1)
