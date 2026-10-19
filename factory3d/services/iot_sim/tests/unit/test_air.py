"""W3 §8.1, AC-55/AC-56 (повітря): ``AIR-MAIN`` — витрата від завантаження компресора, тиск, лічильник, сценарій ``air_leak``."""

import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from iot_sim.core.scenarios import SCENARIOS, ScenarioRunner
from iot_sim.models.air import M3_START
from iot_sim.protocols.modbus_maps import build_all

BIG = 1e9
LOAD = "equipment/COMPRESSOR/load"
PRESSURE = "equipment/COMPRESSOR/pressure_bar"
FLOW = "air/flow_m3min"
TOTAL = "air/m3_total"
XML = Path(__file__).resolve().parents[4] / "odoo_addons/td_iot_sim/data/td_sim_scenario_resources.xml"


def val(world, code: str):
    return world.signals[code].value


def at_load(world, load: float) -> None:
    world.force(LOAD, load, BIG)
    world.step(10)


def test_flow_by_load(world):
    """AC-55: ``load = 66`` → 9,8 м³/хв; ``load = 25`` → 1,6; межі ``act`` 0…1,3."""
    at_load(world, 66.0)
    assert val(world, FLOW) == pytest.approx(9.8)
    at_load(world, 25.0)
    assert val(world, FLOW) == pytest.approx(1.6)
    at_load(world, 45.5)  # половина шкали
    assert val(world, FLOW) == pytest.approx(1.6 + 8.2 * (20.5 / 41.0))
    at_load(world, 10.0)  # нижче load_min: act = 0
    assert val(world, FLOW) == pytest.approx(1.6)
    at_load(world, 100.0)  # act = min(1,83; 1,3)
    assert val(world, FLOW) == pytest.approx(1.6 + 8.2 * 1.3)


def test_pressure_is_compressor_minus_drop(world):
    """AC-55: ``air pressure = compressor − 0,1``."""
    world.force(PRESSURE, 6.81, BIG)
    world.step(10)
    assert val(world, "air/pressure_bar") == pytest.approx(6.71)
    world.force(PRESSURE, 5.5, BIG)  # compressor_fault: pressure_drop
    world.step(10)
    assert val(world, "air/pressure_bar") == pytest.approx(5.4) and val(world, "air/pressure_bar") < 5.8


def test_device_params_override_defaults(world):
    air = world.devices["AIR-MAIN"].model
    assert (air.leak, air.q_ref, air.load_ref, air.load_min, air.drop) == (1.6, 9.8, 66.0, 25.0, 0.1)
    air.leak, air.q_ref = 2.0, 12.0
    at_load(world, 66.0)
    assert val(world, FLOW) == pytest.approx(12.0)
    at_load(world, 25.0)
    assert val(world, FLOW) == pytest.approx(2.0)


def test_air_leak_flag_raises_night_flow(world):
    """AC-56: ``air_leak`` повишає нічну витрату на 3,0 м³/хв (число або словник; без прапора — норма)."""
    at_load(world, 25.0)
    night = val(world, FLOW)
    world.set_flag("air_leak", 3.0)
    world.step(10)
    assert val(world, FLOW) - night == pytest.approx(3.0)
    world.set_flag("air_leak", {"leak_extra": 1.5})
    world.step(10)
    assert val(world, FLOW) - night == pytest.approx(1.5)
    world.set_flag("air_leak", True)  # не число — ігнорується
    world.step(10)
    assert val(world, FLOW) == pytest.approx(night)


def test_counter_grows_with_quantum(world):
    """``m3_total += flow·dt/60`` з квантом 0,1 норм. м³; 9,8 м³/хв · 10 хв = 98."""
    world.force(LOAD, 66.0, BIG)
    world.step(0)
    start = val(world, TOTAL)
    assert start == M3_START
    world.advance(600)
    grown = val(world, TOTAL) - start
    assert grown == pytest.approx(98.0, abs=0.11)
    assert round(grown * 10) == pytest.approx(grown * 10, abs=1e-6)  # кратне 0,1


def test_counter_carries_remainder(world):
    """Малі тіки (1,6 м³/хв · 1 с = 0,027 м³) не губляться: за 10 хв — 16,0 ±0,1."""
    world.force(LOAD, 25.0, BIG)
    world.step(0)
    start = val(world, TOTAL)
    for _ in range(600):
        world.step(1)
    assert val(world, TOTAL) - start == pytest.approx(16.0, abs=0.11)


def test_state_roundtrip(world):
    air = world.devices["AIR-MAIN"].model
    world.advance(300)
    state = air.get_state()
    assert state["pulses"] > 0
    air.set_state({"pulses": 0, "frac": 0.0})
    assert air.pulses == 0
    air.set_state(state)
    assert air.get_state() == state


def test_modbus_u75_registers(world):
    """Адреси W3 §5.4: u75 HR 0 — витрата (u16, ×0,01), HR 2–3 — лічильник (u32, ×0,1), HR 4 — тиск (u16, ×0,01)."""
    world.force(FLOW, 9.8, BIG)
    world.force(TOTAL, 6420.5, BIG)
    world.force("air/pressure_bar", 6.71, BIG)
    um = build_all(world)[75]
    assert um.read("h", 0, 1) == [980]
    lo, hi = um.read("h", 2, 2)
    assert (hi << 16 | lo) == 64205
    assert um.read("h", 4, 1) == [671]


def _xml_records() -> dict[str, dict[str, str]]:
    """``{code: {поле: eval-вираз або текст}}`` записів ``td.sim.scenario`` з XML-файлу даних."""
    out = {}
    for rec in ET.parse(XML).getroot().iter("record"):
        assert rec.get("model") == "td.sim.scenario"
        fields = {f.get("name"): f.get("eval") or (f.text or "").strip() for f in rec.iter("field")}
        out[fields["code"]] = fields
    return out


@pytest.mark.skipif(not XML.is_file(), reason="немає odoo_addons (образ Docker)")
def test_scenario_resources_xml():
    """AC-56: файл ``td_sim_scenario_resources.xml`` містить ``air_leak``, ``gas_overuse``, ``water_leak`` з параметрами."""
    recs = _xml_records()
    assert set(recs) == {"air_leak", "gas_overuse", "water_leak"}
    emu = {c.name: c for c in SCENARIOS}
    expected = {"air_leak": {"leak_extra": 3.0}, "gas_overuse": {"extra_m3h": 45.0}, "water_leak": {"extra_m3h": 0.5}}
    for code, params in expected.items():
        r = recs[code]
        assert r["code"] == code and r["group"] == "energy" and r["duration_s"] == "0"
        assert eval(r["params_default"], {"__builtins__": {}}, {"True": True, "False": False}) == params
        assert "properties" in r["params_schema"]
        assert emu[code].default_duration() == 0
        assert (
            emu[code].Params().model_dump(exclude={"duration_s", "note"}) == params
        )  # значення за замовчуванням збігаються


async def settle(n=6):
    for _ in range(n):
        await asyncio.sleep(0)


async def test_air_leak_scenario(world):
    """AC-56: ``air_leak`` (за замовчуванням +3,0 м³/хв) піднімає нічну витрату; зупинка знімає прапор."""
    at_load(world, 25.0)
    night = val(world, FLOW)
    runner = ScenarioRunner(world)
    run = runner.start("air_leak", {}, run_ref="odoo-air")
    await settle()
    world.advance(10)
    await settle()
    assert world.flags["air_leak"] == 3.0
    assert val(world, FLOW) - night == pytest.approx(3.0)
    run = await runner.stop(run.id)
    assert run.error is None and "air_leak" not in world.flags
    world.step(10)
    assert val(world, FLOW) == pytest.approx(night)
