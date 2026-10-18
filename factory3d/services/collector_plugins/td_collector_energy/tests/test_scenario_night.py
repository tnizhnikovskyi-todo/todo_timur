"""AC-256: «Нічний режим (BMS)» — вікно через північ, дні, DST, ідемпотентність, ручне втручання (R-48)."""

from datetime import UTC, datetime

from helpers import T0, advance, base_cfg, base_raw, kinds, make_env, reqs, standard_inputs, writes_of

from td_collector_energy import config as cfgmod
from td_collector_energy.scenarios import night
from td_collector_energy.timeutil import in_window, next_window_start

NIGHT = datetime(2026, 10, 14, 21, 0, tzinfo=UTC)  # 00:00 Київ (середа 14.10)
DAY = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)  # 12:00 Київ
VENT1, VENT2 = "ventilation/units/RV-01/mode", "ventilation/units/RV-02/mode"
SP1 = "ventilation/units/RV-01/setpoint_night_c"
LT = ["lighting/groups/LT-01/scene", "lighting/groups/LT-02/scene", "lighting/groups/LT-A1/scene"]


def env_at(now, cfg=None, **over):
    return make_env(cfg or base_cfg(), now, **standard_inputs(**over))


def test_window_across_midnight_and_days():  # AC-256
    h = lambda y, m, d, hh, mm: datetime(y, m, d, hh, mm, tzinfo=UTC)  # noqa: E731
    wk = [1, 2, 3, 4, 5]  # пн…пт: дні, З ЯКИХ починається вікно
    assert in_window(h(2026, 10, 14, 20, 30), 23.0, 6.5, wk)  # ср 23:30 EEST
    assert in_window(h(2026, 10, 15, 3, 0), 23.0, 6.5, wk)  # чт 06:00 — вікно, що почалося у ср
    assert not in_window(h(2026, 10, 15, 3, 31), 23.0, 6.5, wk)  # чт 06:31
    assert in_window(h(2026, 10, 16, 20, 30), 23.0, 6.5, wk)  # пт 23:30 — початок у пт
    assert in_window(h(2026, 10, 17, 3, 0), 23.0, 6.5, wk)  # сб 06:00 — частина вікна, що почалося в пт
    assert not in_window(h(2026, 10, 17, 20, 30), 23.0, 6.5, wk)  # сб 23:30 — субота не в `days`
    assert not in_window(h(2026, 10, 18, 3, 0), 23.0, 6.5, wk)  # нд 06:00 — вікно мало початися в сб
    assert in_window(h(2026, 10, 14, 9, 0), 9.0, 17.0, wk) is True  # вікно без півночі: 12:00 Київ в [9, 17)


def test_dst_uses_wall_clock_time():  # AC-256
    wk = list(range(1, 8))
    # 25.10.2026 04:00 EEST → 03:00 EET: «23:00 за стіною» — 20:00Z до переходу й 21:00Z після нього
    assert in_window(datetime(2026, 10, 24, 20, 30, tzinfo=UTC), 23.0, 6.5, wk)  # 23:30 EEST
    assert not in_window(datetime(2026, 10, 25, 20, 30, tzinfo=UTC), 23.0, 6.5, wk)  # 22:30 EET — ще не вікно
    assert in_window(datetime(2026, 10, 25, 21, 30, tzinfo=UTC), 23.0, 6.5, wk)  # 23:30 EET
    assert in_window(datetime(2026, 10, 26, 4, 29, tzinfo=UTC), 23.0, 6.5, wk)  # 06:29 EET
    assert not in_window(datetime(2026, 10, 26, 4, 31, tzinfo=UTC), 23.0, 6.5, wk)  # 06:31 EET
    # весна: 29.03.2026 03:00 EET → 04:00 EEST
    assert in_window(datetime(2026, 3, 28, 21, 30, tzinfo=UTC), 23.0, 6.5, wk)  # 23:30 EET
    assert in_window(datetime(2026, 3, 29, 3, 29, tzinfo=UTC), 23.0, 6.5, wk)  # 06:29 EEST
    assert next_window_start(datetime(2026, 3, 28, 9, 0, tzinfo=UTC), 23.0, wk) == "23:00"


def test_enter_window_writes_vent_mode_setpoint_and_duty_scene():  # AC-256
    out = night.step(env_at(NIGHT))
    assert out.state == "active" and out.facts == {"until": "06:30"}
    vent = {w.target: (w.value, w.text) for w in reqs(out, "vent")[0].writes}
    assert vent == {
        VENT1: (None, "VEL"),
        SP1: (16.0, None),
        VENT2: (None, "VEL"),
    }  # sp_night лише в установки, що його має
    light = {w.target: (w.value, w.text) for w in reqs(out, "light")[0].writes}
    assert light == {t: (1.0, "fade=2.0") for t in LT}  # проходи (aisle) теж у дежурний сценарій
    ev = kinds(out, "auto_step")
    assert len(ev) == 1 and ev[0].text == (
        "Нічний режим: вентиляція RoofVent 2 шт. → 30 %, освітлення — черговий сценарій"
    )


def test_start_inside_window_is_idempotent():  # AC-256
    env = env_at(NIGHT)
    first = night.step(env)
    second = night.step(advance(env, 2))
    assert [(w.target, w.value, w.text) for w in reqs(first, "vent")[0].writes] == [
        (w.target, w.value, w.text) for w in reqs(second, "vent")[0].writes
    ]
    assert not second.events  # подія входу — лише раз


def test_exit_window_writes_day_values_then_stops_holding_the_day():  # AC-256
    env = env_at(NIGHT)
    night.step(env)
    env = advance(env, 7 * 3600 + 60)  # 07:01 Київ: вікно закінчилося о 06:30
    out = night.step(env)
    assert out.state == "armed" and out.facts == {"next_run": "23:00"}
    assert writes_of(out, "vent") == {VENT1: "VE", VENT2: "VE"} and {w.value for w in reqs(out, "light")[0].writes} == {
        2.0
    }
    assert kinds(out, "auto_release")[0].text == "Вентиляція · денний режим: RoofVent 2 шт. → 100 %"
    env = advance(env, 700)  # після 10 хв повторення денних значень сценарій нічого не «тримає»
    assert not night.step(env).requests


def test_outside_window_writes_nothing():  # AC-256
    out = night.step(env_at(DAY))
    assert out.state == "armed" and not out.requests and out.facts["next_run"] == "23:00"


def test_manual_change_marks_target_overridden_until_window_boundary():  # AC-256
    env = env_at(NIGHT)
    night.step(env)
    live = env.inp.live
    from collector.core.types import Reading

    code = LT[0]
    live.update([Reading(code, env.now, value=1.0)])  # наш запис застосовано
    live.note_write(code, 1.0, env.now)
    env = advance(env, 30)
    live.update([Reading(code, env.now, value=5.0)])  # оператор змінив сцену вручну
    out = night.step(env)
    assert code in {w.target for w in reqs(out, "light")[0].writes}  # ще < 60 с
    env = advance(env, 40)
    live.update([Reading(code, env.now, value=5.0)])
    out = night.step(env)
    assert code not in {w.target for w in reqs(out, "light")[0].writes}  # перекрито: не перезаписуємо
    assert kinds(out, "override") and code in env.scen["night"]["overridden"]
    assert not kinds(night.step(advance(env, 2)), "override")  # подія один раз
    env = advance(env, 24 * 3600)  # наступне вікно
    env = advance(env, 0)
    next_night = night.step(env)
    assert code in {w.target for w in reqs(next_night, "light")[0].writes}
    assert env.scen["night"]["overridden"] == []


def test_no_bms_targets_warns_and_fire_blocks_vent_light():  # AC-256
    raw = base_raw()
    raw["bms"] = {"night": {"vent": [], "light": []}, "vent_eco": {"vent": []}, "light_break": {"light": []}}
    cfg = cfgmod.parse(raw).config
    out = night.step(env_at(NIGHT, cfg))
    assert out.state == "warn" and out.facts["reason"] == "немає цілей BMS" and not out.requests
    env = env_at(NIGHT)
    env.blocked.update({"vent", "light"})
    out = night.step(env)
    assert out.state == "warn" and out.facts["reason"] == "пожежна тривога" and not out.requests


def test_manual_overrides_of_resources_skip_groups_and_disabled_is_off():
    env = env_at(NIGHT)
    env.overrides["light"] = {"until": T0.timestamp() + 600}
    out = night.step(env)
    assert reqs(out, "vent") and not reqs(out, "light")  # R-48 п.6
    cfg = base_cfg(night={"enabled": False})
    assert night.step(env_at(NIGHT, cfg)).state == "off"


def test_custom_params_and_missing_sp_night():
    cfg = base_cfg(night={"params": {"vent_mode": "VE", "heat_setpoint_c": 12.0, "light_scene_number": 4}})
    out = night.step(env_at(NIGHT, cfg))
    vent = {w.target: (w.value, w.text) for w in reqs(out, "vent")[0].writes}
    assert vent[VENT1] == (None, "VE") and vent[SP1] == (12.0, None)
    assert {w.value for w in reqs(out, "light")[0].writes} == {4.0}
