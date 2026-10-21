"""td_chp §8 (AC-24): Modbus u72 — старі регістри TEDOM без змін, нові — за картою ``catalog/chp_registers.json``."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from iot_sim.protocols.modbus_maps import ModbusError, build_all
from iot_sim.protocols.modbus_maps.tedom import MAP_PATH, load_map

ROOT = Path(__file__).resolve().parents[2]
TD_CHP_JSON = ROOT.parents[1] / "odoo_addons" / "td_chp" / "data" / "chp_signals.json"
OLD = set(range(40000, 40004)) | {40004, 40005, 40006, 40007} | set(range(40010, 40016)) | {40020}
WORDS = {"u16": 1, "i16": 1, "u32": 2, "i32": 2}


@pytest.fixture
def um(world):
    world.step(1)
    return build_all(world)[72]


@pytest.fixture
def chp(world):
    return world.devices["CHP"].model


def decode(um, row):
    words = um.read("h", row["pdu"], WORDS[row["type"]])
    raw = int.from_bytes(b"".join(w.to_bytes(2, "big") for w in words), "big")
    bits = 16 * len(words)
    if row["type"].startswith("i") and raw >= 1 << (bits - 1):
        raw -= 1 << bits
    return raw * row["scale"]


def test_map_file_is_copy_of_td_chp_data():
    assert MAP_PATH == ROOT / "catalog" / "chp_registers.json"
    if TD_CHP_JSON.exists():  # AC-26 (у Docker-образі td_chp немає)
        assert MAP_PATH.read_bytes() == TD_CHP_JSON.read_bytes()
    assert len(load_map()) == 230


def test_map_addresses_do_not_overlap_old_registers():
    seen: dict[int, str] = {}
    for row in load_map():
        for a in range(row["pdu"], row["pdu"] + WORDS[row["type"]]):
            assert a not in seen, f"{row['code']} перетинається з {seen[a]}"
            seen[a] = row["code"]
    assert not {a for a in seen if 40004 <= a <= 40020}  # 40004…40020 — лише старі регістри TEDOM


def test_old_registers_unchanged(world):
    world.set_flag("chp_run", True)
    world.advance(100)
    um = build_all(world)[72]
    sig = {c: world.signals[c].value for c in ("infra/chp/state", "infra/totals/chp_kw", "infra/chp/heat_kw")}
    assert um.read("h", 40000, 1) == [2] == [round(sig["infra/chp/state"])]
    assert um.read("h", 40001, 1) == [round(sig["infra/totals/chp_kw"])]
    assert um.read("h", 40002, 1) == [round(sig["infra/chp/heat_kw"])]
    assert um.read("h", 40003, 1) == [round(world.signals["infra/chp/gas_m3h"].value / 0.1)]
    assert um.read("h", 40004, 2) == [900, 700] and um.read("h", 40006, 1) == [1500]
    assert um.read("h", 40010, 2)[1] == round(world.signals["infra/chp/hours"].value)
    assert um.read("h", 40012, 2) == [0, 211]
    assert um.read("h", 40020, 1) == [0]
    assert build_all(world)[73].read("h", 230, 4)[2:] == [1, 210]  # u73: permit, gas × 100


def test_load_setpoint_still_starts_chp(world):
    world.step(1)
    um = build_all(world)[72]
    um.write("h", 40007, [60])
    assert world.flags["chp_run"] is True
    um.write("h", 40007, [0])
    assert world.flags["chp_run"] is False


def test_every_signal_is_registered_with_its_type(world, um, chp):
    rows = load_map()
    assert {r["code"] for r in rows} <= set(chp.regs)
    for row in rows:
        words = WORDS[row["type"]]
        assert len(um.read("h", row["pdu"], words)) == words, row["code"]
        writable = "W" in row["rw"]
        assert (um.tables["h"][row["pdu"]][0].set is not None) == writable, row["code"]
    assert sum(1 for r in rows if "W" in r["rw"]) == 6


def test_values_follow_engineering_units(world, um, chp):
    by = {r["code"]: r for r in load_map()}
    for code, expect in {
        "chp/eng/hours": 18400.0,
        "chp/eng/starts": 612,
        "chp/em/kwh": 10912450,
        "chp/gas/total": 3940620,
        "chp/ctl/mode": 4,
        "chp/ctl/sp_pct": 80,
        "chp/ctl/cos_set": 0.98,
        "chp/safe/estop_loop": 1,
        "chp/safe/grid_ok": 1,
        "chp/gas/p_in": 2.10,
        "chp/ctl/remote": 1,
        "chp/ctl/permit": 1,
    }.items():
        assert decode(um, by[code]) == pytest.approx(expect, abs=max(by[code]["scale"], 0.02)), code
    assert um.read("h", 40120, 2) == [184000 >> 16, 184000 & 0xFFFF]  # u32, старше слово першим


def test_cylinder_diagnostics_in_regs(world, um, chp):
    world.set_flag("chp_run", True)
    world.advance(70)
    by = {r["code"]: r for r in load_map()}
    temps = [decode(um, by[f"chp/cyl/{c}/t"]) for c in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8")]
    temps += [decode(um, by[f"chp/cyl/B{n}/t"]) for n in range(1, 9)]
    dev_a5 = temps[4] - sum(temps) / 16
    assert dev_a5 == pytest.approx(27.3, abs=3.5)
    assert decode(um, by["chp/cyl/A5/plug_h"]) == pytest.approx(3560, abs=1)
    assert decode(um, by["chp/cyl/A1/plug_h"]) == pytest.approx(2400, abs=1)


def test_writable_registers_set_model_and_validate(world, um, chp):
    by = {r["code"]: r for r in load_map()}
    um.write("h", by["chp/ctl/mode"]["pdu"], [3])
    um.write("h", by["chp/ctl/sp_pct"]["pdu"], [65])
    um.write("h", by["chp/ctl/cos_set"]["pdu"], [95])
    um.write("h", by["chp/ctl/heat_dir"]["pdu"], [1])
    um.write("h", by["chp/ctl/bypass_mode"]["pdu"], [2])
    assert (chp.s["mode"], chp.s["sp_pct"], chp.s["cos_set"], chp.s["heat_dir"], chp.s["bypass_mode"]) == (
        3,
        65,
        0.95,
        1,
        2,
    )
    assert decode(um, by["chp/ctl/cos_set"]) == pytest.approx(0.95)
    for code, bad in (
        ("mode", 5),
        ("sp_pct", 49),
        ("sp_pct", 101),
        ("cos_set", 89),
        ("heat_dir", 3),
        ("bypass_mode", 3),
    ):
        with pytest.raises(ModbusError) as e:
            um.write("h", by[f"chp/ctl/{code}"]["pdu"], [bad])
        assert e.value.code == 3
    with pytest.raises(ModbusError):  # RO-регістр
        um.write("h", by["chp/ctl/state"]["pdu"], [1])
    with pytest.raises(ModbusError):
        um.write("h", by["chp/ctl/ack"]["pdu"], [1])


def test_write_accept_false_is_exception_4(world, um, chp):
    world.settings = SimpleNamespace(write_accept=False)
    um = build_all(world)[72]
    by = {r["code"]: r for r in load_map()}
    for code in ("chp/ctl/cmd", "chp/ctl/mode", "chp/ctl/sp_pct"):
        with pytest.raises(ModbusError) as e:
            um.write("h", by[code]["pdu"], [1 if code.endswith("cmd") else 60])
        assert e.value.code == 4
    assert chp.s["mode"] == 4 and not world.flags.get("chp_cmd")


def test_local_mode_ignores_register_writes_and_rejects_commands(world, um, chp):
    world.set_flag("ctl_remote", 0)
    by = {r["code"]: r for r in load_map()}
    um.write("h", by["chp/ctl/mode"]["pdu"], [2])
    assert chp.s["mode"] == 4  # прийнято протоколом, проте проігноровано контролером
    um.write("h", by["chp/ctl/cmd"]["pdu"], [1])
    assert decode(um, by["chp/ctl/ack"]) == 2 and decode(um, by["chp/ctl/ack_reason"]) == 3
    assert not world.flags.get("chp_cmd")


def test_json_map_is_valid_utf8_json():
    assert isinstance(json.loads(Path(MAP_PATH).read_text(encoding="utf-8")), list)
