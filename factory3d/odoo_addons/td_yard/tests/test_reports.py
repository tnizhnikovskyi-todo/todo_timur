from odoo.tests import tagged

from ..tools import params as P
from .flow import YardFlowCase, at


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardReports(YardFlowCase):
    def test_wait_avg_by_carrier(self):  # AC-60
        carrier = self.env["res.partner"].create({"name": "Перевізник Т", "is_company": True})
        for i, wait in enumerate((20, 40)):
            self._visit(plate="АА%04dКТ" % i, carrier_id=carrier.id).write(
                {"arrived_at": at(9, 0), "at_dock_at": at(9, wait)}
            )
        self._visit(plate="АА9999КТ", carrier_id=carrier.id).write({"arrived_at": at(9, 0)})
        group = self.env["td.yard.visit"].read_group(
            [("carrier_id", "=", carrier.id)], ["wait_min:avg"], ["carrier_id"]
        )
        self.assertEqual(group[0]["wait_min"], 30.0)

    def test_dock_report(self):  # AC-61
        visit = self._visit(plate="АА1234КТ", batch_id=self._batch().id)
        self._booking(visit, self.dock_t1, at(9, 30), at(10, 30), confirm=True)
        visit.write(
            {
                "state": "left",
                "arrived_at": at(9, 10),
                "at_dock_at": at(9, 30),
                "handling_end_at": at(10, 50),
                "weighed_out_at": at(11, 0),
                "left_at": at(11, 5),
            }
        )
        self.assertEqual((visit.wait_min, visit.dock_min, visit.total_min), (20.0, 80.0, 115.0))
        Report = self.env["td.yard.dock.report"]
        Report.flush_model()
        self.env["td.yard.visit"].flush_model()
        row = Report.search([("dock_id", "=", self.dock_t1.id)])
        self.assertEqual(len(row), 1)
        self.assertEqual((row.busy_min, row.idle_min, row.occupancy_pct, row.visit_count), (80.0, 400.0, 16.7, 1))
        P.set_param(self.env, "dock_shift_min", "600")
        self.env["ir.config_parameter"].flush_model()
        Report.invalidate_model()
        self.assertEqual(Report.search([("dock_id", "=", self.dock_t1.id)]).idle_min, 520.0)
