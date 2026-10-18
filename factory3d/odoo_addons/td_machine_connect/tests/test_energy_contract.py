"""AC-45, AC-46: інтервали для energy (R-28)."""

from datetime import datetime

from odoo.tests import tagged

from .common import F3DMachineCase, kt


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestEnergyContract(F3DMachineCase):
    def setUp(self):
        super().setUp()
        self.wo = self.make_mo(self.wc_ua, qty=14).workorder_ids[:1]
        self.make_log(self.m_ua, "setup", "09:40", "09:55", wo=self.wo)
        self.make_log(self.m_ua, "working", "09:55", "10:25:48", wo=self.wo, pieces=10)
        self.make_log(self.m_ua, "idle", "10:25:48", "10:30")

    def test_wo_intervals_window(self):
        Machine = self.env["td.machine"]
        res = Machine._f3d_wo_intervals(self.wo)
        self.assertEqual(
            res, {self.wo.id: [(kt("09:40"), kt("09:55"), "setup"), (kt("09:55"), kt("10:25:48"), "working")]}
        )
        res = Machine._f3d_wo_intervals(self.wo, kt("10:00"), kt("10:10"))
        self.assertEqual(res, {self.wo.id: [(kt("10:00"), kt("10:10"), "working")]})

    def test_open_interval_until_now(self):
        self.make_log(self.m_io, "working", "10:20", None, wo=self.wo)
        res = self.env["td.machine"]._f3d_wo_intervals(self.wo, kt("10:00"))
        self.assertEqual(res[self.wo.id][-1], (kt("10:20"), datetime.utcnow().replace(microsecond=0), "working"))

    def test_wc_intervals(self):
        res = self.env["td.machine"]._f3d_wc_intervals(self.wc_ua, kt("09:00"), kt("11:00"))
        self.assertEqual(
            res,
            [
                (kt("09:40"), kt("09:55"), "setup", self.wo.id),
                (kt("09:55"), kt("10:25:48"), "working", self.wo.id),
                (kt("10:25:48"), kt("10:30"), "idle", False),
            ],
        )

    def test_run_setup_minutes(self):
        """AC-46: хвилини завдання додаються при закритті інтервалу (R-04 п. 3) через `_f3d_commit_state`."""
        wo = self.make_mo(self.wc_io, qty=5).workorder_ids[:1]
        m = self.m_io.sudo()
        m.write({"active_workorder_id": wo.id})
        m._f3d_commit_state("setup", kt("09:40"))
        m._f3d_commit_state("working", kt("09:55"))
        m._f3d_commit_state("idle", kt("10:25:48"))
        self.assertAlmostEqual(wo.td_run_min, 30.8, 1)
        self.assertAlmostEqual(wo.td_setup_min, 15.0, 1)
