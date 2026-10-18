"""AC-195…AC-204: реєстр блокувань (золоті випадки R-41 п.5), свіжість, комбінації hard/fail_closed."""

from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from ..tools import interlocks as il
from .common import NOW, TAGS, TestControlCommon

OK, FAIL, UNK = il.OK, il.FAIL, il.UNKNOWN


def run(code, values=None, texts=None, params=None, extra=None, absent=()):
    return il.CHECKS[code](il.Ctx(values, texts, absent), params or {}, extra or {})


@tagged(*TAGS)
class TestInterlocks(TestControlCommon):
    def state(self, *a, **kw):
        return run(*a, **kw).state

    def test_remote_island_lock_fresh(self):  # AC-195
        self.assertEqual([self.state("controller_remote", {"remote": v}) for v in (1, 0, None)], [OK, FAIL, UNK])
        self.assertEqual(self.state("no_island", {"ats_pos": 2, "src1_ok": 1}), OK)
        self.assertEqual(self.state("no_island", {"ats_pos": 3, "src1_ok": 1}), FAIL)
        self.assertEqual(self.state("no_island", {"ats_pos": 2, "src1_ok": 0}), FAIL)
        self.assertEqual([self.state("ats_parallel_lock", {"ats_lock": v}) for v in (1, 0, None)], [OK, FAIL, UNK])
        self.assertEqual(run("data_fresh", {"remote": 1}, extra={"fresh_names": ["remote"]}).state, OK)
        res = run("data_fresh", {"remote": 1}, extra={"fresh_names": ["remote", "s1_p"]})
        self.assertEqual(res.state, FAIL)
        self.assertIn("немає свіжих даних", res.detail)

    def test_qs_current(self):  # AC-196
        p = {"rating_a": 1600, "max_ratio": 0.8, "cos_phi": 0.95}
        res = run("qs_current_ok", {"s1_p": 150, "s2_p": 100}, params=p)
        self.assertEqual((res.state, res.values["i_a"]), (OK, 40))
        self.assertEqual(self.state("qs_current_ok", {"s1_p": 1700, "s2_p": 0}, params=p), FAIL)
        closed = run("qs_current_ok", {}, {"qs_state": "closed"}, p)
        self.assertEqual((closed.state, closed.detail), (OK, "QS уже замкнений"))

    def test_bess(self):  # AC-197
        self.assertEqual([self.state("bess_ok", {"bess_state": v}) for v in (1, 0, None)], [OK, FAIL, UNK])
        self.assertEqual(self.state("bess_soc_lt_limit", {"bess_soc": 82}, extra={"soc_limit_pct": 95}), OK)
        self.assertEqual(self.state("bess_soc_lt_limit", {"bess_soc": 95}, extra={"soc_limit_pct": 95}), FAIL)
        extra = {"power_kw": 100, "duration_min": 60}
        p = {"capacity_kwh": 387}
        self.assertEqual(
            self.state("bess_reserve_kept", {"bess_soc": 82, "bess_reserve": 30}, params=p, extra=extra), OK
        )
        self.assertEqual(
            self.state("bess_reserve_kept", {"bess_soc": 50, "bess_reserve": 30}, params=p, extra=extra), FAIL
        )
        self.assertEqual(
            [self.state("bess_temp_ok", {"bess_temp": v}, params={"max_c": 40}) for v in (24, 41, None)],
            [OK, FAIL, UNK],
        )

    def test_chp(self):  # AC-198
        self.assertEqual([self.state("chp_ready", {"chp_state": v}) for v in (0, 1, 2, 3)], [OK, FAIL, FAIL, FAIL])
        p = {"min_bar": 1.5}
        self.assertEqual([self.state("chp_gas_pressure", {"chp_gas": v}, params=p) for v in (2.1, 0.8)], [OK, FAIL])
        self.assertEqual([self.state("chp_permit", {"chp_permit": v}) for v in (1, 0, None)], [OK, FAIL, UNK])
        mr = {"min_run_h": 2}
        self.assertEqual(self.state("chp_min_run", {"chp_state": 0}, params=mr), OK)
        self.assertEqual(self.state("chp_min_run", {"chp_state": 2, "chp_hours": 1.2}, params=mr), FAIL)
        self.assertEqual(self.state("chp_min_run", {"chp_state": 2, "chp_hours": 2.3}, params=mr), OK)

    def test_air_lux_co2_genset_fire(self):  # AC-199
        p = {"margin_bar": 0.2, "max_bar": 8.5}
        got = [
            self.state("air_setpoint_min", {"air_min": 6.2}, params=p, extra={"setpoint_bar": v})
            for v in (6.5, 6.3, 8.6)
        ]
        self.assertEqual(got, [OK, FAIL, FAIL])
        self.assertEqual(
            [self.state("aisle_lux_ge", params={"min_lux": 75}, extra={"lux": v}) for v in ([80], [60], [])],
            [OK, FAIL, UNK],
        )
        self.assertEqual(
            [self.state("co2_lt", {"co2_ppm": v}, params={"max_ppm": 1000}) for v in (620, 1200, None)], [OK, FAIL, UNK]
        )
        self.assertEqual(self.state("genset_fuel", params={"min_pct": 30}, extra={"genset": {"fuel_pct": 78}}), OK)
        self.assertEqual(self.state("genset_fuel", params={"min_pct": 30}, extra={"genset": {"fuel_pct": 25}}), FAIL)
        idle = {"running": False, "test_running": False, "island": False}
        self.assertEqual(self.state("genset_idle", extra={"genset": idle}), OK)
        self.assertEqual(self.state("genset_idle", extra={"genset": dict(idle, running=True)}), FAIL)
        absent = run("no_fire_alarm", absent=("fire_state",))
        self.assertEqual((absent.state, absent.detail), (OK, "не підключено"))
        self.assertEqual(self.state("no_fire_alarm", {"fire_state": 1}, {"fire_state": "alarm"}), FAIL)
        self.assertEqual(self.state("no_fire_alarm", {"fire_state": 0}, {"fire_state": "ok"}), OK)
        self.assertEqual(self.state("no_fire_alarm"), UNK)

    def test_blocking_combinations(self):  # AC-200
        self.assertTrue(il.is_blocking(True, True, FAIL))
        self.assertTrue(il.is_blocking(True, True, UNK))
        self.assertFalse(il.is_blocking(True, False, UNK))
        self.assertFalse(il.is_blocking(False, True, FAIL))
        rows = {
            "chp_min_run": {"name": "x {h}", "hard": True, "fail_closed": False, "where": "collector", "params": {}}
        }
        out, blocked, _reason = il.evaluate([{"code": "chp_min_run", "soft": False}], rows, il.Ctx(), {})
        self.assertEqual((out[0]["state"], out[0]["detail"], blocked), (UNK, "перевіряє збирач", False))

    def test_stale_is_unknown(self):  # AC-201
        self._fresh("energy_control/ctl/remote", 1, age_s=200)
        ctx = il.Ctx.from_env(self.env, NOW)
        self.assertIsNone(ctx.v("remote"))
        self._fresh("energy_control/ctl/remote", 1, status="stale")
        self.assertIsNone(il.Ctx.from_env(self.env, NOW).v("remote"))
        self._fresh("energy_control/ctl/remote", 1)
        self.assertEqual(il.Ctx.from_env(self.env, NOW).v("remote"), 1)
        self._fresh("energy_control/ctl/remote", 1, age_s=int(timedelta(seconds=59).total_seconds()))
        self.assertEqual(il.Ctx.from_env(self.env, NOW).v("remote"), 1)

    def test_registry_rights(self):  # AC-202
        Interlock = self.env["td.energy.interlock"]
        with self.assertRaises(ValidationError), self.cr.savepoint():
            Interlock.sudo().create({"code": "nope", "name": "x"})
        row = Interlock.search([("code", "=", "qs_current_ok")])
        with self.assertRaises(AccessError):
            row.with_user(self.u_chief).write({"params": {"rating_a": 1600, "max_ratio": 0.8, "cos_phi": 0.95}})
        before = self.State.get().config_version
        row.with_user(self.u_admin).write({"params": {"rating_a": 1600, "max_ratio": 0.7, "cos_phi": 0.95}})
        log = self.Action.search([("kind_code", "=", "interlock_param")], limit=1)
        self.assertEqual((log.origin, log.cls, log.state), ("config", "B", "done"))
        self.assertGreater(self.State.get().config_version, before)

    def test_prepare_blocked_by_lock(self):  # AC-203
        self._fresh("energy_control/ats/parallel_lock", 0)
        prep = self.ctl(self.u_chief).prepare("qs_close")
        self.assertTrue(prep["blocked"])
        self.assertEqual(prep["blocked_reason"], "Блокування паралельної роботи T1 і T2 від АВР — не виконано")
        res = self.ctl(self.u_chief).confirm(prep["token"])
        self.assertEqual(res["state"], "blocked")
        self.assertFalse(self.Action.browse(prep["action_id"]).command_id)
        self.assertFalse(self.env["td.command"].search([("origin", "=", "energy")]))

    def test_light_break_checks(self):  # AC-204
        prep = self.ctl(self.u_en1).prepare("light_break")
        by = {c["code"]: c for c in prep["checks"]}
        self.assertEqual(by["aisle_lux_ge"]["state"], UNK)
        self.assertFalse(prep["blocked"])
        self._fresh("energy_control/ctl/remote", 1)
        sig = self.env["td.signal"].sudo().search([("code", "=", "fire/panel/state")], limit=1)
        if not sig:
            sig = (
                self.env["td.signal"]
                .sudo()
                .create(
                    {"code": "fire/panel/state", "name": "Пожежна панель", "kind": "state", "states": ["ok", "alarm"]}
                )
            )
        sig.write({"last_value": 1, "last_text": "alarm", "last_ts": NOW, "status": "ok"})
        prep = self.ctl(self.u_en1).prepare("light_break", {"duration_min": 31})
        by = {c["code"]: c for c in prep["checks"]}
        self.assertEqual(by["no_fire_alarm"]["state"], FAIL)
        self.assertTrue(prep["blocked"])
