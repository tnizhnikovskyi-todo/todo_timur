"""AC-70, AC-71: подписки DataChange, JobOrderList, серцебиття, спільна сесія."""

from __future__ import annotations

from conftest import until


def last(ctx, code: str):
    found = [r for r in ctx.emitted if r.code == code]
    return found[-1] if found else None


async def test_initial_values(ctx, opcua_plugin):
    await until(lambda: all(last(ctx, f"workcenters/SAW-T/{n}") for n in ("state", "mode", "alarm", "pieces_out")))
    state = last(ctx, "workcenters/SAW-T/state")
    assert (state.value, state.text, state.q) == (3.0, "WORKING", "good")
    assert last(ctx, "workcenters/SAW-T/mode").text == "AUTOMATIC"
    alarm = last(ctx, "workcenters/SAW-T/alarm")
    assert (alarm.value, alarm.text) == (0.0, "off")
    pieces = last(ctx, "workcenters/SAW-T/pieces_out")
    assert pieces.value == 0.0 and pieces.text is None


async def test_change_emits(ctx, ua_server, opcua_plugin, vclock):
    await until(lambda: last(ctx, "workcenters/SAW-T/state"))
    before = len(ctx.emitted)
    stamp = vclock.now()
    await ua_server.set("CurrentState", 4)
    await until(lambda: last(ctx, "workcenters/SAW-T/state").text == "ERROR", timeout=2)
    reading = last(ctx, "workcenters/SAW-T/state")
    assert reading.value == 4.0
    assert reading.ts == stamp  # SourceTimestamp сервера
    assert len(ctx.emitted) > before
    await ua_server.set("Alarm", True)
    await until(lambda: last(ctx, "workcenters/SAW-T/alarm").text == "on", timeout=2)


async def test_job_select_running_or_first(ctx, ua_server, opcua_plugin):
    code = "workcenters/SAW-T/job"
    await until(lambda: last(ctx, code))
    assert last(ctx, code).text == "-"  # порожній список
    await ua_server.set_jobs([("WO00014", "AllowedToStart"), ("WO00013", "Running")])
    await until(lambda: last(ctx, code).text == "WO00013", timeout=2)
    await ua_server.set_jobs([("WO00012", "Completed"), ("WO00014", "AllowedToStart")])
    await until(lambda: last(ctx, code).text == "WO00014", timeout=2)
    await ua_server.set_jobs([("WO00012", "Completed"), ("WO00014", "Ended")])
    await until(lambda: last(ctx, code).text == "-", timeout=2)
    await ua_server.set_jobs([])
    await ua_server.set_jobs([("WO1", "Aborted")])
    await until(lambda: last(ctx, code).text == "-", timeout=2)


async def test_heartbeat_60s(ctx, ua_server, opcua_plugin, vclock):
    code = "workcenters/SAW-T/state"
    await until(lambda: last(ctx, code))
    n = len([r for r in ctx.emitted if r.code == code])
    await vclock.tick(60)
    assert len([r for r in ctx.emitted if r.code == code]) == n + 1
    beat = last(ctx, code)
    assert beat.ts == vclock.now() and beat.text == "WORKING" and beat.q == "good"
    # серцебиття не шлеться при offline
    opcua_plugin.session_down("test")
    n = len(ctx.emitted)
    await vclock.tick(60)
    assert len(ctx.emitted) == n


async def test_session_shared(ctx, ua_server, make_opcua, pool):
    p1 = make_opcua("SAW-T")
    p2 = make_opcua("SAW-T2")
    await p1.connect()
    await p2.connect()
    await p1.subscribe()
    await p2.subscribe()
    assert pool.sessions == 1
    await until(lambda: last(ctx, "workcenters/SAW-T2/state") and last(ctx, "workcenters/SAW-T/state"))
    await p1.disconnect()
    assert pool.sessions == 1  # сесія жива, поки є друге джерело
    await p2.disconnect()
    assert pool.sessions == 0


async def test_validate():
    from conftest import opcua_signals
    from f3d_collector_mc.opcua import OpcUaPlugin

    from collector.core.types import SourceCfg

    sigs = tuple(opcua_signals("SAW-T", "UA-SAW-T", events=True))
    ok = SourceCfg("UA-SAW-T", "opcua", True, False, {"endpoint": "opc.tcp://x:4840/f3d/"}, sigs)
    assert OpcUaPlugin.validate(ok) == []
    bad = SourceCfg("UA-SAW-T", "opcua", True, False, {"endpoint": "http://x", "heartbeat_s": 5}, sigs)
    errs = OpcUaPlugin.validate(bad)
    assert any("endpoint" in e for e in errs) and any("heartbeat_s" in e for e in errs)
