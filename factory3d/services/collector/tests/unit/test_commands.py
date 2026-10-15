"""AC-75, AC-95: цикл команд."""
from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from conftest import TOKEN

from collector.core.commands import CommandLoop
from collector.core.errors import WriteError
from collector.core.metrics import Metrics
from collector.core.odoo_client import OdooClient, flush_results
from collector.core.registry import Registry
from collector.util.timeutil import to_iso_z

from . import FakePlugin, sig_json, src_json

WR = "equipment/X/cmd"
RO = "equipment/X/ro"


@pytest.fixture(autouse=True)
def _reset():
    FakePlugin.instances = []


@pytest_asyncio.fixture
async def env(fake_odoo, settings, vclock, buffer):
    fake_odoo.config = {"read_enabled": True, "write_enabled": True, "sources": [
        src_json("S", write=True, signals=[sig_json(WR, write=True), sig_json(RO, write=False),
                                           sig_json("equipment/X/pulse", write=True,
                                                    address={"write": {"pulse_ms": 5000}})])]}
    fake_odoo.write_enabled = True
    settings.write_enabled = True
    client = OdooClient(fake_odoo.url, TOKEN, collector="COL-T", clock=vclock)
    reg = Registry(client, settings, lambda s: None, vclock, Metrics(vclock), plugin_classes={"fake": FakePlugin})
    await reg.load()
    loop = CommandLoop(client, reg, buffer, settings, clock=vclock, call_timeout_s=0.05)
    yield type("Env", (), {"loop": loop, "plugin": reg.plugins["S"], "odoo": fake_odoo, "client": client,
                           "buffer": buffer, "vclock": vclock, "reg": reg})
    await client.close()


def _cmd(env, code=WR, cid=1, payload=None, expires=3600, value=1.0, text=None):
    return {"id": cid, "code": code, "source": "S", "value": value, "text": text, "payload": payload,
            "requested_at": to_iso_z(env.vclock.now()), "expires_at": to_iso_z(env.vclock.now() + timedelta(seconds=expires)),
            "address": {}}


def _results(env):
    return [r for c in env.odoo.calls if c[1].endswith("/commands/result") for r in c[2]["results"]]


def _gets(env):
    return [c for c in env.odoo.calls if c[0] == "GET" and c[1].endswith("/commands")]


async def test_write_disabled_no_poll(env, settings):
    settings.write_enabled = False
    env.odoo.commands = [_cmd(env)]
    for _ in range(6):
        await env.loop.poll_once()
        env.vclock.advance(5)
    assert not _gets(env) and not env.plugin.writes


async def test_write_done(env):
    env.odoo.commands = [_cmd(env, value=2.0, text="VEL")]
    await env.loop.poll_once()
    assert env.plugin.writes == [(WR, 2.0, "VEL")]
    res = _results(env)
    assert len(res) == 1 and res[0]["state"] == "done" and res[0]["result"] == "ok" and res[0]["data"] is None
    assert await env.buffer.count_results() == 0


async def test_odoo_write_disabled_skips_write(env):
    env.odoo.write_enabled = False
    env.odoo.commands = [_cmd(env)]
    await env.loop.poll_once()
    assert not env.plugin.writes and not _results(env)


async def test_signal_write_disabled(env):
    env.odoo.commands = [_cmd(env, code=RO)]
    await env.loop.poll_once()
    assert _results(env)[0]["error"] == "signal write disabled" and not env.plugin.writes


async def test_expired(env):
    env.odoo.commands = [_cmd(env, expires=-1)]
    await env.loop.poll_once()
    assert _results(env)[0] == {**_results(env)[0], "state": "failed", "error": "expired"}
    assert not env.plugin.writes


async def test_write_error(env):
    env.plugin.write_exc = WriteError("WriteAccessDenied")
    env.odoo.commands = [_cmd(env)]
    await env.loop.poll_once()
    assert _results(env)[0]["state"] == "failed" and _results(env)[0]["error"] == "WriteAccessDenied"


async def test_write_timeout(env):
    env.plugin.hang = True
    env.odoo.commands = [_cmd(env)]
    await env.loop.poll_once()
    assert _results(env)[0]["error"] == "timeout"


async def test_timeout_includes_pulse(env, monkeypatch):
    import asyncio

    seen = []
    orig = asyncio.wait_for

    async def spy(aw, timeout):
        seen.append(timeout)
        return await orig(aw, timeout)

    monkeypatch.setattr("collector.core.commands.asyncio.wait_for", spy)
    env.odoo.commands = [_cmd(env, code="equipment/X/pulse")]
    await env.loop.poll_once()
    assert seen == [pytest.approx(0.05 + 5.0)]


async def test_results_buffered(env):
    env.odoo.down = True
    cmds = (_cmd(env),)
    from collector.core.types import Command
    from collector.util.timeutil import parse_iso

    cmd = Command(id=1, code=WR, source="S", value=1.0, text=None, address={},
                  expires_at=parse_iso(cmds[0]["expires_at"]))
    await env.loop.process(cmd)
    assert await flush_results(env.client, env.buffer) == 0
    assert await env.buffer.count_results() == 1
    env.odoo.down = False
    assert await flush_results(env.client, env.buffer) == 1
    assert await env.buffer.count_results() == 0 and _results(env)[-1]["state"] == "done"


async def test_payload_calls_call_not_write(env):
    env.plugin.call_result = {"ReturnStatus": 0}
    payload = {"method": "Stop", "job": "WO00013"}
    env.odoo.commands = [_cmd(env, payload=payload)]
    await env.loop.poll_once()
    assert env.plugin.calls == [(WR, payload)] and env.plugin.writes == []
    res = _results(env)[0]
    assert res["state"] == "done" and res["data"] == {"ReturnStatus": 0} and res["result"] == '{"ReturnStatus": 0}'


async def test_call_not_supported(env):
    env.plugin.call_supported = False
    env.odoo.commands = [_cmd(env, payload={"m": 1})]
    await env.loop.poll_once()
    assert _results(env)[0]["error"] == "call not supported by fake" and not env.plugin.writes


@pytest.mark.parametrize("bad", [[1, 2], {"x": "a" * 70_000}, {"x": {1, 2}}])
async def test_call_invalid_data(env, bad):
    env.plugin.call_result = bad
    env.odoo.commands = [_cmd(env, payload={"m": 1})]
    await env.loop.poll_once()
    assert _results(env)[0]["state"] == "failed" and _results(env)[0]["error"] == "call returned invalid data"


async def test_call_timeout(env):
    env.plugin.hang = True
    env.odoo.commands = [_cmd(env, payload={"m": 1})]
    await env.loop.poll_once()
    assert _results(env)[0]["error"] == "timeout"
