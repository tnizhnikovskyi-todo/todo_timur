"""AC-241, AC-242: реєстр блокувань збирача — золоті випадки R-41 п.5, блокування hard/fail_closed, свіжість."""

from datetime import timedelta

import pytest
from golden import GOLDEN
from helpers import T0, base_cfg, interlock_ctx, make_env

from td_collector_energy import interlocks as il
from td_collector_energy.config import DEFAULT_INTERLOCKS
from td_collector_energy.inputs import Inputs


@pytest.mark.parametrize("code, values, texts, params, extra, state, detail", GOLDEN)
def test_golden_cases(code, values, texts, params, extra, state, detail):  # AC-241
    extra = dict(extra)
    absent = ("fire_state",) if extra.pop("absent", False) else ()
    res = il.CHECKS[code](interlock_ctx(values, texts, absent), params, extra)
    assert res.state == state, res
    if detail:
        assert detail in res.detail, res


def test_qs_current_rounding_to_5a():
    res = il.CHECKS["qs_current_ok"](
        interlock_ctx({"s1_p": 150, "s2_p": 100}), {"rating_a": 1600, "max_ratio": 0.8}, {}
    )
    assert res.values["i_a"] == 40 and res.values["rating_a"] == 1600


def test_registry_covers_collector_checks():
    assert set(il.CHECKS) == set(DEFAULT_INTERLOCKS)  # genset_* (where=odoo) збирач не виконує


def test_blocking_combinations():  # AC-242
    assert il.is_blocking(True, True, il.FAIL) and il.is_blocking(True, True, il.UNKNOWN)
    assert not il.is_blocking(True, False, il.UNKNOWN)  # hard + unknown без fail_closed
    assert not il.is_blocking(False, True, il.FAIL) and not il.is_blocking(
        False, True, il.UNKNOWN
    )  # soft лише показується
    assert il.is_blocking(True, False, il.FAIL)


def test_evaluate_blocks_hard_fail_closed_unknown():
    cfg = base_cfg()
    rows, blocked, reason = il.evaluate([{"code": "controller_remote"}], cfg, interlock_ctx({"remote": None}))
    assert blocked and rows[0]["state"] == il.UNKNOWN and "немає даних" in reason
    rows, blocked, reason = il.evaluate([{"code": "ats_parallel_lock"}], cfg, interlock_ctx({"ats_lock": 0}))
    assert blocked and reason == "Блокування: ats_parallel_lock — не виконано (lock=0)"  # формат C-39


def test_soft_flag_and_unknown_without_fail_closed_do_not_block():
    cfg = base_cfg()
    rows, blocked, _ = il.evaluate([{"code": "bess_temp_ok"}], cfg, interlock_ctx({"bess_temp": None}))
    assert not blocked and rows[0]["state"] == il.UNKNOWN  # hard, но fail_closed=False
    rows, blocked, _ = il.evaluate([{"code": "controller_remote", "soft": True}], cfg, interlock_ctx({"remote": 0}))
    assert not blocked and not rows[0]["hard"] and rows[0]["state"] == il.FAIL


def test_config_overrides_hard_and_fail_closed():
    raw_cfg = base_cfg(
        interlocks={
            "no_fire_alarm": {"hard": True, "fail_closed": True, "params": {}},
            "controller_remote": {"hard": False, "fail_closed": True, "params": {}},
        }
    )
    _, blocked, _ = il.evaluate(
        [{"code": "no_fire_alarm"}], raw_cfg, interlock_ctx({})
    )  # fire_state: unknown + fail_closed
    assert blocked
    _, blocked, _ = il.evaluate([{"code": "controller_remote"}], raw_cfg, interlock_ctx({"remote": 0}))
    assert not blocked  # hard=False у конфігу


def test_unknown_check_code_is_skipped():
    rows, blocked, _ = il.evaluate([{"code": "genset_idle"}, {"code": "nope"}], base_cfg(), interlock_ctx({}))
    assert rows == [] and not blocked  # where='odoo' не виконується збирачем


def test_freshness_max_of_3_periods_and_max_age():  # AC-242
    cfg = base_cfg()
    code = cfg.inp("grid_kw")
    env = make_env(cfg, grid_kw=100, remote=1)
    # вік 59 с < max_age_s 60: свіже; 61 с: відсутнє
    for age, fresh in ((59, True), (61, False)):
        inp = Inputs(cfg, env.inp.live, T0 + timedelta(seconds=age))
        assert (inp.v("grid_kw") is not None) is fresh
    # період 30 с → 3·30 = 90 с > max_age_s: показання живе довше
    inp = Inputs(cfg, env.inp.live, T0 + timedelta(seconds=80), periods={code: 30})
    assert inp.v("grid_kw") == 100
    inp = Inputs(cfg, env.inp.live, T0 + timedelta(seconds=95), periods={code: 30})
    assert inp.v("grid_kw") is None
    # `max_age_s` із конфігу (межа коду 120)
    cfg2 = base_cfg(interlocks={"data_fresh": {"hard": True, "fail_closed": True, "params": {"max_age_s": 200}}})
    assert cfg2.interlock("data_fresh").params["max_age_s"] == 120


def test_bad_quality_is_missing_and_text_state_maps_to_number():
    from collector.core.types import Reading

    cfg = base_cfg()
    env = make_env(cfg, remote="remote", src1_ok="available")
    assert env.inp.v("remote") == 1 and env.inp.v("src1_ok") == 1
    env.inp.live.update([Reading(cfg.inp("grid_kw"), T0, value=5.0, q="bad")])
    assert env.inp.v("grid_kw") is None
    assert il.CHECKS["controller_remote"](il.Ctx.from_inputs(env.inp, ["remote"]), {}, {}).state == il.OK


def test_ctx_absent_means_never_seen_not_stale():
    cfg = base_cfg()
    env = make_env(cfg, remote=1)
    ctx = il.Ctx.from_inputs(env.inp, ["remote", "fire_state"])
    assert ctx.absent("fire_state") and not ctx.absent("remote")
    late = Inputs(cfg, env.inp.live, T0 + timedelta(seconds=500))
    assert late.v("remote") is None and not late.absent("remote")  # несвіже ≠ відсутнє


def test_src1_ok_accepts_ats_source_state_value_2():
    """`infra/ats/src1_state` ATyS (2 — джерело є) теж означає «мережа є»; 0 — немає."""
    ok = il.CHECKS["no_island"](interlock_ctx({"ats_pos": 2, "src1_ok": 2}), {}, {})
    assert ok.state == il.OK
    assert il.CHECKS["no_island"](interlock_ctx({"ats_pos": 2, "src1_ok": 0}), {}, {}).state == il.FAIL
