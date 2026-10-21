"""AC-B03…B07, B09: маршрутизація всіх 9 видів команд КГУ через td_energy_control (D-15, RB-01, RB-02)."""

from datetime import timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from ..tools import energy_route as route
from .common import RUNNING, TAGS, BridgeCase, utc_now

ALL_KINDS = ("start", "stop", "estop", "reset", "set_mode", "set_setpoint", "set_cos", "set_heat_dir", "set_bypass")


@tagged(*TAGS)
class TestRouting(BridgeCase):
    def setUp(self):
        super().setUp()
        self.idle()

    # --- маршрут ---------------------------------------------------------------------------------------------------
    def test_route_is_energy_for_all_nine_kinds(self):
        for kind in ALL_KINDS:
            self.assertEqual(self.Pult._td_route(kind), "energy", kind)
        self.assertIsNone(self.Pult._td_route("nope"))

    def test_route_none_when_kind_deactivated(self):
        self.env["td.energy.command.kind"].search([("code", "=", "chp_start")]).write({"active": False})
        self.assertIsNone(self.Pult._td_route("start"))
        self.assertEqual(self.Pult._td_route("estop"), "energy")
        self.assertFalse(self.pult(self.u_en1).get_state()["caps"]["bridge"])

    # --- start/stop: клас B (AC-B03, B04) ----------------------------------------------------------------------------
    def test_start_is_class_b_with_two_confirmations(self):
        prep = self.prepare("start")
        self.assertEqual(prep["kind"], "start")
        self.assertTrue(prep["ref"].startswith("energy:"))
        self.assertEqual(prep["ref"], f"energy:{prep['action_id']}")
        self.assertEqual((prep["cls"], prep["needs_second"], prep["blocked"]), ("B", True, False))
        self.assertTrue(prep["token"])
        self.assertGreaterEqual(len(prep["checks"]), 14)
        self.assertIn("gas_pressure", [c["code"] for c in prep["checks"]])
        self.assertIn("chp_gas_pressure", [c["code"] for c in prep["checks"]])  # перевірки td_energy_control
        action = self.Action.sudo().browse(prep["action_id"])
        self.assertEqual((action.kind_code, action.cls, action.state), ("chp_start", "B", "prepared"))
        self.assertEqual(self.actions("chp_start"), action)
        res = self.confirm(prep)
        self.assertEqual((res["state"], res["ref"]), ("awaiting_second", prep["ref"]))
        with self.assertRaises(UserError):  # друге підтвердження — інша особа
            self.pult(self.u_en1).command("confirm_second", ref=prep["ref"])
        res = self.pult(self.u_en2).command("confirm_second", ref=prep["ref"])
        self.assertEqual(res["state"], "queued")
        self.assertTrue(action.command_id)

    def test_start_and_stop_write_chp_ctl_cmd_and_verify_by_ack(self):
        """Пуск і стоп — не інтент збирача: `td.command` у `chp/ctl/cmd` (1 / 2), верифікація за `chp/ctl/ack`."""
        start = self.act("start", user=self.e_chief)
        self.assertEqual((start.kind_id.executor, start.state), ("chp", "queued"))
        cmd = start.command_id
        self.assertEqual(
            (cmd.signal_id.code, cmd.value, cmd.origin, cmd.state), ("chp/ctl/cmd", 1.0, "energy", "queued")
        )
        self.assertFalse(cmd.payload)
        self.command_done(start, ack=1)
        self.assertEqual((start.state, start.result_text), ("done", "Контролер прийняв команду"))
        self.put(RUNNING)
        stop = self.act("stop", user=self.e_chief)
        self.assertEqual((stop.command_id.signal_id.code, stop.command_id.value), ("chp/ctl/cmd", 2.0))
        self.command_done(stop, ack=2, reason=12)
        self.assertEqual(stop.state, "failed")
        self.assertIn("стан не допускає команду", stop.error)

    def test_chief_starts_alone(self):
        prep = self.prepare("start", user=self.e_chief)
        self.assertEqual(self.confirm(prep, self.e_chief)["state"], "queued")

    def test_stop_class_b_when_running(self):
        self.put(RUNNING)
        prep = self.prepare("stop")
        self.assertEqual((prep["cls"], prep["kind"], prep["blocked"]), ("B", "stop", False))
        self.assertEqual(self.Action.sudo().browse(prep["action_id"]).kind_code, "chp_stop")

    def test_preflight_blocks_start_without_queueing(self):
        self.put({"gas/p_in": 1.15})  # AC-B05
        prep = self.prepare("start")
        self.assertTrue(prep["blocked"])
        self.assertIsNone(prep["token"])
        self.assertIn("1,15", prep["blocked_reason"])
        self.assertEqual(prep["disabled_reason"], prep["blocked_reason"])
        action = self.Action.sudo().browse(prep["action_id"])
        self.assertEqual(action.state, "blocked")
        self.assertFalse(action.command_id)
        self.assertEqual(self.env["td.command"].sudo().search_count([("energy_action_id", "=", action.id)]), 0)

    def test_confirm_rechecks_and_closes_blocked(self):
        prep = self.prepare("start")
        self.put({"gas/p_in": 1.15})
        res = self.confirm(prep)
        self.assertEqual(res["state"], "blocked")
        self.assertIn("1,15", res["blocked_reason"])
        action = self.Action.sudo().browse(prep["action_id"])
        self.assertEqual((action.state, bool(action.command_id)), ("blocked", False))

    def test_confirm_second_rechecks(self):
        prep = self.prepare("start")
        self.confirm(prep)
        self.put({"safe/fire": 1})
        res = self.pult(self.u_en2).command("confirm_second", ref=prep["ref"])
        self.assertEqual(res["state"], "blocked")

    def test_cancel_and_get(self):
        prep = self.prepare("start")
        self.assertEqual(self.pult(self.u_en1).command("get", ref=prep["ref"])["state"], "prepared")
        res = self.pult(self.u_en1).command("cancel", ref=prep["ref"], token=prep["token"])
        self.assertEqual((res["state"], res["ref"]), ("cancelled", prep["ref"]))
        self.assertEqual(self.pult(self.u_en1).command("get", ref=prep["ref"])["state"], "cancelled")

    # --- estop, reset: клас A, один запис у td_energy (AC-B06 за D-15) ---------------------------------------------
    def test_estop_goes_through_energy_with_single_confirmation(self):
        self.put({"safe/estop_loop": 1, "ctl/remote": 0})  # аварійний стоп дозволено навіть у місцевому режимі
        prep = self.prepare("estop")
        self.assertEqual(
            (prep["cls"], prep["needs_second"], prep["blocked"], prep["kind"]), ("A", False, False, "estop")
        )
        self.assertEqual(prep["title"], "Аварійний стоп КГУ-1")
        self.assertEqual(self.confirm(prep)["state"], "queued")
        action = self.Action.sudo().browse(prep["action_id"])
        self.assertEqual(action.kind_code, "chp_estop")
        cmd = action.command_id
        self.assertEqual((cmd.signal_id.code, cmd.value, cmd.origin), ("chp/ctl/cmd", 3.0, "energy"))
        self.assertEqual(self.Command.search_count([]), 0)  # td.chp.command не створюється (RB-06)
        self.command_done(action, ack=1)
        self.assertEqual(action.state, "done")
        self.assertEqual(action.result_text, "Контролер прийняв команду")

    def test_estop_refused_by_controller_fails_with_reason(self):
        action = self.act("estop")
        self.command_done(action, ack=2, reason=12)
        self.assertEqual(action.state, "failed")
        self.assertIn("стан не допускає команду", action.error)

    def test_estop_blocked_only_in_alarm_state(self):
        self.put({"ctl/state": 3, "alarm/code": 116})
        prep = self.prepare("estop")
        self.assertTrue(prep["blocked"])
        self.assertIsNone(prep["token"])
        self.put({"ctl/state": 0, "alarm/code": 0})
        self.assertFalse(self.prepare("estop")["blocked"])

    def test_estop_not_blocked_by_stale_data(self):
        stale = {"td_chp_now": utc_now().replace(microsecond=0) + timedelta(seconds=3600)}  # дані застаріли
        prep = self.pult(self.u_en1).with_context(**stale).command("prepare", kind="estop")
        self.assertFalse(prep["blocked"])

    def test_reset_in_alarm_state(self):
        self.put({"ctl/state": 3, "alarm/code": 111})
        prep = self.prepare("reset")
        self.assertEqual((prep["cls"], prep["blocked"]), ("A", False))
        self.confirm(prep)
        action = self.Action.sudo().browse(prep["action_id"])
        self.assertEqual(action.command_id.value, 4.0)
        self.command_done(action, ack=1)
        self.assertEqual(action.state, "done")
        self.put({"ctl/state": 0, "alarm/code": 0})
        self.assertTrue(self.prepare("reset")["blocked"])

    # --- уставки (клас A) ---------------------------------------------------------------------------------------------
    def test_set_cos_is_verified_by_target_value(self):
        prep = self.prepare("set_cos", {"cos": 0.97})
        self.assertEqual((prep["cls"], prep["kind"]), ("A", "set_cos"))
        self.assertEqual(prep["text"], "Уставка cos φ: 0,97.")
        self.confirm(prep)
        action = self.Action.sudo().browse(prep["action_id"])
        self.assertEqual(action.summary, "Уставка cos φ КГУ: 0,97")
        cmd = action.command_id
        self.assertEqual((cmd.signal_id.code, cmd.value), ("chp/ctl/cos_set", 0.97))
        self.command_done(action)
        self.assertEqual(action.state, "executing")
        self.put({"ctl/cos_set": 0.97})
        self.assertEqual((action.state, action.result_text), ("done", "Значення прийнято контролером"))

    def test_set_mode_sends_code(self):
        action = self.act("set_mode", {"mode": "peak"})
        self.assertEqual((action.command_id.signal_id.code, action.command_id.value), ("chp/ctl/mode", 2.0))
        self.assertEqual(action.summary, "Режим КГУ: Зрізання піку")

    def test_set_heat_dir_and_bypass(self):
        a = self.act("set_heat_dir", {"dir": "cooler"})
        self.assertEqual((a.command_id.signal_id.code, a.command_id.value), ("chp/ctl/heat_dir", 2.0))
        self.command_done(a, values={"ctl/heat_dir": 2})
        self.assertEqual(a.state, "done")
        b = self.act("set_bypass", {"mode": "bypass"})
        self.assertEqual((b.command_id.signal_id.code, b.command_id.value), ("chp/ctl/bypass_mode", 2.0))

    def test_set_setpoint_needs_manual_mode_and_range(self):
        self.put({"ctl/mode": 0})
        self.assertTrue(self.prepare("set_setpoint", {"sp_pct": 80})["blocked"])
        self.put({"ctl/mode": 3})
        prep = self.prepare("set_setpoint", {"sp_pct": 80})
        self.assertFalse(prep["blocked"])
        with self.assertRaises(ValidationError):
            self.prepare("set_setpoint", {"sp_pct": 45})
        with self.assertRaises(ValidationError):
            self.prepare("set_cos", {"cos": 0.85})
        with self.assertRaises(UserError):
            self.prepare("set_mode", {"mode": "turbo"})
        with self.assertRaises(UserError):
            self.prepare("set_mode", {"nope": 1})

    # --- стоп-крани, права, конфлікти --------------------------------------------------------------------------------
    def test_write_off_raises_for_bridge_kinds(self):
        self.env["ir.config_parameter"].sudo().set_param("td.energy_control.write_enabled", "False")
        for kind, params in (("estop", None), ("set_cos", {"cos": 0.97}), ("start", None)):
            with self.assertRaises(UserError) as err:
                self.prepare(kind, params)
            self.assertIn("td.energy_control.write_enabled", str(err.exception), kind)

    def test_signal_without_write_enabled_blocks_on_confirm(self):
        prep = self.prepare("set_cos", {"cos": 0.97})
        self.Signal.search([("code", "=", "chp/ctl/cos_set")]).write({"write_enabled": False})
        res = self.confirm(prep)
        self.assertEqual(res["state"], "blocked")
        self.assertIn("chp/ctl/cos_set", res["blocked_reason"])

    def test_source_write_off_blocks_on_confirm(self):
        prep = self.prepare("set_mode", {"mode": "el"})
        self.unit.source_id.write({"write_enabled": False})
        res = self.confirm(prep)
        self.assertEqual(res["state"], "blocked")
        self.assertIn("MB-U72-CHP", res["blocked_reason"])

    def test_one_active_command_at_a_time_but_estop_wins(self):
        first = self.act("set_cos", {"cos": 0.97})
        self.assertEqual(first.state, "queued")
        prep = self.prepare("set_mode", {"mode": "el"})
        res = self.confirm(prep)
        self.assertEqual(res["state"], "blocked")
        self.assertIn(first.name, res["blocked_reason"])
        estop = self.act("estop")
        self.assertEqual(estop.state, "queued")
        self.assertEqual(first.state, "cancelled")  # аварійний стоп скасовує інші `queued`

    def test_double_confirm_is_idempotent(self):
        prep = self.prepare("set_cos", {"cos": 0.97})
        self.confirm(prep)
        res = self.confirm(prep)
        self.assertEqual(res["state"], "queued")
        self.assertEqual(self.env["td.command"].sudo().search_count([("energy_action_id", "=", prep["action_id"])]), 1)

    def test_chp_operator_without_energy_role_cannot_command(self):
        with self.assertRaisesRegex(AccessError, "Для команд КГУ потрібна роль Енергетика"):
            self.prepare("estop", user=self.u_op1)
        with self.assertRaises(AccessError):  # `u_user` без ролі оператора КГУ — відмова самого td_chp
            self.prepare("estop", user=self.u_user)
        prep = self.prepare("set_cos", {"cos": 0.97})  # посилання на чужу/наявну дію теж не відкриває команд без ролі
        for op in ("confirm", "cancel", "get"):
            with self.assertRaisesRegex(AccessError, "роль Енергетика"):
                self.pult(self.u_op1).command(op, ref=prep["ref"], token=prep["token"])
        self.assertEqual(self.actions(), self.Action.browse(prep["action_id"]))

    def test_foreign_ref_token_and_garbage(self):
        prep = self.prepare("set_cos", {"cos": 0.97})
        with self.assertRaises(AccessError):  # токен іншого користувача
            self.pult(self.u_en2).command("confirm", ref=prep["ref"], token=prep["token"])
        for ref in ("energy:999999", "energy:abc", "energy:", "x:1"):
            with self.assertRaises(UserError):
                self.pult(self.u_en1).command("get", ref=ref)
        other = self.prepare("set_mode", {"mode": "el"})
        with self.assertRaises(UserError):  # токен від іншої дії
            self.pult(self.u_en1).command("confirm", ref=prep["ref"], token=other["token"])
        plain = self.Action.sudo().search([("kind_code", "not like", "chp\\_%")], limit=1)
        if plain:
            with self.assertRaises(UserError):
                self.pult(self.u_en1).command("get", ref=f"energy:{plain.id}")

    def test_verify_timeout_fails_active_action(self):
        action = self.act("set_cos", {"cos": 0.97})
        self.assertEqual(action.state, "queued")
        self.Action.sudo()._td_chp_expire()
        self.assertEqual(action.state, "queued")  # строк ще не минув
        action._me().write({"started_at": action.started_at - timedelta(seconds=3600)})
        self.assertEqual(self.Action.sudo()._td_chp_expire(), 1)
        self.assertEqual(action.state, "failed")
        self.assertIn("не підтвердив", action.error)

    def test_cron_expire_of_td_chp_runs_bridge_expiry(self):
        action = self.act("set_cos", {"cos": 0.97})
        action._me().write({"started_at": self.now - timedelta(hours=2)})
        self.Command._cron_expire()
        self.assertEqual(action.state, "failed")

    def test_energy_journal_row_for_bridge_action(self):
        action = self.act("set_cos", {"cos": 0.97})
        row = action._td_journal_row()
        self.assertEqual(row["what"], "Уставка cos φ КГУ: 0,97")
        self.assertEqual(row["state"], "queued")

    def test_kind_text_helpers(self):
        self.assertEqual(route.energy_code("estop"), "chp_estop")
        self.assertEqual(route.chp_kind("chp_set_bypass"), "set_bypass")
        self.assertIsNone(route.chp_kind("qs_close"))
        for kind in ("start", "stop", "estop", "reset"):
            self.assertEqual(route.expectation(kind, {}, 1.0), {"signal": "chp/ctl/ack", "kind": "ack"}, kind)
        self.assertEqual(
            route.expectation("set_cos", {"cos": 0.97}, 0.01),
            {"signal": "chp/ctl/cos_set", "kind": "value", "value": 0.97, "tol": 0.005},
        )
