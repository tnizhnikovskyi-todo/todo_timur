"""AC-249…AC-252: «Срезание пика» — блоки 15 хв, активація, BESS, КГУ, скидання, відпускання (R-45, R-51)."""

from datetime import UTC, datetime

from helpers import T0, advance, base_cfg, kinds, make_env, reqs, standard_inputs, writes_of

from td_collector_energy.scenarios import common as c
from td_collector_energy.scenarios import peak
from td_collector_energy.timeutil import block_start


def drive(env, total, dt=2.0, step=peak.step, **vals):
    """Виконує `step` кожні `dt` с протягом `total` с; повертає (env, виходи)."""
    outs = []
    for _ in range(int(total / dt)):
        env = advance(env, dt, **vals)
        outs.append(step(env))
    return env, outs


def start_env(**over):
    vals = standard_inputs(**{"grid_kw": 300, **over})
    return make_env(base_cfg(), T0, **vals), vals


def test_block_is_utc_epoch_aligned_and_dst_safe():  # AC-249
    t = T0.timestamp()
    assert block_start(t) == t and block_start(t + 899) == t and block_start(t + 900) == t + 900
    # зимовий час (Київ, 25.10.2026 04:00 EEST → 03:00 EET): блоки лишаються через 900 с, без дублів і пропусків
    start = datetime(2026, 10, 24, 23, 0, tzinfo=UTC).timestamp()
    blocks = sorted({block_start(start + 60 * i) for i in range(180)})
    assert len(blocks) == 12 and {b - a for a, b in zip(blocks, blocks[1:], strict=False)} == {900}
    spring = datetime(2026, 3, 28, 23, 0, tzinfo=UTC).timestamp()  # весняний перехід
    blocks = sorted({block_start(spring + 60 * i) for i in range(180)})
    assert len(blocks) == 12 and {b - a for a, b in zip(blocks, blocks[1:], strict=False)} == {900}


def test_forecast_formula_and_first_30_seconds():  # AC-249
    st = {}
    now = T0.timestamp()
    assert peak.forecast(st, 700.0, now) == 700.0  # старт блока: proj = grid
    acc = 0.0
    for i in range(1, 226):  # 450 с по 2 с з імпортом 800 кВт
        acc += 800 * 2
        proj = peak.forecast(st, 800.0, now + 2 * i)
    assert st["acc_kws"] == acc == 800 * 450
    assert proj == (acc + 800 * 450) / 900 == 800.0
    # імпорт стрибнув до 900 в середині блока: proj = (acc + 900·remaining)/900
    assert peak.forecast(st, 900.0, now + 452) > 800.0
    # новий блок обнуляє акумулятор
    assert peak.forecast(st, 500.0, now + 900) == 500.0 and st["acc_kws"] == 0.0 and st["block_start"] == now + 900


def test_activation_by_projection_or_instant_limit():  # AC-249
    env, _ = start_env(grid_kw=500)
    out = peak.step(env)
    assert out.state == "armed" and out.facts["margin_kw"] == 260 and not out.requests
    env = advance(env, 2, grid_kw=731)  # перші 30 с блока: proj = grid ≥ 760 − 30
    out = peak.step(env)
    assert out.state == "active" and env.scen["peak"]["stage"] == "bess"
    assert kinds(out, "auto_step")[0].text.startswith("Зрізання піку: старт, прогноз 731")
    env2, _ = start_env(grid_kw=761)
    assert peak.step(env2).state == "active"  # grid ≥ limit
    env3, _ = start_env(grid_kw=729)
    assert peak.step(env3).state == "armed"


def test_disabled_scenario_is_off_and_missing_inputs_warn():
    cfg = base_cfg(peak={"enabled": False})
    assert peak.step(make_env(cfg, T0, **standard_inputs(grid_kw=900))).state == "off"
    env = make_env(base_cfg(), T0, **standard_inputs(grid_kw=None))
    out = peak.step(env)
    assert out.state == "warn" and "infra/totals/grid_kw" in out.facts["reason"] and not out.requests


def test_stage1_bess_request_and_reserve_floor():  # AC-250
    env, _ = start_env(grid_kw=800, bess_soc=82)
    out = peak.step(env)
    assert writes_of(out, "bess") == {"bess_sp": 60, "bess_until": 30, "bess_valid": 30, "bess_mode": 2}
    req = reqs(out, "bess")[0]
    assert req.watchdog == "bess_valid" and req.refresh_s == 10  # перезапис кожні 10 с
    env = advance(env, 2, grid_kw=900, bess_kw=-60)  # excess 160: bess_now + excess = 220 → clamp bess_max_kw 100
    assert writes_of(peak.step(env), "bess")["bess_sp"] == 100
    env = advance(env, 2, grid_kw=800, bess_kw=-100)  # excess 60: p_target = clamp(100 + 60, 0, 100)
    assert writes_of(peak.step(env), "bess")["bess_sp"] == 100


def test_stage1_soc_at_reserve_makes_bess_unavailable_with_one_interlock_event():  # AC-250
    env, _ = start_env(grid_kw=800, bess_soc=32)  # soc ≤ floor 30 + 2
    out = peak.step(env)
    assert not reqs(out, "bess") and len(kinds(out, "interlock")) == 1
    assert "BESS на резерві 32 %" in kinds(out, "interlock")[0].text
    env = advance(env, 2)
    assert not kinds(peak.step(env), "interlock")  # раз на зміну
    env = advance(env, 2, bess_soc=60)
    assert reqs(peak.step(env), "bess")  # знову доступний


def test_bess_not_used_when_manual_override_or_not_ready():  # AC-245
    env, _ = start_env(grid_kw=800)
    env.overrides["bess"] = {"until": T0.timestamp() + 600}
    assert not reqs(peak.step(env), "bess")
    env2, _ = start_env(grid_kw=800, bess_state=0)
    assert not reqs(peak.step(env2), "bess")


def test_stage2_chp_start_after_stage_delay():  # AC-251
    env, vals = start_env(grid_kw=900, bess_soc=31)  # BESS недоступний → uncovered = excess
    out = peak.step(env)
    assert not reqs(out, "chp")
    env, outs = drive(env, 58, grid_kw=900)
    assert not any(reqs(o, "chp") for o in outs)  # ще < stage_delay_s 60
    env, outs = drive(env, 6, grid_kw=900)
    starts = [o for o in outs if reqs(o, "chp")]
    assert len(starts) == 1 and writes_of(starts[0], "chp") == {"chp_cmd": 1}
    assert env.shared["chp"]["owner"] == "peak" and env.scen["peak"]["stage"] == "chp"
    assert "Зрізання піку: пуск КГУ" in kinds(starts[0], "auto_step")[0].text


def test_stage3_shed_by_priority_covers_uncovered_and_skips_unknown_cycle():  # AC-251
    env, _ = start_env(grid_kw=900, bess_soc=31, chp_permit=0)  # КГУ заборонена → одразу скидання після затримки
    peak.step(env)
    env, outs = drive(env, 64, grid_kw=900, chp_permit=0)
    lst = c.shed_list(env)
    # uncovered = 900 − 740 = 160: CHARGING 48 + RV-ALL 60, DRY-1 (немає даних про цикл) пропущено, COMPRESSOR 37 → 145,
    # LP-1 12 → 157 < 160: усе, що можна
    assert [i["node"] for i in lst] == ["CHARGING", "RV-ALL", "COMPRESSOR", "LP-1"]
    assert [i["pct"] for i in lst] == [0.0, 70.0, 0.0, 50.0]
    events = [e.text for o in outs for e in o.events]
    assert any("Скинуто: CHARGING — відкладено на 30 хв" in t for t in events)
    assert any("немає даних про цикл DRY-1" in t for t in events)
    assert env.scen["peak"]["stage"] == "shed"
    # шанс другого кроку: next escalation лише через stage_delay_s
    req = c.shed_request(env)
    assert req.resource == "shed" and req.watchdog == "shed_valid" and req.refresh_s == 20
    assert [w.target for w in req.writes][:2] == ["shed_valid", "energy_control/shed/CHARGING/limit_pct"]


def test_stage3_shed_stops_when_need_covered_and_respects_conditions():  # AC-251
    env, _ = start_env(grid_kw=800, bess_soc=31, chp_permit=0)  # uncovered = 60
    peak.step(env)
    env, _ = drive(env, 64, grid_kw=800, chp_permit=0)
    assert [i["node"] for i in c.shed_list(env)] == ["CHARGING", "RV-ALL"]  # 48 + 60 ≥ 60
    cfg = base_cfg()
    low_air = make_env(cfg, T0, shared={}, **standard_inputs(grid_kw=900, bess_soc=31, chp_permit=0, air_bar=6.0))
    peak.step(low_air)
    low_air, _ = drive(low_air, 64, grid_kw=900, chp_permit=0, air_bar=6.0)
    assert "COMPRESSOR" not in [i["node"] for i in c.shed_list(low_air)]  # тиск повітря < 6,5


def test_no_escalation_while_chp_is_ramping():  # AC-251
    env, _ = start_env(grid_kw=900, bess_soc=31, chp_state=1, chp_permit=1)
    peak.step(env)
    env, outs = drive(env, 130, grid_kw=900, chp_state=1)
    assert not c.shed_list(env) and not any(reqs(o, "chp") for o in outs)  # КГУ розганяється: чекаємо


def test_shed_disabled_or_chp_disallowed_flags():  # AC-251
    cfg = base_cfg(peak={"params": {"limit_kw": 760, "shed_allowed": False, "chp_allowed": False}})
    env = make_env(cfg, T0, **standard_inputs(grid_kw=900, bess_soc=31))
    peak.step(env)
    env, outs = drive(env, 130, grid_kw=900)
    assert not c.shed_list(env) and not any(reqs(o, "chp") for o in outs)


def run_to_release(chp_run_h=0.0):
    """Сценарій розігнано: BESS 100 кВт, КГУ запущена піком, скинуто 2 елементи; далі навантаження спадає."""
    env, _ = start_env(grid_kw=900, bess_soc=70)
    peak.step(env)
    env, _ = drive(env, 10, grid_kw=900, bess_kw=-100)
    env.shared["chp"] = {"owner": "peak", "started_at": env.epoch - chp_run_h * 3600, "stopped_at": None}
    c.shed_list(env).extend(
        [
            {
                "node": "CHARGING",
                "signal": "energy_control/shed/CHARGING/limit_pct",
                "pct": 0.0,
                "by": "peak",
                "t": 0,
                "kw": 48,
                "timer_until": None,
            },
            {
                "node": "RV-ALL",
                "signal": "energy_control/shed/RV-ALL/limit_pct",
                "pct": 70.0,
                "by": "peak",
                "t": 0,
                "kw": 60,
                "timer_until": None,
            },
        ]
    )
    env.scen["peak"]["stage"] = "shed"
    return env


def test_release_restores_in_reverse_order_then_chp_then_bess_ramp():  # AC-252
    env = run_to_release(chp_run_h=2.5)
    low = dict(grid_kw=715, bess_kw=-100, chp_state=2, bess_soc=70)  # нижче limit − release_margin = 720
    env, outs = drive(env, 170, **low)  # release_hold_s 180 ще не минув
    assert all(env.scen["peak"]["release_phase"] is None for _ in [0]) and not kinds(outs[-1], "auto_release")
    env, outs = drive(env, 24, **low)
    assert env.scen["peak"]["release_phase"] == "shed"
    events = [e.text for o in outs for e in o.events if e.kind == "auto_release"]
    assert events[:1] == ["Повернуто: RV-ALL"]  # у зворотному порядку: RV-ALL → CHARGING
    env, outs2 = drive(env, 30, **low)
    events += [e.text for o in outs2 for e in o.events if e.kind == "auto_release"]
    assert events[:2] == ["Повернуто: RV-ALL", "Повернуто: CHARGING"]
    assert [i["pct"] for i in c.shed_list(env)] == [100.0, 100.0]
    chp_stops = [o for o in outs2 if reqs(o, "chp")]
    assert len(chp_stops) == 1 and writes_of(chp_stops[0], "chp") == {"chp_cmd": 2}  # min_run_h 2 год відпрацьовано
    # рампа BESS: уставка 75 зменшується на p_max/4 = 25 кВт кожні 10 с до 0, потім mode 0
    env, outs3 = drive(env, 90, **low)
    outs3 = outs + outs2 + outs3
    sps = [writes_of(o, "bess")["bess_sp"] for o in outs3 if writes_of(o, "bess").get("bess_mode") == 2]
    assert sorted(set(sps), reverse=True)[-2:] == [50, 25] and sps == sorted(sps, reverse=True)
    final = [o for o in outs3 if kinds(o, "auto_release") and any("завершено" in e.text for e in o.events)]
    assert len(final) == 1 and writes_of(final[0], "bess") == {"bess_mode": 0, "bess_valid": 0}
    assert env.scen["peak"]["stage"] == "idle"


def test_release_keeps_chp_until_min_run_hours():  # AC-252
    env = run_to_release(chp_run_h=1.0)
    low = dict(grid_kw=500, bess_kw=-100, chp_state=2, bess_soc=70)
    env, outs = drive(env, 400, **low)
    assert not any(writes_of(o, "chp") for o in outs)  # КГУ лишається (відпрацьовано < 2 год)
    assert env.shared["chp"]["owner"] == "chp"  # власність → сценарій chp (він увімкнений)
    assert env.scen["peak"]["stage"] == "idle"


def test_release_aborted_when_limit_breached_again():  # AC-252
    env = run_to_release(chp_run_h=3)
    low = dict(grid_kw=500, bess_kw=-100, chp_state=2, bess_soc=70)
    env, _ = drive(env, 190, **low)
    assert env.scen["peak"]["release_phase"] == "shed"
    env = advance(env, 2, grid_kw=770, bess_kw=-100, chp_state=2)
    peak.step(env)
    assert env.scen["peak"]["release_phase"] is None and env.scen["peak"]["stage"] != "idle"


def test_disabled_while_holding_releases_without_delay():
    cfg = base_cfg(peak={"enabled": False})
    env = make_env(cfg, T0, **standard_inputs(grid_kw=500))
    env.scen["peak"] = {"stage": "shed", "bess_cmd": 0.0}
    c.shed_list(env).append(
        {
            "node": "CHARGING",
            "signal": "energy_control/shed/CHARGING/limit_pct",
            "pct": 0.0,
            "by": "peak",
            "t": 0,
            "kw": 48,
            "timer_until": None,
        }
    )
    out = peak.step(env)
    assert out.state == "active" and kinds(out, "auto_release")[0].text == "Повернуто: CHARGING"


def test_backup_suspends_peak():  # R-49 п.1
    env, _ = start_env(grid_kw=900)
    env.shared["backup_active"] = True
    out = peak.step(env)
    assert out.state == "armed" and not out.requests and env.scen["peak"]["stage"] == "idle"


def test_orphan_shed_restored_when_idle():
    env, _ = start_env(grid_kw=300)
    c.shed_list(env).append(
        {
            "node": "LP-1",
            "signal": "energy_control/shed/LP-1/limit_pct",
            "pct": 50.0,
            "by": "peak",
            "t": 0,
            "kw": 12,
            "timer_until": None,
        }
    )
    out = peak.step(env)
    assert out.state == "armed" and kinds(out, "auto_release")[0].text == "Повернуто: LP-1"
