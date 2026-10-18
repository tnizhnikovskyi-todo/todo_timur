"""AC-239, AC-240, AC-243: завантаження API-24, схема, значення за замовчуванням, межі коду."""

import copy

import pytest
from helpers import FakeClock, base_raw, contract, make_plugin

from td_collector_energy import config as cfgmod
from td_collector_energy import limits


def test_contract_example_parses_clean():
    parsed = cfgmod.parse(contract("api24_config.json"))
    assert not parsed.errors and not parsed.warnings, (parsed.errors, parsed.warnings)
    cfg = parsed.config
    assert cfg.version == 17 and cfg.automation_enabled and cfg.remote_switching_enabled
    assert cfg.signals["qs_cmd"] == "energy_control/qs/cmd" and cfg.inputs["grid_kw"] == "infra/totals/grid_kw"
    assert cfg.scenario("night").params["from"] == "23:00" and cfg.scenario("peak").params["limit_kw"] == 760


def test_defaults_without_optional_keys():  # AC-240
    parsed = cfgmod.parse({"schema": 1, "config_version": 3})
    cfg = parsed.config
    assert not parsed.errors and cfg.version == 3
    assert (cfg.automation_enabled, cfg.write_enabled, cfg.remote_switching_enabled) == (False, False, False)
    assert cfg.engine.tick_s == 2 and cfg.engine.min_write_interval_s == 10 and cfg.engine.max_writes_per_min == 30
    assert cfg.plant["bess_kwh"] == 387 and cfg.limits.bess_kw_max == 200 and cfg.limits.air_bar_max == 8.5
    assert cfg.scenario("peak").params == cfgmod.PARAM_DEFAULTS["peak"] and not cfg.scenario("peak").enabled
    assert cfg.interlock("chp_gas_pressure").params["min_bar"] == 1.5 and cfg.interlock("controller_remote").hard
    assert cfg.shed == () and cfg.slots == () and cfg.signals == {} and "DUST-1" in cfg.never_shed


def test_unknown_params_warn_and_bad_slots_shed_dropped():  # AC-240
    raw = base_raw()
    raw["scenarios"]["peak"]["params"]["wat"] = 1
    raw["scenarios"]["night"]["params"]["from"] = "25:99"
    raw["slots"] = [
        {"id": 1, "resource": "bess", "date": None, "weekdays": "1111111", "from": 10.0, "to": 10.0, "mode": "charge"},
        {"id": 2, "resource": "bess", "date": None, "weekdays": "1111111", "from": 12.0, "to": 9.0, "mode": "charge"},
        {"id": 3, "resource": "chp", "date": None, "weekdays": "1111100", "from": 16.0, "to": 19.0, "mode": "run"},
    ]
    raw["shed"][1] = {**raw["shed"][1], "signal": None}
    raw["scenarios"]["bogus"] = {"enabled": True, "params": {}}
    parsed = cfgmod.parse(raw)
    cfg = parsed.config
    text = " | ".join(parsed.warnings)
    assert "невідомий параметр wat" in text and "параметр from некоректний" in text and "сценарій bogus" in text
    assert [s.id for s in cfg.slots] == [3] and "слот 1" in text and "слот 2" in text
    assert [i.node for i in cfg.shed] == ["CHARGING", "DRY-1", "COMPRESSOR", "LP-1"] and "RV-ALL" in text
    assert cfg.scenario("night").params["from"] == "23:00"  # некоректне → значення коду


def test_schema_violations_are_errors():
    for bad in (
        {"schema": 2, "config_version": 1},
        {"config_version": 1},
        {"schema": 1, "config_version": "x"},
        {"schema": 1, "config_version": 1, "signals": {"a": 5}},
        [1, 2],
    ):
        parsed = cfgmod.parse(bad)
        assert parsed.errors and parsed.config is None, bad


def test_code_limits_override_config():  # AC-243
    raw = base_raw()
    raw["limits"] = {"bess_kw_max": 500, "pv_limit_min_pct": 2, "air_bar_min": 3.0, "air_bar_max": 9.5}
    raw["interlocks"] = {
        "chp_gas_pressure": {"hard": True, "fail_closed": True, "params": {"min_bar": 0.5}},
        "qs_current_ok": {"hard": True, "fail_closed": True, "params": {"max_ratio": 0.95}},
        "bess_temp_ok": {"hard": True, "fail_closed": False, "params": {"max_c": 60}},
    }
    raw["engine"].update(tick_s=0.2, config_poll_s=1, min_write_interval_s=0.5, max_writes_per_min=900)
    raw["scenarios"]["peak"]["params"].update(bess_max_kw=400, bess_min_soc_pct=3)
    raw["plant"]["bess_reserve_pct"] = 2
    parsed = cfgmod.parse(raw)
    cfg = parsed.config
    assert (cfg.limits.bess_kw_max, cfg.limits.air_bar_max, cfg.limits.air_bar_min, cfg.limits.pv_limit_min_pct) == (
        200,
        8.5,
        5.0,
        10,
    )
    assert cfg.interlock("chp_gas_pressure").params["min_bar"] == 1.0
    assert (
        cfg.interlock("qs_current_ok").params["max_ratio"] == 0.9
        and cfg.interlock("bess_temp_ok").params["max_c"] == 45
    )
    assert (cfg.engine.tick_s, cfg.engine.config_poll_s, cfg.engine.min_write_interval_s) == (1, 5, 2)
    assert cfg.engine.max_writes_per_min == limits.MAX_WRITES_PER_MIN
    assert cfg.params("peak")["bess_max_kw"] == 200 and cfg.params("peak")["bess_min_soc_pct"] == 10
    assert cfg.plant["bess_reserve_pct"] == 10
    assert any("limits.bess_kw_max" in e for e in parsed.events) and any("min_bar" in e for e in parsed.events)


def test_writable_codes_come_only_from_config():
    cfg = cfgmod.parse(base_raw()).config
    codes = cfg.writable_codes()
    assert "energy_control/qs/cmd" in codes and "energy_control/shed/LP-1/limit_pct" in codes
    assert "ventilation/units/RV-01/mode" in codes and "lighting/groups/LT-01/scene" in codes
    assert "infra/totals/grid_kw" not in codes  # входи — лише для читання


async def test_load_200_then_304_and_version_header(tmp_path):  # AC-239
    h = await make_plugin(tmp_path)
    assert h.cfg.version == 17 and h.odoo.config_calls == [None]
    h.odoo.version = 18  # config_version змінився без зміни змісту (A-64): 304 + X-Config-Version
    await h.plugin._load_config()
    assert h.odoo.config_calls[-1] == h.cfg.etag and h.cfg.version == 18
    assert h.plugin.store.cached_config(h.clock.now())["config_version"] == 17  # кеш — зміст останнього 200
    raw = base_raw()
    raw["config_version"], raw["etag"] = 19, "ff" * 32
    h.odoo.raw = raw
    await h.plugin._load_config()
    assert h.cfg.version == 19 and h.cfg.etag == "ff" * 32


async def test_odoo_down_uses_store_cache_up_to_7_days(tmp_path):  # AC-239
    h1 = await make_plugin(tmp_path)
    await h1.plugin.disconnect()  # зберегли кеш у Store
    clock = FakeClock()
    clock.advance(6 * 86400)
    h2 = await make_plugin(tmp_path, odoo_down=True, clock=clock)
    assert h2.cfg is not None and h2.cfg.version == 17
    assert any("кешовано" in e["text"] for e in h2.events("config"))
    await h2.plugin.disconnect()
    clock3 = FakeClock()
    clock3.advance(8 * 86400)
    h3 = await make_plugin(tmp_path, odoo_down=True, clock=clock3)
    assert h3.cfg is None  # кеш старший за 7 діб: рушій у стані off без дій
    await h3.engine.tick()
    assert h3.engine.mode == "off" and h3.device.writes == []


async def test_invalid_config_keeps_previous_valid(tmp_path):  # AC-239
    h = await make_plugin(tmp_path)
    good = copy.deepcopy(h.odoo.raw)
    h.odoo.raw = {**good, "schema": 2, "etag": "bad"}
    await h.plugin._load_config()
    assert h.cfg.version == 17 and h.plugin.config_error.startswith("config invalid:")
    ev = h.events("config")
    assert ev and ev[-1]["text"].startswith("config invalid:")
    await h.plugin.engine.tick()
    assert h.plugin.config_error and h.plugin.health().state == "online"  # попередній валідний лишається
    h.odoo.raw = {**good, "config_version": 20, "etag": "ok2"}
    await h.plugin._load_config()
    assert h.cfg.version == 20 and h.plugin.config_error is None


async def test_clock_skew_event_and_expiry_correction(tmp_path):
    raw = base_raw()
    raw["server_time"] = "2026-10-14T06:01:00Z"  # годинник збирача відстає на 60 с
    h = await make_plugin(tmp_path, raw)
    assert any("Розбіжність годинників" in e["text"] for e in h.events("config"))
    assert h.executor.skew_s == pytest.approx(60.0)
