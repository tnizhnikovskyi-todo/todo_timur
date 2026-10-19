"""W3 §8.1, AC-55/AC-56 (вода і котельня): ``gas_m3h`` котельні, підживлення ``boiler_m3_total``, прапор/сценарій ``water_leak``."""

import asyncio
from datetime import datetime

import pytest
from iot_sim.core.scenarios import ScenarioRunner
from iot_sim.models.water import BOILER_M3_START
from iot_sim.protocols.modbus_maps import build_all

BIG = 1e9
STATE = "equipment/BOILER/state"
TOTAL = "infra/water/boiler_m3_total"
FLOW = "infra/water/boiler_flow_m3h"
MAIN_FLOW = "infra/water/flow_m3h"
SHIFT_10, NIGHT_2330, NIGHT_0600, DAY_0630, EVENING_2259 = (
    datetime(2026, 10, 12, 10, 30),
    datetime(2026, 10, 12, 23, 30),
    datetime(2026, 10, 13, 6, 0),
    datetime(2026, 10, 13, 6, 30),
    datetime(2026, 10, 12, 22, 59),
)


def val(world, code: str):
    return world.signals[code].value


def water(world):
    return world.devices["WATER"].model


def idle_world(world, *, state: int, at: datetime = SHIFT_10) -> None:
    """Фарбувальні РЦ стоять, котельня у стані ``state`` (1 standby, 2 K1, 3 K1+K2, 4 збій), час ``at``."""
    world.clock.set(at)
    for code in ("SPRAY-1", "AUTOSPRAY-1"):
        world.workcenters[code] = {"state": "READY"}
    world.force(STATE, state, BIG)


# --- котельня: gas_m3h ------------------------------------------------------------------------------
def test_boiler_gas_390kw_is_40_6(world):
    """AC-55: ``heat_kw = 390`` → ``gas_m3h = 40,6`` (η 0,914, 10,5 кВт·год/м³)."""
    for code in list(world.signals):
        if code.startswith("ventilation/units/") and code.endswith("/heat_kw"):
            world.force(code, 0.0, BIG)
    world.force("ventilation/units/RV-01/heat_kw", 390.0, BIG)
    world.force("infra/chp/heat_kw", 0.0, BIG)
    world.step(10)
    assert val(world, "equipment/BOILER/heat_kw") == pytest.approx(390.0)
    assert val(world, "equipment/BOILER/gas_m3h") == pytest.approx(390.0 / (0.914 * 10.5))
    assert val(world, "equipment/BOILER/gas_m3h") == pytest.approx(40.6, abs=0.05)


def test_boiler_gas_zero_without_heat_and_in_fault(world):
    for code in list(world.signals):
        if code.startswith("ventilation/units/") and code.endswith("/heat_kw"):
            world.force(code, 0.0, BIG)
    world.force("infra/chp/heat_kw", 0.0, BIG)
    world.step(10)
    assert val(world, "equipment/BOILER/gas_m3h") == 0.0
    world.force("ventilation/units/RV-01/heat_kw", 600.0, BIG)
    world.step(10)
    assert val(world, "equipment/BOILER/gas_m3h") > 0.0
    world.fault("BOILER", "generic")  # збій: heat_kw = 0 → газ 0
    world.step(10)
    assert val(world, "equipment/BOILER/gas_m3h") == 0.0


def test_boiler_gas_does_not_touch_silo(world):
    """D-35: ``gas_m3h`` не впливає на ``silo_fill`` (спалювання брикетів те саме)."""
    world.force("ventilation/units/RV-01/heat_kw", 300.0, BIG)
    world.force("infra/chp/heat_kw", 0.0, BIG)
    world.signals["equipment/BOILER/silo_fill"].value = 62.0
    world.advance(60)
    assert 61.0 < val(world, "equipment/BOILER/silo_fill") < 62.0


# --- підживлення котельні -----------------------------------------------------------------------------
@pytest.mark.parametrize(("state", "rate"), [(1, 0.0125), (2, 0.0125), (3, 0.025), (4, 0.0125)])
def test_refill_rate_by_boilers(world, state, rate):
    """AC-55: ``0,0125·max(1, boilers_on)`` м³/год (``boilers_on = state − 1``; збій — 0 котлів)."""
    idle_world(world, state=state)
    world.step(10)
    assert water(world).boiler_refill() == pytest.approx(rate)
    assert val(world, FLOW) == pytest.approx(rate)


def test_boiler_counter_grows_with_quantum(world):
    """8 год · 0,0125 = 0,1 м³ (квант 0,01, залишок переноситься)."""
    idle_world(world, state=2, at=NIGHT_2330)
    world.step(0)
    start = val(world, TOTAL)
    assert start == BOILER_M3_START
    for _ in range(480):  # 8 год, крок 60 с
        world.advance(60)
    grown = val(world, TOTAL) - start
    assert grown == pytest.approx(0.1, abs=0.011)
    assert round(grown * 100) == pytest.approx(grown * 100, abs=1e-6)  # кратне 0,01


def test_boiler_counter_two_boilers_doubles(world):
    idle_world(world, state=3)
    world.step(0)
    start = val(world, TOTAL)
    for _ in range(240):  # 4 год
        world.advance(60)
    assert val(world, TOTAL) - start == pytest.approx(0.1, abs=0.011)  # 0,025 · 4


def test_main_flow_includes_refill(world):
    """Основна витрата ``q`` збільшується на підживлення: 2,1 + 0,0125 у зміні, 0,3 + 0,0125 поза нею."""
    idle_world(world, state=2)
    world.advance(600)
    assert val(world, MAIN_FLOW) == pytest.approx(2.1 + 0.0125)
    idle_world(world, state=3, at=datetime(2026, 10, 12, 20, 0))
    world.advance(600)
    assert val(world, MAIN_FLOW) == pytest.approx(0.3 + 0.025)


def test_boiler_flow_is_moving_average(world):
    idle_world(world, state=3)
    world.advance(600)
    assert val(world, FLOW) == pytest.approx(0.025)
    world.force(STATE, 1, BIG)
    world.advance(150)  # половина вікна 5 хв: середнє між 0,025 і 0,0125
    assert 0.0125 < val(world, FLOW) < 0.025


def test_state_roundtrip(world):
    wm = water(world)
    idle_world(world, state=2)
    world.advance(1200)
    state = wm.get_state()
    assert state["pulses"] > 0 and "b_pulses" in state
    wm.set_state({})
    assert (wm.pulses, wm.b_pulses) == (0, 0)
    wm.set_state(state)
    assert wm.get_state() == state


def test_modbus_u84_boiler_counter(world):
    """Адреси W3 §5.4: u84 HR 18–19 (DI9) — ``boiler_m3_total`` (u32, молодше слово першим, ×0,01)."""
    world.force(TOTAL, 1205.5, BIG)
    lo, hi = build_all(world)[84].read("h", 18, 2)
    assert (hi << 16 | lo) == 120550


# --- water_leak ---------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("at", "leaking"),
    [(SHIFT_10, False), (EVENING_2259, False), (NIGHT_2330, True), (NIGHT_0600, True), (DAY_0630, False)],
)
def test_water_leak_window_2300_0630(world, at, leaking):
    """AC-56: ``water_leak`` — нічний витрата води +0,5 м³/год при ``23:00 ≤ t < 06:30`` (число або словник)."""
    idle_world(world, state=2, at=at)
    base = water(world).flow()
    world.set_flag("water_leak", 0.5)
    assert water(world).flow() - base == pytest.approx(0.5 if leaking else 0.0)
    world.set_flag("water_leak", {"extra_m3h": 0.25})
    assert water(world).flow() - base == pytest.approx(0.25 if leaking else 0.0)
    world.set_flag("water_leak", "x")
    assert water(world).flow() == pytest.approx(base)


def test_water_leak_raises_night_meter(world):
    idle_world(world, state=2, at=NIGHT_2330)
    world.advance(600)
    base = val(world, MAIN_FLOW)
    world.set_flag("water_leak", 0.5)
    world.advance(600)
    assert val(world, MAIN_FLOW) - base == pytest.approx(0.5)


async def settle(n=6):
    for _ in range(n):
        await asyncio.sleep(0)


async def test_water_leak_scenario(world):
    """AC-56: ``water_leak`` (за замовчуванням +0,5 м³/год) — нічна витрата води; зупинка знімає прапор."""
    idle_world(world, state=2, at=NIGHT_2330)
    world.step(10)
    base = val(world, MAIN_FLOW)
    runner = ScenarioRunner(world)
    run = runner.start("water_leak", {}, run_ref="odoo-water")
    await settle()
    world.advance(600)
    await settle()
    assert world.flags["water_leak"] == 0.5
    assert val(world, MAIN_FLOW) - base == pytest.approx(0.5)
    run = await runner.stop(run.id)
    assert run.error is None and "water_leak" not in world.flags
