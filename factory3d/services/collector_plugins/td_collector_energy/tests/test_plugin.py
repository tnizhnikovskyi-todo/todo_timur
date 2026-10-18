"""AC-268: EnergyCtlPlugin — validate, єдиний екземпляр, subscribe (4 задачі), health, disconnect, heartbeat."""

import asyncio

import pytest
from collector.core.errors import ConnectError, NotSupported
from helpers import FakeClock, FakeDevice, FakeOdoo, base_raw, feed, make_ctx, make_plugin, source_cfg, standard_inputs
from collector.core.live import LiveCache
from collector.core.types import SignalCfg, SourceCfg

from td_collector_energy import EnergyCtlPlugin


def test_declaration_and_schemas():
    assert EnergyCtlPlugin.type == "energy_ctl" and EnergyCtlPlugin.push_mode is True
    assert EnergyCtlPlugin.params_schema["properties"]["engine"]["properties"]["tick_s"]["maximum"] == 10


def test_validate_params_and_addresses():  # AC-268
    assert EnergyCtlPlugin.validate(source_cfg()) == []
    assert EnergyCtlPlugin.validate(source_cfg({"engine": {"tick_s": 5, "config_poll_s": 30}})) == []
    bad = EnergyCtlPlugin.validate(source_cfg({"engine": {"tick_s": 11}}))
    assert bad and "tick_s" in bad[0]
    bad = EnergyCtlPlugin.validate(source_cfg({"engine": {"config_poll_s": 2}}))
    assert bad and "config_poll_s" in bad[0]
    src = SourceCfg(
        "ENERGY-CTL",
        "energy_ctl",
        True,
        True,
        {},
        (SignalCfg("energy_control/intent", "event", "", 10, 1.0, True, None, 0, {}, "ENERGY-CTL"),),
    )
    assert EnergyCtlPlugin.validate(src) == []


async def test_single_instance_guard():  # AC-268
    h = await make_plugin(None)
    ctx2, _ = make_ctx(h.clock, h.live, h.device, h.odoo, None)
    second = EnergyCtlPlugin(source_cfg(), ctx2)
    with pytest.raises(ConnectError, match="energy_ctl: дублікат джерела"):
        await second.connect()
    await h.plugin.disconnect()
    await second.connect()  # після disconnect слот вільний
    await second.disconnect()
    await h.plugin.connect()  # той самий екземпляр можна підключати повторно
    await h.plugin.disconnect()


async def test_connect_makes_no_device_writes_and_loads_first_config():  # AC-268
    h = await make_plugin(None)
    assert h.cfg.version == 17 and h.device.writes == [] and h.plugin.tasks == []


async def test_subscribe_returns_immediately_and_creates_four_tasks():  # AC-268
    h = await make_plugin(None)
    await asyncio.wait_for(h.plugin.subscribe(), 1.0)
    assert len(h.plugin.tasks) == 4
    assert {t.get_name() for t in h.plugin.tasks} == {
        "energy_ctl:config",
        "energy_ctl:engine",
        "energy_ctl:report",
        "energy_ctl:heartbeat",
    }
    await h.plugin.disconnect()
    assert h.plugin.tasks == []


async def test_disconnect_does_not_write_to_devices_and_saves_store(tmp_path):  # AC-268, R-53 №7
    h = await make_plugin(tmp_path)
    feed(h, **standard_inputs(grid_kw=800, bess_soc=82))
    await h.tick()
    n = len(h.device.writes)
    assert n > 0  # у режимі auto плагін писав
    h.engine.shared["bess_by"] = "peak"
    await h.plugin.subscribe()
    await h.plugin.disconnect()
    assert len(h.device.writes) == n  # безпеку дають сторожові таймери контролера, а не запис при відключенні
    assert (tmp_path / "td_energy_ctl.json").is_file()
    assert EnergyCtlPlugin._active is None


async def test_heartbeat_reading_and_scenario_states_on_change():  # AC-268
    h = await make_plugin(None)
    feed(h, **standard_inputs())
    await h.tick()
    h.plugin.beat()
    hb = [r for r in h.box.readings if r.code == "energy_control/auto/heartbeat"]
    assert hb and hb[-1].value == float(h.engine.ticks)
    states = {r.code: r.text for r in h.box.readings if r.code.endswith("/state")}
    assert states["energy_control/auto/peak/state"] == "armed" and states["energy_control/auto/self/state"] == "armed"
    assert states["energy_control/auto/backup/state"] == "armed" and states["energy_control/auto/pfc/state"] == "active"
    n = len(h.box.readings)
    h.plugin.beat()  # стани не змінилися: лише heartbeat
    assert len(h.box.readings) == n + 1
    feed(h, grid_kw=800)
    await h.tick()
    h.plugin.beat()
    assert h.box.readings[-1].code == "energy_control/auto/peak/state" or any(
        r.code == "energy_control/auto/peak/state" and r.text == "active" for r in h.box.readings
    )


async def test_heartbeat_loop_every_10_seconds():  # AC-268
    h = await make_plugin(None)
    h.plugin.clock = h.clock
    task = asyncio.create_task(h.plugin._heartbeat_loop())
    t0 = h.clock.monotonic()
    for _ in range(5):
        await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    beats = [r for r in h.box.readings if r.code == "energy_control/auto/heartbeat"]
    assert len(beats) >= 2 and h.clock.monotonic() - t0 >= 10 * (len(beats) - 1)


async def test_health_online_then_error_when_engine_stalls():  # AC-268
    h = await make_plugin(None)
    assert h.plugin.health().state == "online"
    feed(h, **standard_inputs())
    await h.tick()
    st = h.plugin.health()
    assert st.state == "online" and st.stats["mode"] == "auto" and st.stats["config_version"] == 17
    assert {"ticks", "tick_ms_p95", "writes_last_min", "intents_total", "blocked_total"} <= set(st.stats)
    h.clock.advance(5)  # < 3·tick_s
    assert h.plugin.health().state == "online"
    h.clock.advance(2)
    st = h.plugin.health()
    assert st.state == "error" and "не тікає" in st.error


async def test_health_error_without_any_valid_config():  # AC-268
    raw = base_raw()
    raw["schema"] = 2
    h = await make_plugin(None, raw)
    assert h.cfg is None and h.plugin.config_error.startswith("config invalid:")
    st = h.plugin.health()
    assert st.state == "error" and "config invalid" in st.error


async def test_call_before_connect_and_foreign_signal():
    clock = FakeClock()
    live = LiveCache(clock)
    ctx, _ = make_ctx(clock, live, FakeDevice(lambda: None, live, clock), FakeOdoo(base_raw()), None)
    plugin = EnergyCtlPlugin(source_cfg(), ctx)
    sig = SignalCfg("energy_control/intent", "event", "", 10, 1.0, True, None, 0, {}, "ENERGY-CTL")
    with pytest.raises(ConnectError):
        await plugin.call(sig, {})
    with pytest.raises(NotSupported):
        await plugin.write(sig, 1.0, None)


async def test_loops_run_engine_reporter_and_config_poll_together():  # SPEC 8.1.3
    h = await make_plugin(None)
    feed(h, **standard_inputs(grid_kw=800, bess_soc=82))
    await h.plugin.subscribe()
    for _ in range(30):
        await asyncio.sleep(0)
    await h.plugin.disconnect()
    assert h.engine.ticks > 2 and h.device.writes  # цикл автоматики працює
    assert h.odoo.states and "engine" in h.odoo.states[0] and h.odoo.states[0]["collector"] == "COL-T"
    assert len(h.odoo.config_calls) >= 2 and h.odoo.config_calls[0] is None  # опитування конфігу з If-None-Match
    assert h.odoo.config_calls[1] == h.cfg.etag


async def test_config_etag_in_report_response_wakes_config_loop():  # SPEC 7.4
    h = await make_plugin(None)
    assert not h.plugin._config_wake.is_set()
    h.plugin._on_report("другий-etag", 18)
    assert h.plugin._config_wake.is_set()
    h.plugin._config_wake.clear()
    h.plugin._on_report(h.cfg.etag, 17)
    assert not h.plugin._config_wake.is_set()
