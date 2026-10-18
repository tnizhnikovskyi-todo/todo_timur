"""AC-208, AC-209: скасування дій (R-56 п.5–6)."""

from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestUndo(TestControlCommon):
    def done(self, kind, params=None, user=None):
        act = self.run_action(kind, params, user=user or self.u_chief)
        self.finish(act, "done", "виконано")
        return act

    def undo(self, act, user=None, ctl_now=None):
        ctl = self.ctl(user or self.u_chief)
        if ctl_now:
            ctl = ctl.with_context(f3d_now=ctl_now)
        prep = ctl.undo(act.id)
        ctl.confirm(prep["token"])
        return self.Action.browse(prep["action_id"]).sudo()

    def test_bess_undo(self):  # AC-208
        act = self.done("bess_charge")
        act.invalidate_recordset()
        self.assertTrue(act.undo_available)
        back = self.undo(act)
        self.assertEqual((back.kind_code, back.origin, back.undo_of_id), ("bess_stop", "undo", act))
        self.finish(back, "done")
        act.invalidate_recordset()
        self.assertEqual(act.undone_by_id, back)
        self.assertFalse(act.undo_available)
        with self.assertRaises(UserError):
            self.ctl(self.u_chief).undo(act.id)

    def test_window_and_later_action(self):  # AC-208
        act = self.done("bess_charge")
        late = self.Control.with_user(self.u_chief).with_context(f3d_now=NOW + timedelta(minutes=16))
        act.invalidate_recordset()
        with self.assertRaisesRegex(UserError, "Скасування недоступне"):
            late.undo(act.id)
        act2 = self.done("bess_charge", {"power_kw": 20})
        act3 = self.run_action("bess_stop", user=self.u_chief)
        act3.invalidate_recordset()
        act2.invalidate_recordset()
        self.assertFalse(act2.undo_available)  # є пізніша дія над ресурсом

    def test_undo_kinds(self):  # AC-209
        qs = self.done("qs_close")
        self.assertEqual(self.undo(qs).kind_code, "qs_open")
        air = self.done("air_setpoint", {"setpoint_bar": 6.4})
        self.assertEqual(air.undo_params, {"setpoint_bar": 7.0})
        back = self.undo(air)
        self.assertEqual(back.kind_code, "air_setpoint")
        self.assertEqual(back.params, {"setpoint_bar": 7.0})
        tog = self.done("scenario_toggle", {"scenario": "self", "enabled": True})
        self.assertEqual(self.undo(tog).params, {"scenario": "self", "enabled": False})
        prev = self.Scenario.search([("code", "=", "peak")])._td_params()
        par = self.done("scenario_params", {"scenario": "peak", "params": {"limit_kw": 700}})
        self.assertEqual(par.undo_params["params"]["limit_kw"], prev["limit_kw"])
        self.undo(par)
        self.assertEqual(self.Scenario.search([("code", "=", "peak")])._td_params()["limit_kw"], prev["limit_kw"])
