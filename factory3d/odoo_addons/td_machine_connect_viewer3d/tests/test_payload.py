"""DT-3/DT-5, R-30, R-31: `workcenters[code].downtime_cost`, `flow` і вузли порталу в повному payload переглядача."""

from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from odoo.addons.td_viewer3d.tests.common import F3dViewerBase


NOW = datetime(2026, 10, 12, 9, 0)  # 12:00 за Києвом (EEST, UTC+3), понеділок
DAY_START = datetime(2026, 10, 11, 21, 0)  # 00:00 цієї доби за Києвом, naive UTC


@tagged("post_install", "-at_install", "f3d", "f3d_mc_viewer3d")
class TestDowntimeCostPayload(F3dViewerBase):
    """DT-3: 3D «Простої, ₴» = вартість за поточну київську добу (а не за місяць чи весь час)."""

    @classmethod
    def _downtime(cls, start, hours):
        return cls.env["td.downtime"].create(
            {
                "machine_id": cls.machine.id,
                "date_start": start,
                "date_end": start + timedelta(hours=hours),
                "state_kind": "fault",
                "loss_id": cls.env.ref("mrp.block_reason1").id,
            }
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # цілодобовий календар (Київ): вартість рахується лише в плановому часі РЦ (DT-1), тут перевіряється межа доби
        attendance = [
            (0, 0, {"name": name, "dayofweek": str(dow), "hour_from": lo, "hour_to": hi, "day_period": period})
            for dow in range(7)
            for name, lo, hi, period in (("Ніч-ранок", 0.0, 12.0, "morning"), ("День-вечір", 12.0, 24.0, "afternoon"))
        ]
        cal = env["resource.calendar"].create(
            {"name": "TST 24/7", "tz": "Europe/Kyiv", "attendance_ids": [(5, 0, 0)] + attendance}
        )
        cls.wc = env["mrp.workcenter"].create(
            {
                "name": "TST DT",
                "code": "TSTDT",
                "td_code": "TST-DT-1",
                "costs_hour": 600.0,
                "resource_calendar_id": cal.id,
            }
        )
        cls.machine = env["td.machine"].create({"workcenter_id": cls.wc.id, "protocol": "manual"})
        cls._downtime(DAY_START + timedelta(hours=9), 2)  # сьогодні 09:00–11:00 за Києвом: 2 год = 1200
        cls._downtime(DAY_START - timedelta(hours=15), 1)  # вчора 09:00–10:00: у «сьогодні» не входить
        groups = ["base.group_user", "mrp.group_mrp_user", "stock.group_stock_user", "td_factory3d.group_td_manager"]
        cls.user_cost = cls._make_user("f3d_cost_manager", groups)

    def setUp(self):
        super().setUp()
        frozen = freeze_time(NOW)  # «зараз» фіксований: тест не залежить від дня запуску
        frozen.start()
        self.addCleanup(frozen.stop)

    def _cost(self):
        return self.payload(self.user_cost)["workcenters"]["TST-DT-1"]["downtime_cost"]

    def test_manager_gets_cost(self):
        """Лише сьогоднішній простій (1200); учорашній (600) і решта місяця не рахуються."""
        self.assertEqual(self._cost(), 1200.0)

    def test_kyiv_day_boundary(self):
        """Межа доби — північ за Києвом: 00:30 Києва (21:30 UTC) — сьогодні, 23:30 Києва (20:30 UTC) — вчора."""
        self._downtime(DAY_START + timedelta(minutes=30), 1)  # сьогодні, 1 год = 600
        self._downtime(DAY_START - timedelta(minutes=30), 1)  # вчора 23:30 → закінчується сьогодні, але почався вчора
        self.assertEqual(self._cost(), 1800.0)

    def test_no_downtime_today_zero(self):
        with freeze_time(NOW + timedelta(days=1)):  # наступна доба: простоїв ще не було
            self.assertEqual(self._cost(), 0.0)

    def test_user_without_manager_group_gets_no_cost(self):
        data = self.payload(self.user_f3d)
        self.assertIn("TST-DT-1", data["workcenters"])
        self.assertNotIn("downtime_cost", data["workcenters"]["TST-DT-1"])

    def test_kiosk_gets_no_cost(self):
        data = self.payload(self.user_kiosk, kiosk=True)
        self.assertNotIn("downtime_cost", data["workcenters"].get("TST-DT-1", {}))

    def test_cost_follows_rate_change(self):
        self.wc.costs_hour = 900.0
        self.assertEqual(self._cost(), 1800.0)


FLOW = {
    "station": "Розкрій",
    "key": "area:1",
    "load": 0.9,
    "queue": 3,
    "queue_delta": 1,
    "wait_min": 12.0,
    "output": 40.0,
    "rank": 1,
    "bottleneck": True,
    "period": "day",
    "codes": ["TST-DT-1"],
    "prev": [],
}


@tagged("post_install", "-at_install", "f3d", "f3d_mc_viewer3d")
class TestBottleneckFlowPayload(F3dViewerBase):
    """R-30 п. 5: `workcenters[code].flow` — показники ділянки є в payload для всіх, у т. ч. кіоску (не фінансові)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        wc = cls.env["mrp.workcenter"].create({"name": "TST FLOW", "code": "TSTFL", "td_code": "TST-DT-1"})
        cls.env["td.machine"].create({"workcenter_id": wc.id, "protocol": "manual"})

    def _nodes(self):
        return patch.object(type(self.env["td.bottleneck"]), "_td_flow_nodes", return_value={"TST-DT-1": dict(FLOW)})

    def test_user_gets_flow(self):
        with self._nodes():
            data = self.payload(self.user_f3d)
        self.assertEqual(data["workcenters"]["TST-DT-1"]["flow"], FLOW)

    def test_kiosk_gets_flow(self):
        with self._nodes():
            data = self.payload(self.user_kiosk, kiosk=True)
        self.assertEqual(data["workcenters"]["TST-DT-1"]["flow"]["queue"], 3)

    def test_failure_of_analytics_does_not_break_payload(self):
        failing = patch.object(type(self.env["td.bottleneck"]), "_td_flow_nodes", side_effect=ValueError("boom"))
        with failing, self.assertLogs("odoo.addons.td_machine_connect.tools.payload", level="ERROR"):
            data = self.payload(self.user_f3d)
        self.assertIn("TST-DT-1", data["workcenters"])
        self.assertNotIn("flow", data["workcenters"]["TST-DT-1"])


@tagged("post_install", "-at_install", "f3d", "f3d_mc_viewer3d")
class TestPortalPayload(F3dViewerBase):
    """R-31 п. 1–2: `equipment[GANTRY-1].portal` і `locations[PLT-*].portal` є в payload для всіх, у т. ч. кіоску."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        wh = env["stock.warehouse"].search([("company_id", "=", env.company.id)], limit=1)
        loc = env["stock.location"].search([("td_code", "=", "PLT-04C")], limit=1) or env["stock.location"].create(
            {
                "name": "PLT-04C",
                "location_id": wh.lot_stock_id.id,
                "td_code": "PLT-04C",
                "td_loc_kind": "stack",
                "td_capacity": 60,
            }
        )
        cls.stack = env["td.gantry.stack"].search([("location_id", "=", loc.id)], limit=1) or env[
            "td.gantry.stack"
        ].create({"location_id": loc.id})
        board = env["product.product"].create(
            {
                "name": "ДСП 16 мм тест 2800×2070",
                "default_code": "PLT-BOARD",
                "td_thickness_mm": 16,
                "td_sheet_length_mm": 2800,
                "td_sheet_width_mm": 2070,
            }
        )
        cls.stack.write({"ws_qty": 12, "ws_product": "PLT-BOARD", "ws_seen": fields.Datetime.now()})
        if not env["maintenance.equipment"].search_f3d("GANTRY-1"):
            env["maintenance.equipment"].create({"name": "Портальний склад плит (тест)", "td_code": "GANTRY-1"})
        wc = env["mrp.workcenter"].search_f3d("SAW-1") or env["mrp.workcenter"].create(
            {"name": "TST SAW-1", "code": "TSTSAW1", "td_code": "SAW-1"}
        )
        env["ir.config_parameter"].sudo().set_param("td.viewer.demo_clock", "2026-10-12 10:30")
        cls.job = env["td.gantry.job"].create(
            {
                "state": "active",
                "sheets": 3,
                "done": 1,
                "product_id": board.id,
                "target_workcenter_id": wc.id,
                "stack_id": cls.stack.id,
                "started": cls.env["td.bottleneck"]._td_now() - timedelta(minutes=5),
            }
        )

    def _portal(self, data):
        return data["equipment"]["GANTRY-1"]["portal"]

    def test_user_gets_portal_nodes(self):
        data = self.payload(self.user_f3d)
        portal = self._portal(data)
        self.assertEqual((portal["day"], portal["now"], portal["cycle_s"]), ("2026-10-12", 37800, 27))
        job = next(j for j in portal["jobs"] if j["id"] == self.job.name)
        self.assertEqual((job["state"], job["sheets"], job["done"], job["target"]), ("active", 3, 1, "SAW-1"))
        self.assertEqual(portal["today"]["jobs"], len(portal["jobs"]))
        node = data["locations"]["PLT-04C"]["portal"]
        self.assertEqual((node["qty"], node["src"], node["thickness"], node["capacity"]), (12, "portal", 16, 60))
        self.assertEqual(node["next"]["job"], self.job.name)

    def test_kiosk_gets_portal_nodes(self):
        data = self.payload(self.user_kiosk, kiosk=True)
        self.assertIn("portal", data["equipment"]["GANTRY-1"])
        self.assertEqual(data["locations"]["PLT-04C"]["portal"]["qty"], 12)

    def test_failure_of_portal_does_not_break_payload(self):
        failing = patch.object(type(self.env["td.portal"]), "_td_equipment_node", side_effect=ValueError("boom"))
        with failing, self.assertLogs("odoo.addons.td_machine_connect.tools.payload", level="ERROR"):
            data = self.payload(self.user_f3d)
        self.assertNotIn("portal", data["equipment"]["GANTRY-1"])
        self.assertIn("gantry", data["equipment"]["GANTRY-1"])
