"""W3 §8.1, AC-55 (реактивна енергія): ``kvarh_total`` вводів Q1/Q2 росте на ``|q_kvar|·dt/3600`` (PM5560, pdu 3219
i64)."""

import pytest
from iot_sim.models import meter
from iot_sim.protocols.modbus_maps import build_all

BIG = 1e9
NOMINAL = {"Q1": 21500.0, "Q2": 18300.0}


def val(world, code: str):
    return world.signals[code].value


def code(cell: str, leaf: str) -> str:
    return f"energy/cells/{cell}/{leaf}"


@pytest.mark.parametrize("cell", ["Q1", "Q2"])
def test_kvarh_grows_by_abs_q_dt(world, cell):
    """AC-55: ``kvarh_total += |q_kvar|·dt/3600`` від номіналу каталогу (21 500 / 18 300)."""
    assert val(world, code(cell, "kvarh_total")) == NOMINAL[cell]
    acc = 0.0
    for _ in range(180):  # 30 хв, крок 10 с
        world.step(10)
        acc += abs(val(world, code(cell, "q_kvar"))) * 10 / 3600
    assert acc > 0
    assert val(world, code(cell, "kvarh_total")) == pytest.approx(NOMINAL[cell] + acc, abs=1e-4)


def test_kvarh_uses_absolute_value(world, monkeypatch):
    """Від'ємна реактивна потужність (ємнісна) теж додається за модулем."""
    monkeypatch.setattr(meter, "apparent", lambda p, pf: (-72.0, 0.0, 10.0))
    world.step(0)
    start = val(world, code("Q1", "kvarh_total"))
    world.advance(3600)
    assert val(world, code("Q1", "kvarh_total")) - start == pytest.approx(72.0, abs=0.05)
    assert val(world, code("Q1", "q_kvar")) < 0


def test_kvarh_stops_on_failed_cell(world):
    world.step(10)
    world.fault("Q1", "generic")
    world.step(10)
    stopped = val(world, code("Q1", "kvarh_total"))
    world.advance(600)
    assert val(world, code("Q1", "kvarh_total")) == pytest.approx(stopped)
    assert val(world, code("Q2", "kvarh_total")) > NOMINAL["Q2"]  # Q2 далі рахує


def test_feeders_have_no_kvarh(world):
    assert not any(c.endswith("/kvarh_total") and "/lines/" in c for c in world.signals)
    assert world.devices["QF-1"].model.kvarh_start == 0.0


def test_reset_all_energies_zeroes_kvarh(world):
    """Modbus 2020 (Reset All Energies) обнуляє й реактивну енергію вводу."""
    world.advance(60)
    assert val(world, code("Q1", "kvarh_total")) > NOMINAL["Q1"]
    world.post("meter", {"unit": 1, "cmd": "reset_energy"})
    world.step(10)
    after = val(world, code("Q1", "kvarh_total"))
    assert after < 1.0  # лише приріст за один тік
    assert val(world, code("Q2", "kvarh_total")) > NOMINAL["Q2"]  # інший ввід не торкнуто


def test_state_roundtrip_and_reset_models(world):
    q1 = world.devices["Q1"].model
    world.advance(300)
    state = q1.get_state()
    assert state["kvarh_acc"] > 0 and state["kvarh_start"] == NOMINAL["Q1"]
    q1.set_state({})
    assert q1.kvarh_acc == 0.0
    q1.set_state(state)
    assert q1.get_state() == state
    world.reset_models()  # API-17 reset: лічильник реактивної енергії — знову від номіналу
    assert q1.kvarh_acc == 0.0 and q1.kvarh_start == NOMINAL["Q1"]


@pytest.mark.parametrize(("unit", "cell"), [(1, "Q1"), (2, "Q2")])
def test_modbus_reactive_energy_register(world, unit, cell):
    """Адреса W3 §5.4: HR 3219 (i64, ×0,001) — ``kvarh_total`` вводу у вар·год; фідери віддають 0."""
    world.force(code(cell, "kvarh_total"), 21500.5, BIG)
    maps = build_all(world)
    words = maps[unit].read("h", 3219, 4)
    raw = 0
    for w in words:
        raw = (raw << 16) | w
    assert raw == 21500500
    assert maps[3].read("h", 3219, 4) == [0, 0, 0, 0]
