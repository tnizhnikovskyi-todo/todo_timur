"""W3 §8.1, AC-55 (газ): ``GAS-MAIN`` = BOILER + КГУ + сушарка + їдальня, лічильник, прапор ``gas_extra``, сценарій
``gas_overuse``."""

import asyncio
from datetime import datetime

import pytest
from iot_sim.core.scenarios import ScenarioRunner
from iot_sim.models.gas import M3_START
from iot_sim.protocols.modbus_maps import build_all

BIG = 1e9
BOILER_GAS = "equipment/BOILER/gas_m3h"
CHP_GAS = "infra/chp/gas_m3h"
FLOW = "infra/gas/flow_m3h"
TOTAL = "infra/gas/m3_total"
MONDAY_10, MONDAY_20, SATURDAY_10 = (
    datetime(2026, 10, 12, 10, 30),
    datetime(2026, 10, 12, 20, 0),
    datetime(2026, 10, 17, 10, 30),
)


def val(world, code: str):
    return world.signals[code].value


def branches(world, *, boiler: float, chp: float = 0.0, dry: bool = False, at: datetime = MONDAY_10) -> None:
    """Фіксує гілки газу: витрата котельні/КГУ, стан сушарки, час (будній день/вихідний)."""
    world.clock.set(at)
    world.force(BOILER_GAS, boiler, BIG)
    world.force(CHP_GAS, chp, BIG)
    world.workcenters["DRY-1"] = {"state": "WORKING" if dry else "READY"}


def test_boiler_gas_from_heat(world):
    """AC-55: ``heat_kw = 390`` → ``gas_m3h = 390 / (0,914 · 10,5) = 40,6``; ``heat_kw = 0`` → 0."""
    for code in list(world.signals):
        if code.startswith("ventilation/units/") and code.endswith("/heat_kw"):
            world.force(code, 0.0, BIG)
    world.force("ventilation/units/RV-01/heat_kw", 390.0, BIG)
    world.force("infra/chp/heat_kw", 0.0, BIG)
    world.step(10)
    assert val(world, "equipment/BOILER/heat_kw") == pytest.approx(390.0)
    assert val(world, BOILER_GAS) == pytest.approx(40.6, abs=0.05)
    world.force("ventilation/units/RV-01/heat_kw", 0.0, BIG)
    world.step(10)
    assert val(world, BOILER_GAS) == 0.0


def test_gas_is_sum_of_branches(world):
    """AC-55: ``gas = BOILER + CHP + dry + canteen`` (+ ε ≈ 0,6…1,4 %): будній день, сушарка працює, їдальня
    відкрита."""
    branches(world, boiler=40.6, chp=0.0, dry=True)
    world.step(10)
    expected = 40.6 + 6.0 + 1.0
    q = val(world, FLOW)
    assert q / expected - 1 == pytest.approx(0.01, abs=0.004 + 1e-9)
    assert abs(q - expected) / expected < 0.05  # ТК-02: ±5 % від суми гілок
    gas = world.devices["GAS-MAIN"].model
    assert gas.branches() == {"boiler": 40.6, "chp": 0.0, "dry": 6.0, "canteen": 1.0}


def test_gas_branches_off(world):
    """Сушарка стоїть, вечір (їдальня зачинена): лишаються котельня і КГУ."""
    branches(world, boiler=12.0, chp=109.0, dry=False, at=MONDAY_20)
    world.step(10)
    assert world.devices["GAS-MAIN"].model.branches() == {"boiler": 12.0, "chp": 109.0, "dry": 0.0, "canteen": 0.0}
    assert val(world, FLOW) == pytest.approx(121.0, rel=0.015)


def test_canteen_weekdays_0800_1600_only(world):
    gas = world.devices["GAS-MAIN"].model
    branches(world, boiler=0.0, at=SATURDAY_10)
    world.step(10)
    assert gas.branches()["canteen"] == 0.0
    for at, canteen in (
        (datetime(2026, 10, 12, 7, 59), 0.0),
        (datetime(2026, 10, 12, 8, 0), 1.0),
        (datetime(2026, 10, 12, 15, 59), 1.0),
        (datetime(2026, 10, 12, 16, 0), 0.0),
    ):
        world.clock.set(at)
        assert gas.branches()["canteen"] == canteen


def test_noise_is_deterministic_and_bounded(world):
    branches(world, boiler=40.0, at=MONDAY_20)
    eps = []
    for _ in range(30):
        world.advance(60)
        eps.append(val(world, FLOW) / 40.0 - 1)
    assert all(0.006 - 1e-9 <= e <= 0.014 + 1e-9 for e in eps) and max(eps) > min(eps)


def test_gas_extra_flag(world):
    """AC-56: ``gas_extra`` прибавляє ``extra_m3h``: BOILER 41 + 45 = 86 > 80 м³/год (число або словник)."""
    branches(world, boiler=41.0, at=MONDAY_20)
    world.step(10)
    base = val(world, FLOW)
    assert base < 80.0
    world.set_flag("gas_extra", 45.0)
    world.step(10)
    assert val(world, FLOW) > 80.0 and val(world, FLOW) - base == pytest.approx(45.0, abs=0.2)
    world.set_flag("gas_extra", {"extra_m3h": 10.0})
    world.step(10)
    assert val(world, FLOW) - base == pytest.approx(10.0, abs=0.2)
    world.set_flag("gas_extra", "abc")  # некоректний прапор ігнорується
    world.step(10)
    assert val(world, FLOW) == pytest.approx(base, abs=0.2)


def test_counter_quantum_and_growth(world):
    """``m3_total`` росте на ``q·dt/3600`` з квантом 0,01 м³; залишок переноситься (довге інтегрування сходиться)."""
    branches(world, boiler=40.0, at=MONDAY_20)
    start = val(world, TOTAL)
    assert start == M3_START
    acc = 0.0
    for _ in range(360):  # 1 год, крок 10 с
        world.step(10)
        acc += val(world, FLOW) * 10 / 3600
    grown = val(world, TOTAL) - start
    assert grown == pytest.approx(acc, abs=0.011)
    assert round(grown * 100) == pytest.approx(grown * 100, abs=1e-6)  # кратне 0,01
    assert 40.0 < grown < 41.0


def test_counter_carries_remainder(world):
    """Малі тіки (витрата 1 м³/год · 2 с = 0,00056 м³) не губляться: за 1 год — рівно 1 м³ ±0,01."""
    branches(world, boiler=0.0, at=SATURDAY_10)  # лише ε-шум від нуля: гілок немає
    world.set_flag("gas_extra", 1.0)
    world.step(0)
    start = val(world, TOTAL)
    for _ in range(1800):
        world.step(2)
    assert val(world, TOTAL) - start == pytest.approx(1.0, abs=0.011)


def test_state_roundtrip(world):
    gas = world.devices["GAS-MAIN"].model
    branches(world, boiler=40.0)
    world.advance(600)
    state = gas.get_state()
    assert state["pulses"] > 0
    other = {"pulses": 0, "frac": 0.0}
    gas.set_state(other)
    assert gas.pulses == 0
    gas.set_state(state)
    assert gas.get_state() == state


def test_modbus_u74_registers(world):
    """Адреси W3 §5.4: u74 HR 0–1 — ``m3_total`` (u32, молодше слово першим, ×0,01)."""
    world.force(TOTAL, 31870.25, BIG)
    um = build_all(world)[74]
    lo, hi = um.read("h", 0, 2)
    assert (hi << 16 | lo) == 3187025


async def settle(n=6):
    for _ in range(n):
        await asyncio.sleep(0)


async def test_gas_overuse_scenario(world):
    """AC-56: ``gas_overuse`` (за замовчуванням +45 м³/год) піднімає витрату вище 80 м³/год; зупинка прибирає прапор."""
    branches(world, boiler=41.0, at=MONDAY_20)
    runner = ScenarioRunner(world)
    run = runner.start("gas_overuse", {}, run_ref="odoo-gas")
    await settle()
    world.advance(10)
    await settle()
    assert world.flags["gas_extra"] == 45.0 and val(world, FLOW) > 80.0
    run = await runner.stop(run.id)
    assert run.error is None and "gas_extra" not in world.flags
    world.step(10)
    assert val(world, FLOW) < 80.0
