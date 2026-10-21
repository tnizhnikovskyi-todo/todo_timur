"""td_chp §8 (AC-24, AC-25): нова карта КГУ по Modbus TCP — блоки, команда пуску ``ctl/cmd``, уставки, винятки."""

import pytest

CMD, ACK, REASON, STATE, MODE, SP, COS = 40900, 40901, 40902, 40000, 40903, 40904, 40905
HOURS, CYL_T = 40120, 40800


async def hr(srv, addr, count=1):
    rr = await srv.client.read_holding_registers(addr, count=count, slave=72)
    assert not rr.isError(), (addr, rr)
    return rr.registers


async def write(srv, addr, value):
    return await srv.client.write_register(addr, value, slave=72)


async def test_new_registers_are_readable(modbus, world):
    world.step(1)
    assert await hr(modbus, STATE) == [0]
    assert await hr(modbus, MODE) == [4] and await hr(modbus, SP) == [80] and await hr(modbus, COS) == [98]
    hours = await hr(modbus, HOURS, 2)
    assert (hours[0] << 16 | hours[1]) == 184000  # 18400,0 год × 10
    assert len(await hr(modbus, CYL_T, 16)) == 16  # температури 16 циліндрів одним блоком
    assert len(await hr(modbus, 40100, 17)) == 17  # двигун: суцільний блок 40100…40116


async def test_start_command_over_modbus_runs_nine_steps(modbus, world):
    world.step(1)
    rr = await write(modbus, CMD, 1)
    assert not rr.isError()
    assert await hr(modbus, ACK) == [0]  # нова команда скидає ack до виконання
    world.advance(1)
    assert await hr(modbus, ACK) == [1] and await hr(modbus, CMD) == [0]
    assert await hr(modbus, STATE) == [1] and await hr(modbus, 40908) == [1]  # ctl/step
    world.advance(65)
    assert await hr(modbus, STATE) == [2] and await hr(modbus, 40908) == [0]
    assert (await hr(modbus, 40001))[0] == pytest.approx(400, abs=5)  # P ел., кВт (старий регістр)


async def test_refused_command_has_reason(modbus, world):
    world.step(1)
    world.set_flag("gas_bar", 1.15)
    await write(modbus, CMD, 1)
    world.advance(1)
    assert await hr(modbus, ACK) == [2] and await hr(modbus, REASON) == [2]


async def test_setpoints_and_exceptions(modbus, world):
    world.step(1)
    assert not (await write(modbus, MODE, 3)).isError()
    assert not (await write(modbus, SP, 65)).isError()
    assert not (await write(modbus, COS, 95)).isError()
    assert (await hr(modbus, MODE), await hr(modbus, SP), await hr(modbus, COS)) == ([3], [65], [95])
    for addr, bad in ((MODE, 5), (SP, 40), (COS, 80), (CMD, 9)):
        rr = await write(modbus, addr, bad)
        assert rr.isError() and rr.exception_code == 3, addr
    rr = await write(modbus, ACK, 1)  # RO-регістр
    assert rr.isError() and rr.exception_code == 2
