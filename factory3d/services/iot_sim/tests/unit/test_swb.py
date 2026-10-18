"""W1 §8.1: контролер ГРЩ SWB-CTRL (Modbus u73) — QS, PFC-1/PFC-2, сценарій ``pfc_step_fault``."""
import asyncio
import math
from types import SimpleNamespace

import pytest

from iot_sim.core.scenarios import ScenarioParamsError, ScenarioRunner
from iot_sim.models.meter import SECTIONS
from iot_sim.models.swb import STEP_KVAR, Swb, section_pq, steps_needed
from iot_sim.protocols.modbus_maps import build_all

BIG = 1e9
SIGNALS = (
    "energy/cells/QS/state",
    *(f"energy/cells/PFC-{s}/{leaf}" for s in (1, 2) for leaf in ("q_kvar", "steps_on", "steps_total", "fault_step")),
)


def val(world, code: str) -> float:
    return world.signals[code].value


def pfc(world, section: int, leaf: str) -> float:
    return val(world, f"energy/cells/PFC-{section}/{leaf}")


def set_section(world, section: int, p_kw: float, cos: float) -> None:
    """Σ ``p_now`` ліній секції = ``p_kw`` при заданому ``cos_phi`` (значення утримуються — моделі їх не перепишуть)."""
    lines = SECTIONS[section]
    for line in lines:
        world.force(f"energy/lines/{line}/p_now", p_kw / len(lines), BIG)
        world.force(f"energy/lines/{line}/cos_phi", cos, BIG)


def expected_steps(p_kw: float, cos: float, target: float = 0.95) -> int:
    q = p_kw * math.tan(math.acos(cos))
    need = max(0.0, q - p_kw * math.tan(math.acos(target)))
    return min(10, math.ceil(need / 35.0 - 1e-9))


# --- каталог, регістри ---------------------------------------------------------------------
def test_catalog_device_and_signals(registry):
    dev = registry.devices["SWB-CTRL"]
    assert (dev.driver, dev.unit_id, dev.protocol) == ("swb", 73, "P-07")
    assert sorted(dev.signals) == sorted(SIGNALS)
    for code in SIGNALS:
        spec = registry.by_code[code]
        assert spec.emulated and spec.modbus[:2] == (73, 3) and spec.dtype == "U16", code
    assert registry.by_code["energy/cells/QS/state"].modbus[2] == 100
    for section, base in ((1, 110), (2, 120)):
        assert [registry.by_code[f"energy/cells/PFC-{section}/{leaf}"].modbus[2] for leaf in (
            "q_kvar", "steps_on", "steps_total", "fault_step")] == [base, base + 1, base + 2, base + 3]
    fault = registry.by_code["energy/cells/PFC-1/fault_step"]
    assert fault.alarm == "above" and fault.threshold == 0.5


def test_world_model_and_initial_values(world):
    assert isinstance(world.devices["SWB-CTRL"].model, Swb)
    assert val(world, "energy/cells/QS/state") == 0
    assert pfc(world, 1, "steps_total") == pfc(world, 2, "steps_total") == 10
    assert pfc(world, 1, "fault_step") == pfc(world, 2, "fault_step") == 0


def test_modbus_registers_unit_73(world):
    set_section(world, 2, 400.0, 0.9)
    set_section(world, 1, 0.0, 0.9)
    world.step(1)
    um = build_all(world)[73]
    assert um.read("h", 100, 1) == [0]
    assert um.read("h", 110, 4) == [0, 0, 10, 0]
    assert um.read("h", 120, 4) == [70, 2, 10, 0]


# --- PFC: розрахунок ступенів --------------------------------------------------------------
def test_steps_formula():
    assert steps_needed(400.0, 400.0 * math.tan(math.acos(0.97))) == 0  # вже вище цілі
    assert steps_needed(0.0, 0.0) == 0
    assert steps_needed(1000.0, 1000.0 * math.tan(math.acos(0.6))) == 10  # обмеження 10 ступенів
    assert steps_needed(400.0, 400.0 * math.tan(math.acos(0.9))) == 2


@pytest.mark.parametrize("p_kw, cos", [(400.0, 0.9), (400.0, 0.97), (800.0, 0.85), (1000.0, 0.6), (0.0, 0.9)])
def test_pfc_follows_load(world, p_kw, cos):
    set_section(world, 2, p_kw, cos)
    set_section(world, 1, 0.0, 0.9)
    world.step(1)
    steps = expected_steps(p_kw, cos)
    assert pfc(world, 2, "steps_on") == steps
    assert pfc(world, 2, "q_kvar") == steps * STEP_KVAR
    assert (pfc(world, 2, "steps_total"), pfc(world, 2, "fault_step")) == (10, 0)
    assert pfc(world, 1, "steps_on") == 0 and pfc(world, 1, "q_kvar") == 0
    p, q = section_pq(world, 2)
    assert p == pytest.approx(p_kw) and q == pytest.approx(p_kw * math.tan(math.acos(cos)))


def test_pfc_target_is_world_parameter(world):
    set_section(world, 2, 400.0, 0.9)
    world.step(1)
    assert pfc(world, 2, "steps_on") == 2
    world.settings = SimpleNamespace(pfc_cos_target=0.99)
    world.step(1)
    assert pfc(world, 2, "steps_on") == expected_steps(400.0, 0.9, 0.99)


def test_pfc_off_in_island_and_on_device_fault(world):
    set_section(world, 2, 800.0, 0.85)
    world.step(1)
    assert pfc(world, 2, "steps_on") > 0
    world.set_flag("blackout", {"t0": "x", "phase": "outage", "genset": True, "amf_master": "hgm",
                                "restore_delay_s": 60, "genset_load_kw": None, "chp_island": False})
    world.step(1)
    assert pfc(world, 2, "steps_on") == 0 and pfc(world, 2, "q_kvar") == 0
    world.clear_flag("blackout")
    world.step(1)
    assert pfc(world, 2, "steps_on") > 0
    world.fault("SWB-CTRL", "generic")
    world.step(1)
    assert pfc(world, 2, "steps_on") == 0 and pfc(world, 2, "steps_total") == 10


# --- сценарій pfc_step_fault ----------------------------------------------------------------
def test_step_fault_caps_steps_and_latches(world):
    set_section(world, 2, 800.0, 0.85)  # потрібно > 3 ступенів
    set_section(world, 1, 800.0, 0.85)
    world.step(1)
    assert pfc(world, 2, "steps_on") > 3
    world.set_flag("swb", {"section": 2, "step": 3, "qs_closed": False})
    world.step(1)
    assert (pfc(world, 2, "steps_on"), pfc(world, 2, "q_kvar"), pfc(world, 2, "fault_step")) == (2, 70.0, 3)
    assert pfc(world, 1, "steps_on") > 3 and pfc(world, 1, "fault_step") == 0  # інша секція не зачеплена
    set_section(world, 2, 400.0, 0.9)  # потрібно лише 2 ступені: збій тримається до зупинки сценарію
    world.step(1)
    assert (pfc(world, 2, "steps_on"), pfc(world, 2, "fault_step")) == (2, 3)
    set_section(world, 2, 100.0, 0.9)  # 1 ступінь — менше за step−1
    world.step(1)
    assert (pfc(world, 2, "steps_on"), pfc(world, 2, "fault_step")) == (1, 3)
    world.clear_flag("swb")
    world.step(1)
    assert pfc(world, 2, "fault_step") == 0 and pfc(world, 2, "steps_on") == 1


def test_step_fault_waits_until_steps_reach_step(world):
    set_section(world, 2, 400.0, 0.9)  # потрібно 2 ступені < step 3: збою ще немає
    world.set_flag("swb", {"section": 2, "step": 3, "qs_closed": False})
    world.step(1)
    assert (pfc(world, 2, "steps_on"), pfc(world, 2, "fault_step")) == (2, 0)
    set_section(world, 2, 800.0, 0.85)  # навантаження зросло: ступінь 3 «не вмикається»
    world.step(1)
    assert (pfc(world, 2, "steps_on"), pfc(world, 2, "fault_step")) == (2, 3)


def test_qs_closed_only_by_scenario_param(world):
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 0
    world.set_flag("swb", {"section": 2, "step": 0, "qs_closed": True})
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 1
    assert pfc(world, 2, "fault_step") == 0  # step=0 — без збою ступеня
    world.clear_flag("swb")
    world.step(1)
    assert val(world, "energy/cells/QS/state") == 0


def test_state_snapshot_roundtrip(world):
    set_section(world, 2, 800.0, 0.85)
    world.set_flag("swb", {"section": 2, "step": 3, "qs_closed": False})
    world.step(1)
    model = world.devices["SWB-CTRL"].model
    assert model.get_state() == {"stuck": {"2": 3}}
    model.set_state({"stuck": {"1": 4}})
    assert model.stuck == {1: 4}


async def test_scenario_start_stop(world):
    runner = ScenarioRunner(world)
    set_section(world, 2, 800.0, 0.85)
    run = runner.start("pfc_step_fault", {"section": 2, "step": 3})
    for _ in range(6):
        await asyncio.sleep(0)
    assert world.flags["swb"] == {"section": 2, "step": 3, "qs_closed": False}
    world.step(1)
    assert (pfc(world, 2, "steps_on"), pfc(world, 2, "fault_step")) == (2, 3)
    run = await runner.stop(run.id)
    assert run.state in ("stopped", "done") and run.error is None
    assert "swb" not in world.flags
    world.step(1)
    assert pfc(world, 2, "fault_step") == 0 and pfc(world, 2, "steps_on") > 2


async def test_scenario_params_validation_and_no_conflict_with_energy(world):
    runner = ScenarioRunner(world)
    for bad in ({"section": 3}, {"step": 11}, {"step": -1}, {"extra": 1}):
        with pytest.raises(ScenarioParamsError):
            runner.start("pfc_step_fault", bad)
    runner.start("pv_cloudy", {})  # збій ступеня PFC не конфліктує з рештою «energy»
    runner.start("pfc_step_fault", {})
    await runner.stop_all()
