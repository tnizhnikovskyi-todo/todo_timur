"""R-09: дрейф забивання фільтрів (AC-09)."""

import itertools

import pytest

RV05 = "ventilation/units/RV-05/filter_dp_pa"
DUST = "equipment/DUST-1/filter_dp_kpa"


def test_drift_rate(world):
    sig = world.signals[RV05]
    sig.value = 120.0
    world.step(10)
    r = world.r(RV05)
    assert sig.value == pytest.approx(120 + 0.05 * (1 + 0.5 * r) * 10 / 60, abs=1e-9)
    assert world.signals["ventilation/units/RV-05/filter_extract_dp_pa"].value == pytest.approx(0.8 * sig.value)


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


# --- обмежений дрейф: без сценарію поріг не досягається (R-09) ------------------------------------------


def _run(world, dev, sig, hours):
    """Прокрутити лише модель ``dev`` (швидко): повертає ряд значень ``sig`` кожні 10 sim-с."""
    model, signal, trace = world.devices[dev].model, world.signals[sig], []
    for _ in range(int(hours * 360)):
        world.clock.advance(10)
        model._tick(10)
        trace.append(float(signal.value))
    return trace


def test_supply_filter_bounded_below_threshold(world):
    trace = _run(world, "RV-05", RV05, 24 * 30)
    ceiling = world.devices["RV-05"].model.drift.band()[1]
    assert ceiling == pytest.approx(120 + 0.75 * (250 - 120))
    assert 120 <= min(trace) and max(trace) <= ceiling < 250  # у межах норми
    assert max(trace) > 200  # але фільтр справді забивається
    day1 = trace[: 24 * 360]
    assert 135 < max(day1) < 190  # повільний ріст за добу, не стрибок


def test_filter_change_sawtooth(world):
    trace = _run(world, "RV-05", RV05, 24 * 30)
    drops = sum(1 for a, b in itertools.pairwise(trace) if b < a - 50)
    assert drops >= 2  # за місяць кілька замін фільтра
    assert min(trace[-3600:]) >= 120


def test_dust_filter_bounded_below_threshold(world):
    trace = _run(world, "DUST-1", DUST, 24 * 30)
    assert 1.0 <= min(trace) and max(trace) <= 1.6  # поріг 1,8
    assert max(trace) > 1.45
    assert sum(1 for a, b in itertools.pairwise(trace) if b < a - 0.3) >= 2


def test_drift_deterministic(registry, clock):
    from iot_sim.core.clock import FakeClock
    from iot_sim.core.world import World

    def trace():
        w = World(registry, seed=20261012, clock=FakeClock("2026-10-12T10:30:00"))
        return _run(w, "RV-05", RV05, 48)

    assert trace() == trace()


def test_change_level_staggered_per_device(world):
    levels = {round(world.devices[f"RV-{n:02d}"].model.drift.band()[2], 3) for n in range(1, 26)}
    assert len(levels) >= 10  # установки не скидаються синхронно
    for n in range(1, 26):
        nominal, ceiling, change_at = world.devices[f"RV-{n:02d}"].model.drift.band()
        assert nominal + 0.9 * (ceiling - nominal) <= change_at < ceiling


def test_filter_changed_at_end_of_life(world):
    ceiling = world.devices["RV-05"].model.drift.band()[1]
    world.signals[RV05].value = ceiling - 0.01
    _run(world, "RV-05", RV05, 0.01)  # 3 кроків: скидання й мікроріст від чистого фільтра
    assert world.signals[RV05].value == pytest.approx(120.0, abs=0.05)


def test_scenario_flag_pushes_over_threshold(world):
    world.set_flag("filter_clogged", {"RV-05": 285.0})
    world.signals[RV05].value = 249.0
    trace = _run(world, "RV-05", RV05, 3)
    assert trace[-1] > 250 and trace[-1] > trace[0]  # сценарій: ріст без стелі й без авто-заміни
    world.clear_flag("filter_clogged")
    _run(world, "RV-05", RV05, 0.01)  # 3 кроків: скидання й мікроріст від чистого фільтра
    assert world.signals[RV05].value == pytest.approx(120.0, abs=0.05)


def test_forced_value_over_ceiling_is_held(world):
    world.signals[RV05].value = 285.0
    trace = _run(world, "RV-05", RV05, 2)
    assert set(trace) == {285.0}  # ручне значення: без росту й без авто-заміни
