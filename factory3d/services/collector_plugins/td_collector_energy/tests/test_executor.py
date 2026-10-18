"""AC-263, AC-264, AC-265: виконавець інтентів — повтори, таймаути, fail-safe, блокування, перекриття (R-52, R-53)."""

import asyncio
import copy

from helpers import INTENT_SIGNAL, base_raw, boot_ready, intent, run_intent

CHARGE = {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95}


def raw_with(**engine):
    raw = base_raw()
    raw["engine"].update(engine)
    return raw


async def test_write_error_is_retried_once_after_1s():  # AC-263
    h = await boot_ready()
    h.device.fail["energy_control/bess/valid_s"] = 1
    t0 = h.clock.monotonic()
    res, action = await run_intent(h, "bess_charge", CHARGE)
    assert action["state"] == "done"
    assert h.clock.monotonic() - t0 >= 1.0  # пауза 1 с перед повтором
    assert [c.rsplit("/", 1)[-1] for c, _v, _t in h.device.writes] == ["setpoint_kw", "until_soc", "valid_s", "mode"]


async def test_second_write_error_fails_with_failsafe():  # AC-263
    h = await boot_ready()
    h.device.fail["energy_control/bess/valid_s"] = 2
    res, action = await run_intent(h, "bess_charge", CHARGE)
    assert (
        action["state"] == "failed"
        and "Не виконано" in action["error"]
        and "Повернуто безпечний стан" in action["error"]
    )
    assert [(c.rsplit("/", 1)[-1], v) for c, v, _t in h.device.writes[-2:]] == [("mode", 0), ("valid_s", 0)]


async def test_failsafe_failure_is_reported_as_unknown_device_state():  # R-52 п.5
    h = await boot_ready()
    h.device.fail["energy_control/bess/valid_s"] = 2
    h.device.fail["energy_control/bess/mode"] = 9  # і fail-safe не проходить
    res, action = await run_intent(h, "bess_charge", CHARGE)
    assert action["state"] == "failed" and "Стан пристрою невідомий: перевірте вручну" in action["error"]
    assert any(e["kind"] == "failsafe" for e in h.events())


async def test_verification_timeout_fails():  # AC-263
    h = await boot_ready()
    h.device.hooks.pop("energy_control/chp/cmd")  # КГУ не стартує
    t0 = h.clock.monotonic()
    res, action = await run_intent(h, "chp_start")
    assert action["state"] == "failed" and "Не підтверджено пристроєм: КГУ не запустилась" in action["error"]
    assert 29 <= h.clock.monotonic() - t0 <= 45  # верифікація КГУ — до 30 с


async def test_total_exec_timeout_fails_with_failsafe():  # AC-263
    h = await boot_ready(raw=raw_with(exec_timeout_s=5, verify_timeout_s=30))
    h.device.hooks.pop("energy_control/chp/cmd")
    res, action = await run_intent(h, "chp_start")
    assert action["state"] == "failed" and "Перевищено загальний час виконання" in action["error"]


async def test_exec_timeout_before_a_step():  # AC-263
    h = await boot_ready(raw=raw_with(exec_timeout_s=3))
    orig = h.device.write

    async def slow(code, value=None, text=None, **kw):
        h.clock.advance(2)  # кожен запис «триває» 2 с
        return await orig(code, value, text)

    h.executor.writer._write = slow
    res, action = await run_intent(h, "bess_charge", CHARGE)
    assert action["state"] == "failed" and "перевищено загальний час" in action["error"].lower()
    assert [c.rsplit("/", 1)[-1] for c, _v, _t in h.device.writes[-2:]] == ["mode", "valid_s"]  # fail-safe виконано


async def test_hard_blocks_write_nothing():  # AC-264
    h = await boot_ready(ats_lock=0)
    res = await h.plugin.call(INTENT_SIGNAL, intent("qs_close", now=h.clock.now()))
    assert res["accepted"] is False and res["state"] == "blocked"
    assert res["reason"] == "Блокування: ats_parallel_lock — не виконано (lock=0)"
    assert {"code": "ats_parallel_lock", "state": "fail", "detail": "lock=0"} in res["checks"]
    assert h.device.writes == [] and not h.executor.running
    h2 = await boot_ready(remote=0)
    res = await h2.plugin.call(INTENT_SIGNAL, intent("bess_charge", CHARGE, now=h2.clock.now()))
    assert res["state"] == "blocked" and "controller_remote" in res["reason"] and h2.device.writes == []
    h3 = await boot_ready(remote=None)  # fail-closed: немає даних → блок
    res = await h3.plugin.call(INTENT_SIGNAL, intent("qs_open", now=h3.clock.now()))
    assert res["state"] == "blocked" and "немає даних" in res["reason"]
    h4 = await boot_ready(ats_pos=3)
    res = await h4.plugin.call(INTENT_SIGNAL, intent("bess_charge", CHARGE, now=h4.clock.now()))
    assert res["state"] == "blocked" and "no_island" in res["reason"]
    h5 = await boot_ready(bess_soc=96)
    res = await h5.plugin.call(INTENT_SIGNAL, intent("bess_charge", CHARGE, now=h5.clock.now()))
    assert res["state"] == "blocked" and "bess_soc_lt_limit" in res["reason"]
    assert h.executor.blocked_total == 1 and "blocked" in {r["state"] for r in h.executor.store.intents.values()}


async def test_stale_inputs_block_fail_closed():  # AC-264, R-53 №5
    h = await boot_ready()
    h.clock.advance(120)  # показання старіші за max_age_s
    res = await h.plugin.call(INTENT_SIGNAL, intent("qs_close", now=h.clock.now()))
    assert res["state"] == "blocked" and "немає даних" in res["reason"] or "немає свіжих даних" in res["reason"]


async def test_remote_switching_flag_and_write_flags():  # D-46, AC-309
    raw = base_raw()
    raw["flags"]["remote_switching_enabled"] = False
    h = await boot_ready(raw=raw)
    for kind, params in (("qs_close", {}), ("qs_open", {}), ("chp_start", {}), ("bess_discharge", {"power_kw": 50})):
        res = await h.plugin.call(INTENT_SIGNAL, intent(kind, params, now=h.clock.now(), idem=f"g-{kind}"))
        assert res["state"] == "blocked" and res["reason"].startswith("Дистанційне перемикання вимкнено"), kind
    assert h.device.writes == []
    ok, action = await run_intent(h, "chp_stop", {}, idem="g-stop", action_id=70)  # chp_stop не блокується
    assert ok["accepted"] is True
    ok, action = await run_intent(h, "bess_charge", CHARGE, idem="g-charge", action_id=71)  # заряд — не «перемикання»
    assert ok["accepted"] is True
    raw2 = base_raw()
    raw2["flags"]["write_enabled"] = False
    h2 = await boot_ready(raw=raw2)
    res = await h2.plugin.call(INTENT_SIGNAL, intent("bess_stop", now=h2.clock.now()))
    assert res["state"] == "blocked" and "write_enabled" in res["reason"]
    h3 = await boot_ready()
    h3.plugin.ctx.settings.write_enabled = False  # F3D_WRITE_ENABLED вимкнено
    res = await h3.plugin.call(INTENT_SIGNAL, intent("bess_stop", now=h3.clock.now()))
    assert res["state"] == "blocked" and "F3D_WRITE_ENABLED" in res["reason"]


async def test_denied_or_unconfigured_code_is_refused_with_interlock_event():  # AC-264
    raw = base_raw()
    raw["bms"]["light_break"]["light"][0]["scene_signal"] = "fire/panel/scene"  # заборонений префікс
    h = await boot_ready(raw=raw)
    res, action = await run_intent(h, "light_break", {"scene_number": 3})
    assert action["state"] == "blocked" and "заборонено: fire/" in action["error"]
    assert not any(c.startswith("fire/") for c, _v, _t in h.device.writes)
    assert any(e["kind"] == "interlock" and "fire/panel/scene" in e["text"] for e in h.events())


async def test_recheck_before_activating_step_blocks_and_skips_mode_write():  # R-52 п.2
    h = await boot_ready()

    def degrade(value, text):
        h.device.regs["infra/bess/state"] = (0.0, None)  # BESS «пропав» між приймом і активуючим кроком
        h.device.sync()

    h.device.hooks["energy_control/bess/valid_s"] = degrade
    res, action = await run_intent(h, "bess_charge", CHARGE)
    assert res["accepted"] and action["state"] == "blocked" and "bess_ok" in action["error"]
    assert not any(c.endswith("/bess/mode") for c, _v, _t in h.device.writes)


async def test_write_switch_off_mid_run_cancels_steps_and_runs_failsafe():  # R-53 №14
    h = await boot_ready()
    box = h.box

    def kill_switch(value, text):
        box.settings.write_enabled = False

    h.device.hooks["energy_control/bess/setpoint_kw"] = kill_switch
    res, action = await run_intent(h, "bess_charge", CHARGE)
    assert action["state"] == "blocked" and "Запис вимкнено" in action["error"]
    assert "Стан пристрою невідомий" in action["error"]  # fail-safe теж відхилено збирачем
    assert [c.rsplit("/", 1)[-1] for c, _v, _t in h.device.writes] == ["setpoint_kw"]  # решту кроків скасовано


async def test_progress_reports_and_final_state_are_monotonic():  # R-52 п.9
    h = await boot_ready()
    seen = []
    orig = h.reporter.add_action
    h.reporter.add_action = lambda item, **kw: (
        seen.append((item["state"], item["step"], item["steps_total"])),
        orig(item, **kw),
    )[1]
    res, action = await run_intent(h, "bess_charge", CHARGE)
    assert seen[0] == ("executing", 0, 4) and seen[-1][0] == "done" and ("executing", 4, 4) in seen
    assert action["idem"] == "3f9a7c0e1d2b4a5f6e7d8c9b" and action["checks"] and h.reporter.wake.is_set()
    steps = [s[1] for s in seen if s[0] == "executing"]
    assert steps == sorted(steps)


async def test_override_registered_for_bess_charge_and_removed_by_stop():  # AC-265
    h = await boot_ready()
    now = h.clock.now().timestamp()
    res, action = await run_intent(h, "bess_charge", CHARGE)
    ov = h.executor.store.data["overrides"]["bess"]
    assert ov["until"] == now + 25200 and ov["action_id"] == 55 and ov["kind"] == "bess_charge"
    assert any(e["kind"] == "override" and e["text"].startswith("ручний режим BESS до ") for e in h.events())
    # перекриття діє на рушій: peak/self не пишуть BESS
    assert "bess" in h.engine.active_overrides(now + 10)
    res, action = await run_intent(h, "bess_stop", {}, idem="h2", action_id=56)
    assert action["state"] == "done" and "bess" not in h.executor.store.data["overrides"]
    start = h.clock.now().timestamp()
    res, action = await run_intent(h, "bess_discharge", {"power_kw": 50, "duration_min": 30}, idem="h3", action_id=57)
    assert action["state"] == "done" and h.executor.store.data["overrides"]["bess"]["until"] == start + 1800


async def test_chp_start_sets_manual_owner_and_chp_stop_clears_it():  # AC-265
    h = await boot_ready()
    res, action = await run_intent(h, "chp_start")
    assert action["state"] == "done"
    chp = h.executor.store.data["engine"]["shared"]["chp"]
    assert chp["owner"] == "manual" and chp["started_at"] is not None
    h.device.regs["infra/chp/state"] = (2.0, None)
    h.device.sync()
    h.executor.store.data["engine"]["shared"]["chp"]["started_at"] = h.clock.now().timestamp() - 3 * 3600
    res, action = await run_intent(h, "chp_stop", {}, idem="i2", action_id=60)
    assert action["state"] == "done" and h.executor.store.data["engine"]["shared"]["chp"]["owner"] is None


async def test_light_break_auto_restore_after_duration_with_auto_release_event():  # AC-265
    h = await boot_ready()
    for code in ("lighting/groups/LT-01/scene", "lighting/groups/LT-02/scene"):
        h.device.regs[code] = (2.0, None)
    h.device.sync()
    res, action = await run_intent(h, "light_break", {"duration_min": 30, "scene_number": 3, "level_pct": 50})
    assert action["state"] == "done" and "light" in h.executor.store.data["overrides"]
    await h.executor.tick()
    assert "light" in h.executor.store.data["overrides"] and not h.executor.running  # ще < 30 хв
    h.clock.advance(31 * 60)
    h.device.writes.clear()
    await h.executor.tick()
    await asyncio.gather(*h.executor.running.values())
    assert [v for _c, v, _t in h.device.writes] == [2.0, 2.0]  # автоматичне відновлення запам'ятаних сцен
    assert "light" not in h.executor.store.data["overrides"]
    assert any(e["kind"] == "auto_release" and e["text"] == "Освітлення: перерва завершена" for e in h.events())


async def test_vent_eco_auto_restore_and_idempotent_second_tick():  # AC-265
    h = await boot_ready()
    h.device.regs["ventilation/units/RV-01/mode"] = (None, "VE")
    h.device.regs["ventilation/units/RV-02/mode"] = (None, "VE")
    h.device.sync()
    await run_intent(h, "vent_eco", {"vent_pct": 70, "duration_min": 5})
    h.clock.advance(6 * 60)
    await h.executor.tick()
    await asyncio.gather(*h.executor.running.values())
    assert [t for _c, _v, t in h.device.writes[-2:]] == ["VE", "VE"] and "vent" not in h.executor.store.data[
        "overrides"
    ]
    n = len(h.device.writes)
    await h.executor.tick()
    assert len(h.device.writes) == n


async def test_air_setpoint_failed_verification_restores_previous_setpoint():  # R-42
    h = await boot_ready(air_sp=6.8)
    h.device.hooks["energy_control/air/setpoint_bar"] = lambda v, t: h.device.regs.__setitem__(
        "energy_control/air/setpoint_bar", (6.8, None)
    )  # контролер повертає стару уставку
    res, action = await run_intent(h, "air_setpoint", {"setpoint_bar": 6.5})
    assert action["state"] == "failed" and "уставка тиску" in action["error"]
    assert [v for _c, v, _t in h.device.writes[-2:]] == [6.5, 6.8]  # undo до прежньої уставки (6.8)


async def test_stop_cancels_running_intent_tasks_cleanly():
    h = await boot_ready()
    h.device.hooks.pop("energy_control/chp/cmd")
    await h.plugin.call(INTENT_SIGNAL, intent("chp_start", now=h.clock.now()))
    await h.executor.stop()
    assert not h.executor.running
    assert copy.deepcopy(h.reporter.actions) is not None


async def test_bms_kinds_without_targets_are_rejected():  # R-42 п.2
    raw = base_raw()
    raw["bms"] = {"night": {"vent": [], "light": []}, "vent_eco": {"vent": []}, "light_break": {"light": []}}
    h = await boot_ready(raw=raw)
    for kind in ("light_break", "light_restore", "vent_eco", "vent_restore"):
        res = await h.plugin.call(INTENT_SIGNAL, intent(kind, {}, now=h.clock.now(), idem=f"n-{kind}"))
        assert (res["state"], res["reason"]) == ("rejected", "немає цілей BMS"), kind
    assert h.device.writes == []
