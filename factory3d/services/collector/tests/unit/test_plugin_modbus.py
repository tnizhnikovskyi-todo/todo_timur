"""AC-78, AC-100: плагін modbus_tcp на pymodbus-сервері (R-20, X-46, X-81)."""
from __future__ import annotations

import asyncio

import pytest
from conftest import VirtualClock

from collector.core.errors import PollError, WriteError
from collector.plugins.modbus_tcp import POOL, ModbusTcpPlugin

from . import mk_signal, mk_source

SC_T = 200 / 65535
U70 = [1, 6772, 828, 30, 240, 0, 0, 0, 0, 64, 1630, 0, 0, 0, 0, 0, 0, 0, 0, 0, 17840]


def _fill(h):
    h.slaves[70].setValues(3, 3000, U70)
    h.slaves[96].setValues(3, 0, [35000, 35749, 34000, 33000, 33500, 33200])
    h.slaves[84].setValues(2, 0, [1, 0])
    h.slaves[84].setValues(3, 16, [0x2E2A, 0x001C])
    h.writes.clear()
    h.requests = 0


def _sig(code, address, kind="gauge", **kw):
    return mk_signal(code, kind=kind, address=address, **kw)


def _addr(**kw):
    return {"fc": 3, **kw}


async def _plugin(h, make_ctx, signals, unit=70, clock=None, **params):
    box = make_ctx(clock=clock)
    src = mk_source("M-" + str(unit), "modbus_tcp", signals,
                    params={"host": "127.0.0.1", "port": h.port, "unit": unit, "timeout_s": 0.5, "retries": 0,
                            **params})
    p = ModbusTcpPlugin(src, box.ctx)
    await p.connect()
    return p, box


@pytest.fixture
async def srv(modbus_server):
    from collector.plugins import modbus_tcp

    _fill(modbus_server)
    yield modbus_server
    modbus_tcp.POOL._entries.clear()


def _u70_signals():
    return [
        _sig("equipment/C/pressure", _addr(addr=3001, scale=0.001)),
        _sig("equipment/C/state", _addr(addr=3000, map={"1": "loaded", "0": "off"}), kind="state"),
        _sig("equipment/C/temp", _addr(addr=3002, scale=0.1)),
        _sig("equipment/C/load", _addr(addr=3009)),
        _sig("equipment/C/hours", _addr(addr=3019, type="u32")),
    ]


async def test_block_grouping_one_request(srv, make_ctx):
    p, _ = await _plugin(srv, make_ctx, _u70_signals(), gap_max=10)  # 3010→3019: розрив 9 (SPEC: див. звіт)
    await p.poll(_u70_signals())
    assert srv.requests == 1
    await p.disconnect()


async def test_decode_values(srv, make_ctx):
    sigs = _u70_signals()
    p, _ = await _plugin(srv, make_ctx, sigs, gap_max=10)
    out = {r.code.rsplit("/", 1)[1]: r for r in await p.poll(sigs)}
    assert out["pressure"].value == pytest.approx(6.772)
    assert out["state"].text == "loaded" and out["state"].q == "good"
    assert out["temp"].value == pytest.approx(82.8)
    assert out["load"].value == 64
    assert out["hours"].value == 17840
    assert p.health().state == "online" and p.health().stats["polls"] == 1
    await p.disconnect()


async def test_state_unknown_key_uncertain(srv, make_ctx):
    sg = _sig("equipment/C/st", _addr(addr=3009, map={"1": "x"}), kind="state")
    p, _ = await _plugin(srv, make_ctx, [sg])
    (r,) = await p.poll([sg])
    assert r.text == "64" and r.q == "uncertain"
    await p.disconnect()


async def test_agg_max_rtd(srv, make_ctx):
    t1 = _sig("equipment/T/t1", _addr(addr=0, count=3, agg="max", scale=SC_T, offset=-50))
    t2 = _sig("equipment/T/t2", _addr(addr=3, count=3, agg="min", scale=SC_T, offset=-50))
    p, _ = await _plugin(srv, make_ctx, [t1, t2], unit=96)
    r1, r2 = await p.poll([t1, t2])
    assert r1.value == pytest.approx(59.10, abs=0.01)
    assert r2.value == pytest.approx(33000 * SC_T - 50)
    assert srv.requests == 1  # блок 0…5
    await p.disconnect()


async def test_di_states(srv, make_ctx):
    states = [{"addr": 1, "eq": 1, "text": "fault", "fc": 2}, {"addr": 0, "eq": 1, "text": "running", "fc": 2}]
    sg = _sig("equipment/D/state", {"fc": 2, "states": states}, kind="state")
    p, _ = await _plugin(srv, make_ctx, [sg], unit=84)
    assert (await p.poll([sg]))[0].text == "running"
    srv.slaves[84].setValues(2, 1, [1])
    assert (await p.poll([sg]))[0].text == "fault"
    await p.disconnect()


async def test_water_little_endian(srv, make_ctx):
    sg = _sig("energy/water/m3", _addr(addr=16, type="u32", wordorder="little", scale=0.01))
    p, _ = await _plugin(srv, make_ctx, [sg], unit=84)
    assert (await p.poll([sg]))[0].value == pytest.approx(18468.26)
    await p.disconnect()


async def test_bit_and_bool_coil(srv, make_ctx):
    srv.slaves[70].setValues(3, 10, [0b100])
    srv.slaves[70].setValues(1, 3, [1])
    a = _sig("equipment/C/b2", _addr(addr=10, type="bool", bit=2))
    b = _sig("equipment/C/c3", {"fc": 1, "addr": 3})
    p, _ = await _plugin(srv, make_ctx, [a, b])
    ra, rb = await p.poll([a, b])
    assert ra.value == 1 and rb.value == 1
    await p.disconnect()


async def test_illegal_address(srv, make_ctx):
    sg = _sig("equipment/C/x", _addr(addr=5000))
    p, _ = await _plugin(srv, make_ctx, [sg])
    with pytest.raises(PollError, match="0x02"):
        await p.poll([sg])
    assert p.health().stats["errors"] == 1
    await p.disconnect()


async def test_unknown_unit(srv, make_ctx):
    sg = _sig("equipment/C/x", _addr(addr=3001))
    p, _ = await _plugin(srv, make_ctx, [sg], unit=99)
    with pytest.raises(PollError):
        await p.poll([sg])
    await p.disconnect()


async def test_range_bad(srv, make_ctx):
    sg = _sig("equipment/C/p", _addr(addr=3001, scale=0.001, range=[0, 10]))
    p, _ = await _plugin(srv, make_ctx, [sg])
    assert (await p.poll([sg]))[0].q == "good"
    sg2 = _sig("equipment/C/p2", _addr(addr=3001, scale=0.01, range=[0, 10]))
    (r,) = await p.poll([sg2])
    assert r.q == "bad" and r.value == pytest.approx(67.72)
    await p.disconnect()


async def test_pool_shared(srv, make_ctx):
    sg = _sig("equipment/C/p", _addr(addr=3001))
    p1, box = await _plugin(srv, make_ctx, [sg], unit=70)
    p2, _ = await _plugin(srv, make_ctx, [sg], unit=84)
    assert p1.client is p2.client and len(POOL) == 1
    assert box.allowed == ["127.0.0.1"]
    await p1.disconnect()
    assert len(POOL) == 1
    await p2.disconnect()
    assert len(POOL) == 0


async def test_write_fc6(srv, make_ctx):
    sg = _sig("equipment/C/sp", _addr(addr=3099, scale=0.001, write={"fc": 6, "addr": 3099}), write=True)
    p, _ = await _plugin(srv, make_ctx, [sg])
    assert await p.write(sg, 7.2, None) == "fc6 addr 3099 = 7200"
    assert srv.slaves[70].getValues(3, 3099, 1) == [7200]
    await p.disconnect()


async def test_write_fc16_and_state(srv, make_ctx):
    sg = _sig("equipment/C/sp", _addr(addr=3100, type="u32", write={"fc": 16}), write=True)
    p, _ = await _plugin(srv, make_ctx, [sg])
    assert await p.write(sg, 7000, None) == "fc16 addr 3100 = [0, 7000]"
    st = _sig("equipment/C/m", _addr(addr=3200, map={"3": "run"}, write={"fc": 6}), kind="state", write=True)
    assert (await p.write(st, None, "run")).endswith("= 3")
    with pytest.raises(WriteError):
        await p.write(st, None, "zzz")
    await p.disconnect()


COIL16 = {"fc": 1, "addr": 16, "type": "bool", "write": {"fc": 5, "addr": 16, "pulse_ms": 1500}}


async def test_pulse_write_1_then_0(srv, make_ctx, vclock):
    sg = _sig("yard/gate/open", COIL16, write=True)
    other = _sig("yard/gate/x", _addr(addr=3001))
    p, _ = await _plugin(srv, make_ctx, [sg, other], unit=86)
    t0 = vclock.now()
    res = await p.write(sg, 0.0, None)
    assert res == "fc5 addr 16 pulse 1→0 1500 ms"
    assert [(w[1], w[2], bool(w[3])) for w in srv.writes] == [(5, 16, True), (5, 16, False)]
    assert (srv.writes[1][0] - srv.writes[0][0]).total_seconds() == 1.5 and srv.writes[0][0] == t0
    await p.disconnect()


async def test_poll_during_pulse(srv, make_ctx):
    gate = asyncio.Event()

    class SlowClock(VirtualClock):
        async def sleep(self, s):
            if s >= 1:
                await gate.wait()
            else:
                await super().sleep(s)

    sg = _sig("yard/gate/open", COIL16, write=True)
    other = _sig("yard/gate/x", {"fc": 3, "addr": 3001})
    p, _ = await _plugin(srv, make_ctx, [sg, other], unit=86, clock=SlowClock())
    task = asyncio.create_task(p.write(sg, 1.0, None))
    await asyncio.sleep(0.2)
    assert not task.done()
    assert (await p.poll([other]))[0].code == "yard/gate/x"
    gate.set()
    await task
    await p.disconnect()


async def test_pulse_reset_retry(srv, make_ctx):
    sg = _sig("yard/gate/open", COIL16, write=True)
    p, _ = await _plugin(srv, make_ctx, [sg], unit=86)
    real = p._send
    calls = {"n": 0}

    async def flaky(unit, fc, addr, payload):
        if payload is False:
            calls["n"] += 1
            if calls["n"] <= 2:
                raise WriteError("0x04")
        await real(unit, fc, addr, payload)

    p._send = flaky  # type: ignore[method-assign]
    assert (await p.write(sg, 1.0, None)).startswith("fc5 addr 16 pulse")
    assert calls["n"] == 3
    await p.disconnect()


async def test_pulse_reset_failed(srv, make_ctx):
    sg = _sig("yard/gate/open", COIL16, write=True)
    p, box = await _plugin(srv, make_ctx, [sg], unit=86)
    real = p._send

    async def failing(unit, fc, addr, payload):
        if payload is False:
            raise WriteError("0x04")
        await real(unit, fc, addr, payload)

    p._send = failing  # type: ignore[method-assign]
    with pytest.raises(WriteError, match="pulse reset failed"):
        await p.write(sg, 1.0, None)
    assert box.metrics.modbus_pulse_reset_failed.labels("M-86")._value.get() == 1
    await p.disconnect()


async def test_pulse_first_write_fails_still_resets(srv, make_ctx):
    sg = _sig("yard/gate/open", COIL16, write=True)
    p, _ = await _plugin(srv, make_ctx, [sg], unit=86)
    srv.fail_writes(1)
    with pytest.raises(WriteError, match="0x04"):
        await p.write(sg, 1.0, None)
    assert [bool(w[3]) for w in srv.writes] == [False]
    await p.disconnect()


async def test_pulse_reset_on_cancel(srv, make_ctx):
    class HangClock(VirtualClock):
        async def sleep(self, s):
            if s >= 1:
                await asyncio.Event().wait()
            await super().sleep(s)

    sg = _sig("yard/gate/open", COIL16, write=True)
    p, _ = await _plugin(srv, make_ctx, [sg], unit=86, clock=HangClock())
    task = asyncio.create_task(p.write(sg, 1.0, None))
    await asyncio.sleep(0.3)
    assert srv.slaves[86].getValues(1, 16, 1) == [1]
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert srv.slaves[86].getValues(1, 16, 1) == [0]
    await p.disconnect()


async def test_level_write_no_reset(srv, make_ctx, vclock):
    sg = _sig("yard/gate/hold", {"fc": 1, "addr": 20, "type": "bool", "write": {"fc": 5, "addr": 20}}, write=True)
    p, _ = await _plugin(srv, make_ctx, [sg], unit=86)
    assert await p.write(sg, 1.0, None) == "fc5 addr 20 = True"
    vclock.advance(10)
    assert [(w[1], w[2], bool(w[3])) for w in srv.writes] == [(5, 20, True)]
    assert srv.slaves[86].getValues(1, 20, 1) == [1]
    assert await p.write(sg, 0.0, None) == "fc5 addr 20 = False"
    assert srv.slaves[86].getValues(1, 20, 1) == [0]
    await p.disconnect()


def test_validate_ok_and_errors():
    good = mk_source("M", "modbus_tcp", [_sig("equipment/a/b", {"fc": 3, "addr": 1, "range": [0, 10]})],
                     params={"host": "iot-sim", "unit": 70})
    assert ModbusTcpPlugin.validate(good) == []
    bad = mk_source("M", "modbus_tcp", [
        _sig("equipment/a/b", {"fc": 3, "addr": 70000}),
        _sig("equipment/a/c", {"fc": 1, "addr": 1, "type": "u16"}),
        _sig("equipment/a/d", {"fc": 3, "addr": 1, "write": {"fc": 16, "addr": 1, "pulse_ms": 500}}),
        _sig("equipment/a/e", {"fc": 3, "addr": 1, "range": [5, 1]}),
        _sig("equipment/a/g", {"fc": 3, "addr": 1, "_x": 1}),
        _sig("equipment/a/f", {}),
    ], params={"unit": 70, "token": "x"})
    text = "\n".join(ModbusTcpPlugin.validate(bad))
    assert "host" in text and "секрети" in text and "70000" in text
    assert "equipment/a/c" in text and "pulse_ms" in text and "range" in text and "_x" in text
    assert "equipment/a/f" not in text
