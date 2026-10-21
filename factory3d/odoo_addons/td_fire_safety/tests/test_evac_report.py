"""AC-81…AC-87 (M-09 point_code, M-11b, M-11g, R-16a…R-16d, R-21a): звіт евакуації, живий стан 3D, блокування."""

from unittest import mock

from freezegun import freeze_time
from odoo.addons.td_fire_safety.tools import payload
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import FireCase

SOURCE = "td.fire.passage.source.zz_test"


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestEvacReport(FireCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["hr.attendance"].sudo().search([]).unlink()
        cls.env["td.fire.drill"].sudo().search([("origin", "!=", "demo")]).unlink()
        cls.Exit = cls.env["td.fire.exit"]

    def setUp(self):
        super().setUp()
        # без td_access: його джерело (пріоритет 10) перекриває тестове (5) — вимикаємо, як у TestDrill
        Base = type(self.env["td.fire.passage.source"])
        real = Base._td_source_names
        patcher = mock.patch.object(
            Base, "_td_source_names", lambda model: [n for n in real(model) if n != "td.fire.passage.source.access"]
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- допоміжне -----------------------------------------------------------------------------------------
    @property
    def people_list(self):
        if not hasattr(self, "_people_list"):
            self._people_list = self.people()
        return self._people_list

    def people(self):
        """Чотири людини: двоє з Z-CNC (вихід EX-S3), один із Z-CUT (EX-S2), один без зони."""
        self.emps = [self.make_employee("Звіт %d" % i, "RPT-%d" % i) for i in range(4)]
        zones = ["Z-CNC", "Z-CUT", "Z-CNC", None]
        return [
            {"employee_id": e.id, "since": self.at(-3600 + i), "point": "TURN-1", "zone": z}
            for i, (e, z) in enumerate(zip(self.emps, zones, strict=True))
        ]

    def run_drill(self, passages, stop_s=120):
        """Навчання на тестовому джерелі: люди `people_list` на старті, `passages` — проходи; стан evaluating."""
        on_site = self.people_list
        Source = type(self.env[SOURCE])
        ctx = {"f3d_test_passage_source": True, "f3d_test_passages": passages}
        patcher = mock.patch.object(Source, "_td_on_site", lambda model, at: list(on_site), create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        drill = self.new_drill(zone_id=self.z_cnc.id, device_id=self.dev_cnc05.id).with_context(**ctx)
        with freeze_time(self.at(0)):
            drill.action_start()
        with freeze_time(self.at(stop_s)):
            drill.action_stop()
        return drill

    def out(self, emp, s, point):
        return {"employee_id": emp.id, "ts": self.at(s), "point": point, "direction": "out"}

    # --- AC-81: вихід за точкою проходу -----------------------------------------------------------------------
    def test_exit_by_point(self):
        self.assertEqual(self.Exit._td_by_point("TURN-1").code, "EX-IN")  # point_code EX-IN з data
        self.assertEqual(self.Exit._td_by_point("EX-S3").code, "EX-S3")  # без point_code — за кодом
        self.assertFalse(self.Exit._td_by_point("Відмітка виходу"))
        self.assertFalse(self.Exit._td_by_point(""))
        self.assertFalse(self.Exit._td_by_point(False))
        self.assertEqual(self.Exit.search([("code", "=", "EX-IN")]).point_code, "TURN-1")

    # --- AC-82: зона, маршрут і призначений вихід на старті ------------------------------------------------------
    def test_zone_route_assigned_exit_at_start(self):
        drill = self.run_drill([])
        persons = drill.sudo().person_ids.sorted("seq")
        self.assertEqual([p.zone_id.td_code for p in persons], ["Z-CNC", "Z-CUT", "Z-CNC", False])
        self.assertEqual([p.assigned_exit_id.code for p in persons], ["EX-S3", "EX-S2", "EX-S3", False])
        self.assertEqual(persons[0].route_id.code, "EVAC-CNC")
        self.assertFalse(persons[3].route_id)

    # --- AC-83: не свій вихід, не відмітились, норматив і факт ---------------------------------------------------
    def test_report_wrong_exit_and_missing(self):
        _ = self.people_list  # створює працівників (self.emps) до розкладу проходів
        passages = [
            self.out(self.emps[0], 40, "EX-S3"),  # свій вихід
            self.out(self.emps[1], 55, "EX-S4"),  # не свій (маршрут Z-CUT → EX-S2)
        ]
        drill = self.run_drill(passages)
        persons = drill.sudo().person_ids.sorted("seq")
        self.assertEqual([p.wrong_exit for p in persons], [False, True, False, False])
        self.assertEqual(persons[1].exit_id.code, "EX-S4")
        self.assertEqual(persons[0].exit_id.code, "EX-S3")
        self.assertEqual((drill.wrong_exit_count, drill.evacuated_count, drill.missing_count), (1, 2, 2))
        self.assertEqual((drill.evac_time_s, drill.time_limit_s, drill.evac_in_norm), (55, 300, True))
        self.assertEqual(drill.result_suggested, "failed")  # є не відмічені
        zones = {z.zone_id.td_code or "": z for z in drill.zone_ids}
        self.assertEqual(
            sorted(zones), ["", "Z-CNC", "Z-CUT"], [(z.zone_id.id, z.people, z.drill_id.id) for z in drill.zone_ids]
        )
        cnc, cut, none = zones["Z-CNC"], zones["Z-CUT"], zones[""]
        self.assertEqual((cnc.people, cnc.evacuated, cnc.missing, cnc.first_exit_s, cnc.evac_time_s), (2, 1, 1, 40, 40))
        self.assertEqual((cnc.assigned_exits, cnc.actual_exits, cnc.in_norm), ("EX-S3", "EX-S3", False))  # missing
        self.assertEqual((cut.people, cut.wrong_exit, cut.assigned_exits, cut.actual_exits), (1, 1, "EX-S2", "EX-S4"))
        self.assertTrue(cut.in_norm)
        self.assertEqual((none.people, none.missing), (1, 1))
        self.assertEqual(drill.sudo().wrong_person_ids, persons[1])
        self.assertEqual(drill.sudo().missing_person_ids, persons[2] | persons[3])
        self.assertEqual([z.norm_s for z in drill.sudo().zone_ids], [300, 300, 300])

    def test_wrong_exit_alone_gives_remarks(self):
        drill = self.run_drill([])
        persons = drill.sudo().person_ids.sorted("seq")
        persons.write({"rollcall": "present"})  # усі на перекличці: missing 0, але перекличка → data_quality partial
        persons[0].write({"exit_ts": self.at(30), "exit_point": "EX-S3"})
        persons[1].write({"exit_ts": self.at(40), "exit_point": "EX-S3"})  # Z-CUT → не свій
        self.assertEqual(drill.wrong_exit_count, 1)
        self.assertEqual(drill.result_suggested, "remarks")
        persons[1].write({"exit_point": "EX-S2"})  # виправили: свій
        self.assertEqual(drill.wrong_exit_count, 0)

    def test_over_norm(self):
        _ = self.people_list
        drill = self.run_drill([self.out(self.emps[0], 40, "EX-S3")])
        drill.sudo().time_limit_s = 30
        self.assertFalse(drill.evac_in_norm)
        self.assertFalse(drill.zone_ids.filtered(lambda z: z.zone_id.td_code == "Z-CNC").in_norm)

    # --- AC-84: протокол ------------------------------------------------------------------------------------------
    def test_protocol_sections(self):
        _ = self.people_list
        drill = self.run_drill([self.out(self.emps[0], 40, "EX-S3"), self.out(self.emps[1], 55, "EX-S4")])
        render = self.env["ir.actions.report"]._render_qweb_html
        html = render("td_fire_safety.report_td_fire_drill", drill.ids)[0].decode()
        self.assertIn("4. Звіт евакуації", html)
        self.assertEqual(html.count("f3d-drill-zone"), 3)
        self.assertEqual(html.count("f3d-drill-wrong"), 1)
        self.assertEqual(html.count("f3d-drill-missing"), 2)
        self.assertIn("EX-S4", html)
        self.assertNotIn("Звіт 1", html)  # прізвищ немає без print_names
        drill.print_names = True
        html = render("td_fire_safety.report_td_fire_drill", drill.ids)[0].decode()
        self.assertIn("Звіт 1", html)

    # --- AC-85: живий стан для 3D --------------------------------------------------------------------------------
    def test_live_payload_drill(self):
        on_site = self.people_list
        Source = type(self.env[SOURCE])
        ctx = {"f3d_test_passage_source": True, "f3d_test_passages": [self.out(self.emps[0], 40, "EX-S3")]}
        with mock.patch.object(Source, "_td_on_site", lambda model, at: list(on_site), create=True):
            drill = self.new_drill(zone_id=self.z_cnc.id, device_id=self.dev_cnc05.id).with_context(**ctx)
            with freeze_time(self.at(0)):
                drill.action_start()
            with freeze_time(self.at(60)):
                drill._tick()
                live = payload.build_evacuation(self.env)["live"]
        self.assertEqual((live["mode"], live["state"], live["name"]), ("drill", "running", drill.name))
        self.assertEqual((live["zone"], live["zone_code"], live["total"], live["limit_s"]), ("FA-CNC", "Z-CNC", 4, 300))
        self.assertEqual(live["stuck_after_s"], 120)
        self.assertEqual(live["now_ms"] - live["start_ms"], 60_000)
        self.assertIsNone(live["end_ms"])
        self.assertEqual(len(live["origin"]), 2)
        people = live["people"]
        self.assertEqual([p["n"] for p in people], [1, 2, 3, 4])
        self.assertEqual(
            people[0],
            {
                "n": 1,
                "zone": "Z-CNC",
                "exit": "EX-S3",
                "out_ms": live["start_ms"] + 40_000,
                "out_exit": "EX-S3",
                "wrong": False,
            },
        )
        self.assertEqual(people[1]["out_ms"], None)
        self.assertEqual(set(people[0]), {"n", "zone", "exit", "out_ms", "out_exit", "wrong"})  # без особистих даних
        self.assertTrue(all(s["code"].startswith("SZ-") for s in live["smoke"]))
        self.assertTrue(live["smoke"])  # контур FA-CNC перетинає димову зону

    def test_live_kept_after_stop_then_dropped(self):
        """Після кінця евакуації `evaluating` тримається в 3D не довше 10 хв (параметр 60 теж обрізається до 10)."""
        _ = self.people_list
        drill = self.run_drill([self.out(self.emps[0], 40, "EX-S3")])
        with freeze_time(self.at(120 + 9 * 60)):
            live = payload.build_evacuation(self.env)["live"]
        self.assertEqual((live["state"], live["end_ms"] - live["start_ms"]), ("evaluating", 120_000))
        self.assertEqual(live["people"][0]["out_exit"], "EX-S3")
        self.assertEqual(live["people"][0]["wrong"], False)
        with freeze_time(self.at(120 + 11 * 60)):
            self.assertIsNone(payload.build_evacuation(self.env)["live"])
        self.env["ir.config_parameter"].sudo().set_param("td.fire_safety.drill_3d_keep_min", "60")
        with freeze_time(self.at(120 + 9 * 60)):
            self.assertEqual(payload.build_evacuation(self.env)["live"]["state"], "evaluating")
        with freeze_time(self.at(120 + 11 * 60)):
            self.assertIsNone(payload.build_evacuation(self.env)["live"])
        drill.sudo().state = "cancelled"

    def test_live_closed_or_cancelled_not_shown(self):
        """Закрите (`done`) і скасоване навчання в 3D не показується, навіть одразу після завершення."""
        _ = self.people_list
        drill = self.run_drill([self.out(self.emps[0], 40, "EX-S3")])
        with freeze_time(self.at(130)):
            self.assertEqual(payload.build_evacuation(self.env)["live"]["state"], "evaluating")
            drill.sudo().write({"result": "ok", "conclusions": "Висновки"})
            drill.action_close()
            self.assertEqual(drill.state, "done")
            self.assertIsNone(payload.build_evacuation(self.env)["live"])
        drill.sudo().state = "cancelled"
        with freeze_time(self.at(135)):
            self.assertIsNone(payload.build_evacuation(self.env)["live"])

    def test_live_none_without_drill_or_alarm(self):
        with freeze_time(self.at(0)):
            self.assertIsNone(payload.build_evacuation(self.env)["live"])

    def test_live_real_alarm(self):
        self.z_cnc.sudo().write({"state": "alarm", "state_ts": self.at(5)})
        self.env["td.fire.event"]._log("alarm", "FA-CNC", self.at(5), "Тривога", zone_id=self.z_cnc.id)
        with freeze_time(self.at(65)):
            live = payload.build_evacuation(self.env)["live"]
        self.assertEqual(
            (live["mode"], live["zone"], live["zone_code"], live["people"]), ("alarm", "FA-CNC", "Z-CNC", [])
        )
        self.assertEqual(live["now_ms"] - live["start_ms"], 60_000)
        self.assertTrue(live["smoke"])

    def test_evacuation_section_size(self):
        _ = self.people_list
        self.run_drill([self.out(self.emps[0], 40, "EX-S3")])
        with freeze_time(self.at(130)):
            size = len(str(payload.build_evacuation(self.env)))
        self.assertLess(size, 25 * 1024)  # API-02: evacuation ≤ 25 КБ

    # --- AC-86: зняття блокувань ----------------------------------------------------------------------------------
    def test_release_locks_called_on_stop_cancel_close(self):
        Drill = type(self.env["td.fire.drill"])
        drill = self.new_drill(zone_id=self.z_cnc.id)
        with mock.patch.object(Drill, "_td_release_locks", return_value=2) as release:
            with freeze_time(self.at(0)):
                drill.action_start()
            with freeze_time(self.at(30)):
                drill.action_stop()
            self.assertEqual(release.call_count, 1)
            self.assertIn("Зняті блокування тривоги: 2", "".join(drill.message_ids.mapped("body")))
            drill.write({"result": "ok", "conclusions": "ок"})
            drill.action_close()
            self.assertEqual(release.call_count, 2)
        d2 = self.new_drill(zone_id=self.z_cnc.id, title="Скасоване")
        with mock.patch.object(Drill, "_td_release_locks", return_value=0) as release:
            with freeze_time(self.at(100)):
                d2.action_start()
                d2.action_cancel()
            self.assertEqual(release.call_count, 1)
            d3 = self.new_drill(zone_id=self.z_cnc.id)
            d3.action_cancel()  # чернетка: каскад не запускався
            self.assertEqual(release.call_count, 1)
        self.assertEqual(self.new_drill(zone_id=self.z_cnc.id)._td_release_locks(), 0)  # базова реалізація

    # --- AC-87: кнопка запуску з емулятором -----------------------------------------------------------------------
    def test_start_evac_sim_unavailable(self):
        if "td.sim.run" in self.env:
            self.skipTest("iot_sim встановлено")
        drill = self.new_drill(zone_id=self.z_cnc.id)
        self.assertFalse(drill.sim_evac_available)
        with self.assertRaisesRegex(UserError, "немає сценарію fire_evacuation"):
            drill.action_start_evac_sim()

    def test_start_evac_sim_bridge(self):
        if "td.sim.run" not in self.env:
            self.skipTest("iot_sim не встановлено")
        scenario = self.env["td.sim.scenario"].sudo().search([("code", "=", "fire_evacuation")])
        self.assertTrue(scenario)
        drill = self.new_drill(zone_id=self.z_cnc.id, device_id=self.dev_cnc05.id)
        self.assertTrue(drill.sim_evac_available)
        Drill = type(drill)
        run = mock.Mock(state="running")
        run.name = "RUN/2026/0008"
        with mock.patch.object(Drill, "_td_sim_create_run", return_value=run) as create:
            drill.action_start_evac_sim()
        self.assertEqual(create.call_args[0][0], scenario)
        self.assertEqual(create.call_args[0][1]["zone"], "FA-CNC")
        self.assertEqual((drill.mode, drill.sim_run_ref, drill.state), ("sim", "RUN/2026/0008", "running"))
