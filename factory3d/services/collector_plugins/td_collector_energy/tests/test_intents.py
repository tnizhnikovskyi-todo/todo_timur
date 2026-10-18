"""AC-259, AC-260, AC-261, AC-262: приймання інтенту (`call`), кроки й верифікація 12 видів (R-42 п.3, R-52)."""

import asyncio

import pytest
from helpers import INTENT_SIGNAL, T0, boot_ready, intent, run_intent

from td_collector_energy import intents as it
from td_collector_energy.executor import Executor  # noqa: F401


def writes(h):
    return [(c.split("energy_control/")[-1], v if v is not None else t) for c, v, t in h.device.writes]


async def test_valid_intent_accepted_immediately_without_waiting_for_steps():  # AC-259
    h = await boot_ready()
    payload = intent("bess_charge", {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95}, now=h.clock.now())
    res = await asyncio.wait_for(h.plugin.call(INTENT_SIGNAL, payload), 1.0)
    assert (
        res == {"accepted": True, "run_id": "r-3f9a", "state": "executing", "checks": res["checks"]}
        and res["checks"][0]["code"] == "controller_remote"
    )
    assert h.device.writes == []  # кроки ще не виконано: call() лише ставить у чергу
    assert h.executor.running["bess"] is not None
    await asyncio.gather(*h.executor.running.values())


async def test_reject_reasons():  # AC-259
    h = await boot_ready()
    call = lambda p: h.plugin.call(INTENT_SIGNAL, p)  # noqa: E731
    good = intent("qs_open", now=h.clock.now())
    res = await call({**good, "v": 2})
    assert res["accepted"] is False and res["state"] == "rejected" and res["reason"].startswith("bad schema: v")
    res = await call({k: v for k, v in good.items() if k != "idem"})
    assert res["state"] == "rejected" and "idem" in res["reason"]
    res = await call(intent("teleport", now=h.clock.now(), idem="a1"))
    assert (res["state"], res["reason"]) == ("rejected", "unknown kind")
    res = await call(intent("bess_charge", {"power_kw": 300}, now=h.clock.now(), idem="a2"))
    assert (res["state"], res["reason"]) == ("rejected", "bad params: power_kw > 200")
    res = await call(intent("bess_charge", {"soc_limit_pct": 10}, now=h.clock.now(), idem="a3"))
    assert res["reason"] == "bad params: soc_limit_pct < 50"
    res = await call(intent("air_setpoint", {"setpoint_bar": 9.5}, now=h.clock.now(), idem="a4"))
    assert res["reason"] == "bad params: setpoint_bar > 8.5"
    res = await call(intent("qs_open", now=h.clock.now(), idem="a5", ttl_s=-1))
    assert (res["state"], res["reason"]) == ("rejected", "expired")
    assert h.executor.store.intents.get("a5") is None  # відхилені не зберігаються: повтор з новим TTL можливий


async def test_duplicate_idem_returns_saved_result_without_second_execution():  # AC-259
    h = await boot_ready()
    first, _ = await run_intent(h, "qs_close")
    n = len(h.device.writes)
    again = await h.plugin.call(INTENT_SIGNAL, intent("qs_close", now=h.clock.now()))
    assert again["duplicate"] is True and again["accepted"] is True and again["run_id"] == first["run_id"]
    assert len(h.device.writes) == n
    blocked = await h.plugin.call(INTENT_SIGNAL, intent("qs_close", now=h.clock.now(), idem="b1", action_id=61))
    assert blocked["state"] in ("executing", "blocked", "rejected")


async def test_busy_resource_and_queue_limit():  # AC-259
    h = await boot_ready()
    first = await h.plugin.call(INTENT_SIGNAL, intent("bess_charge", now=h.clock.now(), idem="c1", action_id=1))
    assert first["accepted"] is True
    second = await h.plugin.call(INTENT_SIGNAL, intent("bess_stop", now=h.clock.now(), idem="c2", action_id=2))
    assert (second["accepted"], second["state"], second["reason"]) == (False, "rejected", "busy: bess")
    other = await h.plugin.call(INTENT_SIGNAL, intent("chp_stop", now=h.clock.now(), idem="c3", action_id=3))
    assert other["state"] in ("blocked", "executing", "rejected")  # інший ресурс не зайнятий
    await asyncio.gather(*h.executor.running.values())
    h.executor.queued = 4
    res = await h.plugin.call(INTENT_SIGNAL, intent("qs_open", now=h.clock.now(), idem="c4", action_id=4))
    assert res["reason"] == "busy: queue"


async def test_call_rejects_foreign_signal_and_write_not_supported():  # AC-259, AC-268
    from collector.core.errors import NotSupported
    from collector.core.types import SignalCfg

    h = await boot_ready()
    other = SignalCfg("energy_control/auto/heartbeat", "counter", "", 10, 1.0, False, None, 0, {}, "ENERGY-CTL")
    with pytest.raises(NotSupported):
        await h.plugin.call(other, {})
    with pytest.raises(NotSupported):
        await h.plugin.write(INTENT_SIGNAL, 1.0, None)


@pytest.mark.parametrize(
    "kind, params, expected_writes, summary",
    [
        ("qs_close", {}, [("qs/cmd", 2)], "QS замкнено"),
        ("qs_open", {}, [("qs/cmd", 1)], "QS розімкнено"),
        (
            "bess_charge",
            {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95},
            [("bess/setpoint_kw", 50), ("bess/until_soc", 95), ("bess/valid_s", 25200), ("bess/mode", 1)],
            "BESS: заряд 50 кВт до 16:00 (valid_s 25200)",
        ),
        (
            "bess_discharge",
            {"power_kw": 80, "duration_min": 30},
            [("bess/setpoint_kw", 80), ("bess/until_soc", 30), ("bess/valid_s", 1800), ("bess/mode", 2)],
            "BESS: розряд 80 кВт на 30 хв",
        ),
        ("bess_stop", {}, [("bess/mode", 0), ("bess/valid_s", 0)], "BESS: автоматичний режим"),
        ("chp_start", {}, [("chp/cmd", 1)], "КГУ: пуск"),
        ("air_setpoint", {"setpoint_bar": 6.5}, [("air/setpoint_bar", 6.5)], "Уставка тиску 6.5 бар"),
    ],
)
async def test_each_energy_kind_steps_and_verification(kind, params, expected_writes, summary):  # AC-260
    h = await boot_ready()
    if kind == "chp_stop":
        h.device.set("chp_state", 2)
    res, action = await run_intent(h, kind, params)
    assert res["accepted"], res
    assert writes(h) == expected_writes
    assert action["state"] == "done" and action["steps_total"] == len(expected_writes)
    assert action["result"].startswith(summary)


async def test_chp_stop_and_restore_kinds_and_air_undo_memo():  # AC-260
    h = await boot_ready(chp_state=2, chp_hours=3.0)
    h.executor.store.data["engine"].setdefault("shared", {})["chp"] = {
        "owner": "manual",
        "started_at": h.clock.now().timestamp() - 3 * 3600,
        "stopped_at": None,
    }
    res, action = await run_intent(h, "chp_stop", {})
    assert res["accepted"] and writes(h) == [("chp/cmd", 2)] and action["state"] == "done"
    assert h.executor.store.data["engine"]["shared"]["chp"]["owner"] is None  # chp_stop знімає володіння


async def test_bms_kinds_write_scene_mode_per_target_and_aisle_untouched():  # AC-260
    h = await boot_ready()
    for code, v in (("lighting/groups/LT-01/scene", 2.0), ("lighting/groups/LT-02/scene", 2.0)):
        h.device.regs[code] = (v, None)
    h.device.regs["ventilation/units/RV-01/mode"] = (None, "VE")
    h.device.regs["ventilation/units/RV-02/mode"] = (None, "VE")
    h.device.sync()
    res, action = await run_intent(
        h, "light_break", {"level_pct": 50, "duration_min": 30, "scene_number": 3}, idem="d1"
    )
    assert res["accepted"] and action["state"] == "done" and action["steps_total"] == 2
    assert [(c, v, t) for c, v, t in h.device.writes] == [
        ("lighting/groups/LT-01/scene", 3.0, "fade=2.0"),
        ("lighting/groups/LT-02/scene", 3.0, "fade=2.0"),
    ]  # LT-A1 — аварійні проходи
    assert h.executor.store.data["memo"]["light"] == {
        "lighting/groups/LT-01/scene": 2.0,
        "lighting/groups/LT-02/scene": 2.0,
    }
    res, action = await run_intent(h, "vent_eco", {"vent_pct": 70, "duration_min": 120}, idem="d2", action_id=56)
    assert action["state"] == "done"
    assert [(c, t) for c, _v, t in h.device.writes[2:]] == [
        ("ventilation/units/RV-01/mode", "VEL"),
        ("ventilation/units/RV-02/mode", "VEL"),
    ]
    h.device.writes.clear()
    res, action = await run_intent(h, "light_restore", {}, idem="d3", action_id=57)
    assert action["state"] == "done" and [v for _c, v, _t in h.device.writes] == [2.0, 2.0]  # запам'ятані сцени
    assert "light" not in h.executor.store.data["overrides"]  # light_restore знімає перекриття
    h.device.writes.clear()
    res, action = await run_intent(h, "vent_restore", {}, idem="d4", action_id=58)
    assert [t for _c, _v, t in h.device.writes] == ["VE", "VE"] and "vent" not in h.executor.store.data["overrides"]


async def test_restore_without_memo_uses_day_defaults():  # R-42
    h = await boot_ready()
    for code in ("lighting/groups/LT-01/scene", "lighting/groups/LT-02/scene"):
        h.device.regs[code] = (2.0, None)
    h.device.regs["ventilation/units/RV-01/mode"] = (None, "VE")
    h.device.regs["ventilation/units/RV-02/mode"] = (None, "VE")
    h.device.sync()
    await run_intent(h, "light_restore", {}, idem="e1")
    assert [v for _c, v, _t in h.device.writes] == [2.0, 2.0]  # light_scene_day_number
    h.device.writes.clear()
    await run_intent(h, "vent_restore", {}, idem="e2", action_id=60)
    assert [t for _c, _v, t in h.device.writes] == ["VE", "VE"]  # day_vent_mode


async def test_qs_close_controller_refusal_success_and_no_change():  # AC-261
    h = await boot_ready()
    h.device.hooks["energy_control/qs/cmd"] = lambda v, t: h.device.regs.__setitem__(
        "energy_control/qs/ack", (2.0, None)
    )
    res, action = await run_intent(h, "qs_close")
    assert action["state"] == "failed" and "Контролер відмовив: блокування" in action["error"]
    h2 = await boot_ready()
    res, action = await run_intent(h2, "qs_close")
    assert action["state"] == "done"
    h3 = await boot_ready()
    h3.device.hooks.pop("energy_control/qs/cmd")  # QS не змінив положення
    res, action = await run_intent(h3, "qs_close")
    assert action["state"] == "failed" and "Не підтверджено пристроєм: QS не змінив положення" in action["error"]
    assert h3.clock.monotonic() - 1000.0 >= 10  # верифікація тривала ≤ 10 с (читання раз на секунду)


async def test_bess_charge_valid_s_until_and_limits():  # AC-262
    h = await boot_ready()
    cfg = h.cfg
    plan = it.build_plan("bess_charge", {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95}, cfg, T0, {})
    assert [s.writes[0].value for s in plan.steps] == [50, 95, 25200, 1]  # 09:00 → 16:00 = 7 год
    plan = it.build_plan("bess_charge", {"power_kw": 50, "until": "23:59", "soc_limit_pct": 95}, cfg, T0, {})
    assert plan.steps[2].writes[0].value == 43200  # максимум 12 год
    with pytest.raises(it.ParamError, match="Час «до» має бути пізніше за поточний"):
        it.build_plan("bess_charge", {"power_kw": 50, "until": "08:00", "soc_limit_pct": 95}, cfg, T0, {})
    res = await h.plugin.call(INTENT_SIGNAL, intent("bess_charge", {"until": "09:00"}, now=T0, idem="f1"))
    assert res["state"] == "rejected" and "Час «до» має бути пізніше за поточний" in res["reason"]
    assert it.seconds_until(T0, "09:00") == 0


async def test_bess_charge_failed_verification_runs_failsafe():  # AC-262
    h = await boot_ready()
    h.device.hooks["energy_control/bess/mode"] = lambda v, t: h.device.regs.__setitem__(
        "energy_control/bess/mode", (0.0, None)
    )
    res, action = await run_intent(h, "bess_charge", {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95})
    assert action["state"] == "failed" and "Не підтверджено пристроєм: режим BESS" in action["error"]
    assert "Повернуто безпечний стан" in action["error"]
    tail = [(c.split("energy_control/")[-1], v) for c, v, _t in h.device.writes[-2:]]
    assert tail == [("bess/mode", 0), ("bess/valid_s", 0)]  # fail-safe: режим 0 і valid_s 0
    assert "bess" not in h.executor.store.data["overrides"]


async def test_bess_charge_soft_check_adds_warning_to_result():  # AC-262
    h = await boot_ready()  # bess_kw = 0: потужність заряду не набрала 0,5·power_kw
    res, action = await run_intent(h, "bess_charge", {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95})
    assert action["state"] == "done" and "(попередження: потужність заряду < 25 кВт)" in action["result"]
    h2 = await boot_ready(bess_kw=30)
    res, action = await run_intent(h2, "bess_charge", {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95})
    assert action["state"] == "done" and "попередження" not in action["result"]


async def test_bess_kw_max_bound_uses_min_of_code_config_and_payload():  # R-42 п.1
    h = await boot_ready()
    cfg = h.cfg
    assert it.bess_kw_max(cfg, {"bess_kw_max": 120}) == 120 and it.bess_kw_max(cfg, {"bess_kw_max": 900}) == 200
    p = it.validate_params("bess_discharge", {"power_kw": 120}, cfg, {"bess_kw_max": 120})
    assert p == {"power_kw": 120.0, "duration_min": 60.0}
    with pytest.raises(it.ParamError, match="power_kw > 120"):
        it.validate_params("bess_discharge", {"power_kw": 121}, cfg, {"bess_kw_max": 120})
    with pytest.raises(it.ParamError, match="duration_min"):
        it.validate_params("bess_discharge", {"duration_min": 1.5}, cfg)
    with pytest.raises(it.ParamError, match="scene_number > 16"):
        it.validate_params("light_break", {"scene_number": 17}, cfg)


CHARGE = {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95}
TEXT_STATES = {"remote": "remote", "bess_state": "standby", "chp_state": "stop", "ats_pos": "pos_I",
               "src1_ok": "available", "qs_state": "open"}


async def test_state_signals_with_text_like_real_modbus_plugin():  # C-39: kind=state з `map` дає лише `text`
    h = await boot_ready(**TEXT_STATES)

    def chp(value, text):
        h.device.regs["infra/chp/state"] = (None, "starting" if value == 1 else "cooling")

    def qs(value, text):
        h.device.regs["energy/cells/QS/state"] = (None, "closed" if value == 2 else "open")

    h.device.hooks["energy_control/chp/cmd"], h.device.hooks["energy_control/qs/cmd"] = chp, qs
    h.device.sync()
    res, action = await run_intent(h, "bess_charge", CHARGE, idem="t1", action_id=81)
    assert res["accepted"] and action["state"] == "done", (res, action)  # bess_ok/no_island бачать індекси станів
    res, action = await run_intent(h, "chp_start", {}, idem="t2", action_id=82)
    assert res["accepted"] and action["state"] == "done"  # verify: chp_state "starting" → 1
    res, action = await run_intent(h, "qs_close", {}, idem="t3", action_id=83)
    assert res["accepted"] and action["state"] == "done"


async def test_text_states_in_engine_inputs():
    h = await boot_ready(**TEXT_STATES, grid_kw=800, bess_soc=82)
    h.device.set("bess_state", None, "running")
    await h.tick()
    assert any(c.endswith("/bess/mode") for c, _v, _t in h.device.writes)  # peak: bess_state «running» → 2 ∈ {1,2,4}
    assert h.engine.snapshot()["engine"]["controller_remote"] is True


@pytest.mark.parametrize("name, text, number", [
    ("bess_state", "sleep", 4), ("bess_state", "fault", 3), ("chp_state", "running", 2), ("chp_state", "cooling", 4),
    ("ats_pos", "pos_II", 3), ("ats_pos", "pos_I", 2), ("remote", "local", 0), ("src1_ok", "available", 1)])
def test_text_state_mapping_table(name, text, number):
    from collector.core.types import Reading

    from td_collector_energy.inputs import text_value

    assert text_value(name, Reading("x", T0, text=text)) == number
    assert text_value(name, Reading("x", T0, value=7.0, text=text)) == 7.0
    assert text_value(name, Reading("x", T0, text="невідомо")) is None
