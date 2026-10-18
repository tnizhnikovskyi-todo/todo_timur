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
