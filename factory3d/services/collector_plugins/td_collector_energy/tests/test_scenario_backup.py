"""AC-257: «Резервне живлення» — дебаунс, скидання до need, пропуск critical/never_shed, відновлення (R-49, R-51)."""

from helpers import T0, advance, base_cfg, base_raw, kinds, make_env, standard_inputs

from td_collector_energy import config as cfgmod
from td_collector_energy.scenarios import backup, peak
from td_collector_energy.scenarios import common as c


def drive(env, total, dt=2.0, **vals):
    outs = []
    for _ in range(int(total / dt)):
        env = advance(env, dt, **vals)
        outs.append(backup.step(env))
    return env, outs


def lost(**over):
    return {**standard_inputs(), "src1_ok": 0, "p_total": 700, **over}


def test_debounce_two_ticks_before_active():  # AC-257
    env = make_env(base_cfg(), T0, **lost())
    out = backup.step(env)
    assert out.state == "armed" and not c.shed_list(env) and env.shared["backup_active"] is False
    env = advance(env, 2, **lost())
    out = backup.step(env)
    assert out.state == "active" and env.shared["backup_active"] is True
    assert kinds(out, "auto_step")[0].text.startswith("Втрата мережі")


def test_one_tick_glitch_does_not_trigger():  # AC-257
    env = make_env(base_cfg(), T0, **lost())
    backup.step(env)
    env = advance(env, 2, **standard_inputs())
    assert backup.step(env).state == "armed"
    env = advance(env, 2, **lost())
    assert backup.step(env).state == "armed"  # лічильник тіків скинуто


def test_ats_position_island_is_also_mains_lost():  # AC-257
    env = make_env(base_cfg(), T0, **standard_inputs(ats_pos=3))
    backup.step(env)
    env = advance(env, 2, **standard_inputs(ats_pos=3))
    assert backup.step(env).state == "active"


def test_shed_to_need_skips_critical_and_never_shed():  # AC-257
    raw = base_raw()
    raw["shed"].insert(
        0,
        {
            "id": 9,
            "seq": 0,
            "node": "DUST-1",
            "action": "off",
            "param": 0,
            "kw": 25,
            "critical": False,
            "signal": "energy_control/shed/DUST-1/limit_pct",
            "condition": "none",
            "condition_value": None,
        },
    )
    cfg = cfgmod.parse(raw).config
    env = make_env(cfg, T0, **lost())
    backup.step(env)
    env = advance(env, 2, **lost())
    out = backup.step(env)
    # need = 700 − 0,9·507 = 243,7: DUST-1 (never_shed) пропущено; CHARGING 48 + RV-ALL 60 = 108; DRY-1 — немає даних;
    # COMPRESSOR і LP-1 — critical → backup їх не скидає
    assert [i["node"] for i in c.shed_list(env)] == ["CHARGING", "RV-ALL"]
    texts = [e.text for e in out.events]
    assert any("DUST-1 заборонено" in t for t in texts) and any("немає даних про цикл DRY-1" in t for t in texts)
    assert not any("COMPRESSOR" in t or "LP-1" in t for t in texts)


def test_shed_repeats_every_stage_delay_until_need_covered():  # AC-257
    env = make_env(base_cfg(), T0, **lost(p_total=1500))
    backup.step(env)
    env = advance(env, 2, **lost(p_total=1500))
    backup.step(env)
    first = len(c.shed_list(env))
    env, _ = drive(env, 8, **lost(p_total=1500))  # < stage_delay_s (10 с, дефолт backup)
    assert len(c.shed_list(env)) == first
    env, _ = drive(env, 8, **lost(p_total=1500))
    assert len(c.shed_list(env)) == first  # усе, що можна, вже скинуто: список вичерпано
    env2 = make_env(base_cfg(), T0, **lost(p_total=300))  # навантаження менше за 0,9·ДГУ: need = 0
    backup.step(env2)
    env2 = advance(env2, 2, **lost(p_total=300))
    backup.step(env2)
    assert c.shed_list(env2) == []


def test_unknown_p_total_means_shed_everything_possible():  # AC-257
    env = make_env(base_cfg(), T0, **lost(p_total=None))
    backup.step(env)
    env = advance(env, 2, **lost(p_total=None))
    backup.step(env)
    assert [i["node"] for i in c.shed_list(env)] == ["CHARGING", "RV-ALL"]


def test_peak_is_suspended_during_backup_and_shed_kept():  # AC-257
    env = make_env(base_cfg(), T0, **lost(grid_kw=900))
    backup.step(env)
    env = advance(env, 2, **lost(grid_kw=900))
    backup.step(env)
    out = peak.step(env)
    assert out.state == "armed" and not out.requests and env.shared["backup_active"]
    assert c.shed_list(env)  # скидання лишаються до відновлення мережі


def test_restore_after_stable_mains_step_by_step():  # AC-257
    env = make_env(base_cfg(), T0, **lost())
    backup.step(env)
    env = advance(env, 2, **lost())
    backup.step(env)
    good = standard_inputs(p_total=300)
    env, outs = drive(env, 118, **good)  # restore_delay_s 120 ще не минув
    assert not any(kinds(o, "auto_release") for o in outs) and env.shared["backup_active"]
    env, outs = drive(env, 4, **good)
    assert [e.text for o in outs for e in o.events] == ["Повернуто: RV-ALL"]  # у зворотному порядку
    env, outs = drive(env, 40, **good)
    texts = [e.text for o in outs for e in o.events]
    assert texts[0] == "Повернуто: CHARGING" and texts[-1] == "Мережа відновлена: навантаження повернено"
    assert env.shared["backup_active"] is False and env.scen["backup"]["active"] is False


def test_mains_loss_during_restore_resets_the_wait():  # AC-257
    env = make_env(base_cfg(), T0, **lost())
    backup.step(env)
    env = advance(env, 2, **lost())
    backup.step(env)
    env, _ = drive(env, 100, **standard_inputs(p_total=300))
    env = advance(env, 2, **lost())
    backup.step(env)
    assert env.scen["backup"]["restored_since"] is None and env.shared["backup_active"]


def test_missing_ats_data_warns_and_disabled_is_off():  # R-49 п.4
    env = make_env(base_cfg(), T0, **standard_inputs(src1_ok=None))
    out = backup.step(env)
    assert out.state == "warn" and "infra/ats/src1_ok" in out.facts["reason"]
    off = make_env(base_cfg(backup={"enabled": False}), T0, **lost())
    assert backup.step(off).state == "off"
