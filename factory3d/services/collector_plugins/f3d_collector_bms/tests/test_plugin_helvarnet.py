"""AC-68…AC-72, AC-74…AC-78: плагін helvarnet проти фейкового роутера."""

from __future__ import annotations

import asyncio
import importlib.metadata
import time
import tomllib
from pathlib import Path

import pytest
from conftest import make_signal, make_source

from collector.core.errors import AllowlistDenied, ConnectError, NotSupported, PollError, WriteError
from collector.plugins.base import SourcePlugin
from f3d_collector_bms.connection import POOL
from f3d_collector_bms.helvarnet import HelvarNetPlugin

G12 = [f"@1.2.1.{d}" for d in range(1, 28)]


async def test_level_sample_median(fake_router, plugin_factory):
    router = await fake_router()
    router.set_level(12, 60)
    sig = make_signal(12, "level")
    plugin = await plugin_factory(router, [sig])
    [r] = await plugin.poll([sig])
    assert (r.value, r.q, r.code) == (60.0, "good", sig.code)
    assert router.queries[152] == 3 and router.queries[164] == 1
    assert [q for q in router.received if "C:152" in q] == [
        ">V:2,C:152,@1.2.1.1#",
        ">V:2,C:152,@1.2.1.14#",
        ">V:2,C:152,@1.2.1.27#",
    ]
    await plugin.poll([sig])
    assert router.queries[164] == 1  # склад із кешу (TTL)
    assert router.queries[152] == 6


async def test_level_decode_and_errors(fake_router, plugin_factory):
    router = await fake_router()
    sig = make_signal(12, "level")
    router.levels["@1.2.1.1"] = 100
    router.levels["@1.2.1.14"] = 0x80000000
    router.levels["@1.2.1.27"] = 100
    plugin = await plugin_factory(router, [sig])
    [r] = await plugin.poll([sig])
    assert r.value == 100.0  # median_low([0, 100, 100])
    router.levels["@1.2.1.1"] = 0x80000001
    plugin2 = await plugin_factory(router, [make_signal(12, "level", sample=1)])
    [r] = await plugin2.poll(plugin2.source.signals)
    assert r.value == 0.0
    # пристрій 14 -> 11: медіана з двох
    router2 = await fake_router()
    router2.set_level(12, 60)
    router2.fail(152, "@1.2.1.14", 11)
    p3 = await plugin_factory(router2, [sig])
    [r] = await p3.poll([sig])
    assert (r.value, r.q) == (60.0, "good")
    # усі помилки -> bad
    router2.fail(152, None, 11)
    p4 = await plugin_factory(router2, [sig])
    [r] = await p4.poll([sig])
    assert (r.value, r.q) == (None, "bad")


async def test_membership_cache_fallback(fake_router, plugin_factory):
    router = await fake_router()
    router.set_level(12, 60)
    router.fail(164, 12, 15)
    sig = make_signal(12, "level", devices=["@1.2.1.1-27"])
    plugin = await plugin_factory(router, [sig])
    [r] = await plugin.poll([sig])
    assert (r.value, r.q) == (60.0, "good")
    assert router.queries[164] == 1 and router.queries[152] == 3
    # без фолбека -> bad
    router2 = await fake_router()
    router2.fail(164, 12, 15)
    bare = make_signal(12, "level")
    p2 = await plugin_factory(router2, [bare])
    [r] = await p2.poll([bare])
    assert r.q == "bad" and r.value is None
    assert router2.queries[152] == 0


async def test_partial_membership(fake_router, plugin_factory):
    router = await fake_router(partial=True)
    sigs = [make_signal(16, "faults")]
    plugin = await plugin_factory(router, sigs)
    [r] = await plugin.poll(sigs)
    assert (r.value, r.q) == (0.0, "good")
    assert router.queries[110] == 91  # склад 164 зібрано з частин `$`


async def test_power_scene(fake_router, plugin_factory):
    router = await fake_router()
    power = make_signal(12, "power", scale=0.001)
    scene = make_signal(12, "scene")
    lvl = make_signal(12, "level")
    plugin = await plugin_factory(router, [power, scene, lvl])
    rp, rs = await plugin.poll([power, scene])
    assert rp.value == pytest.approx(3.402) and rs.value == 0.0
    assert await plugin.write(lvl, 100, None) is not None
    await plugin.write(make_signal(12, "scene"), 3, None)
    [rs] = await plugin.poll([scene])
    assert rs.value == 3.0
    router.set_level(12, 50)
    [rp] = await plugin.poll([power])
    assert rp.value == pytest.approx(1.701)


async def test_faults_faulty_router(fake_router, plugin_factory):
    router = await fake_router()
    faults = make_signal(12, "faults")
    faulty = make_signal(12, "faulty")
    rsig = make_signal(None, "router", device="@1.2.0.0", code="lighting/panels/LP-2/state")
    plugin = await plugin_factory(router, [faults, faulty, rsig])
    router.states["@1.2.1.5"] = 0x02
    router.states["@1.2.1.6"] = 0x100  # EM_Resting — не несправність
    rf, rt = await plugin.poll([faults, faulty])
    assert (rf.value, rt.text) == (1.0, "1.2.1.5")
    assert router.queries[110] == 27  # один обхід на обидва сигнали
    router.fail(110, "@1.2.1.9", 11)
    router.states["@1.2.1.5"] = 0x02
    plugin._sweeps.clear()
    rf, rt = await plugin.poll([faults, faulty])
    assert (rf.value, rt.text) == (2.0, "1.2.1.5,1.2.1.9")
    [rr] = await plugin.poll([rsig])
    assert (rr.text, rr.q) == ("fault", "good")
    for d in range(10, 22):
        router.states[f"@1.2.1.{d}"] = 0x08
    router.error_codes.clear()
    plugin._sweeps.clear()
    rf, rt = await plugin.poll([faults, faulty])
    assert rf.value == 13.0 and len(rt.text) <= 64 and "+" in rt.text
    # здоровий щит: стан ok; роутера 3 немає серед 1,2,3? — є; роутера 9 немає
    plugin3 = await plugin_factory(router, [rsig], router=3)
    [rr] = await plugin3.poll([rsig])
    assert rr.text == "ok"
    gone = make_signal(None, "router", device="@1.9.0.0", code="x/router")
    p9 = await plugin_factory(router, [gone], router=9)
    [rr] = await p9.poll([gone])
    assert (rr.q, rr.text, rr.value) == ("bad", "offline", None)
    assert p9.health().state == "error" and "not in cluster" in p9.health().error


async def test_missing_devices_from_address(fake_router, plugin_factory):
    router = await fake_router()
    faults = make_signal(19, "faults", devices=["@1.2.1.28-31"])
    plugin = await plugin_factory(router, [faults])
    [r] = await plugin.poll([faults])
    assert r.value == 1.0  # @1.2.1.31 немає у складі з роутера


async def test_push_emit(fake_router, plugin_factory):
    router = await fake_router()
    lvl = make_signal(12, "level", code="lighting/groups/LT-CUT/level")
    scn = make_signal(12, "scene", code="lighting/groups/LT-CUT/scene")
    plugin = await plugin_factory(router, [lvl, scn])
    await router.send_push(">V:2,C:13,G:12,L:0,F:100#")
    await router.send_push(">V:2,C:11,G:12,B:1,S:5,F:100#")
    await router.send_push(">V:2,C:13,G:99,L:5,F:100#")  # чужа група
    await router.send_push(">V:2,C:23,G:12#")
    for _ in range(100):
        if plugin.push_count >= 3 and plugin.push_ignored >= 1:
            break
        await asyncio.sleep(0.01)
    got = {r.code: r.value for r in plugin.ctx.emitted}
    assert got == {"lighting/groups/LT-CUT/level": 0.0, "lighting/groups/LT-CUT/scene": 5.0}
    assert plugin.push_ignored == 1
    off = await plugin_factory(router, [lvl], push=False)
    await router.send_push(">V:2,C:13,G:12,L:7,F:100#")
    await asyncio.sleep(0.1)
    assert off.ctx.emitted == []


async def test_write_ack_verify_fail(fake_router, plugin_factory):
    router = await fake_router(push=False)
    sig = make_signal(19, "level", code="lighting/groups/LT-MAINT/level")
    plugin = await plugin_factory(router, [sig])
    assert await plugin.write(sig, 50, "fade=1.0") == "C13 G19 L50 F100 ack"
    assert router.received[-1] == ">V:2,C:13,G:19,L:50,F:100,A:1#"
    assert router.level_of("@1.2.1.28") == 50
    # без ack, рівень змінено -> verified
    quiet = await fake_router(push=False, ack=False)
    p2 = await plugin_factory(quiet, [sig])
    assert await p2.write(sig, 50, "fade=0") == "C13 G19 L50 F0 verified"
    # без ack і рівень не змінено -> WriteError
    quiet.set_level(19, 100)
    quiet.set_level = lambda g, level: None  # роутер «ігнорує» команду
    with pytest.raises(WriteError, match="no ack, level now 100"):
        await p2.write(sig, 50, "fade=0")
    # код помилки
    router.fail(13, 19, 1)
    with pytest.raises(WriteError, match="HelvarNet error 1: "):
        await plugin.write(sig, 10, None)
    # сцена: C:11 + перевірка C:109
    router.error_codes.clear()
    scn = make_signal(19, "scene", code="lighting/groups/LT-MAINT/scene")
    p3 = await plugin_factory(router, [sig, scn])
    assert (await p3.write(scn, 3, "fade=0")).startswith("C11 G19 S3")
    assert router.received[-1] == ">V:2,C:11,G:19,B:1,S:3,F:0,A:1#"
    assert router.scenes[19] == 3
    with pytest.raises(WriteError):
        await p3.write(sig, 101, None)


async def test_write_scene_verified(fake_router, plugin_factory):
    router = await fake_router(push=False, ack=False)
    scn = make_signal(19, "scene")
    plugin = await plugin_factory(router, [scn])
    assert await plugin.write(scn, 3, "fade=0") == "C11 G19 S3 F0 verified"
    assert router.queries[109] == 1


async def test_write_not_supported(fake_router, plugin_factory):
    router = await fake_router()
    sigs = [
        make_signal(12, "power"),
        make_signal(12, "faults"),
        make_signal(None, "router", device="@1.2.0.0"),
        make_signal(40, "level"),
        make_signal(12, "level"),
    ]
    plugin = await plugin_factory(router, sigs)
    for sg in sigs[:4]:
        with pytest.raises(NotSupported):
            await plugin.write(sg, 1, None)
    with pytest.raises(NotSupported):  # група поза сигналами джерела
        await plugin.write(make_signal(21, "level"), 10, None)
    with pytest.raises(NotSupported):
        await plugin.subscribe()
    assert router.queries[13] == 0 and router.queries[11] == 0


async def test_version_fallback(fake_router, plugin_factory):
    router = await fake_router(version=1)
    sig = make_signal(12, "power")
    plugin = await plugin_factory(router, [sig])
    assert router.received[:2] == [">V:2,C:191#", ">V:1,C:191#"]
    assert plugin.health().stats["version"] == 1
    [r] = await plugin.poll([sig])
    assert r.q == "good"
    assert router.received[-1].startswith(">V:1,C:161")


async def test_reconnect_offline_allowlist(fake_router, plugin_factory):
    router = await fake_router(drop_after=5)
    sigs = [make_signal(12, "level"), make_signal(12, "power"), make_signal(12, "scene")]
    plugin = await plugin_factory(router, sigs)
    with pytest.raises(PollError):
        await plugin.poll(sigs)
    assert plugin.health().state == "offline"
    out = await plugin.poll(sigs)
    assert [r.q for r in out] == ["good"] * 3
    assert router.connections == 2
    assert plugin.health().state == "online"
    # роутер зупинено
    dead = await fake_router()
    port = dead.port
    await dead.stop()
    plugin2 = HelvarNetPlugin(make_source(port, sigs), plugin.ctx)
    with pytest.raises(ConnectError):
        await plugin2.connect()
    assert plugin2.health().state == "offline"
    # allowlist
    alive = await fake_router()
    with pytest.raises(AllowlistDenied):
        await plugin_factory(alive, sigs, deny=True)
    assert alive.connections == 0
    # udp
    with pytest.raises(ConnectError, match="udp not supported"):
        await plugin_factory(alive, sigs, protocol="udp")
    assert alive.connections == 0


async def test_rate_limit_timeouts(fake_router, plugin_factory):
    router = await fake_router()
    plugin = await plugin_factory(router, [], rate_per_s=10)
    conn = plugin._conn
    from f3d_collector_bms.protocol import build_query, key_for

    started = time.monotonic()
    for _ in range(40):
        await conn.request(build_query(2, 191), key_for(191), 1)
    assert time.monotonic() - started >= 3.0
    # таймаути
    slow = await fake_router()
    sig = make_signal(12, "power")
    p2 = await plugin_factory(slow, [sig], timeout_s=0.5)
    slow.delay_s = 5  # connect (C:191) уже пройшов без затримки
    for _ in range(2):
        [r] = await p2.poll([sig])
        assert (r.q, r.value) == ("bad", None)
    with pytest.raises(PollError):
        await p2.poll([sig])
    assert p2.health().state == "offline"


async def test_shared_connection(fake_router, plugin_factory):
    router = await fake_router()
    plugins = [await plugin_factory(router, [make_signal(12, "power")], code=f"HN-LP-{i}") for i in (1, 2, 3)]
    assert router.connections == 1
    assert POOL.count("127.0.0.1", router.port) == 3
    await plugins[0].disconnect()
    await plugins[1].disconnect()
    conn = plugins[2]._conn
    assert conn.alive and router.connections == 1
    [r] = await plugins[2].poll(plugins[2].source.signals)
    assert r.q == "good"
    await plugins[2].disconnect()
    assert not conn.alive and POOL.count("127.0.0.1", router.port) == 0


def test_entry_point():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    target = data["project"]["entry-points"]["factory3d_collector.plugins"]["helvarnet"]
    assert target == "f3d_collector_bms.helvarnet:HelvarNetPlugin"
    assert issubclass(HelvarNetPlugin, SourcePlugin) and HelvarNetPlugin.type == "helvarnet"
    assert HelvarNetPlugin.push_mode is False
    eps = importlib.metadata.entry_points(group="factory3d_collector.plugins")
    if any(ep.name == "helvarnet" for ep in eps):  # пакет встановлено (pip install -e)
        from collector.core.registry import load_plugins

        assert load_plugins()["helvarnet"] is HelvarNetPlugin


async def test_validate_data():
    sigs = [
        make_signal(12, "level", devices=["@1.2.1.1-27"]),
        make_signal(None, "router", device="@1.2.0.0", map={"ok": "ok", "fault": "fault"}),
    ]
    source = make_source(50000, sigs, push=True)
    assert HelvarNetPlugin.validate(source) == []
    bad = make_source(50000, [make_signal(12, "level", sample=0)], rate_per_s=0)
    assert len(HelvarNetPlugin.validate(bad)) == 2
    no_router = make_source(50000, sigs)
    params = {k: v for k, v in no_router.params.items() if k != "router"}
    assert HelvarNetPlugin.validate(type(no_router)(**{**no_router.__dict__, "params": params}))
