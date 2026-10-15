from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.tests import tagged

from .. import hooks
from .flow import YardFlowCase, at, freeze

NOW = datetime(2026, 10, 14, 3, 0)


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardCron(YardFlowCase):
    def _event(self, days, key):
        return self.env["f3d.yard.lpr.event"].create(
            {
                "ts": NOW - timedelta(days=days),
                "received_at": NOW - timedelta(days=days),
                "dedup_key": key,
                "camera_code": "CAM-05",
                "plate_norm": "AA1111KT",
            }
        )

    def _attach(self, event):
        return self.env["ir.attachment"].create(
            {"name": "img.jpg", "res_model": event._name, "res_id": event.id, "raw": b"\xff\xd8x"}
        )

    def test_crons_defined(self):  # §6
        for xmlid, method in (
            ("cron_f3d_yard_queue", "_cron_queue"),
            ("cron_f3d_yard_gc", "_cron_gc"),
            ("cron_f3d_yard_day_reset", "_cron_day_reset"),
        ):
            cron = self.env.ref("factory3d_yard.%s" % xmlid)
            self.assertTrue(cron.active)
            self.assertEqual(cron.model_id.model, "f3d.yard.visit")
            self.assertEqual(cron.user_id, self.env.ref("base.user_root"))
            self.assertIn(method, cron.code)

    def test_cron_times(self):  # §6: найближчі 03:00 / 00:05 за Києвом
        kyiv = ZoneInfo("Europe/Kyiv")
        now = datetime(2026, 10, 14, 1, 0, tzinfo=kyiv)
        for at_time, expected in ((hooks.CRONS[0][1], (14, 3, 0)), (hooks.CRONS[1][1], (15, 0, 5))):
            local = hooks._next_local(at_time, now).replace(tzinfo=timezone.utc).astimezone(kyiv)
            self.assertEqual((local.day, local.hour, local.minute), expected)
        hooks.set_cron_times(self.env)
        self.assertTrue(self.env.ref("factory3d_yard.cron_f3d_yard_gc").nextcall)

    def test_gc_pii(self):  # AC-70
        old = self._visit(plate="АА1111КТ", driver_phone="+380501112233", driver_doc="ВВ123456")
        old.write({"state": "left", "left_at": NOW - timedelta(days=96)})
        fresh = self._visit(plate="АА2222КТ", driver_phone="+380502223344", driver_doc="ВВ654321")
        fresh.write({"state": "left", "left_at": NOW - timedelta(days=86)})
        rej = self._visit(plate="АА3333КТ", driver_phone="+380503334455")
        rej.write({"state": "rejected", "rejected_at": NOW - timedelta(days=100)})
        with freeze(NOW):
            res = self.env["f3d.yard.visit"]._cron_gc()
        self.assertGreaterEqual(res["pii_cleared"], 2)
        self.assertEqual(
            (old.driver_phone, old.driver_doc, old.pii_cleared, old.plate), (False, False, True, "АА1111КТ")
        )
        self.assertTrue(rej.pii_cleared)
        self.assertEqual((fresh.driver_phone, fresh.pii_cleared), ("+380502223344", False))

    def test_gc_lpr_and_weighings(self):  # AC-71
        old, keep = self._event(31, "gc-old"), self._event(29, "gc-keep")
        att_old, att_keep = self._attach(old), self._attach(keep)
        scale = self.env.ref("factory3d_yard.scale_truck")
        W = self.env["f3d.yard.weighing"]
        w_old = W.create({"scale_id": scale.id, "kind": "in", "weight_kg": 1000, "ts": NOW - timedelta(days=8)})
        w_new = W.create({"scale_id": scale.id, "kind": "in", "weight_kg": 1000, "ts": NOW - timedelta(days=6)})
        self.assertEqual((w_old.state, w_new.state), ("unassigned", "unassigned"))
        with freeze(NOW):
            res = self.env["f3d.yard.visit"]._cron_gc()
        self.assertFalse(old.exists())
        self.assertFalse(att_old.exists())
        self.assertTrue(keep.exists() and att_keep.exists())
        self.assertFalse(w_old.exists())
        self.assertTrue(w_new.exists())
        self.assertEqual(
            (res["lpr_deleted"] >= 1, res["images_deleted"] >= 1, res["weighings_deleted"] >= 1), (True,) * 3
        )

    def test_day_reset_and_no_show(self):  # AC-80
        gate = self.env.ref("factory3d_yard.gate_w")
        gate.write({"counter_value": 17, "passes_today": 5, "admitted_today": 4, "tailgate_today": 1})
        self.env["f3d.yard.visit"]._cron_day_reset()
        self.assertEqual(
            (gate.passes_day_start, gate.passes_today, gate.admitted_today, gate.tailgate_today), (17, 0, 0, 0)
        )
        visit = self._visit(plate="АА4444КТ")
        self._booking(visit, self.dock_t1, at(10), at(11), confirm=True)
        self._force(visit, "planned")
        with freeze(at(14)):
            self.env["f3d.yard.visit"]._cron_queue()
            self.assertTrue(visit.is_no_show)
            self.assertIsInstance(fields.Datetime.now(), datetime)
