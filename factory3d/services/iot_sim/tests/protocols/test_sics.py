"""P-11: автоваги, SICS по TCP (SPEC §8.13.3)."""
import asyncio

import pytest

from iot_sim.protocols.sics_server import SicsServer


@pytest.fixture
async def scale(world, port):
    srv = SicsServer(world, port=port, host="127.0.0.1", stable_wait_s=0.3, stream_period_s=0.05)
    await srv.start()
    srv.world_ = world
    yield srv
    await srv.stop()


async def ask(srv, *cmds):
    r, w = await asyncio.open_connection("127.0.0.1", srv.port)
    out = []
    for c in cmds:
        w.write(c.encode() + b"\r\n")
        await w.drain()
        out.append((await asyncio.wait_for(r.readline(), 2)).decode().rstrip("\r\n"))
    w.close()
    return out


def set_scale(world, weight, stable=True):
    sigs = world.devices["TRUCK-SCALE"].signals
    sigs["weight_kg"].force(weight, world.now())
    sigs["stable"].force(1 if stable else 0, world.now())


async def test_stable_weight_format(scale):
    set_scale(scale.world, 21380)
    s, si = await ask(scale, "S", "SI")
    assert s == "S S      21380 kg" and si == s
    assert len(s.split("S S ")[1].removesuffix(" kg")) == 10  # 10 символів праворуч


async def test_discretization_20kg(scale):
    set_scale(scale.world, 21389)
    assert (await ask(scale, "SI"))[0] == "S S      21380 kg"


async def test_dynamic_and_unstable_S(scale):
    set_scale(scale.world, 18000, stable=False)
    si, s = await ask(scale, "SI", "S")
    assert si == "S D      18000 kg" and s == "S I"  # чекає ≤ stable_wait і здається


async def test_S_waits_for_stabilisation(scale):
    set_scale(scale.world, 18000, stable=False)
    asyncio.get_running_loop().call_later(0.1, set_scale, scale.world, 18000, True)
    assert (await ask(scale, "S"))[0] == "S S      18000 kg"


async def test_overload_and_underload(scale):
    set_scale(scale.world, 61000)
    assert (await ask(scale, "S", "SI")) == ["S +", "S +"]
    set_scale(scale.world, -500)
    assert (await ask(scale, "S"))[0] == "S -"


async def test_zero_only_without_truck(scale):
    set_scale(scale.world, 14000)
    assert (await ask(scale, "Z"))[0] == "Z I"
    set_scale(scale.world, 20)
    assert (await ask(scale, "Z"))[0] == "Z A"
    assert (await ask(scale, "ZI"))[0] == "ZI S"


async def test_tare(scale):
    set_scale(scale.world, 14000)
    t, ta = await ask(scale, "T", "TA")
    assert t == "T S      14000 kg" and ta == "TA A      14000 kg"
    assert (await ask(scale, "TA 5000 kg"))[0] == "TA I"  # запис без write_accept
    set_scale(scale.world, 14000, stable=False)
    assert (await ask(scale, "TI"))[0] == "TI D      14000 kg"


async def test_tare_write_when_accepted(world, port):
    srv = SicsServer(world, port=port, host="127.0.0.1", write_accept=True)
    await srv.start()
    try:
        assert (await ask(srv, "TA 5000 kg"))[0] == "TA A       5000 kg"
    finally:
        await srv.stop()


async def test_identification_and_errors(scale):
    out = await ask(scale, "I0", "I1", "I2", "I3", "I4", "@", "BOGUS", "i4")
    assert out[0] == 'I0 B 0 "I0"' and out[1] == 'I1 A "01" "2.30"'
    assert out[2] == 'I2 A "AKSIS 60-18 (sim) 60000 kg"' and out[3] == 'I3 A "sim-0.1"'
    assert out[4] == out[5] == out[7] == 'I4 A "AX2026-0001"'
    assert out[6] == "ES"


async def test_sir_stream_until_next_command(scale):
    set_scale(scale.world, 21380)
    r, w = await asyncio.open_connection("127.0.0.1", scale.port)
    w.write(b"SIR\r\n")
    await w.drain()
    lines = [(await asyncio.wait_for(r.readline(), 2)).decode().rstrip() for _ in range(3)]
    assert lines == ["S S      21380 kg"] * 3
    set_scale(scale.world, 21380, stable=False)
    w.write(b"I4\r\n")
    await w.drain()
    for _ in range(10):  # потік може встигнути ще кадри до обробки команди
        line = (await asyncio.wait_for(r.readline(), 2)).decode().rstrip()
        if line.startswith("I4"):
            break
    assert line == 'I4 A "AX2026-0001"'
    await asyncio.sleep(0.2)
    assert not r._buffer  # після іншої команди потік зупинено
    w.close()
