"""AC-86, AC-88 (SPEC td_fire_safety R-16a, R-16b): двері виходів у СКУД і зняття блокувань після навчання."""

from freezegun import freeze_time
from odoo.tests import tagged

from odoo.addons.td_access.tests.common import AccessCase, make_row

EXIT_DOORS = {
    "EX-S1": "11",
    "EX-S2": "12",
    "EX-S3": "13",
    "EX-S4": "14",
    "EX-S5": "15",
    "EX-S6": "16",
    "EX-N1": "17",
    "EX-N2": "18",
    "EX-N3": "19",
    "EX-N5": "20",
    "EX-N4": "21",
}
START = "2026-10-12 08:00:00"


@tagged("post_install", "-at_install", "f3d", "f3d_fire_access")
class TestBridge(AccessCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["td.fire.drill"].sudo().search([("origin", "!=", "demo")]).unlink()
        cls.fire_zone = cls.env.ref("td_fire_safety.fire_zone_fa_cnc")
        cls.n = 100

    def row(self, sec, code, user=None, door="1", tna="", device="5390001"):
        self.n += 1
        return make_row(
            self.n, "2026-10-12T08:%02d:%02d.00Z" % divmod(sec, 60), code, user, device=device, door=door, tna=tna
        )

    def feed_at(self, sec, *rows):
        return self.feed(*rows, at="2026-10-12 08:%02d:%02d" % divmod(sec + 1, 60))

    def enter_people(self):
        self.feed(
            make_row(1, "2026-10-12T03:52:00.00Z", 4102, "TSTA1", tna="1"),
            make_row(2, "2026-10-12T03:53:00.00Z", 4102, "TSTB2", tna="1"),
        )

    def drill(self, **vals):
        vals.update(zone_id=self.fire_zone.id, title="Міст")
        return self.env["td.fire.drill"].sudo().create(vals)

    # --- двері виходів ---------------------------------------------------------------------------------------
    def test_exit_doors_in_access(self):
        doors = self.env["td.access.door"].search([("code", "in", list(EXIT_DOORS))])
        self.assertEqual({d.code: d.biostar_id for d in doors}, EXIT_DOORS)
        self.assertTrue(all(d.is_perimeter and d.server_id == self.server for d in doors))
        self.assertEqual(self.env["td.fire.exit"].search_count([("code", "in", list(EXIT_DOORS))]), 11)
        self.assertEqual(self.env["td.fire.exit"]._td_by_point("TURN-1").code, "EX-IN")  # вхід персоналу — турнікет

    def test_exit_door_pass_is_out_on_perimeter(self):
        self.enter_people()
        ev = self.feed(self.row(10, 4102, "TSTA1", door="12", tna="2"))
        self.assertEqual((ev.door_id.code, ev.direction, ev.is_perimeter), ("EX-S2", "out", True))
        self.assertFalse(self.emp_a.td_access_present)

    # --- вихід не своїм виходом -------------------------------------------------------------------------------
    def test_wrong_exit_end_to_end(self):
        self.enter_people()
        zones = (self.emp_a.td_access_zone_id, self.emp_b.td_access_zone_id)
        self.assertEqual(zones, (self.z["Z-CUT"], self.z["Z-ASM"]))
        drill = self.drill()
        with freeze_time(START):
            drill.action_start()
        self.assertEqual(drill.passage_source, "access")
        by_emp = {p.employee_id: p for p in drill.sudo().person_ids}
        self.assertEqual(by_emp[self.emp_a].assigned_exit_id.code, "EX-S2")  # Z-CUT
        self.assertEqual(by_emp[self.emp_b].assigned_exit_id.code, "EX-IN")  # Z-ASM, турнікет
        self.assertEqual(by_emp[self.emp_b].zone_id, self.z["Z-ASM"])
        self.feed_at(
            40,
            self.row(40, 4102, "TSTA1", door="12", tna="2"),  # свій вихід EX-S2
            self.row(50, 4867, "TSTB2", door="11", tna="2"),  # не свій: EX-S1 замість турнікета
        )
        with freeze_time("2026-10-12 08:02:00"):
            drill.action_stop()
        pa, pb = by_emp[self.emp_a], by_emp[self.emp_b]
        self.assertEqual((pa.exit_point, pa.exit_id.code, pa.wrong_exit), ("EX-S2", "EX-S2", False))
        self.assertEqual((pb.exit_point, pb.exit_id.code, pb.wrong_exit), ("EX-S1", "EX-S1", True))
        self.assertEqual((drill.wrong_exit_count, drill.evacuated_count, drill.evac_time_s), (1, 2, 50))
        self.assertEqual(drill.result_suggested, "remarks")
        self.assertEqual(
            {z.zone_id.td_code: (z.assigned_exits, z.actual_exits, z.wrong_exit) for z in drill.zone_ids},
            {"Z-CUT": ("EX-S2", "EX-S2", 0), "Z-ASM": ("EX-IN", "EX-S1", 1)},
        )

    def test_staff_exit_via_turnstile_is_own_exit(self):
        self.enter_people()
        drill = self.drill()
        with freeze_time(START):
            drill.action_start()
        self.feed_at(30, self.row(30, 4102, "TSTB2", door="1", tna="2"))  # турнікет TURN-1 = вихід EX-IN
        with freeze_time("2026-10-12 08:02:00"):
            drill.action_stop()
        pb = drill.sudo().person_ids.filtered(lambda p: p.employee_id == self.emp_b)
        got = (pb.exit_point, pb.exit_id.code, pb.assigned_exit_id.code, pb.wrong_exit)
        self.assertEqual(got, ("TURN-1", "EX-IN", "EX-IN", False))

    # --- зняття блокувань ------------------------------------------------------------------------------------
    def fire_cascade(self):
        """Каскад емулятора: 20480 на дверях (турнікет і вихід EX-S1) + 26368 «пожежна тривога» на всіх дверях."""
        self.feed_at(
            12,
            self.row(12, 20480, door="1"),
            self.row(12, 20480, door="11"),
            self.row(13, 26368, device="5390001", door=None),
        )
        door_exit = self.env["td.access.door"].search([("code", "=", "EX-S1")])
        self.assertEqual((self.door_turn_1.state, door_exit.state), ("unlocked", "unlocked"))
        self.assertTrue(self.door_turn_1.alarm and door_exit.alarm)
        self.assertEqual(self.door_turn_1.alarm_reason, "fire")
        return door_exit

    def test_release_locks_on_stop(self):
        self.enter_people()
        drill = self.drill()
        with freeze_time(START):
            drill.action_start()
        door_exit = self.fire_cascade()
        with freeze_time("2026-10-12 08:03:00"):
            drill.action_stop()
        for door in (self.door_turn_1, door_exit):
            self.assertEqual((door.state, door.alarm, door.alarm_reason), ("locked", False, False))
        self.assertIn("Зняті блокування тривоги", "".join(drill.message_ids.mapped("body")))
        self.assertEqual(drill.sudo()._td_release_locks(), 0)  # ідемпотентно
        late = self.feed(self.row(60, 20480, door="1"), at="2026-10-12 08:00:30")  # запізніла: старша за стан
        self.assertEqual(late.door_id.state, "locked")

    def test_release_keeps_doors_not_touched_by_drill(self):
        self.door_turn_1.sudo().write({"state": "unlocked", "state_ts": "2026-10-12 06:00:00"})  # до навчання
        drill = self.drill()
        with freeze_time(START):
            drill.action_start()
        with freeze_time("2026-10-12 08:03:00"):
            drill.action_stop()
        self.assertEqual(self.door_turn_1.state, "unlocked")

    def test_real_alarm_is_not_acknowledged(self):
        drill = self.drill()
        with freeze_time(START):
            drill.action_start()
        self.fire_cascade()
        drill.sudo().real_alarm = True
        with freeze_time("2026-10-12 08:03:00"):
            drill.action_stop()
        door = self.door_turn_1
        self.assertEqual((door.state, door.alarm, door.alarm_reason), ("locked", True, "fire"))

    def test_release_on_cancel(self):
        drill = self.drill()
        with freeze_time(START):
            drill.action_start()
        self.fire_cascade()
        with freeze_time("2026-10-12 08:03:00"):
            drill.action_cancel()
        self.assertEqual((self.door_turn_1.state, self.door_turn_1.alarm), ("locked", False))
