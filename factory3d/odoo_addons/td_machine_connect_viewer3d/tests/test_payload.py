"""DT-3/DT-5: `workcenters[code].downtime_cost` у повному payload переглядача (td_viewer3d + td_machine_connect)."""

from datetime import timedelta

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
