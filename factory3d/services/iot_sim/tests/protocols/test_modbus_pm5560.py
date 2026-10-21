"""P-05 PM5560 (SPEC §8.7.1): PDU-адреси, F32/INT64 big, службові регістри, винятки (AC-03, AC-37, AC-44)."""

import struct

import pytest
from iot_sim.protocols.modbus_maps import pm5560


def f32(regs):
    return struct.unpack(">f", struct.pack(">HH", *regs))[0]


def i64(regs):
    v = 0
    for r in regs:
        v = (v << 16) | r
    return v - (1 << 64) if v >= 1 << 63 else v


def text(regs):
    return b"".join(r.to_bytes(2, "big") for r in regs).rstrip(b"\0").decode()


async def hr(srv, unit, addr, count=1, fc=3):
    fn = srv.client.read_holding_registers if fc == 3 else srv.client.read_input_registers
    return await fn(addr, count=count, slave=unit)


async def test_ac03_active_power_total(modbus, world):
    world.force("energy/consumers/SAW-1/p_now", 12.18, hold_s=600)
    rr = await hr(modbus, 11, 3059, 2)
    assert not rr.isError()
    assert f32(rr.registers) == pytest.approx(12.18, abs=0.01)
    # fc04 — дзеркало fc03
    assert (await hr(modbus, 11, 3059, 2, fc=4)).registers == rr.registers


async def test_pdu_not_document_number(modbus, world):
    """Адреса 3060 (номер документа) — вже сусідній регістр: старше слово виходить зсунутим."""
    world.force("energy/consumers/SAW-1/p_now", 12.18, hold_s=600)
    good = (await hr(modbus, 11, 3059, 2)).registers
    shifted = (await hr(modbus, 11, 3060, 2)).registers
    assert shifted[0] == good[1] and shifted != good


async def test_energy_int64_wh(modbus, world):
    world.force("energy/consumers/SAW-1/kwh_total", 1234.567, hold_s=600)
    rr = await hr(modbus, 11, 3203, 4)
    assert i64(rr.registers) == 1234567
    assert f32((await hr(modbus, 11, 2699, 2)).registers) == pytest.approx(1234.567, rel=1e-5)
    assert i64((await hr(modbus, 11, 3211, 4)).registers) == 1234567


async def test_identity_registers(modbus):
    assert text((await hr(modbus, 11, 29, 20)).registers) == "PM-SAW-1"
    assert text((await hr(modbus, 1, 29, 20)).registers) == "PM-Q1"
    assert text((await hr(modbus, 11, 49, 20)).registers) == "PM5560"
    assert text((await hr(modbus, 11, 69, 20)).registers) == "Schneider Electric"
    serial = (await hr(modbus, 12, 129, 2)).registers
    assert (serial[0] << 16 | serial[1]) == 2026000012
    assert (await hr(modbus, 11, 1636, 3)).registers == [2, 7, 4]
    assert (await hr(modbus, 1, 2028, 2)).registers == [1600, 5]
    assert (await hr(modbus, 11, 2028, 2)).registers == [100, 5]


async def test_derived_electricals(modbus, world):
    world.force("energy/consumers/SAW-1/p_now", 12.0, hold_s=600)
    p = f32((await hr(modbus, 11, 3059, 2)).registers)
    s = f32((await hr(modbus, 11, 3075, 2)).registers)
    assert s >= p > 0
    ia = f32((await hr(modbus, 11, 2999, 2)).registers)
    assert ia == pytest.approx(s * 1000 / (3**0.5 * 400), rel=1e-4)
    assert f32((await hr(modbus, 11, 3109, 2)).registers) == pytest.approx(50.0)
    assert f32((await hr(modbus, 11, 3019, 2)).registers) == pytest.approx(400.0)


async def test_breaker_state_feeders_only(modbus, world):
    world.force("energy/cells/Q1/state", 2, hold_s=600)
    assert (await hr(modbus, 1, 2017)).registers == [2]
    assert (await hr(modbus, 11, 2017)).isError()


async def test_unknown_unit_and_address(modbus):
    rr = await hr(modbus, 200, 3059, 2)
    assert rr.isError() and rr.exception_code == 0x0B
    rr = await hr(modbus, 11, 9998, 2)
    assert rr.isError() and rr.exception_code == 0x02


async def test_ac44_write_to_readonly_is_02(modbus):
    rr = await modbus.client.write_register(3059, 1, slave=11)
    assert rr.isError() and rr.exception_code == 0x02
    rr = await modbus.client.write_registers(3059, [1, 2], slave=11)
    assert rr.isError() and rr.exception_code == 0x02


async def test_command_semaphore_and_reset(modbus, world):
    rr = await modbus.client.write_register(5679, 2020, slave=21)
    assert not rr.isError()
    assert (await hr(modbus, 21, 5679)).registers == [2020]
    assert world.drain("meter") == [{"unit": 21, "cmd": "reset_energy"}]
    assert world.events.since(0, kind="command")[0]


async def test_all_meter_units_respond(modbus):
    assert set(pm5560.UNITS) <= set(modbus.units)
    assert len(pm5560.UNITS) == 8 + 49
    for u in (1, 8, 11, 59):
        assert not (await hr(modbus, u, 3059, 2)).isError()
    for u in (9, 10, 60):
        assert (await hr(modbus, u, 3059, 2)).exception_code == 0x0B


async def test_incomer_registers_carry_net_power_with_chp(modbus, world):
    """Регресія: u1/u2 PDU 3059 — потужність вводу Q1/Q2 (з СЕС/КГУ), а не навантаження секції (T1/T2 p_kw мають ту ж
    адресу в каталозі). КГУ запущено: Odoo бачить імпорт, зменшений на його потужність."""
    from iot_sim.models.meter import ALL_CONSUMERS

    for c in ALL_CONSUMERS:
        world.force(f"energy/consumers/{c}/p_now", 0.0, hold_s=3600)
    world.force("energy/consumers/GANTRY-1/p_now", 300.0, hold_s=3600)  # секція 1
    world.force("energy/consumers/SAW-1/p_now", 326.0, hold_s=3600)  # секція 2
    world.force("infra/totals/pv_now", 0.0, hold_s=3600)
    world.set_flag("bess_auto_idle", True)
    world.advance(10)
    q1 = f32((await hr(modbus, 1, 3059, 2)).registers)
    q2 = f32((await hr(modbus, 2, 3059, 2)).registers)
    assert (q1, q2) == (pytest.approx(300.0), pytest.approx(326.0))  # КГУ в резерві
    world.set_flag("chp_run", True)
    world.advance(100)
    chp = world.signals["infra/totals/chp_kw"].value
    assert chp > 300
    q1 = f32((await hr(modbus, 1, 3059, 2)).registers)
    q2 = f32((await hr(modbus, 2, 3059, 2)).registers)
    assert q1 == pytest.approx(300.0) and q2 == pytest.approx(326.0 - chp, abs=0.01)
    assert q2 == pytest.approx(world.signals["energy/cells/Q2/p_now"].value, abs=0.01)
    assert q1 + q2 == pytest.approx(626.0 - chp, abs=0.01)
