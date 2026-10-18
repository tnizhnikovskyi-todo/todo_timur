"""AC-179, AC-180, AC-182, AC-183, AC-187…AC-193: потік prepare → confirm → виконання, токени, транспорт."""

import hashlib
import secrets
from datetime import timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestActionFlow(TestControlCommon):
    def test_prepare_shape(self):  # AC-179
        prep = self.ctl(self.u_en1).prepare("qs_close")
        for key in ("action_id", "token", "ttl_s", "kind", "cls", "title", "text", "sub", "checks", "blocked",
                    "blocked_reason", "needs_second", "confirm_label", "disabled_reason"):  # fmt: skip
            self.assertIn(key, prep)
        self.assertEqual((prep["ttl_s"], prep["kind"], prep["cls"]), (60, "qs_close", "B"))
        self.assertEqual(prep["verify_timeout_s"], 30)
        self.assertEqual(prep["title"], "Увімкнути секційний вимикач QS?")
        self.assertEqual([c["code"] for c in prep["checks"]][:2], ["controller_remote", "data_fresh"])
        self.assertTrue(prep["needs_second"])
        self.assertEqual(prep["confirm_label"], "Підтвердити (1/2)")
        self.assertGreaterEqual(len(prep["token"]), 32)
        act = self.Action.browse(prep["action_id"])
        self.assertEqual(act.token_hash, hashlib.sha256(prep["token"].encode()).hexdigest())
        self.assertNotIn(prep["token"], str(act.read()))
        chief = self.ctl(self.u_chief).prepare("qs_close")
        self.assertFalse(chief["needs_second"])
        self.assertEqual(chief["confirm_label"], "Виконати")
        self.assertTrue(prep["checks"][3]["hard"])
        self.assertEqual(prep["checks"][3]["state"], "ok")

    def test_prepare_dedup(self):  # AC-180
        a = self.ctl(self.u_en1).prepare("bess_charge")
        b = self.ctl(self.u_en1).prepare("bess_charge")
        self.assertEqual(a["action_id"], b["action_id"])
        self.assertNotEqual(a["token"], b["token"])
        with self.assertRaises(UserError):
            self.ctl(self.u_en1).confirm(a["token"])
        later = self.Control.with_user(self.u_en1).with_context(f3d_now=NOW + timedelta(seconds=6))
        c = later.prepare("bess_charge")
        self.assertNotEqual(c["action_id"], a["action_id"])

    def test_confirm_class_a_command(self):  # AC-182
        prep = self.ctl(self.u_en1).prepare("bess_charge", {"power_kw": 50, "until": "16:00"})
        res = self.ctl(self.u_en1).confirm(prep["token"])
        act = self.Action.browse(prep["action_id"])
        self.assertEqual((res["state"], act.state), ("queued", "queued"))
        cmd = self.env["td.command"].search([("energy_action_id", "=", act.id)])
        self.assertEqual(len(cmd), 1)
        self.assertEqual((cmd.signal_id.code, cmd.origin), ("energy_control/intent", "energy"))
        payload = cmd.payload
        self.assertEqual((payload["v"], payload["kind"], payload["cls"]), (1, "bess_charge", "A"))
        self.assertEqual(payload["params"], {"power_kw": 50.0, "until": "16:00", "soc_limit_pct": 95.0})
        self.assertEqual(payload["idem"], act.idem)
        self.assertEqual(cmd.expires_at, NOW + timedelta(seconds=120))
        res2 = self.ctl(self.u_en1).confirm(prep["token"])  # ідемпотентність
        self.assertEqual(res2["state"], "queued")
        self.assertEqual(self.env["td.command"].search_count([("energy_action_id", "=", act.id)]), 1)

    def test_token_errors(self):  # AC-183
        prep = self.ctl(self.u_en1).prepare("bess_charge")
        with self.assertRaises(AccessError):
            self.ctl(self.u_en2).confirm(prep["token"])
        with self.assertRaisesRegex(UserError, "Підтвердження не знайдено"):
            self.ctl(self.u_en1).confirm("nope")
        late = self.Control.with_user(self.u_en1).with_context(f3d_now=NOW + timedelta(seconds=61))
        with self.assertRaisesRegex(UserError, "Час підтвердження минув"), self.cr.savepoint():
            late.confirm(prep["token"])
        act = self.Action.browse(prep["action_id"])
        self.Action.with_context(f3d_now=NOW + timedelta(seconds=61))._cron_expire()
        self.assertEqual(act.state, "expired")
        prep2 = self.ctl(self.u_en1).prepare("bess_charge", {"power_kw": 40})
        self.ctl(self.u_en1).cancel(prep2["token"])
        with self.assertRaises(UserError):
            self.ctl(self.u_en1).confirm(prep2["token"])

    def test_resource_conflict(self):  # AC-187
        first = self.run_action("bess_charge", user=self.u_en1)
        self.assertEqual(first.state, "queued")
        prep = self.ctl(self.u_en1).prepare("bess_stop")
        res = self.ctl(self.u_en1).confirm(prep["token"])
        self.assertEqual(res["state"], "blocked")
        self.assertIn("Для ресурсу «bess» уже виконується дія", res["blocked_reason"])

    def test_command_transport(self):  # AC-188
        act = self.run_action("bess_charge", user=self.u_en1)
        cmd = act.command_id
        cmd.write({"state": "sent"})
        self.assertEqual(act.state, "sent")
        cmd.write({"state": "done", "result_data": {"accepted": True, "state": "executing", "run_id": "r1"}})
        self.assertEqual(act.state, "executing")
        act2 = self.run_action("qs_close", user=self.u_chief)
        act2.command_id.write(
            {"state": "done", "result_data": {"accepted": False, "state": "blocked", "reason": "lock=0"}}
        )
        self.assertEqual((act2.state, act2.error), ("blocked", "lock=0"))
        act3 = self.run_action("chp_start", user=self.u_chief)
        act3.command_id.write(
            {"state": "done", "result_data": {"accepted": False, "state": "rejected", "reason": "bad params"}}
        )
        self.assertEqual(act3.state, "failed")
        act4 = self.run_action("light_break", user=self.u_en1)
        act4.command_id.write({"state": "failed", "error": "timeout"})
        self.assertEqual((act4.state, act4.error), ("failed", "timeout"))
        act5 = self.run_action("vent_eco", user=self.u_en1)
        act5.command_id.write({"state": "expired"})
        self.assertEqual(act5.state, "expired")
        act6 = self.run_action("air_setpoint", {"setpoint_bar": 6.5}, user=self.u_chief)
        act6.command_id.write({"state": "cancelled"})
        self.assertEqual(act6.state, "cancelled")

    def test_engine_reports(self):  # AC-189
        advice = (
            self.env["td.energy.advice"]
            .sudo()
            .create({"code": "T", "title": "t", "text": "t", "level": "info", "state": "open", "actions": []})
        )
        prep = self.ctl(self.u_en1).prepare("bess_charge", advice_id=advice.id)
        self.ctl(self.u_en1).confirm(prep["token"])
        act = self.Action.browse(prep["action_id"]).sudo()
        self.assertTrue(self.finish(act, "executing"))
        self.assertEqual(act.state, "executing")
        self.assertTrue(self.finish(act, "done", "BESS: заряд 50 кВт"))
        self.assertEqual((act.state, act.result_text), ("done", "BESS: заряд 50 кВт"))
        self.assertTrue(act.finished_at)
        self.assertEqual(advice.state, "done")
        self.assertIsNone(self.finish(act, "done"))  # повтор — без ефекту
        self.assertEqual(self.finish(act, "failed"), "already_final")
        self.assertEqual(self.Action._td_on_engine({"id": 999999, "state": "done"}), "unknown_action")
        late = self.run_action("qs_close", user=self.u_chief)
        late._me()._td_close("expired", "прострочено")
        self.assertTrue(self.finish(late, "done"))  # авторитетний звіт для `expired`
        self.assertEqual(late.state, "done")

    def test_config_action(self):  # AC-190
        act = self.run_action("scenario_toggle", {"scenario": "peak", "enabled": False}, user=self.u_chief)
        self.assertEqual(act.state, "done")
        self.assertFalse(act.applied)
        self.assertEqual(act._td_result_chip()[0], "збережено, очікує збирач")
        self.State._td_report({"collector": "X", "config_version_applied": act.config_version})
        act.invalidate_recordset(["applied"])
        self.assertEqual(act._td_result_chip()[0], "виконано")

    def test_cancel(self):  # AC-191
        prep = self.ctl(self.u_en1).prepare("bess_charge")
        self.assertEqual(self.ctl(self.u_en1).cancel(prep["token"])["state"], "cancelled")
        self.assertEqual(self.ctl(self.u_en1).cancel(prep["token"])["state"], "cancelled")  # ідемпотентно
        queued = self.run_action("bess_charge", {"power_kw": 30}, user=self.u_en1)
        self.assertEqual(queued.state, "queued")
        queued.command_id.action_cancel()
        self.assertEqual(queued.state, "cancelled")
        executing = self.run_action("light_break", user=self.u_en1)
        self.finish(executing, "executing")
        with self.assertRaises(UserError):
            self.ctl(self.u_en1).cancel(self._token_of(executing))

    def _token_of(self, action):
        token = secrets.token_urlsafe(24)
        action.token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token

    def test_write_flags(self):  # AC-192
        self._enable_control(write=False, remote=True)
        with self.assertRaisesRegex(UserError, "Керування вимкнено"):
            self.ctl(self.u_chief).prepare("qs_close")
        self._enable_control(write=True, remote=True)
        self.env["td.source"].sudo().search([("code", "=", "ENERGY-CTL")]).write({"write_enabled": False})
        prep = self.ctl(self.u_en1).prepare("bess_charge")
        res = self.ctl(self.u_en1).confirm(prep["token"])
        self.assertEqual(res["state"], "blocked")
        self.assertIn("Запис вимкнено", res["blocked_reason"])
        self.assertFalse(self.Action.browse(prep["action_id"]).command_id)

    def test_command_creation_guard(self):  # AC-193
        sig = self.env["td.signal"].sudo().search([("code", "=", "energy_control/intent")])
        with self.assertRaisesRegex(UserError, "створює лише модуль керування"):
            self.env["td.command"].sudo().create({"signal_id": sig.id, "origin": "energy"})
        with self.assertRaises(AccessError):
            self.env["td.command"].with_user(self.u_view).create({"signal_id": sig.id, "origin": "manual"})
