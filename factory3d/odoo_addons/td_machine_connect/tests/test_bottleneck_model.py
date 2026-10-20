"""AC-111…AC-117: вузьке місце заводу (R-30) на моделях: показники з `mrp.workorder` і журналів, ділянки за мітками РЦ,
аналітика `td_report`, плитка `td_tile`, вузли `flow` у payload переглядача, тур."""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import F3DMachineCase, F3DMachineHttpCase


class BottleneckMixin:
    """МО з трьох операцій: Розкрій (SAW-T) → Присадка (CNC-T) → UA-T; час київський, «зараз» 10:30."""

    def make_line(self, start="08:00", qty=14):
        ops = [(self.wc_saw, 1), (self.wc_cnc, 2), (self.wc_ua, 3)]
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": self.fg.product_tmpl_id.id,
                "product_qty": 1,
                "bom_line_ids": [(0, 0, {"product_id": self.board.id, "product_qty": 0.5})],
                "operation_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Операція %s" % wc.td_code,
                            "workcenter_id": wc.id,
                            "time_mode": "manual",
                            "time_cycle_manual": 2.0,
                            "sequence": seq,
                        },
                    )
                    for wc, seq in ops
                ],
            }
        )
        mo = self.env["mrp.production"].create({"product_id": self.fg.id, "product_qty": qty, "bom_id": bom.id})
        mo.action_confirm()
        mo.write({"date_start": self.kt(start)})
        return mo

    def finish(self, wo, machine, start, end, qty=14):
        """Завдання виконано: журнал станів `working` `start`–`end` і завершення в `end`."""
        self.make_log(machine, "working", start, end, wo=wo, pieces=qty)
        wo.write({"state": "done", "date_finished": self.kt(end), "qty_produced": qty})

    def scenario(self):
        """МО A: Розкрій, Присадка виконано (07:00–08:00, 08:00–09:00), на UA-T чекає з 09:00; МО B, C — на Розкрої.

        Розкрій зайнятий усю зміну (07:00–10:30 = 100 %), Присадка 60 з 210 хв.
        """
        mo_a, mo_b, mo_c = self.make_line("07:00"), self.make_line("09:30"), self.make_line("09:30")
        a1, a2, a3 = mo_a.workorder_ids.sorted("sequence")
        self.finish(a1, self.m_saw, "07:00", "08:00")
        self.finish(a2, self.m_cnc, "08:00", "09:00")
        self.make_log(self.m_saw, "working", "08:00", "10:30")  # решта зміни Розкрій зайнятий іншою роботою
        return mo_a, mo_b, mo_c

    def analyze(self, period="day", group_by="workcenter", boost=20.0):
        return self.env["td.bottleneck"]._td_analyze(period, group_by, boost)

    def by_name(self, res):
        return {r["name"]: r for r in res["rows"]}


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestBottleneckModel(BottleneckMixin, F3DMachineCase):
    # --- AC-111…AC-113: показники з даних -------------------------------------------------------------------
    def test_orders_queue_wait_output(self):
        mo_a = self.make_line("08:00")
        a1 = mo_a.workorder_ids.sorted("sequence")[0]
        self.finish(a1, self.m_saw, "08:00", "09:00")
        rows = self.by_name(self.analyze())
        saw, cnc, ua = rows["Розкрій (тест)"], rows["Присадка (тест)"], rows["Верстат OPC UA (тест)"]
        self.assertEqual((saw["output"], saw["done"], saw["queue"], saw["wait_min"]), (14.0, 1, 0, 0.0))
        # Присадка: попередня операція завершена о 09:00, не почата; на 10:30 чекає 90 хв, на початок доби черги не було
        self.assertEqual((cnc["queue"], cnc["queue_start"], cnc["queue_delta"], cnc["wait_min"]), (1, 0, 1, 90.0))
        self.assertEqual((ua["queue"], ua["output"]), (0, 0.0))  # попередня (Присадка) ще не завершена

    def test_load_is_work_over_available_time(self):
        """Завантаження = `run_min / ppt_min` верстата (OEE-вікно): Розкрій 60 хв із 210 (07:00–10:30)."""
        mo_a = self.make_line("08:00")
        self.finish(mo_a.workorder_ids.sorted("sequence")[0], self.m_saw, "08:00", "09:00")
        rows = self.by_name(self.analyze())
        self.assertAlmostEqual(rows["Розкрій (тест)"]["load"], 60 / 210, places=3)
        self.assertEqual(rows["Присадка (тест)"]["load"], 0.0)

    def test_first_operation_not_started_waits_since_mo_start(self):
        self.make_line("09:00")
        saw = self.by_name(self.analyze())["Розкрій (тест)"]
        self.assertEqual((saw["queue"], saw["queue_delta"], saw["wait_min"]), (1, 1, 90.0))
        self.make_line("12:00")  # початок у майбутньому — ще не в черзі
        self.assertEqual(self.by_name(self.analyze())["Розкрій (тест)"]["queue"], 1)

    def test_timelog_fallback_without_state_log(self):
        """Верстат без журналу станів: робота й випуск — з журналу часу й завершених завдань (як у OEE)."""
        mo_a = self.make_line("07:00")
        wo = mo_a.workorder_ids.sorted("sequence")[0]
        self.env["mrp.workcenter.productivity"].create(
            {
                "workcenter_id": self.wc_saw.id,
                "workorder_id": wo.id,
                "loss_id": self.env.ref("mrp.block_reason7").id,
                "date_start": self.kt("07:00"),
                "date_end": self.kt("08:00"),
            }
        )
        wo.write({"state": "done", "date_finished": self.kt("08:00"), "qty_produced": 9})
        saw = self.by_name(self.analyze())["Розкрій (тест)"]
        self.assertEqual((saw["output"], saw["done"]), (9.0, 1))
        self.assertAlmostEqual(saw["load"], 60 / 210, places=3)

    # --- AC-114: вузьке місце -----------------------------------------------------------------------------
    def test_bottleneck_is_busiest_station_with_growing_queue(self):
        self.scenario()
        res = self.analyze()
        self.assertEqual(res["verdict"], "growing")
        top = res["rows"][0]
        self.assertEqual((top["name"], top["bottleneck"], top["rank"]), ("Розкрій (тест)", True, 1))
        self.assertAlmostEqual(top["load"], 1.0, places=3)
        self.assertEqual((top["queue"], top["queue_delta"]), (2, 2))
        self.assertEqual(
            self.by_name(res)["Верстат OPC UA (тест)"]["queue"], 1
        )  # МО A чекає на UA-T, але вона не завантажена
        self.assertFalse(self.by_name(res)["Присадка (тест)"]["bottleneck"])

    def test_no_data_no_bottleneck(self):
        res = self.analyze()
        self.assertEqual((res["bottleneck"], res["verdict"], res["hint"]), (None, None, ""))

    # --- AC-115: «що якщо» ------------------------------------------------------------------------------------
    def test_what_if_hint_on_scenario(self):
        self.scenario()
        res = self.analyze(boost=20.0)
        self.assertEqual(
            res["hint"], "+20 % потужності на Розкрій (тест) → +20 % випуску, далі обмежує Присадка (тест)"
        )
        res = self.analyze(boost=500.0)  # Присадка (потужність 14 / 0,286 ≈ 49) обмежує вже в межах +500 %
        self.assertTrue(res["what_if"]["capped"])
        self.assertTrue(res["hint"].startswith("+500 % потужності на Розкрій (тест) → +250 % випуску"), res["hint"])

    # --- ділянки за мітками РЦ ---------------------------------------------------------------------------------
    def test_area_grouping_by_workcenter_tag(self):
        self.scenario()
        tag = self.env["mrp.workcenter.tag"].create({"name": "Дільниця тест"})
        (self.wc_saw | self.wc_cnc).write({"tag_ids": [(4, tag.id)]})
        res = self.analyze(group_by="area")
        rows = self.by_name(res)
        area = rows["Дільниця тест"]
        self.assertEqual(sorted(res["stations"]["area:%s" % tag.id]["codes"]), ["CNC-T", "SAW-T"])
        self.assertEqual(area["machines"], 2)
        self.assertAlmostEqual(area["load"], (210 + 60) / 420, places=3)  # сума роботи / сума доступного часу
        self.assertIn("Верстат OPC UA (тест)", rows)  # РЦ без мітки — окрема ділянка
        self.assertEqual(self.analyze(group_by="bad")["group_by"], "area")

    def test_demo_clock_is_now(self):
        icp = self.env["ir.config_parameter"].sudo()
        Model = self.env["td.bottleneck"]
        icp.set_param("td.viewer.demo_clock", "2026-10-11 09:00")
        self.assertEqual(Model._td_now(), self.kt("09:00", self.D0.replace(day=11)))
        icp.set_param("td.viewer.demo_clock", "не дата")
        self.assertEqual(
            Model._td_now(), self.kt("10:30")
        )  # невалідний годинник ігнорується: реальний (тут заморожений) час
        icp.set_param("td.viewer.demo_clock", "")
        self.assertEqual(Model._td_now(), self.kt("10:30"))

    # --- AC-116: аналітика і плитка ---------------------------------------------------------------------
    def test_report_and_tile(self):
        self.scenario()
        report = self.env["td.bottleneck"].with_user(self.user_f3d).td_report("day", "workcenter", 20)
        self.assertEqual(report["bottleneck"]["name"], "Розкрій (тест)")
        self.assertEqual((report["verdict"], report["boost_pct"], report["gain_pct"]), ("growing", 20.0, 20.0))
        self.assertEqual([r["rank"] for r in report["rows"]], list(range(1, len(report["rows"]) + 1)))
        self.assertEqual(report["rows"][0]["load"], 1.0)
        self.assertTrue(report["hint"].startswith("+20 % потужності на Розкрій (тест)"))
        bad = self.env["td.bottleneck"].td_report("rubbish", "rubbish", "abc")
        self.assertEqual((bad["period"], bad["group_by"], bad["boost_pct"]), ("day", "area", 20.0))
        tile = self.env["td.bottleneck"].with_user(self.user_f3d).td_tile()
        self.assertEqual((tile["name"], tile["queue"], tile["verdict"]), ("Розкрій (тест)", 2, "growing"))

    def test_report_and_tile_need_factory_user(self):
        self.scenario()
        Model = self.env["td.bottleneck"].with_user(self.user_plain)
        with self.assertRaises(AccessError):
            Model.td_report()
        self.assertFalse(Model.td_tile())

    def test_tile_without_bottleneck_is_false(self):
        self.assertFalse(self.env["td.bottleneck"].with_user(self.user_f3d).td_tile())

    # --- AC-117: вузли flow у payload переглядача ------------------------------------------------------------------
    def _payload(self, *codes):
        return {"workcenters": {c: {"code": c} for c in codes}}

    def test_flow_nodes_in_payload(self):
        self.scenario()
        provider = self.env["td.viewer.provider.machines"]
        payload = self._payload("SAW-T", "CNC-T", "UA-T")
        provider._td_viewer_collect(payload, {})
        saw, cnc = payload["workcenters"]["SAW-T"]["flow"], payload["workcenters"]["CNC-T"]["flow"]
        self.assertTrue(saw["bottleneck"])
        self.assertEqual(
            (saw["station"], saw["load"], saw["queue"], saw["queue_delta"], saw["rank"], saw["verdict"], saw["period"]),
            ("Розкрій (тест)", 1.0, 2, 2, 1, "growing", "day"),
        )
        self.assertEqual((saw["codes"], saw["prev"]), (["SAW-T"], []))
        self.assertTrue(saw["hint"].startswith("+20 % потужності на Розкрій (тест)"))
        self.assertFalse(cnc["bottleneck"])
        self.assertNotIn("hint", cnc)
        self.assertEqual(cnc["wait_min"], 0.0)  # Присадка стартувала одразу після Розкрою
        kiosk = self._payload("SAW-T")
        provider._td_viewer_collect(kiosk, {"kiosk": True})  # показники не фінансові: є й у кіоску
        self.assertIn("flow", kiosk["workcenters"]["SAW-T"])

    def test_flow_delta_only_for_nodes_in_patch(self):
        self.scenario()
        patch = self._payload("CNC-T")
        self.env["td.viewer.provider.machines"]._td_viewer_delta(patch, {})
        self.assertEqual(set(patch["workcenters"]), {"CNC-T"})
        self.assertIn("flow", patch["workcenters"]["CNC-T"])

    def test_flow_prev_is_main_upstream_station(self):
        """Вузьке місце — UA-T (зайнята всю зміну, МО A чекає з 09:00); перед нею за маршрутом — Присадка (CNC-T)."""
        mo_a = self.make_line("07:00")
        a1, a2, _a3 = mo_a.workorder_ids.sorted("sequence")
        self.finish(a1, self.m_saw, "07:00", "08:00")
        self.finish(a2, self.m_cnc, "08:00", "09:00")
        self.make_log(self.m_ua, "working", "07:00", "10:30")
        res = self.analyze()
        self.assertEqual((res["rows"][0]["name"], res["verdict"]), ("Верстат OPC UA (тест)", "growing"))
        self.assertEqual(res["upstream"], self.by_name(res)["Присадка (тест)"]["key"])
        flows = self.env["td.bottleneck"]._td_flow_nodes()
        self.assertEqual(
            (flows["UA-T"]["bottleneck"], flows["UA-T"]["prev"], flows["UA-T"]["codes"]), (True, ["CNC-T"], ["UA-T"])
        )
        self.assertEqual(flows["CNC-T"]["bottleneck"], False)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestBottleneckTour(BottleneckMixin, F3DMachineHttpCase):
    def test_bottleneck_tile_and_report_tour(self):
        """V-34: плитка «Вузьке місце: <ділянка>, черга N» в «Огляді верстатів» і аналітика (рейтинг, «що якщо»)."""
        self.scenario()
        self.start_tour(
            "/odoo/action-td_machine_connect.action_td_machine_dashboard",
            "td_machine_connect_bottleneck",
            login="admin",
            timeout=180,
        )
