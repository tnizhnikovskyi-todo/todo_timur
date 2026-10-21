"""AC-120…AC-124: портальний склад плит у 3D (R-31): вузли payload, плитка, демо-історія. Без td_viewer3d."""

from datetime import timedelta
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools import demo_portal
from ..tools import portal as portal_tools
from ..tools.states import parse_ts
from .common import F3DMachineCase, F3DMachineHttpCase


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestPortalPure(F3DMachineCase):
    def test_waste_is_weighted_by_sheets(self):
        self.assertEqual(portal_tools.waste_weighted([(10.0, 2), (4.0, 6)]), 5.5)
        self.assertEqual(portal_tools.waste_weighted([(10.0, 2), (None, 50), (7.0, 0)]), 10.0)
        self.assertIsNone(portal_tools.waste_weighted([]))
        self.assertIsNone(portal_tools.waste_weighted([(None, 3)]))

    def test_day_start_and_seconds_are_kyiv(self):
        now = self.kt("10:30")
        d0 = portal_tools.day_start(now)
        self.assertEqual(d0, self.kt("00:00"))  # київська північ (EEST)
        self.assertEqual(portal_tools.to_sec(self.kt("10:30:15"), d0), 10 * 3600 + 30 * 60 + 15)
        self.assertEqual(portal_tools.to_sec(self.kt("00:00") - (self.kt("10:30") - self.kt("10:29")), d0), -60)
        self.assertIsNone(portal_tools.to_sec(False, d0))


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestPortalNodes(F3DMachineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal = cls.env["td.portal"]
        cls.env["ir.config_parameter"].sudo().set_param("td.viewer.demo_clock", "2026-10-12 10:30")

    def _iso(self, t):
        return self.kt(t).isoformat()

    def _scenario(self):
        """МО на SAW-T, карта `released` (відходи 9,5 %), стос T1 з порталу, завдання: виконане, активне, у черзі."""
        mo = self.make_mo(self.wc_saw, qty=14, name="WH/MO/T0233")
        self.put_stock(self.board, self.loc_t1, 40, self.lot_l1)
        self.stack_t1.write(
            {
                "ws_qty": 37,
                "ws_product": "BOARD-T",
                "ws_lot": "L1",
                "ws_updated": self.kt("10:28"),
                "ws_seen": self.kt("10:29"),
            }
        )
        self.stack_t1._td_refresh()
        cmap = self.env["td.cut.map"].create(
            {
                "production_id": mo.id,
                "material_product_id": self.board.id,
                "sheet_length_mm": 2800,
                "sheet_width_mm": 2070,
                "thickness_mm": 16,
                "qty": 14,
                "state": "released",
                "plan_sheets": 7,
                "plan_waste_pct": 9.54,
            }
        )
        Job = self.env["td.gantry.job"]
        common = {
            "stack_id": self.stack_t1.id,
            "product_id": self.board.id,
            "lot_id": self.lot_l1.id,
            "target_workcenter_id": self.wc_saw.id,
            "external_ref": mo.name,
            "production_id": mo.id,
            "cut_map_id": cmap.id,
        }
        done = Job.create(
            {
                **common,
                "state": "done",
                "sheets": 2,
                "done": 2,
                "started": self.kt("09:40"),
                "finished": self.kt("09:43"),
                "sheet_log": [
                    {"id": 1, "ts": self._iso("09:41"), "stack": "PLT-T1", "lot": "L1"},
                    {"id": 2, "ts": self._iso("09:43"), "stack": "PLT-T1", "lot": "L1"},
                ],
            }
        )
        active = Job.create(
            {
                **common,
                "state": "active",
                "sheets": 4,
                "done": 2,
                "started": self.kt("10:25"),
                "sheet_log": [
                    {"id": 3, "ts": self._iso("10:27"), "stack": "PLT-T1", "lot": "L1"},
                    {"id": 4, "ts": self._iso("10:28"), "stack": "PLT-T1", "lot": "L1"},
                ],
            }
        )
        queued = Job.create({**common, "state": "queued", "sheets": 1, "priority": 3})
        return mo, cmap, done, active, queued

    # --- AC-120: вузол порталу ---------------------------------------------------------------------
    def test_equipment_node_chain_and_today(self):
        mo, cmap, done, active, queued = self._scenario()
        node = self.portal._td_equipment_node()
        self.assertEqual((node["day"], node["now"], node["cycle_s"]), ("2026-10-12", 10 * 3600 + 30 * 60, 27))
        by_id = {j["id"]: j for j in node["jobs"]}
        self.assertEqual(set(by_id), {done.name, active.name, queued.name})
        job = by_id[active.name]
        self.assertEqual(
            (job["state"], job["stack"], job["target"], job["sheets"], job["done"], job["product"], job["lot"]),
            ("active", "PLT-T1", "SAW-T", 4, 2, "BOARD-T", "L1"),
        )
        self.assertEqual((job["ref"], job["mo"], job["mo_product"]), (mo.name, mo.name, mo.product_id.name))
        self.assertEqual(job["cut"], {"name": cmap.name, "state": "released", "sheets": 7, "waste_pct": 9.5})
        self.assertEqual((job["s"], job["e"]), (10 * 3600 + 25 * 60, None))
        self.assertEqual(job["log"], [[10 * 3600 + 27 * 60, "PLT-T1"], [10 * 3600 + 28 * 60, "PLT-T1"]])
        self.assertEqual(by_id[done.name]["e"], 9 * 3600 + 43 * 60)
        self.assertIsNone(by_id[queued.name]["s"])
        # зведення «сьогодні»: завдань 3, подано 4 листи; відходи — середньозважені за листами завдань
        self.assertEqual(node["today"], {"jobs": 3, "sheets": 4, "waste_pct": 9.5})
        # порядок за початком; у черзі (без початку) — після
        self.assertEqual([j["id"] for j in node["jobs"]][:2], [done.name, active.name])

    def test_node_hides_future_and_clips_log_to_now(self):
        _mo, _cmap, _done, active, _queued = self._scenario()
        job = self.env["td.gantry.job"].create(
            {
                "state": "active",
                "sheets": 3,
                "done": 1,
                "product_id": self.board.id,
                "target_workcenter_id": self.wc_saw.id,
                "started": self.kt("11:00"),
            }
        )
        active.sheet_log = active.sheet_log + [{"id": 9, "ts": self._iso("10:45"), "stack": "PLT-T1", "lot": "L1"}]
        node = self.portal._td_equipment_node()
        self.assertNotIn(job.name, [j["id"] for j in node["jobs"]])  # старт після «зараз» (демо-годинник)
        mine = next(j for j in node["jobs"] if j["id"] == active.name)
        self.assertEqual(len(mine["log"]), 2)  # лист 10:45 ще не покладений

    def test_cut_waste_only_for_planned_maps(self):
        _mo, cmap, _done, active, _queued = self._scenario()
        cmap.state = "draft"
        node = self.portal._td_equipment_node()
        job = next(j for j in node["jobs"] if j["id"] == active.name)
        self.assertEqual((job["cut"]["state"], job["cut"]["waste_pct"]), ("draft", None))
        self.assertIsNone(node["today"]["waste_pct"])  # немає запланованих карт — «—», не 0

    def test_job_without_mo_has_no_cut(self):
        job = self.env["td.gantry.job"].create(
            {
                "state": "active",
                "sheets": 3,
                "done": 0,
                "product_id": self.board.id,
                "target_workcenter_id": self.wc_saw.id,
                "started": self.kt("10:00"),
            }
        )
        node = self.portal._td_equipment_node()
        mine = next(j for j in node["jobs"] if j["id"] == job.name)
        self.assertNotIn("cut", mine)
        self.assertEqual((mine["ref"], mine["mo"]), ("", ""))

    # --- AC-121: стоси ----------------------------------------------------------------------------
    def test_stack_nodes_portal_and_odoo_sources(self):
        _mo, _cmap, _done, active, queued = self._scenario()
        self.put_stock(self.board, self.loc_t2, 12)
        self.stack_t2._td_refresh()
        nodes = self.portal._td_stack_nodes()
        t1, t2 = nodes["PLT-T1"], nodes["PLT-T2"]
        self.assertEqual(
            (t1["qty"], t1["upd"], t1["src"], t1["capacity"], t1["thickness"], t1["product"], t1["lot"]),
            (37, 10 * 3600 + 28 * 60, "portal", 60, 16, "BOARD-T", "L1"),
        )
        self.assertEqual(t1["next"], {"job": active.name, "state": "active", "target": "SAW-T", "sheets": 4,
                                      "done": 2, "ref": active.external_ref})  # fmt: skip
        # без даних порталу — за Odoo; наступного завдання немає
        self.assertEqual((t2["qty"], t2["upd"], t2["src"], t2["product"]), (12, None, "odoo", "BOARD-T"))
        self.assertNotIn("next", t2)
        self.assertEqual(set(self.portal._td_stack_nodes(["PLT-T2"])), {"PLT-T2"})
        self.assertEqual(self.portal._td_stack_nodes([]), {})
        self.assertEqual(queued.state, "queued")

    def test_next_job_prefers_active_then_priority(self):
        _mo, _cmap, _done, active, queued = self._scenario()
        active.state = "done"
        active.finished = self.kt("10:29")
        node = self.portal._td_stack_nodes(["PLT-T1"])["PLT-T1"]
        self.assertEqual(node["next"]["job"], queued.name)
        queued.state = "done"
        self.assertNotIn("next", self.portal._td_stack_nodes(["PLT-T1"])["PLT-T1"])

    # --- AC-122: payload провайдера ---------------------------------------------------------------
    def test_payload_collect_and_delta_carry_portal(self):
        self._scenario()
        provider = self.env["td.viewer.provider.machines"]
        payload = {
            "equipment": {"GANTRY-1": {"state": "idle"}},
            "locations": {"PLT-T1": {"kind": "stack"}, "PLT-T2": {"kind": "stack"}},
            "workcenters": {},
        }
        provider._td_viewer_collect(payload, {})
        self.assertEqual(len(payload["equipment"]["GANTRY-1"]["portal"]["jobs"]), 3)
        self.assertEqual(payload["locations"]["PLT-T1"]["portal"]["qty"], 37)
        self.assertIn("portal", payload["locations"]["PLT-T2"])
        # дельта: лише вузли патча
        patch_ = {"locations": {"PLT-T1": {"code": "PLT-T1"}}}
        provider._td_viewer_delta(patch_, {})
        self.assertEqual(patch_["locations"]["PLT-T1"]["portal"]["src"], "portal")
        self.assertNotIn("equipment", patch_)
        patch_ = {"equipment": {"GANTRY-1": {"code": "GANTRY-1"}}}
        provider._td_viewer_delta(patch_, {})
        self.assertIn("portal", patch_["equipment"]["GANTRY-1"])
        self.assertNotIn("locations", patch_)

    def test_portal_failure_does_not_break_payload(self):
        payload = {"equipment": {"GANTRY-1": {}}, "locations": {"PLT-T1": {}}, "workcenters": {}}
        with (
            patch.object(type(self.portal), "_td_equipment_node", side_effect=ValueError("boom")),
            mute_logger("odoo.addons.td_machine_connect.tools.payload"),
        ):
            self.env["td.viewer.provider.machines"]._td_viewer_collect(payload, {})
        self.assertNotIn("portal", payload["equipment"]["GANTRY-1"])
        self.assertIn("gantry", payload["equipment"]["GANTRY-1"])  # решта R-25 на місці

    # --- AC-123: плитка ---------------------------------------------------------------------------
    def test_tile_counts_jobs_and_waste(self):
        self._scenario()
        tile = self.portal.with_user(self.user_f3d).td_tile()
        self.assertEqual(tile, {"jobs": 3, "sheets": 4, "waste_pct": 9.5})

    def test_tile_needs_factory_user_and_portal(self):
        self.assertFalse(self.portal.with_user(self.user_plain).td_tile())
        self.env["td.gantry.stack"].search([]).unlink()
        self.assertFalse(self.portal.with_user(self.user_f3d).td_tile())  # немає ні стосів, ні завдань
        job = self.env["td.gantry.job"].create(
            {"state": "queued", "sheets": 1, "product_id": self.board.id, "target_workcenter_id": self.wc_saw.id}
        )
        self.assertEqual(self.portal.with_user(self.user_f3d).td_tile(), {"jobs": 1, "sheets": 0, "waste_pct": None})
        self.assertTrue(job)

    # --- шина: хід завдання оновлює 3D ------------------------------------------------------------
    def test_events_notify_equipment_and_stacks(self):
        if "td.viewer.event" not in self.env:
            self.skipTest("td_viewer3d не встановлено")
        Event = type(self.env["td.viewer.event"])
        job = self.env["td.gantry.job"].create(
            {
                "state": "queued",
                "ws_id": "wj-9",
                "sheets": 2,
                "product_id": self.board.id,
                "target_workcenter_id": self.wc_saw.id,
            }
        )
        items = [
            {"id": 1, "ts": self.kt("10:00").isoformat(), "type": "job_started", "job": "wj-9", "stack": "PLT-T1"},
            {"id": 2, "ts": self.kt("10:01").isoformat(), "type": "sheet_placed", "job": "wj-9", "stack": "PLT-T1"},
        ]
        with patch.object(Event, "_notify") as notify:
            self.env["td.gantry.job"]._td_apply_events(items)
        calls = [c.args for c in notify.call_args_list]
        self.assertIn(("maintenance.equipment", ["GANTRY-1"], "state"), calls)
        self.assertIn(("stock.location", ["PLT-T1"], "stock"), calls)
        self.assertEqual((job.state, job.done), ("active", 1))


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestDemoGantry(F3DMachineCase):
    """AC-124: демо-історія порталу (`tools/demo_portal.demo_gantry`, R-31 п. 6)."""

    def _setup_cut(self):
        env = self.env
        self.put_stock(self.board, self.loc_t1, 30, self.lot_l1)
        self.stack_t1._td_refresh()
        env["ir.config_parameter"].sudo().set_param("td.viewer.demo_clock", "2026-10-12 10:30")
        mo1 = self.make_mo(self.wc_saw, qty=14, name="WH/MO/D0001")  # BOARD-T 0.5 × 14 = 7 арк.
        mo2 = self.make_mo(self.wc_saw, qty=6, name="WH/MO/D0002")  # 3 арк.
        for mo, start, state in ((mo1, "09:00", "done"), (mo2, "10:10", "progress")):
            wo = mo.workorder_ids[:1]
            wo.write({"date_start": self.kt(start), "state": state})
        return mo1, mo2

    def test_not_demo_or_existing_jobs_changes_nothing(self):
        self._setup_cut()
        with patch.object(demo_portal, "is_demo", return_value=False):
            self.assertEqual(demo_portal.demo_gantry(self.env), {"gantry_jobs": 0, "cut_maps": 0})
        self.assertFalse(self.env["td.gantry.job"].search_count([]))

    def test_builds_jobs_maps_and_stack_readings(self):
        mo1, mo2 = self._setup_cut()
        with patch.object(demo_portal, "is_demo", return_value=True):
            res = demo_portal.demo_gantry(self.env)
            again = demo_portal.demo_gantry(self.env)
        self.assertEqual(res, {"gantry_jobs": 2, "cut_maps": 2})
        self.assertEqual(again, {"gantry_jobs": 0, "cut_maps": 0})  # ідемпотентний
        jobs = self.env["td.gantry.job"].search([], order="id")
        j1, j2 = jobs
        self.assertEqual((j1.external_ref, j1.state, j1.sheets, j1.done), ("WH/MO/D0001", "done", 7, 7))
        self.assertEqual(len(j1.sheet_log), 7)
        self.assertEqual((j2.external_ref, j2.state, j2.sheets, j2.done), ("WH/MO/D0002", "active", 3, 2))
        self.assertEqual(parse_ts(j2.sheet_log[-1]["ts"]), self.kt("10:29:35"))  # останній лист — 25 с до «зараз»
        # портал один: завдання йдуть по черзі, без накладання
        self.assertLessEqual(j1.finished, j2.started)
        self.assertTrue(j1.cut_map_id and j1.cut_map_id.state == "released")
        self.assertEqual(j1.cut_map_id.production_id, mo1)
        self.assertTrue(6.0 <= j1.cut_map_id.plan_waste_pct < 15.0)
        self.assertEqual(j1.cut_map_id.plan_sheets, 7)
        self.assertEqual(j1.cut_map_id.gantry_job_id, j1)
        # показання стосу = Odoo − подане в МО, що не закриті
        stack = self.stack_t1
        self.assertEqual(stack.odoo_qty, 30)
        self.assertEqual(stack.ws_qty, 30 - 7 - 2)
        self.assertEqual(stack.state, "ok")
        self.assertTrue(mo2)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestGantryTileTour(F3DMachineHttpCase):
    def test_gantry_tile_tour(self):
        """AC-123: плитка «Портал» в «Огляді верстатів» і клік у завдання порталу (відходи — середньозважені: 8,0 %)."""
        mo = self.make_mo(self.wc_saw, qty=14, name="WH/MO/T0300")
        self.env["ir.config_parameter"].sudo().set_param("td.viewer.demo_clock", "2026-10-12 10:30")
        Job, Cut = self.env["td.gantry.job"], self.env["td.cut.map"]
        for sheets, waste, start in ((2, 6.0, "09:00"), (4, 9.0, "09:30")):
            cmap = Cut.create(
                {
                    "production_id": mo.id,
                    "material_product_id": self.board.id,
                    "sheet_length_mm": 2800,
                    "sheet_width_mm": 2070,
                    "thickness_mm": 16,
                    "qty": 14,
                    "state": "released",
                    "plan_sheets": sheets,
                    "plan_waste_pct": waste,
                }
            )
            Job.create(
                {
                    "state": "done",
                    "sheets": sheets,
                    "done": sheets,
                    "product_id": self.board.id,
                    "target_workcenter_id": self.wc_saw.id,
                    "production_id": mo.id,
                    "cut_map_id": cmap.id,
                    "started": self.kt(start),
                    "finished": self.kt(start) + timedelta(minutes=5),
                }
            )
        self.start_tour(
            "/odoo/action-td_machine_connect.action_td_machine_dashboard",
            "td_machine_connect_gantry_tile",
            login="admin",
            timeout=180,
        )
