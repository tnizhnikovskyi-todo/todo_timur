"""P-07 SUN2000, LUNA2000, Elektronikon, ATyS p, TEDOM (SPEC §8.9.1–§8.9.5; AC-11, AC-12, AC-14, AC-20)."""

import struct
from types import SimpleNamespace

import pytest


def s32(regs):
    v = (regs[0] << 16) | regs[1]
    return v - (1 << 32) if v >= 1 << 31 else v


def u32(regs):
    return (regs[0] << 16) | regs[1]


def text(regs):
    return b"".join(r.to_bytes(2, "big") for r in regs).rstrip(b"\0").decode()


async def hr(srv, unit, addr, count=1):
    return await srv.client.read_holding_registers(addr, count=count, slave=unit)


async def test_sun2000_core_registers(modbus, world):
    world.force("infra/pv/PV-INV-1/p_kw", 88.123, hold_s=600)
    world.force("infra/pv/PV-INV-1/status", 0x0200, hold_s=600)
    world.force("infra/pv/PV-INV-1/kwh_today", 321.45, hold_s=600)
    world.force("infra/pv/PV-INV-1/kwh_total", 9999.9, hold_s=600)
    assert s32((await hr(modbus, 61, 32080, 2)).registers) == 88123
    assert (await hr(modbus, 61, 32089)).registers == [0x0200]
    assert u32((await hr(modbus, 61, 32114, 2)).registers) == 32145
    assert u32((await hr(modbus, 61, 32106, 2)).registers) == 999990
    assert text((await hr(modbus, 61, 30000, 15)).registers) == "SUN2000-115KTL-M2"
    assert u32((await hr(modbus, 61, 30073, 2)).registers) == 115000
    assert (await hr(modbus, 61, 32066)).registers == [4000]
    assert (await hr(modbus, 61, 32090)).registers == [0]


async def test_sun2000_night_and_blackout(modbus, world):
    world.force("infra/pv/PV-INV-8/p_kw", 0.0, hold_s=600)
    world.force("infra/pv/PV-INV-8/status", 0xA000, hold_s=600)
    assert s32((await hr(modbus, 68, 32080, 2)).registers) == 0
    assert (await hr(modbus, 68, 32089)).registers == [0xA000]
    world.force("infra/pv/PV-INV-8/status", 0x0303, hold_s=600)
    assert (await hr(modbus, 68, 32090)).registers == [2032]


async def test_sun2000_rw_system_time_guarded(modbus, world):
    assert not (await modbus.client.write_registers(40000, [0x1, 0x2], slave=61)).isError()
    assert (await hr(modbus, 61, 40000, 2)).registers == [1, 2]
    world.settings = SimpleNamespace(write_accept=False)
    rr = await modbus.client.write_register(42000, 5, slave=61)
    assert rr.isError() and rr.exception_code == 0x04
    rr = await modbus.client.write_register(32080, 5, slave=61)
    assert rr.isError() and rr.exception_code == 0x02


async def test_ac14_luna_registers_no_overlap(modbus, world):
    world.force("infra/totals/bess_kw", 200.0, hold_s=600)
    world.force("infra/totals/bess_soc", 76.0, hold_s=600)
    world.force("infra/bess/state", 2, hold_s=600)
    world.force("infra/bess/kwh_charge_total", 1000.5, hold_s=600)
    assert s32((await hr(modbus, 69, 37001, 2)).registers) == 200000
    assert (await hr(modbus, 69, 37004)).registers == [760]
    assert (await hr(modbus, 69, 37000)).registers == [2]
    assert u32((await hr(modbus, 69, 37014, 2)).registers) == 100050
    world.force("infra/totals/bess_kw", -50.0, hold_s=600)
    assert s32((await hr(modbus, 69, 37001, 2)).registers) == -50000
    assert u32((await hr(modbus, 69, 37046, 2)).registers) == 387000
    assert (await hr(modbus, 69, 37050)).registers == [990]
    assert (await hr(modbus, 69, 37018, 4)).registers == [0, 0, 0, 0]  # добові: без руху — 0


async def test_elektronikon_pdu_not_document_number(modbus, world):
    world.force("equipment/COMPRESSOR/pressure_bar", 6.81, hold_s=600)
    world.force("equipment/COMPRESSOR/load", 64.0, hold_s=600)
    world.force("equipment/COMPRESSOR/hours", 17840.0, hold_s=600)
    world.force("equipment/COMPRESSOR/state", 1, hold_s=600)
    assert (await hr(modbus, 70, 3001)).registers == [6810]  # документ 3002
    assert (await hr(modbus, 70, 3009)).registers == [64]  # документ 3010
    assert (await hr(modbus, 70, 3000)).registers == [1]
    assert u32((await hr(modbus, 70, 3019, 2)).registers) == 17840
    assert (await hr(modbus, 70, 3010)).registers == [1200 + 36 * 64]
    assert (await hr(modbus, 70, 3029)).registers == [160]
    assert (await hr(modbus, 70, 3039)).registers == [0]
    world.force("equipment/COMPRESSOR/state", 3, hold_s=600)
    assert (await hr(modbus, 70, 3039)).registers == [11]


async def test_elektronikon_setpoint_rw(modbus):
    assert (await hr(modbus, 70, 3099)).registers == [7000]
    assert not (await modbus.client.write_register(3099, 6800, slave=70)).isError()
    assert (await hr(modbus, 70, 3099)).registers == [6800]


async def test_ac20_atys_registers(modbus, world):
    world.force("infra/ats/position", 3, hold_s=600)
    world.force("infra/ats/src1_state", 0, hold_s=600)
    world.force("infra/ats/src2_state", 2, hold_s=600)
    world.force("infra/ats/mode", 32, hold_s=600)
    regs = (await hr(modbus, 71, 20482, 6)).registers
    assert regs == [32, 3, 0, 1, 0, 2]
    assert (await hr(modbus, 71, 57635)).registers == [71]
    assert (await hr(modbus, 71, 20490, 3)).registers == [0, 0, 0]  # мережі немає


async def test_atys_write_mode_guarded(modbus, world):
    rr = await modbus.client.write_register(21761, 0x10, slave=71)
    assert not rr.isError()
    assert world.signals["infra/ats/mode"].value == 0x10
    assert world.events.since(0, kind="command")[0]
    rr = await modbus.client.write_register(21761, 0x77, slave=71)
    assert rr.isError() and rr.exception_code == 0x03
    world.settings = SimpleNamespace(write_accept=False)
    rr = await modbus.client.write_register(21761, 0x20, slave=71)
    assert rr.isError() and rr.exception_code == 0x04


async def test_tedom_registers(modbus, world):
    world.force("infra/chp/state", 2, hold_s=600)
    world.force("infra/totals/chp_kw", 397.0, hold_s=600)
    world.force("infra/chp/heat_kw", 497.0, hold_s=600)
    world.force("infra/chp/gas_m3h", 109.0, hold_s=600)
    world.force("infra/chp/hours", 3412.0, hold_s=600)
    world.force("infra/chp/kwh_total", 123456.0, hold_s=600)
    assert (await hr(modbus, 72, 40000, 4)).registers == [2, 397, 497, 1090]
    assert (await hr(modbus, 72, 40004, 3)).registers == [900, 700, 1500]
    assert u32((await hr(modbus, 72, 40010, 2)).registers) == 3412
    assert u32((await hr(modbus, 72, 40014, 2)).registers) == 123456
    assert (await hr(modbus, 72, 40020)).registers == [0]
    world.force("infra/chp/state", 3, hold_s=600)
    assert (await hr(modbus, 72, 40020)).registers == [101]
    assert not (await modbus.client.write_register(40007, 70, slave=72)).isError()
    assert (await hr(modbus, 72, 40007)).registers == [70]
    assert world.flag("chp_run") is True  # ненульове завдання навантаження запускає КГУ
    assert not (await modbus.client.write_register(40007, 0, slave=72)).isError()
    assert world.flag("chp_run") is False  # 0 — зупинка


async def test_bit_exact_float_roundtrip_f32(modbus, world):
    world.force("energy/cells/Q2/p_now", -39.0, hold_s=600)
    world.force("energy/transformers/T2/p_kw", -39.0, hold_s=600)
    regs = (await hr(modbus, 2, 3059, 2)).registers
    assert struct.unpack(">f", struct.pack(">HH", *regs))[0] == pytest.approx(-39.0)
