"""DT-3/DT-5, R-30: `workcenters[code].downtime_cost` і `flow` у повному payload переглядача."""

from datetime import timedelta
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.td_viewer3d.tests.common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_mc_viewer3d")
class TestDowntimeCostPayload(F3dViewerBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.wc = env["mrp.workcenter"].create(
            {"name": "TST DT", "code": "TSTDT", "td_code": "TST-DT-1", "costs_hour": 600.0}
        )
        cls.machine = env["td.machine"].create({"workcenter_id": cls.wc.id, "protocol": "manual"})
        start = env["td.downtime"]._td_month_start() + timedelta(hours=1)  # завжди в поточному місяці
        env["td.downtime"].create(
            {
                "machine_id": cls.machine.id,
                "date_start": start,
                "date_end": start + timedelta(hours=2),
                "state_kind": "fault",
                "loss_id": env.ref("mrp.block_reason1").id,
            }
        )
        groups = ["base.group_user", "mrp.group_mrp_user", "stock.group_stock_user", "td_factory3d.group_td_manager"]
        cls.user_cost = cls._make_user("f3d_cost_manager", groups)

    def test_manager_gets_cost(self):
        data = self.payload(self.user_cost)
        self.assertEqual(data["workcenters"]["TST-DT-1"]["downtime_cost"], 1200.0)

    def test_user_without_manager_group_gets_no_cost(self):
        data = self.payload(self.user_f3d)
        self.assertIn("TST-DT-1", data["workcenters"])
        self.assertNotIn("downtime_cost", data["workcenters"]["TST-DT-1"])

    def test_kiosk_gets_no_cost(self):
        data = self.payload(self.user_kiosk, kiosk=True)
        self.assertNotIn("downtime_cost", data["workcenters"].get("TST-DT-1", {}))

    def test_cost_follows_rate_change(self):
        self.wc.costs_hour = 900.0
        self.assertEqual(self.payload(self.user_cost)["workcenters"]["TST-DT-1"]["downtime_cost"], 1800.0)


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
