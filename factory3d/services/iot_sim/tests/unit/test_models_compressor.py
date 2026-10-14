"""R-08: компресор (AC-12)."""
import pytest

from iot_sim.models.compressor import production

P = "equipment/COMPRESSOR/pressure_bar"


def _all_working(world, factor: float = 1.0) -> None:
    for dev in world.devices.values():
        if dev.driver == "machine":
            s = world.signals[f"energy/consumers/{dev.code}/p_now"]
            world.force(s.code, float(s.params["nominal"] or 0.0) * factor, 1e9)


def test_load_from_production(world, registry):
    # у W1b-2 модель machine може бути ще відсутня: підставляємо пристрої driver=machine вручну
    _all_working(world)
    prod, pmax = production(world)
    assert prod == pytest.approx(pmax) and pmax > 0
    world.advance(1200)
    assert world.signals["equipment/COMPRESSOR/load"].value >= 80
    assert world.signals[P].status != "alarm"
    assert world.signals["equipment/COMPRESSOR/state"].value == 1
    assert world.signals["equipment/COMPRESSOR/hours"].value > 17840.8
    assert 70 < world.signals["equipment/COMPRESSOR/temp_c"].value < 100


def test_idle_load_floor(world):
    _all_working(world, 0.0)
    world.advance(1800)
    assert world.signals["equipment/COMPRESSOR/load"].value < 40
    for dev in world.devices.values():
        dev.driver = "passive" if dev.driver == "machine" else dev.driver
    assert production(world) == (0.0, 0.0)
    world.step(10)  # pmax = 0 → load тягнеться до 25


def test_overload_lowers_pressure_nominal(world):
    model = world.devices["COMPRESSOR"].model
    world.force("energy/consumers/SAW-1/p_now", 1e6, 1e9)  # load → 100
    world.advance(1200)
    assert model.nominal < 6.81
    assert model.nominal >= 6.2
    world.force("energy/consumers/SAW-1/p_now", 0.0, 1e9)
    world.advance(3600)
    assert model.nominal == pytest.approx(6.81)


def test_fault_pressure_drop(world):
    world.set_flag("compressor_fault", {"kind": "pressure_drop"})
    world.advance(900)
    assert world.signals[P].value == pytest.approx(5.5, abs=0.1)
    assert world.signals[P].status == "alarm"
    assert world.signals["equipment/COMPRESSOR/state"].value == 3
    world.clear_flag("compressor_fault")
    world.advance(1500)
    assert world.signals[P].value > 6.5
    assert world.signals["equipment/COMPRESSOR/state"].value == 1


def test_fault_overtemp_and_comm(world):
    world.set_flag("compressor_fault", {"kind": "overtemp"})
    world.step(10)
    assert world.signals["equipment/COMPRESSOR/temp_c"].value == 115.0
    assert world.signals["equipment/COMPRESSOR/temp_c"].status == "alarm"
    world.set_flag("compressor_fault", {"kind": "comm"})
    world.step(10)
    dev = world.devices["COMPRESSOR"]
    assert dev.fault == "comm" and dev.state == "offline"
    world.clear_flag("compressor_fault")
    world.step(10)
    assert dev.fault is None and dev.state == "ok"


def test_state_roundtrip(world):
    model = world.devices["COMPRESSOR"].model
    model.set_state({"nominal": 6.4, "hours": 5.0, "comm_from_flag": True})
    assert model.get_state() == {"nominal": 6.4, "hours": 5.0, "comm_from_flag": True}
