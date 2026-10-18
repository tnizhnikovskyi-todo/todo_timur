"""AC-253, AC-254: «Самоспоживання СЕС» — заряд BESS надлишком, інтегральне обмеження СЕС, відпускання (R-46)."""

from helpers import T0, advance, base_cfg, kinds, make_env, reqs, standard_inputs, writes_of

from td_collector_energy.scenarios import common as c
from td_collector_energy.scenarios import selfcons


def drive(env, total, dt=2.0, **vals):
    outs = []
    for _ in range(int(total / dt)):
        env = advance(env, dt, **vals)
        outs.append(selfcons.step(env))
    return env, outs


def mk(**over):
    vals = standard_inputs(**{"pv_kw": 400, "export_kw": 26, "bess_soc": 82, **over})
    return make_env(base_cfg(), T0, **vals)


def test_export_above_deadband_charges_bess_with_clamped_setpoint():  # AC-253
    out = selfcons.step(mk(export_kw=26))
    assert writes_of(out, "bess") == {"bess_sp": 6, "bess_until": 95, "bess_valid": 30, "bess_mode": 1}  # 26 − 20
    assert out.state == "active"
    out = selfcons.step(mk(export_kw=300))  # clamp: bess_max_kw 100
    assert writes_of(out, "bess")["bess_sp"] == 100
    out = selfcons.step(mk(export_kw=60, bess_kw=30))  # вже заряджається 30: p = 30 + (60 − 20) = 70
    assert writes_of(out, "bess")["bess_sp"] == 70


def test_export_within_deadband_means_no_action():  # AC-253
    for export in (25, 20, 0):
        out = selfcons.step(mk(export_kw=export))
        assert out.state == "armed" and not out.requests, export
    out = selfcons.step(mk(pv_kw=0, export_kw=0))
    assert out.state == "armed"


def test_soc_target_reached_only_curtails():  # AC-254
    env = mk(export_kw=60, bess_soc=95)
    out = selfcons.step(env)
    assert not reqs(out, "bess")  # SOC ≥ 95: заряд не запитується
    env, outs = drive(env, 58, export_kw=60, bess_soc=95)
    assert not any(reqs(o, "pv") for o in outs)  # ще < curtail_delay_s 60
    env, outs = drive(env, 6, export_kw=60, bess_soc=95)
    pv = [o for o in outs if reqs(o, "pv")]
    assert pv and writes_of(pv[0], "pv") == {"shed_valid": 60, "pv_limit": 95}  # 100 − ceil(100·40/920) = 95
    assert reqs(pv[0], "pv")[0].watchdog == "shed_valid" and reqs(pv[0], "pv")[0].refresh_s == 20
    assert "Обмеження СЕС 95 %" in kinds(pv[0], "auto_step")[0].text
    assert pv[0].state == "active" and env.shared["pv_limited"] is True


def test_curtail_is_integral_and_rate_limited():  # AC-253
    env = mk(export_kw=60, bess_soc=95)
    selfcons.step(env)
    env, _ = drive(env, 64, export_kw=60, bess_soc=95)
    assert env.scen["self"]["limit_pct"] == 95
    env, outs = drive(env, 4, export_kw=60, bess_soc=95)  # < min_write_interval_s 10 с з останнього кроку
    assert env.scen["self"]["limit_pct"] == 95
    env, _ = drive(env, 8, export_kw=60, bess_soc=95)
    assert env.scen["self"]["limit_pct"] == 90  # інтегральний крок
    env, _ = drive(env, 600, export_kw=500, bess_soc=95)  # величезний надлишок: не нижче pv_limit_min_pct 10
    assert env.scen["self"]["limit_pct"] == 10


def test_peak_active_blocks_self_charging():  # AC-254
    env = mk(export_kw=60)
    env.scen["peak"] = {"stage": "bess"}
    assert not reqs(selfcons.step(env), "bess")
    env = mk(export_kw=60)
    env.shared["bess_by"] = "peak"  # BESS уже віддано піку
    assert not reqs(selfcons.step(env), "bess")
    env = mk(export_kw=60)
    env.overrides["bess"] = {"until": T0.timestamp() + 60}  # ручне перекриття
    assert not reqs(selfcons.step(env), "bess")


def test_restore_plus_5_percent_after_hold_and_zero_watchdog():  # AC-253
    env = mk(export_kw=0, bess_soc=95)
    env.scen["self"] = {"limit_pct": 80.0, "curtailed": True, "charging": False}
    env, outs = drive(env, 118, export_kw=0, bess_soc=95)  # restore_hold_s 120
    assert env.scen["self"]["limit_pct"] == 80.0
    env, outs = drive(env, 6, export_kw=0, bess_soc=95)
    assert env.scen["self"]["limit_pct"] == 85.0
    env, outs = drive(env, 12, export_kw=0, bess_soc=95)
    assert env.scen["self"]["limit_pct"] == 90.0  # +5 % не частіше min_write_interval_s
    env, outs = drive(env, 40, export_kw=0, bess_soc=95)
    assert env.scen["self"]["limit_pct"] == 100.0
    assert any("Обмеження СЕС знято" in e.text for o in outs for e in o.events) or env.scen["self"]["limit_pct"] == 100
    assert env.shared["pv_limited"] is False


def test_bess_released_when_export_gone_and_target_reached():  # AC-253
    env = mk(export_kw=40, bess_soc=80)
    out = selfcons.step(env)
    assert reqs(out, "bess") and env.shared["bess_by"] == "self"
    env = advance(env, 2, export_kw=0, bess_soc=96, bess_kw=0)
    out = selfcons.step(env)
    assert writes_of(out, "bess") == {"bess_mode": 0, "bess_valid": 0} and env.shared["bess_by"] is None
    assert kinds(out, "auto_release")


def test_disabled_and_missing_inputs():
    cfg = base_cfg(**{"self": {"enabled": False}})
    out = selfcons.step(make_env(cfg, T0, **standard_inputs(pv_kw=400, export_kw=60)))
    assert out.state == "off" and not out.requests
    out = selfcons.step(mk(export_kw=None))
    assert out.state == "warn" and "export" in out.facts["reason"]
    assert c.shed_list(mk()) == []
