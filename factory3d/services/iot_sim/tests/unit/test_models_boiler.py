"""R-10: бункер котельні і кількість котлів (AC-10)."""
import pytest

SILO = "equipment/BOILER/silo_fill"


def _heat(world, vent_total: float, chp_heat: float) -> None:
    for code in list(world.signals):
        if code.startswith("ventilation/units/") and code.endswith("/heat_kw"):
            world.force(code, 0.0, 1e9)
    world.force("ventilation/units/RV-01/heat_kw", vent_total, 1e9)
    world.force("infra/chp/heat_kw", chp_heat, 1e9)


def test_level_refill(world):
    world.signals[SILO].value = 16.0
    world.step(10)
    assert world.signals[SILO].value < 16.0
    world.signals[SILO].value = 15.0
    world.step(10)
    assert world.signals[SILO].value == 95.0
    assert any(e.message == "Бункер поповнено" for e in world.events.since(0)[0])
    world.advance(60)
    assert world.signals[SILO].value < 95.0


def test_boilers_on_logic(world):
    boiler = world.devices["BOILER"].model
    _heat(world, 322.0, 497.0)  # макет: КГУ покриває
    world.step(10)
    assert boiler.boilers_on == 0
    assert world.signals["equipment/BOILER/state"].value == 1
    assert world.signals["ventilation/heat_plant/check"].value == "норма"
    _heat(world, 600.0, 0.0)
    world.step(10)
    assert boiler.boilers_on == 2
    assert world.signals["equipment/BOILER/state"].value == 3
    _heat(world, 300.0, 0.0)
    world.step(10)
    assert boiler.boilers_on == 1
    assert world.signals["equipment/BOILER/heat_kw"].value == pytest.approx(300.0)
    _heat(world, 1200.0, 0.0)
    world.step(10)
    assert world.signals["ventilation/heat_plant/check"].value == "дефіцит тепла"


def test_silo_burn_rate_by_boilers(world):
    silo = world.signals[SILO]
    _heat(world, 322.0, 497.0)
    silo.value = 62.0
    world.advance(60)
    slow = 62.0 - silo.value
    _heat(world, 600.0, 0.0)
    silo.value = 62.0
    world.advance(60)
    fast = 62.0 - silo.value
    assert slow < 0.1 * fast * 2  # 0 котлів: лише 0,1·rate
    assert fast == pytest.approx(0.02 * 2 * 1.0, rel=0.4)  # ≈ rate·k_fire


def test_force_on_flag_and_fault(world):
    boiler = world.devices["BOILER"].model
    _heat(world, 0.0, 0.0)
    world.set_flag("boiler_force_on", 2)
    world.step(10)
    assert boiler.boilers_on == 2
    world.set_flag("boiler_force_on", -1)
    world.step(10)
    assert boiler.boilers_on == 0
    world.fault("BOILER", "generic")
    world.step(10)
    assert world.signals["equipment/BOILER/state"].value == 4
    assert boiler.get_state()["boilers_on"] == 0
    boiler.set_state({"boilers_on": 1, "refills": 3})
    assert boiler.boilers_on == 1
