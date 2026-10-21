"""td_chp §8 (AC-25, AC-27): повна модель КГУ — пуск у 9 кроків, аварії, зупинки без аварії, команди, режими."""

import asyncio

import pytest
from iot_sim.core.scenarios import ScenarioRunner
from iot_sim.protocols.modbus_maps import build_all
from iot_sim.protocols.modbus_maps.tedom import load_map

BY = {r["code"]: r for r in load_map()}
STEP_DUR = [5, 6, 5, 7, 6, 5, 5, 9, 12]


@pytest.fixture
def chp(world):
    world.step(1)
    return world.devices["CHP"].model


@pytest.fixture
def um(world, chp):
    return build_all(world)[72]


def reg(chp, name):
    return chp.regs[f"chp/{name}"]


def cmd(world, um, value, secs=1):
    um.write("h", BY["chp/ctl/cmd"]["pdu"], [value])
    world.advance(secs)


def ack(world):
    return world.flags.get("chp_ack", 0), world.flags.get("chp_ack_reason", 0)


def start_and_run(world, um, chp):
    cmd(world, um, 1)
    world.advance(65)
    assert chp.s["state"] == 2


async def settle(n=6):
    for _ in range(n):
        await asyncio.sleep(0)


# --- AC-25: пуск ----------------------------------------------------------------------------------------------
def test_standby_by_default(world, chp):
    assert reg(chp, "ctl/state") == 0 and reg(chp, "ctl/step") == 0 and reg(chp, "eng/rpm") == 0
    assert chp.s["hours"] == 18400.0 and chp.s["starts"] == 612 and reg(chp, "gen/p_kw") == 0


def test_start_runs_nine_steps_in_60_s(world, um, chp):
    um.write("h", BY["chp/ctl/cmd"]["pdu"], [1])
    assert ack(world) == (0, 0)  # нова команда скидає ack до виконання
    seq = []
    for _ in range(62):
        world.advance(1)
        seq.append((chp.regs["chp/ctl/state"], chp.regs["chp/ctl/step"]))
    assert ack(world) == (1, 0)
    steps = [1] + [s for st, s in seq if st == 1]  # + початок кроку 1 у момент команди (t = 0)
    assert [steps.count(i) for i in range(1, 10)] == STEP_DUR  # R-13: 5, 6, 5, 7, 6, 5, 5, 9, 12 с
    assert sorted(set(steps)) == list(range(1, 10)) and steps == sorted(steps)
    assert seq[0] == (1, 1) and seq[58] == (1, 9) and seq[59][0] == 2 and seq[-1] == (2, 0)
    assert chp.s["starts"] == 613 and chp.s["hours"] > 18400.0


def test_start_step_details(world, um, chp):
    cmd(world, um, 1)
    assert reg(chp, "gas/yv1") == 0 and reg(chp, "safe/qf_closed") == 0
    world.advance(16)  # крок 4 (перевірка герметичності): клапани в тесті, valve proving виконується
    assert reg(chp, "ctl/step") == 4 and reg(chp, "gas/yv1") == 2 and reg(chp, "gas/vp_state") == 1
    world.advance(8)
    assert reg(chp, "gas/vp_state") == 2 and reg(chp, "gas/vp_ts") > 0 and reg(chp, "eng/starter_on") == 1
    world.advance(20)
    assert reg(chp, "ctl/step") == 8 and reg(chp, "gas/yv1") == 1
    assert reg(chp, "ctl/sync_ok") in (0, 1) and reg(chp, "eng/rpm") > 1400
    world.advance(10)
    assert reg(chp, "safe/qf_closed") == 1 and reg(chp, "ctl/step") == 9


def test_warm_step_skipped_when_engine_warm(world, um, chp):
    chp.s["t_jo"] = 70.0
    cmd(world, um, 1)
    assert chp.s["warm_skip"] is True and reg(chp, "ctl/warm_skip") == 1
    world.advance(6)  # вентиляція 5 с + підігрів 1,5 с (замість 6) → з 6,5 с триває «Попереднє змащення»
    assert reg(chp, "ctl/step") == 3
    world.advance(55)
    assert chp.s["state"] == 2


def test_start_scaled_by_chp_start_s(world, um, chp):
    world.set_flag("chp_start_s", 30.0)
    cmd(world, um, 1)
    world.advance(20)
    assert chp.s["state"] == 1
    world.advance(12)
    assert chp.s["state"] == 2


@pytest.mark.parametrize(
    ("flags", "reason"),
    [
        ({"chp_permit": 0}, 1),
        ({"gas_bar": 1.15}, 2),
        ({"ctl_remote": 0}, 3),
        ({"chp_rocof": 1}, 5),
        ({"chp_gas_leak": 1}, 6),
        ({"chp_fire": 1}, 7),
        ({"chp_ret_fault": 1}, 8),
        ({"chp_temp_fault": 1}, 9),
    ],
)
def test_start_refused_with_reason(world, um, chp, flags, reason):
    for k, v in flags.items():
        world.set_flag(k, v)
    um.write("h", BY["chp/ctl/cmd"]["pdu"], [1])
    world.advance(1)
    assert ack(world) == (2, reason)
    assert chp.s["state"] in (0, 3) and not world.flags.get("chp_run")  # пожежа/загазованість — одразу аварія
    assert reg(chp, "ctl/ack_reason") == reason and reg(chp, "ctl/ack") == 2


def test_start_refused_in_wrong_state(world, um, chp):
    start_and_run(world, um, chp)
    cmd(world, um, 1)
    assert ack(world) == (2, 12) and chp.s["state"] == 2


def test_start_refused_when_no_grid(world, um, chp):
    world.set_flag("blackout", {"phase": "outage", "genset": True, "chp_island": False})
    world.advance(1)
    cmd(world, um, 1)
    assert ack(world) == (2, 4)


# --- стоп і охолодження ---------------------------------------------------------------------------------------------
def test_stop_cools_for_60_s_then_reserve(world, um, chp):
    start_and_run(world, um, chp)
    cmd(world, um, 2)
    assert ack(world) == (1, 0) and chp.s["state"] == 4 and reg(chp, "ctl/state") == 4
    assert 55 < reg(chp, "ctl/cool_left") <= 60 and reg(chp, "gen/p_kw") == 0
    world.advance(40)
    assert chp.s["state"] == 4 and reg(chp, "safe/qf_closed") == 0
    world.advance(22)
    assert chp.s["state"] == 0 and reg(chp, "eng/rpm") < 100 and not world.flags.get("chp_run")
    cmd(world, um, 2)  # стоп у резерві: уже зупинено
    assert ack(world) == (1, 0)


def test_stop_in_cooling_or_alarm_is_refused(world, um, chp):
    start_and_run(world, um, chp)
    cmd(world, um, 2)
    cmd(world, um, 2)
    assert ack(world) == (2, 12)


def test_stop_during_start_without_cranking_goes_to_reserve(world, um, chp):
    cmd(world, um, 1)
    world.advance(3)
    assert chp.s["state"] == 1
    cmd(world, um, 2)
    assert chp.s["state"] == 0 and ack(world) == (1, 0)


def test_stop_ignored_in_local_mode(world, um, chp):
    start_and_run(world, um, chp)
    world.set_flag("ctl_remote", 0)
    cmd(world, um, 2)
    assert ack(world) == (2, 3) and chp.s["state"] == 2


# --- аварії: AC-27 --------------------------------------------------------------------------------------------------
async def run_scenario(world, chp, um, name, secs=60):
    start_and_run(world, um, chp)
    runner = ScenarioRunner(world)
    run = runner.start(name, {})
    await settle()
    world.advance(secs)
    await settle()
    return runner, run


@pytest.mark.parametrize(
    ("name", "code", "secs"),
    [("chp_overheat", 112, 30), ("chp_hot_return", 113, 40), ("chp_gas_leak", 114, 30), ("chp_fire", 115, 10)],
)
async def test_scenario_raises_alarm_code(world, um, chp, name, code, secs):
    runner, run = await run_scenario(world, chp, um, name, secs)
    assert chp.s["state"] == 3 and reg(chp, "alarm/code") == code
    assert reg(chp, "safe/qf_closed") == 0 and reg(chp, "gas/yv1") == 0 and reg(chp, "gen/p_kw") == 0
    assert reg(chp, "ctl/state") == 3 and not world.flags.get("chp_run")
    await runner.stop(run.id)


async def test_hot_return_reduces_power_before_alarm(world, um, chp):
    start_and_run(world, um, chp)
    runner = ScenarioRunner(world)
    run = runner.start("chp_hot_return", {})
    await settle()
    world.advance(8)
    assert chp.s["state"] == 2 and reg(chp, "ht/cap_pct") < 100 and chp.s["load"] < 0.5 + 1e-9
    assert reg(chp, "ht/t_ret_raw") > 75
    world.advance(40)
    assert chp.s["state"] == 3 and chp.s["alarm"] == 113
    await runner.stop(run.id)


async def test_gas_leak_reaches_20_percent(world, um, chp):
    runner, run = await run_scenario(world, chp, um, "chp_gas_leak", 30)
    assert reg(chp, "safe/lel") >= 20
    await runner.stop(run.id)


async def test_fire_triggers_extinguisher(world, um, chp):
    runner, run = await run_scenario(world, chp, um, "chp_fire", 3.5)
    assert reg(chp, "safe/fire") == 1 and reg(chp, "safe/ext_state") == 1
    world.advance(6)
    assert reg(chp, "safe/ext_state") == 2 and reg(chp, "safe/ext_level") == 0
    await runner.stop(run.id)
    world.advance(1)
    assert reg(chp, "safe/ext_state") == 2  # гасіння відпрацювало, скидання — лише командою
    cmd(world, um, 4)
    assert ack(world) == (1, 0) and reg(chp, "safe/ext_state") == 0 and reg(chp, "safe/ext_level") == 100


async def test_rocof_trip_stops_without_alarm(world, um, chp):
    runner, run = await run_scenario(world, chp, um, "chp_rocof", 3)
    assert chp.s["state"] == 4 and reg(chp, "alarm/trip") == 2 and reg(chp, "alarm/code") == 0
    assert reg(chp, "safe/rocof") == 1 and reg(chp, "safe/rocof_dfdt") == pytest.approx(2.4)
    assert reg(chp, "safe/rocof_dphi") == 14 and not world.flags.get("chp_run")
    world.advance(65)
    assert chp.s["state"] == 0 and reg(chp, "alarm/trip") == 2  # причина ще є
    cmd(world, um, 1)
    assert ack(world) == (2, 5)
    await runner.stop(run.id)
    world.advance(1)
    assert reg(chp, "alarm/trip") == 0
    cmd(world, um, 1)
    assert ack(world) == (1, 0)


async def test_no_permit_trip_and_refusal(world, um, chp):
    runner, run = await run_scenario(world, chp, um, "chp_no_permit", 3)
    assert chp.s["state"] == 4 and reg(chp, "alarm/trip") == 3 and reg(chp, "ctl/permit") == 0
    world.advance(65)
    cmd(world, um, 1)
    assert ack(world) == (2, 1)
    await runner.stop(run.id)
    world.advance(1)
    assert reg(chp, "alarm/trip") == 0 and reg(chp, "ctl/permit") == 1


async def test_no_permit_during_start_cools_down(world, um, chp):
    cmd(world, um, 1)
    world.advance(30)  # прокрутка стартером вже почалась
    assert chp.s["state"] == 1 and chp.s["rpm"] > 50
    runner = ScenarioRunner(world)
    run = runner.start("chp_no_permit", {})
    await settle()
    world.advance(2)
    assert chp.s["state"] == 4 and chp.s["trip"] == 3
    await runner.stop(run.id)


def test_grid_trip_restarts_after_outage(world, um, chp):
    start_and_run(world, um, chp)
    world.set_flag("blackout", {"phase": "outage", "genset": True, "chp_island": False})
    world.advance(2)
    assert chp.s["state"] == 4 and reg(chp, "alarm/trip") == 1 and reg(chp, "safe/grid_ok") == 0
    world.advance(65)
    assert chp.s["state"] == 0
    world.clear_flag("blackout")
    world.advance(2)
    assert chp.s["state"] == 1 and reg(chp, "alarm/trip") == 0
    world.advance(65)
    assert chp.s["state"] == 2


# --- скидання й аварійний стоп --------------------------------------------------------------------------------------
async def test_reset_only_when_cause_removed(world, um, chp):
    runner, run = await run_scenario(world, chp, um, "chp_fire", 5)
    assert chp.s["state"] == 3
    cmd(world, um, 4)
    assert ack(world) == (2, 7) and chp.s["state"] == 3
    await runner.stop(run.id)
    world.advance(1)
    cmd(world, um, 4)
    assert ack(world) == (1, 0) and chp.s["state"] == 0 and reg(chp, "alarm/code") == 0
    assert reg(chp, "safe/estop_loop") == 1 and reg(chp, "safe/fire") == 0


def test_reset_refused_outside_alarm(world, um, chp):
    cmd(world, um, 4)
    assert ack(world) == (2, 12)


def test_estop_gives_alarm_116_and_reset_closes_loop(world, um, chp):
    start_and_run(world, um, chp)
    cmd(world, um, 3)
    assert ack(world) == (1, 0) and chp.s["state"] == 3
    assert reg(chp, "alarm/code") == 116 and reg(chp, "safe/estop_loop") == 0 and reg(chp, "safe/qf_closed") == 0
    cmd(world, um, 3)
    assert ack(world) == (2, 12)  # уже в аварії
    cmd(world, um, 1)
    assert ack(world) == (2, 12)
    cmd(world, um, 4)
    assert ack(world) == (1, 0) and chp.s["state"] == 0 and reg(chp, "safe/estop_loop") == 1
    cmd(world, um, 1)
    assert ack(world) == (1, 0)


def test_estop_works_from_reserve_and_in_local_mode(world, um, chp):
    world.set_flag("ctl_remote", 0)
    cmd(world, um, 3)
    assert ack(world) == (1, 0) and reg(chp, "alarm/code") == 116 and chp.s["state"] == 3
    cmd(world, um, 4)
    assert ack(world) == (2, 3)  # скидання — лише в дистанційному режимі


def test_unknown_command_value_is_rejected_by_protocol(world, um, chp):
    from iot_sim.protocols.modbus_maps import ModbusError

    with pytest.raises(ModbusError) as e:
        um.write("h", BY["chp/ctl/cmd"]["pdu"], [7])
    assert e.value.code == 3


# --- режими й уставки -----------------------------------------------------------------------------------------------
def test_default_mode_is_legacy_profile(world, um, chp):
    start_and_run(world, um, chp)
    assert reg(chp, "ctl/mode") == 4 and chp.s["load"] == 0.5
    assert world.signals["infra/chp/heat_kw"].value == 497 and world.signals["infra/chp/gas_m3h"].value == 109
    assert reg(chp, "ht/q_total") == 497 and reg(chp, "gas/flow") == 109
    assert reg(chp, "gen/p_kw") == pytest.approx(400, abs=4.1)
    assert reg(chp, "ctl/target_pct") == 50


def test_manual_mode_follows_setpoint_with_rate_limit(world, um, chp):
    start_and_run(world, um, chp)
    um.write("h", BY["chp/ctl/mode"]["pdu"], [3])
    um.write("h", BY["chp/ctl/sp_pct"]["pdu"], [100])
    world.advance(1)
    assert chp.s["load"] == pytest.approx(0.54, abs=0.011)  # не швидше 0,04·P_nom за секунду
    world.advance(20)
    assert chp.s["load"] == pytest.approx(1.0) and reg(chp, "gen/load_pct") == pytest.approx(100)
    assert reg(chp, "gen/p_kw") == pytest.approx(800, abs=4.1)
    assert reg(chp, "ctl/target_pct") == 100
    um.write("h", BY["chp/ctl/sp_pct"]["pdu"], [60])
    world.advance(20)
    assert chp.s["load"] == pytest.approx(0.6) and reg(chp, "gen/p_kw") == pytest.approx(480, abs=4.1)
    assert 70 < reg(chp, "ht/q_total") < 497 + 80


@pytest.mark.parametrize(("mode", "hour_target"), [(1, 0.88), (2, 0.60), (0, None)])
def test_other_modes_have_their_targets(world, um, chp, mode, hour_target):
    start_and_run(world, um, chp)  # 10:30 Київ: пік 08–11 → режим «піки» дає 1,0
    um.write("h", BY["chp/ctl/mode"]["pdu"], [mode])
    world.advance(1)
    target = reg(chp, "ctl/target_pct") / 100
    if mode == 2:
        assert target == pytest.approx(1.0)
    elif mode == 1:
        assert target == pytest.approx(hour_target)
    else:
        assert 0.5 <= target <= 1.0 and reg(chp, "ctl/heat_demand") == pytest.approx(694.5, abs=60)


def test_cos_phi_setpoint_changes_reactive_power(world, um, chp):
    start_and_run(world, um, chp)
    assert reg(chp, "gen/cos") == pytest.approx(0.98, abs=0.005)
    q1 = reg(chp, "gen/q_kvar")
    um.write("h", BY["chp/ctl/cos_set"]["pdu"], [90])
    world.advance(2)
    assert reg(chp, "gen/cos") == pytest.approx(0.90, abs=0.005) and reg(chp, "gen/q_kvar") > q1 * 2


def test_heat_direction_and_bypass_flap(world, um, chp):
    start_and_run(world, um, chp)
    q = reg(chp, "ht/q_phe") + reg(chp, "ht/q_exh")
    um.write("h", BY["chp/ctl/heat_dir"]["pdu"], [1])
    world.advance(3)
    assert reg(chp, "ht/q_boiler") == pytest.approx(q, rel=0.02) and reg(chp, "ht/q_cooler") == 0
    um.write("h", BY["chp/ctl/heat_dir"]["pdu"], [2])
    world.advance(3)
    assert reg(chp, "ht/q_cooler") == pytest.approx(q, rel=0.02) and reg(chp, "ht/q_boiler") == 0
    assert reg(chp, "ht/cooler_fan") > 12
    um.write("h", BY["chp/ctl/bypass_mode"]["pdu"], [2])
    world.advance(10)
    assert reg(chp, "exh/bypass_pct") > 95 and reg(chp, "ht/q_exh") < 0.1 * reg(chp, "ht/q_phe")
    assert reg(chp, "ht/q_total") == pytest.approx(0.55 * 497, rel=0.03, abs=15) or reg(chp, "ht/q_total") < 497


# --- сталі показання, лічильники, знімок ----------------------------------------------------------------------------
def test_running_values_are_plausible(world, um, chp):
    start_and_run(world, um, chp)
    hours = world.signals["infra/chp/hours"].value
    world.advance(30)
    assert reg(chp, "eng/rpm") == pytest.approx(1500, abs=5) and reg(chp, "gen/f_hz") == pytest.approx(50, abs=0.1)
    assert reg(chp, "gen/u_v") == pytest.approx(400, abs=3) and 80 < reg(chp, "eng/t_jacket_out") < 95
    assert 1.5 < reg(chp, "gas/p_in") < 2.7 and reg(chp, "oil/level") > 60 and reg(chp, "air/louver") > 90
    assert reg(chp, "em/kwh") > 10912450 and reg(chp, "gas/total") > 3940620 and reg(chp, "gas/day") > 0
    assert reg(chp, "em/runh_day") > 0 and reg(chp, "eng/starter_on") == 0 and reg(chp, "ht/pump_ht_run") == 1
    assert world.signals["infra/chp/hours"].value > hours  # legacy-сигнал росте як раніше


def test_gas_pressure_drop_raises_alarm_111(world, um, chp):
    start_and_run(world, um, chp)
    world.set_flag("gas_bar", 1.15)
    world.advance(5)
    assert chp.s["state"] == 3 and reg(chp, "alarm/code") == 111 and reg(chp, "gas/psl") == 1


def test_snapshot_roundtrip_in_the_middle_of_start(world, um, chp):
    cmd(world, um, 1)
    world.advance(25)
    snap = chp.get_state()
    chp.set_state(snap)
    assert chp.get_state() == snap
    import json

    json.dumps(snap)  # знімок серіалізується
    world.advance(40)
    assert chp.s["state"] == 2


def test_fault_freezes_model_and_clear_resumes(world, um, chp):
    start_and_run(world, um, chp)
    world.fault("CHP")
    world.advance(2)
    assert world.signals["infra/chp/state"].value == 3 and world.signals["infra/totals/chp_kw"].value == 0
    world.clear("CHP")
    world.advance(2)
    assert world.signals["infra/chp/state"].value == 2 and chp.s["state"] == 2


def test_reset_models_returns_standby(world, um, chp):
    start_and_run(world, um, chp)
    world.reset_models()
    assert chp.s["state"] == 0 and chp.s["starts"] == 612
