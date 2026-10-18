"""AC-238: CommandLoop.write_direct / read_now (C-40): запобіжники, таймаут, без буфера результатів."""

from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from conftest import TOKEN

from collector.core.commands import CommandLoop
from collector.core.errors import WriteError, WriteRefused
from collector.core.live import LiveCache
from collector.core.metrics import Metrics
from collector.core.odoo_client import OdooClient
from collector.core.registry import Registry

from . import FakePlugin, reading, sig_json, src_json

WR = "equipment/X/cmd"
RO = "equipment/X/ro"
SC = "equipment/X/scaled"


@pytest.fixture(autouse=True)
def _reset():
    FakePlugin.instances = []


@pytest_asyncio.fixture
async def env(fake_odoo, settings, vclock, buffer):
    fake_odoo.config = {
        "read_enabled": True,
        "write_enabled": True,
        "sources": [
            src_json(
                "S",
                write=True,
                signals=[
                    sig_json(WR, write=True),
                    sig_json(RO, write=False),
                    sig_json(SC, scale=0.1),
                    sig_json("equipment/X/pulse", write=True, address={"write": {"pulse_ms": 5000}}),
                ],
            ),
            src_json("RW", write=False, signals=[sig_json("equipment/Y/cmd", write=True)]),
        ],
    }
    settings.write_enabled = True
    client = OdooClient(fake_odoo.url, TOKEN, collector="COL-T", clock=vclock)
    reg = Registry(client, settings, lambda s: None, vclock, Metrics(vclock), plugin_classes={"fake": FakePlugin})
    await reg.load()
    live = LiveCache(vclock)
    loop = CommandLoop(client, reg, buffer, settings, clock=vclock, call_timeout_s=0.05, live=live)
    yield type(
        "Env",
        (),
        {
            "loop": loop,
            "plugin": reg.plugins["S"],
            "reg": reg,
            "live": live,
            "buffer": buffer,
            "vclock": vclock,
            "settings": settings,
        },
    )
    await client.close()


async def test_write_ok_no_buffer(env):
    assert await env.loop.write_direct(WR, 2.0, "VEL") == "ok"
    assert env.plugin.writes == [(WR, 2.0, "VEL")]
    assert await env.buffer.count_results() == 0  # результат у буфер не потрапляє


async def test_refusals(env):
    cases = [
        ("equipment/none", "unknown signal"),
        (RO, "signal write disabled"),
        ("equipment/Y/cmd", "source write disabled"),
    ]
    for code, part in cases:
        with pytest.raises(WriteRefused) as e:
            await env.loop.write_direct(code, 1.0)
        assert part in e.value.reason, code
    env.reg.write_enabled = False
    with pytest.raises(WriteRefused, match="registry"):
        await env.loop.write_direct(WR, 1.0)
    env.reg.write_enabled = True
    env.settings.write_enabled = False
    with pytest.raises(WriteRefused, match="F3D_WRITE_ENABLED"):
        await env.loop.write_direct(WR, 1.0)
    assert not env.plugin.writes


async def test_expires_at(env):
    past = env.vclock.now() - timedelta(seconds=1)
    with pytest.raises(WriteRefused, match="expired"):
        await env.loop.write_direct(WR, 1.0, expires_at=past)
    future = env.vclock.now() + timedelta(seconds=30)
    assert await env.loop.write_direct(WR, 1.0, expires_at=future) == "ok"


async def test_timeout_and_plugin_error(env):
    env.plugin.hang = True
    with pytest.raises(WriteError, match="timeout"):
        await env.loop.write_direct(WR, 1.0)
    env.plugin.hang = False
    env.plugin.write_exc = WriteError("device refused")
    with pytest.raises(WriteError, match="device refused"):
        await env.loop.write_direct(WR, 1.0)


async def test_read_now_scales_and_updates_live(env):
    env.plugin.script = [[reading(SC, 20.0)]]
    got = await env.loop.read_now(SC)
    assert got is not None and got.value == pytest.approx(2.0)  # масштаб ядра
    assert env.live.get(SC).value == pytest.approx(2.0)
    assert env.plugin.polls == [[SC]]
    assert await env.buffer.count() == 0  # без запису в буфер показань


async def test_read_now_failures(env):
    assert await env.loop.read_now("equipment/none") is None
    env.plugin.script = [WriteError("boom")]
    assert await env.loop.read_now(WR) is None
    env.plugin.script = [[]]
    assert await env.loop.read_now(WR) is None
