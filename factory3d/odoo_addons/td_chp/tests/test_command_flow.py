"""AC-11, AC-12, AC-13, AC-15: потік команд (prepare → confirm → [confirm_second] → queued) і блокування."""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import TAGS, ChpCase


@tagged(*TAGS)
class TestCommandFlow(ChpCase):
    def setUp(self):
        super().setUp()
        self.skip_if_bridge()
        self.idle()

    def cmd(self, user, op, **kw):
        return self.pult(user).command(op, **kw)

    def run_class_b(self, kind="start", first=None, second=None):
        prep = self.cmd(first or self.u_op1, "prepare", kind=kind)
        conf = self.cmd(first or self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])
        return prep, conf

    # --- AC-11 -----------------------------------------------------------------------------------------------------
    def test_start_two_person(self):
        with self.assertRaises(AccessError):
            self.cmd(self.u_user, "prepare", kind="start")
        prep = self.cmd(self.u_op1, "prepare", kind="start")
        self.assertEqual((prep["cls"], prep["needs_second"], prep["blocked"]), ("B", True, False))
        self.assertEqual(len(prep["checks"]), 14)
        self.assertEqual(prep["confirm_label"], "Підтвердити (1/2)")
        self.assertEqual(prep["title"], "Пуск КГУ-1")
        self.assertTrue(prep["ref"].startswith("chp:"))
        conf = self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])
        self.assertEqual((conf["state"], conf["needs_second"]), ("awaiting_second", True))
        pending = self.pult(self.u_op2).get_state()["pending"]
        self.assertEqual([(p["ref"], p["kind"], p["can_second"]) for p in pending], [(prep["ref"], "start", True)])
        self.assertFalse(self.pult(self.u_op1).get_state()["pending"][0]["can_second"])
        with self.assertRaises(UserError):  # той самий користувач не може бути другим
            self.cmd(self.u_op1, "confirm_second", ref=prep["ref"])
        with self.assertRaises(AccessError):  # admin без груп КГУ не підтверджує
            self.cmd(self.u_admin, "confirm_second", ref=prep["ref"])
        done = self.cmd(self.u_op2, "confirm_second", ref=prep["ref"])
        self.assertEqual(done["state"], "queued")
        rec = self.Command.browse(int(prep["ref"].split(":")[1]))
        self.assertEqual((rec.prepared_by, rec.confirmed_by, rec.second_by), (self.u_op1, self.u_op1, self.u_op2))
        cmd = rec.command_id
        self.assertEqual((cmd.signal_id.code, cmd.value, cmd.origin, cmd.state), ("chp/ctl/cmd", 1.0, "chp", "queued"))
        self.assertEqual(cmd.requested_by, self.u_op1)  # R-08 п. 4: requested_by = confirmed_by
        self.assertEqual(self.cmd(self.u_op2, "get", ref=prep["ref"])["state"], "queued")
        self.assertEqual(rec.name[:4], "CHP/")

    def test_class_a_single_confirm(self):
        prep = self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.97})
        self.assertEqual((prep["cls"], prep["needs_second"], prep["confirm_label"]), ("A", False, "Виконати"))
        self.assertEqual(self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])["state"], "queued")
        with self.assertRaises(UserError):  # клас A: друге підтвердження не потрібне
            self.cmd(self.u_op2, "confirm_second", ref=prep["ref"])

    def test_chief_single_and_second(self):
        prep, conf = self.run_class_b(first=self.u_chief)
        self.assertFalse(prep["needs_second"])
        self.assertEqual(prep["confirm_label"], "Виконати")
        self.assertEqual(conf["state"], "queued")
        # chief може бути другою особою
        self.Command.search([("state", "=", "queued")])._td_cancel_record()
        self.idle()
        prep2 = self.cmd(self.u_op1, "prepare", kind="start")
        self.cmd(self.u_op1, "confirm", ref=prep2["ref"], token=prep2["token"])
        self.assertEqual(self.cmd(self.u_chief2, "confirm_second", ref=prep2["ref"])["state"], "queued")

    # --- AC-12 -----------------------------------------------------------------------------------------------------
    def test_blocked_by_interlock(self):
        self.idle(**{"gas/p_in": 1.15})
        n_cmd = self.env["td.command"].search_count([])
        prep = self.cmd(self.u_op1, "prepare", kind="start")
        self.assertTrue(prep["blocked"])
        self.assertIsNone(prep["token"])
        self.assertIn("тиск газу 1,15 бар < 1,5 бар", prep["blocked_reason"])
        rec = self.Command.browse(prep["action_id"])
        self.assertEqual((rec.state, rec.token_hash), ("blocked", False))
        self.assertFalse(rec.command_id)
        self.assertEqual(self.env["td.command"].search_count([]), n_cmd)
        rows = [i for i in self.pult(self.u_user).get_journal()["items"] if i["type"] == "command"]
        self.assertEqual([(r["state"], r["level"]) for r in rows], [("blocked", "warn")])
        self.assertEqual(rows[0]["text"], "Команда «Пуск»: Заблоковано")

    def test_stop_estop_rules(self):
        self.idle(**{"ctl/state": 2})
        self.enable_write(True, remote=False)  # дистанційні перемикання вимкнено
        with self.assertRaisesRegex(UserError, "remote_switching_enabled"):
            self.cmd(self.u_op1, "prepare", kind="start")
        stop = self.cmd(self.u_op1, "prepare", kind="stop")  # `stop` від цього параметра не залежить (D-09)
        self.assertFalse(stop["blocked"])
        self.assertEqual([c["code"] for c in stop["checks"]], ["remote", "state_run"])
        self.idle(**{"ctl/remote": 0})
        self.assertTrue(self.cmd(self.u_op1, "prepare", kind="stop")["blocked"])
        late = self.later(200)["td.chp.pult"].with_user(self.u_op1)  # застарілі дані
        es = late.command("prepare", kind="estop")
        self.assertFalse(es["blocked"])  # аварійний стоп проходить і при ctl/remote=0, і без свіжих даних
        self.idle(**{"ctl/state": 3, "ctl/remote": 0})
        self.assertTrue(self.cmd(self.u_op1, "prepare", kind="estop")["blocked"])  # лише ctl/state=3 блокує
        self.assertTrue(self.cmd(self.u_op1, "prepare", kind="reset")["blocked"])  # ctl/remote=0
        self.idle(**{"ctl/state": 3})
        self.assertFalse(self.cmd(self.u_op1, "prepare", kind="reset")["blocked"])

    # --- AC-13 -----------------------------------------------------------------------------------------------------
    def test_setpoints(self):
        sp = self.cmd(self.u_op1, "prepare", kind="set_setpoint", params={"sp_pct": 80})
        self.assertTrue(sp["blocked"])  # ctl/mode ≠ 3 («Ручний»)
        self.assertIn("лише в режимі «Ручний»", sp["blocked_reason"])
        self.idle(**{"ctl/mode": 3})
        sp = self.cmd(self.u_op1, "prepare", kind="set_setpoint", params={"sp_pct": 80})
        self.assertFalse(sp["blocked"])
        with self.assertRaisesRegex(ValidationError, "поза межами 50…100"):
            self.cmd(self.u_op1, "prepare", kind="set_setpoint", params={"sp_pct": 45})
        prep = self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.98})
        self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])
        cmd = self.Command.browse(prep["action_id"]).command_id
        self.assertEqual((cmd.signal_id.code, cmd.value), ("chp/ctl/cos_set", 0.98))
        with self.assertRaises(ValidationError):
            self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.985})
        with self.assertRaises(ValidationError):
            self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 1.2})

    def test_param_mapping(self):
        for kind, params, code, value in (
            ("set_mode", {"mode": "peak"}, "chp/ctl/mode", 2.0),
            ("set_heat_dir", {"dir": "cooler"}, "chp/ctl/heat_dir", 2.0),
            ("set_bypass", {"mode": "bypass"}, "chp/ctl/bypass_mode", 2.0),
        ):
            prep = self.cmd(self.u_chief, "prepare", kind=kind, params=params)
            self.cmd(self.u_chief, "confirm", ref=prep["ref"], token=prep["token"])
            cmd = self.Command.browse(prep["action_id"]).command_id
            self.assertEqual((cmd.signal_id.code, cmd.value), (code, value), kind)
            cmd.action_cancel()  # звільнити агрегат для наступної команди
            self.assertEqual(self.Command.browse(prep["action_id"]).state, "cancelled")

    def test_telemetry_write_off_blocks(self):
        self.env["ir.config_parameter"].sudo().set_param("td.telemetry.write_enabled", "False")
        prep = self.cmd(self.u_op1, "prepare", kind="start")
        self.assertTrue(prep["blocked"])
        self.assertIn("Запис вимкнено: td.telemetry.write_enabled", prep["blocked_reason"])

    def test_write_flags(self):
        self.enable_write(False)
        with self.assertRaisesRegex(UserError, "td.chp.write_enabled"):
            self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.98})
        self.enable_write(True)
        self.Signal.search([("code", "=", "chp/ctl/cos_set")]).write({"write_enabled": False})
        prep = self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.98})
        self.assertTrue(prep["blocked"])
        self.assertIn("Запис вимкнено: сигнал chp/ctl/cos_set", prep["blocked_reason"])

    def test_bad_arguments(self):  # 13.3: невідомі kind/params/ref → UserError
        for kw in (
            {"kind": "launch"},
            {"kind": "start", "params": {"x": 1}},
            {"kind": "set_mode", "params": {"mode": "turbo"}},
            {"kind": "set_cos", "params": "0.9"},
            {"kind": "set_cos"},
        ):
            with self.assertRaises(UserError, msg=str(kw)):
                self.cmd(self.u_op1, "prepare", **kw)
        for kw in ({"ref": "x:1"}, {"ref": "chp:abc"}, {"ref": None}):
            with self.assertRaises(UserError, msg=str(kw)):
                self.cmd(self.u_op1, "get", **kw)
        with self.assertRaises(UserError):
            self.cmd(self.u_op1, "frobnicate")
        with self.assertRaises(UserError):
            self.cmd(self.u_op1, "get", ref="chp:999999")
        with self.assertRaises(UserError):
            self.cmd(self.u_op1, "confirm", ref="chp:1", token="")

    def test_direct_write_denied(self):
        prep = self.cmd(self.u_op1, "prepare", kind="start")
        rec = self.Command.browse(prep["action_id"])
        with self.assertRaises(AccessError):
            rec.with_user(self.u_admin).write({"state": "done"})
        with self.assertRaises(AccessError):
            self.Command.with_user(self.u_admin).create({"unit_id": self.unit.id, "kind_code": "start"})
        with self.assertRaises(AccessError):
            self.Event.with_user(self.u_admin).create({"unit_id": self.unit.id, "text": "x"})
        with self.assertRaises(UserError):  # origin='chp' створює лише модуль
            self.env["td.command"].create(
                {"signal_id": self.Signal.search([("code", "=", "chp/ctl/cmd")]).id, "value": 1, "origin": "chp"}
            )

    # --- AC-15 -----------------------------------------------------------------------------------------------------
    def test_double_confirm_and_token_rules(self):
        prep = self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.97})
        with self.assertRaises(AccessError):  # чужий токен
            self.cmd(self.u_op2, "confirm", ref=prep["ref"], token=prep["token"])
        n = self.env["td.command"].search_count([("origin", "=", "chp")])
        first = self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])
        again = self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])
        self.assertEqual((first["state"], again["state"]), ("queued", "queued"))
        self.assertEqual(self.env["td.command"].search_count([("origin", "=", "chp")]), n + 1)
        with self.assertRaises(UserError):
            self.cmd(self.u_op1, "confirm", ref=prep["ref"], token="nope")

    def test_expired_token(self):
        prep = self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.97})
        late = self.later(61)
        with self.assertRaisesRegex(UserError, "Час підтвердження минув"), self.cr.savepoint():
            late["td.chp.pult"].with_user(self.u_op1).command("confirm", ref=prep["ref"], token=prep["token"])
        self.assertEqual(late["td.chp.command"]._cron_expire(), 1)
        rec = self.Command.browse(prep["action_id"])
        self.assertEqual(rec.state, "expired")
        with self.assertRaises(UserError):  # прострочену вже не підтвердити
            self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])

    def test_second_expires(self):
        prep, _conf = self.run_class_b()
        self.assertEqual(self.later(601)["td.chp.command"]._cron_expire(), 1)
        self.assertEqual(self.Command.browse(prep["action_id"]).state, "expired")
        with self.assertRaisesRegex(UserError, "Час другого підтвердження минув"):
            self.cmd(self.u_op2, "confirm_second", ref=prep["ref"])

    def test_cancel(self):
        prep = self.cmd(self.u_op1, "prepare", kind="start")
        self.assertEqual(self.cmd(self.u_op1, "cancel", ref=prep["ref"], token=prep["token"])["state"], "cancelled")
        self.assertEqual(self.cmd(self.u_op1, "cancel", ref=prep["ref"], token=prep["token"])["state"], "cancelled")
        with self.assertRaises(UserError):
            self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])

    def test_repeat_prepare_reuses_record(self):
        a = self.cmd(self.u_op1, "prepare", kind="start")
        b = self.cmd(self.u_op1, "prepare", kind="start")
        self.assertEqual(a["action_id"], b["action_id"])
        self.assertNotEqual(a["token"], b["token"])
        with self.assertRaises(UserError):  # старий токен недійсний
            self.cmd(self.u_op1, "confirm", ref=a["ref"], token=a["token"])

    def test_second_active_command_blocked(self):
        first = self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.97})
        self.cmd(self.u_op1, "confirm", ref=first["ref"], token=first["token"])
        second = self.cmd(self.u_op1, "prepare", kind="set_heat_dir", params={"dir": "boiler"})
        res = self.cmd(self.u_op1, "confirm", ref=second["ref"], token=second["token"])
        self.assertEqual(res["state"], "blocked")
        self.assertIn(self.Command.browse(first["action_id"]).name, res["blocked_reason"])
        # аварійний стоп завжди дозволено й скасовує чергу
        es = self.cmd(self.u_op1, "prepare", kind="estop")
        out = self.cmd(self.u_op1, "confirm", ref=es["ref"], token=es["token"])
        self.assertEqual(out["state"], "queued")
        self.assertEqual(self.Command.browse(first["action_id"]).state, "cancelled")
        self.assertEqual(self.Command.browse(first["action_id"]).command_id.state, "cancelled")

    def test_recheck_blocks_on_confirm(self):
        prep = self.cmd(self.u_op1, "prepare", kind="start")
        self.idle(**{"gas/p_in": 1.0})
        res = self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])
        self.assertEqual(res["state"], "blocked")
        self.assertIn("тиск газу", res["blocked_reason"])
        self.assertFalse(self.Command.browse(prep["action_id"]).command_id)

    def test_write_off_at_enqueue(self):
        prep = self.cmd(self.u_op1, "prepare", kind="set_cos", params={"cos": 0.97})
        self.Signal.search([("code", "=", "chp/ctl/cos_set")]).write({"write_enabled": False})
        res = self.cmd(self.u_op1, "confirm", ref=prep["ref"], token=prep["token"])
        self.assertEqual(res["state"], "blocked")
        self.assertIn("Запис вимкнено", res["blocked_reason"])
