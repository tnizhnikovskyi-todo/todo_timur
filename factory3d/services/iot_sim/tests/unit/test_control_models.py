"""W2 §8.2 (AC-270…AC-274): реакції моделей на вікно керування — BESS, QS/PFC, КГУ, повітря, СЕС, скидання, сценарії."""
import asyncio
import math

import pytest

from iot_sim.core.scenarios import ScenarioConflict, ScenarioParamsError, ScenarioRunner
from iot_sim.models.meter import (
    SECTIONS,
    base_load,
    ctl,
    extra_load,
    shed_factor,
    total_load,
)
from iot_sim.protocols.modbus_maps import build_all

BIG = 1e9
SOC = "infra/totals/bess_soc"
BESS_KW = "infra/totals/bess_kw"
GRID, EXPORT = "infra/totals/grid_kw", "infra/totals/export_kw"
PV, CHP_KW, CHP_STATE = "infra/totals/pv_now", "infra/totals/chp_kw", "infra/chp/state"
LOCK = "energy_control/ats/parallel_lock"


def val(world, code):
    return world.signals[code].value


def warm_up(world):
    """Прогрів: споживачі виходять на робочі значення (перші тіки світу)."""
    for _ in range(3):
        world.step(1)


def settle_loads(world):
    """Фіксує джерела: СЕС 0, споживачі не змінюються між тіками (для точних порівнянь)."""
    world.force(PV, 0.0, BIG)
    warm_up(world)


def bess_forced(world, mode, setpoint=50.0, until=0.0, valid=600.0):
    world.set_flag("bess_mode", mode)
    world.set_flag("bess_setpoint_kw", setpoint)
    world.set_flag("bess_until_soc", until)
    world.set_flag("bess_valid_s", valid)
    world.set_flag("bess_valid_left", valid)


def uctl(world):
    return build_all(world)[73]


def set_section(world, section, p_kw, cos):
    lines = SECTIONS[section]
    for line in lines:
        world.force(f"energy/lines/{line}/p_now", p_kw / len(lines), BIG)
        world.force(f"energy/lines/{line}/cos_phi", cos, BIG)


# --- BESS (AC-270) -----------------------------------------------------------------------------
def test_bess_auto_idle_flag(world):
    world.force(PV, 3000.0, BIG)  # надлишок → у авто заряд
    world.step(1)
    assert val(world, BESS_KW) > 0
    world.set_flag("bess_auto_idle", True)
    world.step(1)
    assert val(world, BESS_KW) == 0.0


def test_bess_forced_charge_until_soc(world):
    settle_loads(world)
    world.signals[SOC].value = 94.0
    bess_forced(world, 1, setpoint=50.0, until=95.0)
    world.step(1)
    assert val(world, BESS_KW) == 50.0 and val(world, "infra/bess/state") == 2
    assert val(world, SOC) == pytest.approx(94.0 + 50.0 / 3600.0 / 387.0 * 100.0)
    world.signals[SOC].value = 95.0
    world.step(1)
    assert val(world, BESS_KW) == 0.0  # заряд зупинено на until_soc
    world.set_flag("bess_until_soc", 0.0)  # без межі — до 100 %
    world.step(1)
    assert val(world, BESS_KW) == 50.0
    world.signals[SOC].value = 100.0
    world.step(1)
    assert val(world, BESS_KW) == 0.0


def test_bess_forced_charge_comes_from_grid_and_caps_at_200(world):
    settle_loads(world)  # СЕС 0: заряд забезпечує мережа
    bess_forced(world, 1, setpoint=500.0)
    world.step(1)
    assert val(world, BESS_KW) == 200.0  # min(setpoint, 200)
    assert val(world, GRID) - val(world, EXPORT) == pytest.approx(total_load(world) + 200.0)
    assert val(world, EXPORT) == 0.0


def test_bess_forced_discharge_floor(world):
    settle_loads(world)
    world.signals[SOC].value = 60.0
    bess_forced(world, 2, setpoint=80.0, until=40.0)
    world.step(1)
    assert val(world, BESS_KW) == -80.0
    assert val(world, GRID) == pytest.approx(max(0.0, total_load(world) - 80.0))
    world.signals[SOC].value = 40.0  # floor = max(until, reserve 30) = 40
    world.step(1)
    assert val(world, BESS_KW) == 0.0
    world.set_flag("bess_until_soc", 0.0)  # until 0 → floor = reserve 30
    world.signals[SOC].value = 31.0
    world.step(1)
    assert val(world, BESS_KW) == -80.0
    world.signals[SOC].value = 30.0
    world.step(1)
    assert val(world, BESS_KW) == 0.0


def test_bess_hold_mode_zero_kw(world):
    world.force(PV, 3000.0, BIG)
    bess_forced(world, 3)
    world.step(1)
    assert val(world, BESS_KW) == 0.0
    assert val(world, EXPORT) == pytest.approx(3000.0 - total_load(world))


def test_bess_watchdog_returns_auto_by_world_time(world):
    world.force(PV, 3000.0, BIG)
    bess_forced(world, 3, valid=30.0)
    world.advance(29)
    assert ctl(world, "bess_mode") == 3 and 0 < ctl(world, "bess_valid_left") <= 1.0
    assert val(world, BESS_KW) == 0.0
    world.advance(2)
    assert ctl(world, "bess_mode") == 0 and ctl(world, "bess_valid_left") == 0.0
    world.step(1)
    assert val(world, BESS_KW) > 0  # знову авто: заряд з надлишку СЕС
    assert [e.message for e in world.events.since(0, kind="info")[0] if "valid_s" in e.message]


def test_bess_mode_ack_refusals_via_registers(world):
    world.step(1)
    um = uctl(world)
    world.signals[SOC].value = 30.0
    um.write("h", 220, [2])  # розряд при SOC ≤ reserve (30) → відмова
    assert (ctl(world, "bess_mode"), um.read("h", 226, 1)) == (0, [2])
    world.signals[SOC].value = 50.0
    um.write("h", 220, [2])
    assert (ctl(world, "bess_mode"), um.read("h", 226, 1)) == (2, [0])
    um.write("h", 220, [0])
    world.force(BESS_KW, 400.0, BIG)  # температура 25 + 0,05·400 = 45 °C > 40
    um.write("h", 220, [2])
    assert (ctl(world, "bess_mode"), um.read("h", 226, 1)) == (0, [2])
    um.write("h", 220, [1])  # заряд без обмежень за SOC/температурою
    assert ctl(world, "bess_mode") == 1 and um.read("h", 226, 1) == [0]


def test_bess_temperature_formula(world):
    settle_loads(world)
    um = uctl(world)
    bess_forced(world, 1, setpoint=100.0)
    world.step(1)
    assert val(world, "energy_control/bess/temp_c") == pytest.approx(25.0 + 0.05 * 100.0)
    assert um.read("h", 227, 1) == [300]
    world.signals[SOC].value = 80.0
    bess_forced(world, 2, setpoint=200.0)
    world.step(1)
    assert um.read("h", 227, 1) == [350]  # |P| = 200 кВт


def test_bess_remaining_s_register(world):
    settle_loads(world)
    um = uctl(world)
    um.write("h", 223, [100])
    um.write("h", 220, [1])
    um.write("h", 221, [10])
    world.advance(30)
    assert um.read("h", 224, 1) == [70]
    um.write("h", 220, [0])
    assert um.read("h", 224, 1) == [0]


# --- QS і PFC (AC-271) -------------------------------------------------------------------------
def test_qs_close_requires_lock_and_no_island(world):
    world.step(1)
    q1, q2 = "energy/cells/Q1/p_now", "energy/cells/Q2/p_now"
    um = uctl(world)
    assert val(world, "energy/cells/QS/state") == 0 and val(world, q1) != pytest.approx(val(world, q2))
    um.write("h", 200, [2])
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 1 and um.read("h", 201, 1) == [1] and um.read("h", 200, 1) == [0]
    world.step(1)  # контролер замикає QS після вводів: вирівнювання — з наступного тіку
    assert val(world, q1) == pytest.approx(val(world, q2))  # вводи Q1 = Q2 = (P1 + P2) / 2
    um.write("h", 200, [1])  # розімкнути — завжди
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 0 and um.read("h", 201, 1) == [1]
    world.force(LOCK, 0, BIG)  # блокування АВР знято → замкнути не можна
    um.write("h", 200, [2])
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 0 and um.read("h", 201, 1) == [2]
    world.force(LOCK, 1, BIG)
    world.set_flag("blackout", {"phase": "outage", "genset": True, "chp_island": False})
    um.write("h", 200, [2])
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 0 and um.read("h", 201, 1) == [2]  # острів → відмова


def test_qs_sums_stay_consistent_when_closed(world):
    world.step(1)
    world.set_flag("qs_closed", True)
    world.step(1)
    total = val(world, "energy/cells/Q1/p_now") + val(world, "energy/cells/Q2/p_now")
    assert total == pytest.approx(val(world, GRID) - val(world, EXPORT))


def test_qs_scenario_param_still_closes(world):
    world.set_flag("swb", {"section": 2, "step": 0, "qs_closed": True})
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 1


def steps_on(world, section):
    return val(world, f"energy/cells/PFC-{section}/steps_on")


def test_pfc_mode_and_cos_target_flags(world):
    set_section(world, 2, 400.0, 0.9)
    set_section(world, 1, 0.0, 0.9)
    um = uctl(world)
    world.step(1)
    assert steps_on(world, 2) == 2
    um.write("h", 211, [99])  # ціль 0,99 → потрібно більше ступенів
    world.step(1)
    need = math.ceil((400.0 * math.tan(math.acos(0.9)) - 400.0 * math.tan(math.acos(0.99))) / 35.0 - 1e-9)
    assert steps_on(world, 2) == need > 2
    um.write("h", 210, [0])  # ручний режим: ступені вимкнені
    world.step(1)
    assert (steps_on(world, 1), steps_on(world, 2), val(world, "energy/cells/PFC-2/q_kvar")) == (0, 0, 0)
    um.write("h", 210, [1])
    world.step(1)
    assert steps_on(world, 2) == need


# --- КГУ (AC-272) ------------------------------------------------------------------------------
def test_chp_start_stop_commands(world):
    world.step(1)
    um = uctl(world)
    assert val(world, CHP_STATE) == 0
    world.set_flag("chp_start_s", 10.0)  # D-33: тривалість запуску — прапор
    um.write("h", 230, [1])
    world.step(1)
    assert ctl(world, "chp_run") is True and um.read("h", 231, 1) == [1] and val(world, CHP_STATE) == 1
    world.advance(5)
    assert val(world, CHP_STATE) == 1
    world.advance(7)
    assert val(world, CHP_STATE) == 2 and val(world, CHP_KW) > 0
    um.write("h", 230, [2])
    world.step(1)
    assert ctl(world, "chp_run") is False and val(world, CHP_STATE) == 4  # охолодження
    world.advance(61)
    assert val(world, CHP_STATE) == 0


def test_chp_default_start_takes_60_s(world):
    world.step(1)
    world.set_flag("chp_cmd", 1)
    world.advance(30)
    assert val(world, CHP_STATE) == 1
    world.advance(40)
    assert val(world, CHP_STATE) == 2


def test_chp_refused_without_gas_or_permit(world):
    world.step(1)
    um = uctl(world)
    world.set_flag("gas_bar", 0.80)
    assert um.read("h", 233, 1) == [80]
    um.write("h", 230, [1])
    world.step(1)
    assert um.read("h", 231, 1) == [2] and not ctl(world, "chp_run") and val(world, CHP_STATE) == 0
    world.set_flag("gas_bar", 2.10)
    world.set_flag("chp_permit", 0)
    assert um.read("h", 232, 1) == [0]
    um.write("h", 230, [1])
    world.step(1)
    assert um.read("h", 231, 1) == [2] and not ctl(world, "chp_run")
    world.set_flag("chp_permit", 1)
    um.write("h", 230, [1])
    world.step(1)
    assert um.read("h", 231, 1) == [1] and ctl(world, "chp_run")
    assert val(world, "energy_control/chp/ack") == 1  # віддзеркалено у сигнал


# --- повітря, СЕС, скидання (AC-272, AC-273) ---------------------------------------------------
def test_air_setpoint_sets_pressure(world):
    um = uctl(world)
    comp = world.devices["COMPRESSOR"].model
    pressure = "equipment/COMPRESSOR/pressure_bar"
    world.advance(1500)
    assert comp.nominal == pytest.approx(6.81) and val(world, pressure) == pytest.approx(6.81, abs=0.25)  # W0 збережено
    um.write("h", 240, [650])
    world.advance(1500)
    assert comp.nominal == pytest.approx(6.31) and val(world, pressure) == pytest.approx(6.31, abs=0.25)
    um.write("h", 240, [700])
    world.advance(1500)
    assert comp.nominal == pytest.approx(6.81) and val(world, pressure) == pytest.approx(6.81, abs=0.25)
    assert um.read("h", 241, 1) == [620]


def test_pv_limit_scales_inverters_and_status(world):
    warm_up(world)
    full = val(world, PV)
    assert full > 50.0
    world.set_flag("pv_limit_pct", 50.0)
    world.set_flag("shed_valid_left", 600.0)
    world.step(1)
    assert val(world, PV) == pytest.approx(full * 0.5, rel=1e-3)
    for n in range(1, 9):
        assert val(world, f"infra/pv/PV-INV-{n}/p_kw") == pytest.approx(full * 0.5 / 8, rel=1e-3)
        assert val(world, f"infra/pv/PV-INV-{n}/status") == 0x0200  # інвертор працює, лише обмежений
    world.set_flag("pv_limit_pct", 0.0)
    world.step(1)
    assert val(world, PV) == 0.0 and val(world, "infra/pv/PV-INV-1/status") == 0x0200


def test_shed_limit_reduces_consumer_power(world):
    world.force("energy/consumers/CHARGING/p_now", 40.0, BIG)
    warm_up(world)
    full = total_load(world)
    world.set_flag("shed_limit", {"CHARGING": 25.0})
    world.set_flag("shed_valid_left", 600.0)
    assert shed_factor(world, "CHARGING") == 0.25 and shed_factor(world, "LP-1") == 1.0
    world.step(1)
    assert total_load(world) == pytest.approx(full - 30.0, abs=0.5)  # шум інших споживачів між тіками
    line = val(world, "energy/lines/QF-6/p_now") if "energy/lines/QF-6/p_now" in world.signals else None
    assert line is None or line >= 0
    world.set_flag("shed_limit", {"CHARGING": 0.0})
    world.step(1)
    assert total_load(world) == pytest.approx(full - 40.0, abs=0.5)


def test_shed_watchdog_restores_limits_and_pv(world):
    um = uctl(world)
    um.write("h", 270, [30])
    um.write("h", 263, [0])
    um.write("h", 250, [40])
    world.advance(25)
    assert um.read("h", 263, 1) == [0] and um.read("h", 250, 1) == [40]
    um.write("h", 270, [30])  # перезапис продовжує таймер
    world.advance(25)
    assert um.read("h", 263, 1) == [0]
    world.advance(10)
    assert (um.read("h", 263, 1), um.read("h", 250, 1)) == ([100], [100])
    assert "shed_limit" not in world.flags and ctl(world, "pv_limit_pct") == 100.0


def test_limit_without_watchdog_is_not_kept(world):
    um = uctl(world)
    um.write("h", 262, [0])  # valid_s не задано → контролер не тримає обмеження
    world.step(1)
    assert um.read("h", 262, 1) == [100]


# --- сценарії (AC-274) -------------------------------------------------------------------------
async def settle(n=6):
    for _ in range(n):
        await asyncio.sleep(0)


async def test_scenario_peak_load(world):
    runner = ScenarioRunner(world)
    world.set_flag("bess_shave_kw", BIG)  # без піку-шейвінгу BESS у авто
    settle_loads(world)
    base = val(world, GRID)
    assert base == pytest.approx(base_load(world))
    run = runner.start("peak_load", {"extra_kw": 200, "duration_s": 600})
    await settle()
    assert world.flags["extra_load_kw"] == 200
    world.step(1)
    assert extra_load(world) == 200 and val(world, GRID) == pytest.approx(base_load(world) + 200.0)
    assert val(world, "energy/cells/Q1/p_now") + val(world, "energy/cells/Q2/p_now") == pytest.approx(val(world, GRID))
    world.flags["extra_load_kw"] = -1e6  # не нижче −load
    assert total_load(world) == 0.0
    run = await runner.stop(run.id)
    assert run.error is None and "extra_load_kw" not in world.flags
    world.step(1)
    assert val(world, GRID) == pytest.approx(base_load(world))


async def test_scenario_export_demo(world):
    runner = ScenarioRunner(world)
    world.force(PV, 3000.0, BIG)
    world.step(1)
    run = runner.start("export_demo", {"export_kw": 26, "duration_s": 600})
    await settle()
    for _ in range(3):
        world.step(1)
        assert val(world, EXPORT) == pytest.approx(26.0) and val(world, GRID) == 0.0
        assert val(world, BESS_KW) == 0.0  # BESS авто, утримання 0 кВт
        assert val(world, "energy/cells/Q1/p_now") + val(world, "energy/cells/Q2/p_now") == pytest.approx(-26.0)
    await runner.stop(run.id)
    assert world.flags == {} or "export_target_kw" not in world.flags
    world.step(1)
    assert val(world, BESS_KW) > 0  # авто: надлишок знову заряджає BESS


async def test_scenario_export_demo_gen_below_target_does_not_force_load(world):
    runner = ScenarioRunner(world)
    world.force(PV, 10.0, BIG)
    world.set_flag("bess_shave_kw", BIG)
    runner.start("export_demo", {"export_kw": 26})
    await settle()
    world.step(1)
    assert extra_load(world) == 0.0 and val(world, EXPORT) == pytest.approx(max(0.0, 10.0 - total_load(world)))


async def test_scenarios_ctl_local_and_chp_no_gas(world):
    runner = ScenarioRunner(world)
    um = uctl(world)
    local = runner.start("ctl_local", {})
    gas = runner.start("chp_no_gas", {})
    await settle()
    world.step(1)
    assert um.read("h", 291, 1) == [0] and um.read("h", 233, 1) == [80]
    um.write("h", 230, [1])
    world.step(1)
    assert um.read("h", 231, 1) == [2] and not ctl(world, "chp_run")
    await runner.stop(local.id)
    await runner.stop(gas.id)
    assert world.flags.get("ctl_remote", 1) == 1 and world.flags.get("gas_bar", 2.1) == 2.1
    assert (um.read("h", 291, 1), um.read("h", 233, 1)) == ([1], [210])


async def test_new_scenarios_params_and_conflicts(world):
    runner = ScenarioRunner(world)
    for name, bad in (("peak_load", {"extra_kw": 5000}), ("export_demo", {"export_kw": -1}),
                      ("chp_no_gas", {"gas_bar": 2.0}), ("ctl_local", {"x": 1})):
        with pytest.raises(ScenarioParamsError):
            runner.start(name, bad)
    runner.start("peak_load", {})
    with pytest.raises(ScenarioConflict):
        runner.start("export_demo", {})
    runner.start("blackout", {})  # енергетичний тег не конфліктує з навантаженням
    await runner.stop_all()


def test_reset_flags_cover_all_defaults(world):
    """R-59 п. 3: після очищення прапорів моделі повертаються до значень за замовчуванням."""
    world.step(1)
    bess_forced(world, 1)
    world.set_flag("chp_run", True)
    world.set_flag("qs_closed", True)
    world.set_flag("shed_limit", {"CHARGING": 0.0})
    world.set_flag("pv_limit_pct", 10.0)
    world.flags.clear()  # як POST /sim/v1/reset
    assert [ctl(world, n) for n in ("bess_mode", "chp_run", "qs_closed", "pv_limit_pct", "ctl_remote", "pfc_mode")] == [
        0, False, False, 100.0, 1, 1]
    assert ctl(world, "air_setpoint_bar") == 7.0 and ctl(world, "pfc_cos_target") is None
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 0 and val(world, "energy_control/pfc/cos_target") == 0.95
