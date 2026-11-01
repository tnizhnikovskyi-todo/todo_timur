"""AC-32 (M-14, R-22): заявки ТО за сигналами пожежної безпеки."""

from contextlib import contextmanager

from odoo.tests import tagged

from .common import FireCase


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestRequests(FireCase):
    CODE = "fire/groups/FA-CUT/state"

    def requests(self):
        sig = self.env["td.signal"].search([("code", "=", self.CODE)])
        return self.env["maintenance.request"].search([("td_signal_id", "=", sig.id)])

    def test_zone_fault_request_linked(self):
        self.push_text(self.CODE, "fault", self.at(0))
        request = self.requests()
        self.assertEqual(len(request), 1)
        self.assertEqual(request.td_fire_zone_id, self.z_cut)
        event = self.ev("fault", object_code="FA-CUT")
        self.assertEqual(request.td_fire_event_id, event)
        self.assertEqual(event.request_id, request)
        self.assertEqual(request.maintenance_team_id, self.team)
        self.assertIn("Пожежна безпека: зона FA-CUT (Розкрій).", request.description)
        self.assertEqual(request.action_f3d_fire_open_zone()["res_id"], self.z_cut.id)

    def test_no_duplicate(self):
        self.push_text(self.CODE, "fault", self.at(0))
        self.push_text(self.CODE, "tamper", self.at(30))
        self.push_text(self.CODE, "fault", self.at(60))
        self.assertEqual(len(self.requests()), 1)

    def test_team_param_overrides(self):
        other = self.env["maintenance.team"].create({"name": "Інша команда"})
        self.equipment["FA-CUT"].maintenance_team_id = other
        self.push_text(self.CODE, "fault", self.at(0))
        self.assertEqual(self.requests().maintenance_team_id, self.team)

    @contextmanager
    def capture_queries(self):
        queries = []
        yield from self._patchExecute(queries)

    def test_zone_request_compute_batched(self):  # один пошук заявок на весь набір зон
        Request, Stage = self.env["maintenance.request"], self.env["maintenance.stage"]
        open_stage = Stage.search([("done", "=", False)], limit=1)
        done_stage = Stage.search([("done", "=", True)], limit=1)
        self.assertTrue(open_stage and done_stage)
        zones = self.z_cut | self.z_eb | self.z_cnc | self.z_fac | self.z_fg | self.z_rcv1
        mk = lambda name, stage, **kw: Request.create({"name": name, "stage_id": stage.id, **kw})  # noqa: E731
        # z_fac: дві відкриті заявки за зоною — береться перша за id
        fac_first = mk("ТО-1", open_stage, td_fire_zone_id=self.z_fac.id)
        mk("ТО-2", open_stage, td_fire_zone_id=self.z_fac.id)
        # z_cut: закрита заявка ігнорується, далі — відкрита за сигналом групи
        mk("Закрита", done_stage, td_fire_zone_id=self.z_cut.id)
        cut_signal = mk("За сигналом", open_stage, td_signal_id=self.z_cut.signal_id.id)
        # z_eb: за сигналом, але раніше за id, ніж заявка за зоною — береться менший id
        eb_signal = mk("Сигнал EB", open_stage, td_signal_id=self.z_eb.signal_id.id)
        mk("Зона EB", open_stage, td_fire_zone_id=self.z_eb.id)
        zones.invalidate_recordset(["maintenance_request_id", "maintenance_request_name"])
        with self.capture_queries() as queries:
            got = {z.code: (z.maintenance_request_id, z.maintenance_request_name) for z in zones}
        self.assertEqual(got[self.z_fac.code], (fac_first, "ТО-1"))
        self.assertEqual(got[self.z_cut.code], (cut_signal, "За сигналом"))
        self.assertEqual(got[self.z_eb.code], (eb_signal, "Сигнал EB"))
        self.assertEqual(got[self.z_cnc.code], (Request, False))
        self.assertEqual(got[self.z_fg.code][0], Request)
        requests_sql = [q for q in queries if 'FROM "maintenance_request"' in q]
        self.assertLessEqual(len(requests_sql), 2, requests_sql)  # пошук + читання; не по запиту на зону
