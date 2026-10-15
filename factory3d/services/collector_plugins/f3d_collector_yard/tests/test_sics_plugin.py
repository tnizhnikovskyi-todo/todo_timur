"""AC-50…AC-52: SicsPlugin проти FakeSicsServer (SPEC §8.3, §8.6, §8.7)."""

from __future__ import annotations

import asyncio

import pytest
from conftest import make_ctx, make_signal, make_source

from collector.core.errors import AllowlistDenied, NotSupported, PollError, WriteError
from f3d_collector_yard.sics import SicsPlugin

W, S = make_signal("weight"), make_signal("stable")


async def _plugin(server, ctx=None, signals=(W, S), **params):
    plugin = SicsPlugin(make_source(server.port, signals, **params), ctx or make_ctx())
    await plugin.connect()
    return plugin


async def _wait_frames(plugin, n=1):
    for _ in range(100):
        if plugin.frames >= n:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("кадри не надійшли")


async def test_poll_mode_returns_weight_and_stable(fake_sics):
    server = await fake_sics()
    plugin = await _plugin(server, mode="poll")
    try:
        readings = await plugin.poll([W, S])
        assert [(r.value, r.q) for r in readings] == [(21380.0, "good"), (1.0, "good")]
        assert "SI" in server.received and "SIR" not in server.received
        assert plugin.health().state == "online"
    finally:
        await plugin.disconnect()


async def test_stream_mode_returns_latest_then_empty(fake_sics):
    server = await fake_sics(rate_hz=1)
    plugin = await _plugin(server)
    try:
        await _wait_frames(plugin)
        assert "SIR" in server.received
        readings = await plugin.poll([W, S])
        assert [r.value for r in readings] == [21380.0, 1.0]
        assert await plugin.poll([W, S]) == []
    finally:
        await plugin.disconnect()


async def test_reset_reads_device_and_tolerates_es(fake_sics):
    server = await fake_sics()
    plugin = await _plugin(server, mode="poll")
    assert plugin.health().stats["device"] == "FAKE-0001"
    assert server.received[0] == "@"
    await plugin.disconnect()
    server = await fake_sics(support_reset=False)
    plugin = await _plugin(server, mode="poll")
    try:
        assert plugin.health().stats["device"] is None
        assert (await plugin.poll([W]))[0].value == 21380.0
    finally:
        await plugin.disconnect()


async def test_poll_timeout_raises_and_three_errors_give_error_health(fake_sics):
    server = await fake_sics(reply_delay_s=10)
    plugin = await _plugin(server, mode="poll", reset_on_connect=False, timeout_s=0.5)
    try:
        with pytest.raises(PollError):
            await plugin.poll([W])
        for _ in range(2):
            with pytest.raises(PollError):
                await plugin.poll([W])
        assert plugin.health().state == "error"
    finally:
        await plugin.disconnect()


async def test_stream_drop_raises_and_reconnect_recovers(fake_sics):
    server = await fake_sics(drop_after=3, rate_hz=50)
    plugin = await _plugin(server)
    try:
        await asyncio.sleep(0.3)
        with pytest.raises(PollError):
            await plugin.poll([W])
        server.drop_after = None
        await plugin.disconnect()
        await plugin.connect()
        await _wait_frames(plugin, 4)
        assert (await plugin.poll([W]))[0].value == 21380.0
        assert plugin.reconnects == 1
    finally:
        await plugin.disconnect()


async def test_allowlist_denied_before_connect(fake_sics):
    server = await fake_sics()
    plugin = SicsPlugin(make_source(server.port), make_ctx(deny=True))
    with pytest.raises(AllowlistDenied):
        await plugin.connect()
    assert server.received == []


async def test_write_z_in_stream_resends_sir(fake_sics):
    server = await fake_sics(rate_hz=5)
    sig = make_signal("weight", write="Z")
    plugin = await _plugin(server, signals=(sig,))
    try:
        assert await plugin.write(sig, 1.0, None) == "Z A"
        await asyncio.sleep(0.05)
        i = server.received.index("Z")
        assert server.received[i + 1] == "SIR"
    finally:
        await plugin.disconnect()


async def test_write_t_and_tac_and_errors(fake_sics):
    server = await fake_sics([("S", 14000.0, "kg")], es_on=())
    plugin = await _plugin(server, mode="poll", signals=())
    try:
        assert (await plugin.write(make_signal("weight", write="T"), 1, None)).startswith("T S 14000")
        assert await plugin.write(make_signal("weight", write="TAC"), 1, None) == "TAC A"
        bad = make_signal("weight")
        bad.address["write"] = {"cmd": "TA"}
        with pytest.raises(NotSupported):
            await plugin.write(bad, 1, None)
        plugin.ctx.settings.write_enabled = False
        with pytest.raises(WriteError):
            await plugin.write(make_signal("weight", write="Z"), 1, None)
    finally:
        await plugin.disconnect()


async def test_write_tac_es_raises(fake_sics):
    server = await fake_sics(rate_hz=5, es_on=("TAC",))
    sig = make_signal("weight", write="TAC")
    plugin = await _plugin(server, signals=(sig,))
    try:
        with pytest.raises(WriteError, match="ES"):
            await plugin.write(sig, 1, None)
    finally:
        await plugin.disconnect()


def test_validate_schemas():
    def src(params, *addresses):
        sigs = [make_signal("weight", address=addr, code="yard/scale/T/s%d" % i) for i, addr in enumerate(addresses)]
        source = make_source(1, sigs)
        source.params.clear()
        source.params.update(params)
        return source

    ok_params = {"host": "iot-sim", "port": 4001, "mode": "stream", "period_s": 1, "timeout_s": 5, "unit": "kg"}
    good = src(
        ok_params,
        {"cmd": "SI", "field": "weight", "doc": "x"},
        {"field": "stable"},
        {"field": "weight", "scale": 0.001, "offset": 0},
        {"field": "weight", "write": {"cmd": "Z"}},
    )
    assert SicsPlugin.validate(good) == []
    for addr in (
        {"field": "weight", "write": {"cmd": "TA"}},
        {"field": "weight", "scale": 0},
        {"field": "weight", "extra": 1},
        {"cmd": "SI"},
    ):
        assert SicsPlugin.validate(src(ok_params, addr)), addr
    no_host = src(ok_params)
    del no_host.params["host"]
    assert SicsPlugin.validate(no_host)
    bad = src(ok_params)
    bad.params["unknown"] = 1
    assert SicsPlugin.validate(bad)
