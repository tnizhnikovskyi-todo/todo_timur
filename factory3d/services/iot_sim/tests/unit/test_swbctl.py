"""W2 §8.2 (AC-269): вікно керування контролера ГРЩ SWB-CTRL — Modbus u73, HR 200…291 (A-45, C-47)."""

from types import SimpleNamespace

import pytest
from iot_sim.protocols.modbus_maps import ModbusError, build_all
from iot_sim.protocols.modbus_server import UnitContext

# (HR, код сигналу, R/W) — таблиця SPEC §5.6 / contracts/c47_registers.json
REGISTERS = [
    (290, "ctl/heartbeat", "R"),
    (291, "ctl/remote", "R"),
    (200, "qs/cmd", "W"),
    (201, "qs/ack", "R"),
    (202, "ats/parallel_lock", "R"),
    (210, "pfc/mode", "RW"),
    (211, "pfc/cos_target", "RW"),
    (220, "bess/mode", "RW"),
    (221, "bess/setpoint_kw", "RW"),
    (222, "bess/until_soc", "RW"),
    (223, "bess/valid_s", "RW"),
    (224, "bess/remaining_s", "R"),
    (225, "bess/reserve_pct", "R"),
    (226, "bess/ack", "R"),
    (227, "bess/temp_c", "R"),
    (230, "chp/cmd", "W"),
    (231, "chp/ack", "R"),
    (232, "chp/permit", "R"),
    (233, "chp/gas_bar", "R"),
    (240, "air/setpoint_bar", "RW"),
    (241, "air/min_consumer_bar", "R"),
    (250, "pv/limit_pct", "RW"),
    (260, "shed/CHARGING/limit_pct", "RW"),
    (261, "shed/RV-ALL/limit_pct", "RW"),
    (262, "shed/DRY-1/limit_pct", "RW"),
    (263, "shed/COMPRESSOR/limit_pct", "RW"),
    (264, "shed/LP-1/limit_pct", "RW"),
    (270, "shed/valid_s", "RW"),
]
WRITABLE = [(a, n) for a, n, rw in REGISTERS if "W" in rw]
READ_ONLY = [(a, n) for a, n, rw in REGISTERS if rw == "R"]
# значення за замовчуванням після старту / reset (SPEC §5.6, R-59 п. 3)
DEFAULTS = {
    291: 1,
    200: 0,
    201: 0,
    202: 1,
    210: 1,
    211: 95,
    220: 0,
    221: 0,
    222: 0,
    223: 0,
    224: 0,
    225: 30,
    226: 0,
    230: 0,
    231: 0,
    232: 1,
    233: 210,
    240: 700,
    241: 620,
    250: 100,
    260: 100,
    261: 100,
    262: 100,
    263: 100,
    264: 100,
    270: 0,
}


@pytest.fixture
def um(world):
    world.step(1)
    return build_all(world)[73]


def hr(um, addr):
    return um.read("h", addr, 1)[0]


def write(um, addr, value):
    um.write("h", addr, [value])


def test_catalog_matches_register_map(registry, um):
    assert len(REGISTERS) == 28
    for addr, leaf, _rw in REGISTERS:
        spec = registry.by_code[f"energy_control/{leaf}"]
        assert spec.emulated and spec.modbus[:3] == (73, 3, addr) and spec.dtype == "U16", leaf
        assert registry.devices["SWB-CTRL"].signals.count(spec.code) == 1
        entry = um.tables["h"][addr][0]
        assert entry.name != spec.code  # адресу зайняла карта swbctl, а не bind_catalog (HR 100…123 лишаються за ним)
    assert hr(um, 100) == 0 and hr(um, 112) == 10 and hr(um, 122) == 10  # HR 100…123 W1 не зачеплено


def test_defaults(um):
    for addr, expected in DEFAULTS.items():
        assert hr(um, addr) == expected, addr
    assert 0 <= hr(um, 290) <= 65535
    assert 250 <= hr(um, 227) <= 350  # 25 + 0,05·|P| (≤ 200 кВт) °C × 10


def test_all_readonly_registers_reject_write(um):
    for addr, _name in READ_ONLY:
        with pytest.raises(ModbusError) as e:
            write(um, addr, 1)
        assert e.value.code == 2, addr  # Illegal Data Address


def test_write_roundtrip_in_range(world, um):
    cases = {
        210: 0,
        211: 97,
        221: 120,
        222: 90,
        223: 600,
        240: 650,
        250: 40,
        260: 0,
        261: 70,
        262: 20,
        263: 0,
        264: 50,
        270: 60,
    }
    for addr, value in cases.items():
        write(um, addr, value)
        assert hr(um, addr) == value, addr
    assert world.flags["pfc_cos_target"] == pytest.approx(0.97)
    assert world.flags["air_setpoint_bar"] == pytest.approx(6.5)
    assert world.flags["shed_limit"] == {
        "CHARGING": 0.0,
        "RV-ALL": 70.0,
        "DRY-1": 20.0,
        "COMPRESSOR": 0.0,
        "LP-1": 50.0,
    }
    assert (world.flags["shed_valid_s"], world.flags["bess_valid_s"]) == (60.0, 600.0)


@pytest.mark.parametrize(
    "addr, bad",
    [
        (200, 3),
        (230, 3),
        (210, 2),
        (211, 79),
        (211, 101),
        (220, 4),
        (221, 201),
        (222, 101),
        (223, 65536 + 1),
        (240, 499),
        (240, 851),
        (250, 101),
        (260, 101),
        (264, 101),
        (270, 65536 + 1),
    ],
)
def test_out_of_bounds_is_exception_3(um, addr, bad):
    before = hr(um, addr)
    with pytest.raises(ModbusError) as e:
        write(um, addr, bad)
    assert e.value.code == 3  # Illegal Data Value
    assert hr(um, addr) == before


def test_write_accept_false_is_exception_4(world, um):
    world.settings = SimpleNamespace(write_accept=False, pfc_cos_target=0.95)
    um = build_all(world)[73]
    for addr, _name in WRITABLE:
        with pytest.raises(ModbusError) as e:
            write(um, addr, 0)
        assert e.value.code == 4, addr
    assert hr(um, 291) == 1  # читання не зачеплено


def test_modbus_context_maps_error_codes(world, um):
    ctx = UnitContext(um)
    assert ctx.setValues(6, 210, [1]) is None
    assert ctx.setValues(6, 210, [5]) == 3
    assert ctx.setValues(6, 201, [1]) == 2
    assert ctx.getValues(3, 291, 1) == [1]
    world.settings = SimpleNamespace(write_accept=False)
    assert UnitContext(build_all(world)[73]).setValues(6, 210, [0]) == 4


def test_cmd_registers_self_clear_next_tick(world, um):
    write(um, 200, 1)
    write(um, 230, 2)
    assert (hr(um, 200), hr(um, 230)) == (1, 2)
    events = [e.message for e in world.events.since(0, kind="command")[0]]
    assert "Modbus u73: QS cmd = 1" in events and "Modbus u73: CHP cmd = 2" in events
    world.step(1)
    assert (hr(um, 200), hr(um, 230)) == (0, 0)
    assert hr(um, 201) == 1 and hr(um, 231) == 1  # результат команд
    write(um, 200, 0)  # 0 — «нічого»: подія й прапор не створюються
    assert world.flags.get("qs_cmd", 0) == 0


def test_heartbeat_grows_per_simulated_second(world, um):
    h0 = hr(um, 290)
    world.advance(3)
    assert hr(um, 290) == h0 + 3
    world.advance(10)
    assert hr(um, 290) == h0 + 13
    assert world.signals["energy_control/ctl/heartbeat"].value == h0 + 13


def test_local_mode_ignores_commands_with_ack_2(world, um):
    world.set_flag("ctl_remote", 0)
    assert hr(um, 291) == 0
    write(um, 200, 2)
    write(um, 230, 1)
    write(um, 220, 1)
    write(um, 210, 0)
    write(um, 240, 650)
    world.step(1)
    assert (hr(um, 201), hr(um, 231), hr(um, 226)) == (2, 2, 2)
    assert world.flags.get("qs_closed") is None and not world.flags.get("chp_run")
    assert (hr(um, 220), hr(um, 210), hr(um, 240)) == (0, 1, 700)  # записи параметрів теж ігноруються
    world.set_flag("ctl_remote", 1)
    write(um, 210, 0)
    assert hr(um, 210) == 0


def test_registers_mirror_into_signals(world, um):
    write(um, 270, 600)  # без сторожового таймера ліміти скидаються в тіку
    write(um, 211, 93)
    write(um, 250, 80)
    write(um, 262, 10)
    world.step(1)
    sig = world.signals
    assert sig["energy_control/pfc/cos_target"].value == pytest.approx(0.93)
    assert sig["energy_control/pv/limit_pct"].value == 80
    assert sig["energy_control/shed/DRY-1/limit_pct"].value == 10
    assert sig["energy_control/ctl/remote"].value == 1
    assert sig["energy_control/air/setpoint_bar"].value == pytest.approx(7.0)


def test_reset_restores_defaults(world, um):
    """R-59 п. 3: ``POST /sim/v1/reset`` очищає прапори → стандартні значення регістрів."""
    from fastapi.testclient import TestClient
    from iot_sim.config import Settings
    from iot_sim.core.scenarios import ScenarioRunner
    from iot_sim.protocols.control_api import create_app

    for addr, value in {210: 0, 211: 99, 221: 80, 222: 90, 223: 120, 240: 600, 250: 20, 261: 10, 270: 30}.items():
        write(um, addr, value)
    world.set_flag("ctl_remote", 0)
    world.set_flag("gas_bar", 0.8)
    world.set_flag("chp_run", True)
    world.set_flag("qs_closed", True)
    token = "t" * 40
    follow = SimpleNamespace(configured=True, last_ok=None, status=dict, kick=lambda: None)
    app = create_app(
        Settings(_env_file=None, api_token=token), world=world, runner=ScenarioRunner(world), follow=follow
    )
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as api:
        assert api.post("/sim/v1/reset", json={"keep_time": True}).status_code == 200
    um = build_all(world)[73]
    for addr, expected in DEFAULTS.items():
        if addr != 290:
            assert hr(um, addr) == expected, addr
    assert not world.flags.get("chp_run") and not world.flags.get("qs_closed")


def test_register_table_equals_frozen_contract_c47():
    """`contracts/c47_registers.json` (C-47) — єдине джерело таблиці регістрів для плагіна, Odoo-даних і емулятора."""
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[4] / "odoo_addons" / "td_energy_control" / "contracts" / "c47_registers.json"
    )
    if not path.is_file():  # образ сервісу без Odoo-аддонів
        pytest.skip("contracts/c47_registers.json недоступний")
    ref = json.loads(path.read_text("utf-8"))
    assert ref["source"]["unit"] == 73 and ref["source"]["fc_read"] == 3 and ref["source"]["fc_write"] == 6
    table = {(r["hr"], r["code"].removeprefix("energy_control/"), r["rw"]) for r in ref["registers"]}
    assert table == set(REGISTERS) and len(table) == 28
    scaled = {r["code"].removeprefix("energy_control/"): r["scale"] for r in ref["registers"] if r["scale"]}
    assert scaled == {
        "pfc/cos_target": 0.01,
        "bess/temp_c": 0.1,
        "chp/gas_bar": 0.01,
        "air/setpoint_bar": 0.01,
        "air/min_consumer_bar": 0.01,
    }
