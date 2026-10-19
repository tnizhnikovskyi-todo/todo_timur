"""AC-52…AC-56: завдання порталу — створення з МО, відправка, результати команд, дзеркало woodStore, списання."""

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import F3DMachineCase

SRC = "REST-WOODSTORE-T"
FEED_PAYLOAD = {
    "op": "feed",
    "stack": "PLT-T1",
    "target": "SAW-T",
    "sheets": 4,
    "product": "BOARD-T",
    "priority": 5,
    "ref": "WH/MO/T0001",
}


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestGantryJob(F3DMachineCase):
    def setUp(self):
        super().setUp()
        # telemetry `_td_handler_models` чекає класи від `registry.descendants`, а в 19.0 це імена: 0 обробників
        patcher = patch.object(
            type(self.env["td.push.handler"]),
            "_td_handler_models",
            lambda _self, route: ["td.push.handler.machine_connect"] if route.startswith("mc_") else [],
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.Job = self.env["td.gantry.job"]
        self.env["stock.quant"]._update_available_quantity(self.board, self.loc_t1, 45, lot_id=self.lot_l1)
        self.mo = self.make_mo(self.wc_saw, name="WH/MO/T0001", qty=4, comps=((self.board, 1),))

    def _job(self, **kw):
        vals = {
            "type": "feed",
            "product_id": self.board.id,
            "target_workcenter_id": self.wc_saw.id,
            "stack_id": self.stack_t1.id,
            "production_id": self.mo.id,
            "external_ref": self.mo.name,
            "sheets": 4,
        }
        return self.Job.create({**vals, **kw})

    def test_from_production_no_dup(self):
        job = self.Job._td_from_production(self.mo)
        self.assertEqual(self.Job._td_from_production(self.mo), job)
        self.assertEqual(self.Job.search_count([("production_id", "=", self.mo.id)]), 1)
        self.assertEqual((job.type, job.state, job.origin), ("feed", "draft", "odoo"))
        self.assertEqual((job.stack_id, job.lot_id, job.sheets), (self.stack_t1, self.lot_l1, 4))
        self.assertEqual((job.product_id, job.target_workcenter_id), (self.board, self.wc_saw))
        self.assertEqual(job.external_ref, "WH/MO/T0001")
        mo2 = self.make_mo(self.wc_cnc, comps=((self.board, 0.5),))
        with self.assertRaises(UserError):
            self.Job._td_from_production(mo2)
        job.state = "done"
        with self.assertRaises(UserError):  # плити вже подано
            self.Job._td_from_production(self.mo)

    def test_stack_product_mismatch(self):
        with self.assertRaises(ValidationError):
            self._job(product_id=self.board2.id)

    def test_send_payload(self):
        job = self.Job._td_from_production(self.mo)
        job.action_send()
        self.assertEqual(job.state, "to_send")
        self.gantry_tick("10:31")
        self.assertEqual(job.state, "to_send")
        self.assertTrue(job.error.startswith("Запис вимкнено"))
        self.enable_write()
        self.gantry_tick("10:32")
        self.assertEqual(job.state, "sent")
        cmd = job.command_id
        self.assertEqual(cmd.payload, FEED_PAYLOAD)
        self.assertEqual(cmd.text, "feed;PLT-T1;SAW-T;4;BOARD-T;5;WH/MO/T0001")
        self.assertEqual((cmd.signal_id, cmd.origin, cmd.td_gantry_job_id), (self.sig_g_cmd, "machine_connect", job))

    def test_command_results(self):
        self.enable_write()
        jobs = [self._job(state="to_send") for _i in range(3)]
        self.gantry_tick("10:31")
        self.assertEqual([j.state for j in jobs], ["sent"] * 3)
        self.cmd_done(jobs[0].command_id, data={"id": "wj-00412", "state": "queued"})
        self.assertEqual((jobs[0].ws_id, jobs[0].state), ("wj-00412", "queued"))
        self.cmd_fail(jobs[1].command_id, "CONFLICT: not enough sheets")
        self.assertEqual(jobs[1].state, "error")
        self.assertIn("CONFLICT", jobs[1].error)
        self.cmd_expire(jobs[2].command_id)
        self.assertEqual((jobs[2].state, jobs[2].error), ("error", "Колектор не забрав команду"))
        jobs[2].action_retry()
        self.assertEqual(jobs[2].state, "to_send")
        # скасування в порталі: queued -> команда cancel -> cancelled
        jobs[0].action_cancel()
        cmd = jobs[0].cancel_command_id
        self.assertEqual(cmd.payload, {"op": "cancel", "id": "wj-00412"})
        self.cmd_done(cmd, data={"id": "wj-00412", "state": "cancelled"})
        self.assertEqual(jobs[0].state, "cancelled")

    def test_cancel_needs_write(self):
        job = self._job(state="queued", ws_id="wj-1")
        with self.assertRaises(UserError):
            job.action_cancel()
        local = self._job(state="to_send")
        local.action_cancel()
        self.assertEqual(local.state, "cancelled")

    def test_mirror_and_sheets(self):
        item = {
            "id": "wj-00500",
            "type": "feed",
            "source": "PLT-T1",
            "target": "SAW-T",
            "sheets": 4,
            "done": 0,
            "product": "BOARD-T",
            "priority": 5,
            "external_ref": "WH/MO/T0001",
            "state": "active",
            "created": "2026-10-12T07:00:00Z",
        }
        self.push_event("mc_woodstore", {"kind": "jobs", "source": SRC, "items": [item]}, SRC)
        job = self.Job.search([("ws_id", "=", "wj-00500")])
        self.assertEqual((job.origin, job.production_id, job.state), ("machine", self.mo, "active"))
        self.assertEqual(
            (job.stack_id, job.target_workcenter_id, job.product_id), (self.stack_t1, self.wc_saw, self.board)
        )
        ev = [
            {"id": "e1", "ts": "2026-10-12T07:01:00Z", "type": "sheet_placed", "job": "wj-00500", "stack": "PLT-T1"},
            {"id": "e2", "ts": "2026-10-12T07:02:00Z", "type": "sheet_placed", "job": "wj-00500", "stack": "PLT-T1"},
            {"id": "e1", "ts": "2026-10-12T07:01:00Z", "type": "sheet_placed", "job": "wj-00500", "stack": "PLT-T1"},
        ]
        self.push_event("mc_woodstore", {"kind": "events", "source": SRC, "items": ev}, SRC)
        self.assertEqual((job.done, len(job.sheet_log)), (2, 2))
        done = {"id": "e3", "ts": "2026-10-12T07:03:00Z", "type": "job_finished", "job": "wj-00500"}
        self.push_event("mc_woodstore", {"kind": "events", "source": SRC, "items": [done]}, SRC)
        self.assertEqual(job.state, "done")
        self.assertEqual(job.consumed_qty, 2)
        # тревога порталу — у чатер обладнання
        alarm = {"id": "e4", "ts": "2026-10-12T07:04:00Z", "type": "alarm", "message": "Вакуум"}
        self.push_event("mc_woodstore", {"kind": "events", "source": SRC, "items": [alarm]}, SRC)
        bodies = self.eq_gantry.message_ids.mapped("body")
        self.assertTrue(any("Тривога порталу: Вакуум" in (b or "") for b in bodies))

    def test_consume_move_lines(self):
        self.env["stock.quant"]._update_available_quantity(self.board, self.loc_t2, 10, lot_id=self.lot_l2)
        self.stack_t2._td_refresh()
        self.assertEqual(self.stack_t2.odoo_lot_id, self.lot_l2)
        move = self.mo.move_raw_ids.filtered(lambda m: m.product_id == self.board)
        self.assertEqual(move.move_line_ids.location_id, self.loc_t1)  # резерв рядка був у PLT-T1
        log = [{"id": "s%d" % i, "ts": "2026-10-12T07:00:00Z", "stack": "PLT-T2", "lot": "L2"} for i in range(4)]
        job = self._job(state="done", done=4, sheet_log=log)
        job._td_consume()
        lines = move.move_line_ids
        t2 = lines.filtered(lambda ml: ml.location_id == self.loc_t2)
        self.assertEqual((sum(t2.mapped("quantity")), t2.picked, t2.lot_id), (4, True, self.lot_l2))
        self.assertEqual(sum(lines.filtered(lambda ml: ml.location_id == self.loc_t1).mapped("quantity")), 0)
        self.assertEqual(job.consumed_qty, 4)
        before = (len(move.move_line_ids), sum(move.move_line_ids.mapped("quantity")))
        job._td_consume()
        self.assertEqual((len(move.move_line_ids), sum(move.move_line_ids.mapped("quantity"))), before)
        self.assertEqual(job.consumed_qty, 4)
