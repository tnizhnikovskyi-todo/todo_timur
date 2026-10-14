"""R-09: дрейф забивання фільтрів (AC-09)."""
import pytest

RV05 = "ventilation/units/RV-05/filter_dp_pa"
DUST = "equipment/DUST-1/filter_dp_kpa"


def test_drift_rate(world):
    sig = world.signals[RV05]
    sig.value = 120.0
    world.step(10)
    r = world.r(RV05)
    assert sig.value == pytest.approx(120 + 0.05 * (1 + 0.5 * r) * 10 / 60, abs=1e-9)
    assert world.signals["ventilation/units/RV-05/filter_extract_dp_pa"].value == pytest.approx(
        0.8 * sig.value)


def test_reset_on_maintenance_closed(world):
    world.signals[RV05].value = 285.0
    world.maintenance_closed.add("RV-05")
    world.step(10)
    assert world.signals[RV05].value == pytest.approx(120.0)
    assert "RV-05" not in world.maintenance_closed


def test_reset_by_signal_code_and_clear(world):
    world.signals[DUST].value = 1.9
    world.maintenance_closed.add(DUST)
    world.step(10)
    assert world.signals[DUST].value == pytest.approx(1.0, abs=1e-3)
    world.signals[DUST].value = 1.9
    world.fault("DUST-1")
    world.step(10)
    assert world.signals["equipment/DUST-1/state"].value == 0
    world.clear("DUST-1")
    assert world.signals[DUST].value == pytest.approx(1.0)
    world.step(10)
    assert world.signals["equipment/DUST-1/state"].value == 1


def test_filter_clogged_flag_release(world):
    world.set_flag("filter_clogged", {"RV-05": 285.0})
    world.force(RV05, 285.0, hold_s=15)
    world.step(10)
    assert world.signals[RV05].value == 285.0  # утримання діє
    world.advance(30)
    assert world.signals[RV05].value > 285.0  # R-09 продовжує
    world.clear_flag("filter_clogged")
    world.step(10)
    assert world.signals[RV05].value == pytest.approx(120.0)


def test_drift_alarm_threshold(world):
    world.signals[RV05].value = 285.0
    world.step(10)
    assert world.signals[RV05].status == "alarm"
    assert world.signals["equipment/DUST-1/airflow_m3h"].value > 0
    assert world.devices["DUST-1"].model.get_state() == {"clogged": False}
    world.devices["DUST-1"].model.set_state({"clogged": True})
    assert world.devices["DUST-1"].model.drift.clogged
