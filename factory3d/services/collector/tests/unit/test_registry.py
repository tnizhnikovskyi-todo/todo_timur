"""AC-74, AC-76: реєстр джерел і плагіни."""

from __future__ import annotations

import asyncio
import json
from abc import abstractmethod
from datetime import timedelta

import pytest
import pytest_asyncio
from conftest import TOKEN, VirtualClock

from collector.core import registry as registry_mod
from collector.core.metrics import Metrics
from collector.core.odoo_client import OdooClient
from collector.core.registry import Registry, load_plugins
from collector.plugins.base import SourcePlugin
from collector.util.timeutil import to_iso_z

from . import CountingClock, FakePlugin, sig_json, src_json


@pytest.fixture(autouse=True)
def _reset():
    FakePlugin.instances = []


@pytest_asyncio.fixture
async def client(fake_odoo):
    c = OdooClient(fake_odoo.url, TOKEN, collector="COL-T", clock=VirtualClock())
    yield c
    await c.close()


def _cfg(fake_odoo, extra=None):
    fake_odoo.config = {
        "read_enabled": True,
        "write_enabled": False,
        "sources": [
            src_json("S1", signals=[sig_json("equipment/A/x")], params={"host": "h1"}),
            src_json("S2", signals=[sig_json("equipment/B/x")], params={"host": "h2"}),
            *(extra or []),
        ],
    }


def _reg(client, settings, vclock, classes=None, clock=None):
    return Registry(
        client,
        settings,
        lambda s: None,
        clock or vclock,
        Metrics(vclock),
        plugin_classes={"fake": FakePlugin} if classes is None else classes,
    )


async def test_load_and_connect(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo)
    reg = _reg(client, settings, vclock)
    await reg.load()
    assert sorted(reg.plugins) == ["S1", "S2"]
    assert [p.connects for p in FakePlugin.instances] == [1, 1]
    assert reg.etag == "etag-1" and reg.connected == {"S1", "S2"}
    assert reg.find_signal("equipment/B/x")[0].code == "S2"
    assert json.loads(settings.state_file.read_text())["config"]["sources"]


async def test_304_no_restart(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo)
    reg = _reg(client, settings, vclock)
    await reg.load()
    assert await reg.refresh() is False
    assert len(FakePlugin.instances) == 2 and all(p.disconnects == 0 for p in FakePlugin.instances)
    hdr = [c for c in fake_odoo.calls if c[1].endswith("/config")]
    assert len(hdr) == 2


async def test_changed_source_restart_only(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo)
    reg = _reg(client, settings, vclock)
    await reg.load()
    first = dict(reg.plugins)
    fake_odoo.config["sources"][0]["params"] = {"host": "h1-new"}
    fake_odoo.etag = "etag-2"
    assert await reg.refresh() is True
    assert reg.plugins["S2"] is first["S2"] and first["S2"].disconnects == 0
    assert reg.plugins["S1"] is not first["S1"]
    assert first["S1"].disconnects == 1 and reg.plugins["S1"].connects == 1


async def test_cached_config_age(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo)
    fake_odoo.down = True
    cache = {"saved_at": to_iso_z(vclock.now() - timedelta(days=6)), "config": fake_odoo.config}
    settings.state_file.write_text(json.dumps(cache))
    reg = _reg(client, settings, vclock)
    await reg.load()
    assert sorted(reg.plugins) == ["S1", "S2"]
    # 8 діб — кеш не діє, очікування з бекофом
    FakePlugin.instances = []
    cache["saved_at"] = to_iso_z(vclock.now() - timedelta(days=8))
    settings.state_file.write_text(json.dumps(cache))
    clock = CountingClock(max_sleeps=4)
    reg2 = _reg(client, settings, vclock, clock=clock)
    with pytest.raises(asyncio.CancelledError):
        await reg2.load()
    assert clock.sleeps[:3] == [1, 2, 4] and not FakePlugin.instances


async def test_invalid_schema_source_error(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo, [src_json("BAD", signals=[sig_json("equipment/C/x", address={"bad": True})])])
    reg = _reg(client, settings, vclock)
    await reg.load()
    assert reg.errors["BAD"].error.startswith("schema: ") and reg.errors["BAD"].state == "error"
    assert "BAD" not in reg.plugins and "S1" in reg.connected  # connect не викликано для BAD


async def test_validate_before_connect(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo, [src_json("BAD", signals=[sig_json("equipment/C/x", address={"bad": True})])])
    await _reg(client, settings, vclock).load()
    assert len(FakePlugin.instances) == 2  # лише S1, S2


def test_load_plugins(monkeypatch):
    class EP:
        def __init__(self, name, obj):
            self.name, self.obj = name, obj

        def load(self):
            if self.obj is None:
                raise ImportError("boom")
            return self.obj

    eps = [EP("modbus_tcp", FakePlugin), EP("broken", None)]
    monkeypatch.setattr(registry_mod, "entry_points", lambda group: eps)
    assert load_plugins() == {"modbus_tcp": FakePlugin}


def test_load_real_plugins_exactly_four():
    """AC-76: базові плагіни ядра — рівно 4 (entry points pyproject.toml); `energy_ctl` (W2) — штатний п'ятий, коли
    встановлений, як і зовнішні `helvarnet`/`sics`."""
    plugins = load_plugins()
    base = {"bacnet_ip", "http_push", "modbus_tcp", "mqtt"}
    assert base <= set(plugins) <= base | {"energy_ctl", "helvarnet", "sics"}
    assert {n for n in plugins if n in base} == base
    for typ, cls in plugins.items():
        assert cls.type == typ and cls.address_schema and cls.params_schema
        assert issubclass(cls, SourcePlugin) and not getattr(cls, "__abstractmethods__", None)
    assert plugins["mqtt"].push_mode and plugins["http_push"].push_mode
    assert not plugins["modbus_tcp"].push_mode and not plugins["bacnet_ip"].push_mode


async def test_missing_plugin(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo, [src_json("OPC", type_="opcua")])
    reg = _reg(client, settings, vclock)
    await reg.load()
    assert reg.errors["OPC"].error == "plugin opcua not installed" and reg.errors["OPC"].state == "error"
    assert "S1" in reg.connected


async def test_abstract_plugin(fake_odoo, client, settings, vclock):
    class Abstract(SourcePlugin):
        type = "abs"

        @abstractmethod
        async def must_implement(self): ...

    with pytest.raises(TypeError):
        Abstract(None, None)  # type: ignore[arg-type]
    _cfg(fake_odoo, [src_json("ABS", type_="abs")])
    reg = _reg(client, settings, vclock, classes={"fake": FakePlugin, "abs": Abstract})
    await reg.load()
    assert reg.errors["ABS"].state == "error" and "S1" in reg.connected


async def test_read_disabled_global_disconnects(fake_odoo, client, settings, vclock):
    _cfg(fake_odoo)
    reg = _reg(client, settings, vclock)
    await reg.load()
    await reg.set_flags(False)
    assert not reg.plugins and all(p.disconnects == 1 for p in FakePlugin.instances)
    await reg.set_flags(True)
    assert sorted(reg.plugins) == ["S1", "S2"]
