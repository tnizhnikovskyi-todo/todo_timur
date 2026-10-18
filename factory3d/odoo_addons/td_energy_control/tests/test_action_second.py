"""AC-184…AC-186: клас B, друге підтвердження, сповіщення."""

from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestActionSecond(TestControlCommon):
    def test_class_b_awaiting_second(self):  # AC-184
        act = self.run_action("qs_close", user=self.u_en1)
        self.assertEqual(act.state, "awaiting_second")
        self.assertEqual(act.second_expires_at, NOW + timedelta(seconds=600))
        self.assertFalse(act.command_id)
        self.assertTrue(act.needs_second)
        direct = self.run_action("qs_open", user=self.u_chief)
        self.assertEqual(direct.state, "queued")
        self.assertFalse(direct.needs_second)

    def test_second_rules(self):  # AC-185
        act = self.run_action("chp_start", user=self.u_en1)
        self.assertEqual(act.state, "awaiting_second")
        with self.assertRaisesRegex(UserError, "інший енергетик"):
            self.ctl(self.u_en1).confirm_second(act.id)
        with self.assertRaises(AccessError):
            self.ctl(self.u_view).confirm_second(act.id)
        res = self.ctl(self.u_en2).confirm_second(act.id)
        self.assertEqual(res["state"], "queued")
        self.assertEqual(act.second_by, self.u_en2)
        self.assertTrue(act.command_id)
        with self.assertRaises(UserError):
            self.ctl(self.u_en2).confirm_second(act.id)
        other = self.run_action("qs_close", user=self.u_en1)
        self.assertEqual(self.ctl(self.u_chief2).confirm_second(other.id)["state"], "queued")
        late = self.run_action("bess_discharge", user=self.u_en1)
        self.Control.with_user(self.u_en2).with_context(f3d_now=NOW + timedelta(seconds=601))
        self.Action.with_context(f3d_now=NOW + timedelta(seconds=601))._cron_expire()
        self.assertEqual(late.state, "expired")
        with self.assertRaisesRegex(UserError, "Час другого підтвердження минув"):
            self.ctl(self.u_en2).confirm_second(late.id)

    def test_activities_and_pending(self):  # AC-186
        act = self.run_action("chp_start", user=self.u_en1)
        activities = (
            self.env["mail.activity"].sudo().search([("res_model", "=", "td.energy.action"), ("res_id", "=", act.id)])
        )
        users = activities.mapped("user_id")
        self.assertIn(self.u_en2, users)
        self.assertNotIn(self.u_en1, users)
        self.assertLessEqual(len(users), 10)
        pend = self.ctl(self.u_en2).get_control()["pending"]
        self.assertEqual([p["id"] for p in pend], [act.id])
        self.assertTrue(pend[0]["can_confirm_second"])
        mine = self.ctl(self.u_en1).get_control()["pending"]
        self.assertFalse(mine[0]["can_confirm_second"])
        self.assertEqual(self.ctl(self.u_view).get_control()["pending"], [])
        self.ctl(self.u_en2).confirm_second(act.id)
        self.assertFalse(
            self.env["mail.activity"]
            .sudo()
            .search_count([("res_model", "=", "td.energy.action"), ("res_id", "=", act.id)])
        )

    # --- кнопки форми журналу V-41 (type=object) -------------------------------------------------------------------
    def test_button_confirm_second(self):
        act = self.run_action("chp_start", user=self.u_en1)
        self.assertEqual(act.state, "awaiting_second")
        with self.assertRaisesRegex(UserError, "інший енергетик"):
            act.with_user(self.u_en1).action_confirm_second()
        with self.assertRaises(AccessError):
            act.with_user(self.u_view).action_confirm_second()
        self._enable_control(write=True, remote=False)  # D-46: гейт діє й для кнопки
        with self.assertRaisesRegex(UserError, "Дистанційне перемикання вимкнено"):
            act.with_user(self.u_en2).action_confirm_second()
        self._enable_control(write=True, remote=True)
        res = act.with_user(self.u_en2).action_confirm_second()
        self.assertEqual((res["type"], res["tag"]), ("ir.actions.client", "display_notification"))
        self.assertEqual(res["params"]["type"], "success")
        self.assertEqual((act.state, act.second_by), ("queued", self.u_en2))
        qs = self.run_action("qs_close", user=self.u_en1)
        self.assertEqual(qs.state, "awaiting_second")
        self._fresh("energy_control/ats/parallel_lock", 0)  # інтерлок: блокування АВР на момент другого підтвердження
        res = qs.with_user(self.u_chief2).action_confirm_second()
        self.assertEqual((qs.state, res["params"]["type"]), ("blocked", "warning"))
        self.assertIn("АВР", res["params"]["message"])

    def test_button_cancel(self):
        act = self.run_action("qs_close", user=self.u_en1)
        with self.assertRaises(AccessError):
            act.with_user(self.u_en2).action_cancel()  # не готував і не chief
        with self.assertRaises(AccessError):
            act.with_user(self.u_view).action_cancel()
        res = act.with_user(self.u_en1).action_cancel()
        self.assertEqual(res["params"]["type"], "success")
        self.assertEqual(act.state, "cancelled")
        act.with_user(self.u_en1).action_cancel()  # повтор ідемпотентний
        other = self.run_action("chp_start", user=self.u_en1)
        other.with_user(self.u_chief).action_cancel()
        self.assertEqual(other.state, "cancelled")
        queued = self.run_action("bess_charge", user=self.u_en1)
        self.assertEqual(queued.state, "queued")
        queued.with_user(self.u_en1).action_cancel()
        self.assertEqual((queued.state, queued.command_id.state), ("cancelled", "cancelled"))
        running = self.run_action("light_break", user=self.u_en1)
        self.finish(running, "executing")
        with self.assertRaises(UserError):
            running.with_user(self.u_en1).action_cancel()

    def test_button_undo(self):
        act = self.run_action("bess_charge", user=self.u_en1)
        self.finish(act, "done")
        with self.assertRaises(AccessError):
            act.with_user(self.u_view).action_undo()
        res = act.with_user(self.u_en1).action_undo()
        self.assertEqual(res["tag"], "display_notification")
        back = self.Action.search([("undo_of_id", "=", act.id)])
        self.assertEqual((back.kind_code, back.origin, back.state), ("bess_stop", "undo", "queued"))
        with self.assertRaisesRegex(UserError, "Скасування недоступне"):
            act.with_user(self.u_en1).action_undo()  # вже є зворотна дія / ресурс зайнятий
        qs = self.run_action("qs_close", user=self.u_chief)
        self.finish(qs, "done")
        self._enable_control(write=True, remote=False)  # зворотна дія qs_open — під D-46
        with self.assertRaisesRegex(UserError, "Дистанційне перемикання вимкнено"):
            qs.with_user(self.u_chief).action_undo()
        self._enable_control(write=True, remote=True)
        res = qs.with_user(self.u_en1).action_undo()  # клас B без chief → друге підтвердження
        undo_qs = self.Action.search([("undo_of_id", "=", qs.id)])
        self.assertEqual(undo_qs.state, "awaiting_second")
        self.assertEqual(res["params"]["type"], "success")
