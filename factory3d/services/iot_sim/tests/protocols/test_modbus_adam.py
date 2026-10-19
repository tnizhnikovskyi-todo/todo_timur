"""P-02/P-09/P-11 ADAM-6050/6060/6017/6015 (SPEC §8.4.2, §8.9.6, §8.11.3, §8.13.1; AC-37, AC-44)."""

import struct
from types import SimpleNamespace

import pytest
from iot_sim.protocols.modbus_maps import adam6015, adam6017


def u32_little(regs):
    return regs[0] | (regs[1] << 16)


def f32_little(regs):
    return struct.unpack(">f", struct.pack(">HH", regs[1], regs[0]))[0]


async def hr(srv, unit, addr, count=1):
    return await srv.client.read_holding_registers(addr, count=count, slave=unit)


async def di(srv, unit, addr, count=1):
    return await srv.client.read_discrete_inputs(addr, count=count, slave=unit)


async def test_ac37_machine_module(modbus, world):
    world.force("workcenters/SLIDE-1/state", 1, hold_s=600)
    world.force("workcenters/SLIDE-1/alarm", 0, hold_s=600)
    world.force("workcenters/SLIDE-1/pieces_out", 70000, hold_s=600)
    rr = await di(modbus, 80, 0, 12)
    assert not rr.isError() and rr.bits[:2] == [True, False]
    assert rr.bits[10:12] == [False, False]  # DI10/DI11 — резерв
    # fc01 дзеркалить DI
    assert (await modbus.client.read_coils(0, count=12, slave=80)).bits[:12] == rr.bits[:12]
    cnt = (await hr(modbus, 80, 0, 2)).registers
    assert cnt == [70000 & 0xFFFF, 70000 >> 16]  # молодше слово першим (little)
    assert u32_little(cnt) == 70000
    assert not (await hr(modbus, 80, 0, 24)).isError()


async def test_ac37_unit_address_errors_and_module_name(modbus):
    rr = await hr(modbus, 200, 0)
    assert rr.isError() and rr.exception_code == 0x0B
    rr = await hr(modbus, 11, 9998)
    assert rr.isError() and rr.exception_code == 0x02
    assert (await hr(modbus, 80, 210)).registers == [0x6050]
    assert (await hr(modbus, 86, 210)).registers == [0x6060]
    assert (await di(modbus, 80, 12, 1)).isError()  # поза 12 DI


async def test_machine_layout_second_machine_and_fault(modbus, world):
    world.force("workcenters/VSAW-1/state", 0, hold_s=600)
    world.force("workcenters/VSAW-1/alarm", 1, hold_s=600)
    bits = (await di(modbus, 80, 0, 12)).bits
    assert bits[3] is True and bits[2] is False  # DI2 в роботі, DI3 аварія -> VSAW-1 m=1


async def test_all_machine_units_present(modbus):
    for u in (80, 81, 82, 83, 84, 85, 86, 90, 96):
        assert u in modbus.units


async def test_counter_clear_and_start_coils(modbus, world):
    world.force("workcenters/SLIDE-1/pieces_out", 100, hold_s=600)
    assert u32_little((await hr(modbus, 80, 0, 2)).registers) == 100
    rr = await modbus.client.write_coil(33, True, slave=80)  # Clear counter k=0 (00034)
    assert not rr.isError()
    assert u32_little((await hr(modbus, 80, 0, 2)).registers) == 0
    world.force("workcenters/SLIDE-1/pieces_out", 130, hold_s=600)
    assert u32_little((await hr(modbus, 80, 0, 2)).registers) == 30
    assert (await modbus.client.read_coils(32, count=1, slave=80)).bits[0] is True  # start=1


async def test_reserved_do_accepted_logged(modbus, world):
    rr = await modbus.client.write_coil(16, True, slave=80)
    assert not rr.isError()
    assert (await modbus.client.read_coils(16, count=6, slave=80)).bits[0] is True
    assert (await hr(modbus, 80, 302)).registers == [1]
    assert world.events.since(0, kind="command")[0]


async def test_do_all_register_write(modbus):
    assert not (await modbus.client.write_register(302, 0b101, slave=80)).isError()
    assert (await modbus.client.read_coils(16, count=6, slave=80)).bits[:3] == [True, False, True]


async def test_dust_and_water_u84(modbus, world):
    world.force("equipment/DUST-1/state", 1, hold_s=600)
    assert (await di(modbus, 84, 0, 2)).bits[:2] == [True, False]
    world.force("equipment/DUST-1/state", 2, hold_s=600)
    assert (await di(modbus, 84, 0, 2)).bits[:2] == [False, True]
    world.force("infra/water/m3_total", 18642.0, hold_s=600)
    regs = (await hr(modbus, 84, 16, 2)).registers
    assert u32_little(regs) == 1864200  # 1 імп = 10 л -> ×0,01 м³
    start = (await modbus.client.read_coils(64, count=1, slave=84)).bits[0]  # 00065
    assert start is True


async def test_spark_and_smoke_u85(modbus, world):
    world.force("fire/spark/SPARK-1/state", 1, hold_s=600)
    world.force("fire/spark/SPARK-1/water_ok", 1, hold_s=600)
    world.force("fire/spark/SPARK-1/count_today", 3, hold_s=600)
    bits = (await di(modbus, 85, 0, 7)).bits
    assert bits[0] and bits[3] and not bits[2]
    assert u32_little((await hr(modbus, 85, 0, 2)).registers) == 3
    rr = await modbus.client.write_coil(16, True, slave=85)  # DO0 «відкрити клапани»
    assert not rr.isError()
    cmds = world.drain("smoke")
    assert cmds and cmds[0]["cmd"] == "open"


async def test_smoke_do_rejected_without_write_accept(modbus, world):
    world.settings = SimpleNamespace(write_accept=False)
    rr = await modbus.client.write_coil(16, True, slave=85)
    assert rr.isError() and rr.exception_code == 0x04
    assert world.drain("smoke") == []


async def test_ac44_gate_open_command(modbus, world):
    rr = await modbus.client.write_coil(16, True, slave=86)  # DO0 = «відкрити» GATE-W
    assert not rr.isError()
    assert world.signals["yard/gates/GATE-W/cmd_open"].value == 1
    posts = world.drain("yard")
    assert posts and posts[0]["kind"] == "gate_cmd" and posts[0]["gate"] == "GATE-W"
    assert posts[0]["cmd"] == "cmd_open" and posts[0]["value"] is True
    assert world.events.since(0, kind="command")[0]
    assert (await modbus.client.read_coils(16, count=6, slave=86)).bits[0] is True
    # FC 06 у регістр лічильника/DI-карти PM5560 -> 0x02
    rr = await modbus.client.write_register(3059, 1, slave=11)
    assert rr.isError() and rr.exception_code == 0x02


async def test_gates_di_layout_and_hold_channels(modbus, world):
    world.force("yard/gates/GATE-E/state", 1, hold_s=600)
    world.force("yard/gates/GATE-W/loop", 1, hold_s=600)
    world.force("yard/gates/GATE-W/passes_today", 7, hold_s=600)
    world.force("yard/gates/GATE-E/passes_today", 6, hold_s=600)
    bits = (await di(modbus, 86, 0, 6)).bits[:6]
    assert bits == [False, True, True, False, False, False]  # DI0 W state, DI1 W loop, DI2 E state
    assert u32_little((await hr(modbus, 86, 2, 2)).registers) == 7  # 40003–40004
    assert u32_little((await hr(modbus, 86, 6, 2)).registers) == 6  # 40007–40008
    # «тримати відкритим»: DO4 лише GATE-W, DO5 лише GATE-E (X-47)
    assert not (await modbus.client.write_coil(20, True, slave=86)).isError()
    assert world.signals["yard/gates/GATE-W/cmd_hold"].value == 1
    assert world.signals["yard/gates/GATE-E/cmd_hold"].value == 0
    assert not (await modbus.client.write_coil(21, True, slave=86)).isError()
    assert world.signals["yard/gates/GATE-E/cmd_hold"].value == 1


async def test_adam6017_raw_and_float(modbus, world):
    world.force("equipment/DUST-1/airflow_m3h", 16000.0, hold_s=600)
    world.force("equipment/SPRINKLERS/pressure_bar", 7.15, hold_s=600)
    raw = (await hr(modbus, 90, 0, 8)).registers
    assert raw[0] == round(65535 * 0.5)
    assert raw[2] == adam6017.raw_of(7.15, 0, 16)
    assert raw[4:] == [0, 0, 0, 0]
    ma = f32_little((await hr(modbus, 90, 30, 2)).registers)
    assert ma == pytest.approx(12.0, abs=1e-4)
    assert (await modbus.client.read_coils(124, count=4, slave=90)).bits[:4] == [True] * 4
    assert (await modbus.client.read_coils(120, count=4, slave=90)).bits[:4] == [False] * 4
    assert (await hr(modbus, 90, 210)).registers == [0x6017]


async def test_adam6015_rtd(modbus, world):
    world.force("energy/transformers/T1/temp_c", 59.1, hold_s=600)
    world.force("energy/transformers/T2/temp_c", 55.6, hold_s=600)
    raw = (await hr(modbus, 96, 0, 7)).registers
    assert raw[0] == adam6015.raw_of(59.1) and max(raw[0:3]) == raw[0]
    assert raw[3] == adam6015.raw_of(55.6)
    assert raw[6] == 0
    assert f32_little((await hr(modbus, 96, 30, 2)).registers) == pytest.approx(59.1, abs=1e-4)
    assert f32_little((await hr(modbus, 96, 36, 2)).registers) == pytest.approx(55.6, abs=1e-4)
    assert (await modbus.client.read_coils(126, count=1, slave=96)).bits[:1] == [True]
