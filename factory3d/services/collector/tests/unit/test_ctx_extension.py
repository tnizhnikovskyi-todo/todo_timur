"""AC-237: нові необов'язкові поля PluginContext (C-40); `_make_ctx` заповнює їх для будь-якого джерела."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from collector.core.app import Collector
from collector.core.live import LiveCache
from collector.plugins.base import PluginContext

from . import mk_source

NEW_FIELDS = ("live", "write_signal", "read_signal", "odoo", "clock", "state_dir")


def test_new_fields_default_none(make_ctx):
    fields = {f.name: f for f in dataclasses.fields(PluginContext)}
    for name in NEW_FIELDS:
        assert fields[name].default is None, name
    import logging

    ctx = PluginContext(
        settings=None, secrets=str, allowlist=str, emit=str, emit_event=str, metrics=None, log=logging.getLogger("t")
    )
    assert all(getattr(ctx, n) is None for n in NEW_FIELDS)


async def test_make_ctx_fills_fields(settings, vclock):
    app = Collector(settings, clock=vclock)
    try:
        for src in (mk_source("A", "modbus_tcp"), mk_source("B", "mqtt"), mk_source("C", "energy_ctl")):
            ctx = app._make_ctx(src)
            assert isinstance(ctx.live, LiveCache) and ctx.live is app.live
            assert ctx.write_signal == app.commands.write_direct
            assert ctx.read_signal == app.commands.read_now
            assert ctx.odoo is app.client and ctx.clock is vclock
            assert ctx.state_dir == Path(settings.buffer_dir)
            assert ctx.log.name == f"collector.plugin.{src.type}.{src.code}"
        assert app.emitter.live is app.live and app.scheduler.live is app.live and app.commands.live is app.live
    finally:
        await app.client.close()
        await app.buffer.close()


@pytest.mark.parametrize("mod", ["modbus_tcp", "bacnet_ip", "mqtt", "http_push"])
def test_builtin_plugins_unchanged(mod, make_ctx):
    """Вбудовані плагіни створюються зі старим контекстом (без нових полів) і не читають їх."""
    import importlib

    module = importlib.import_module(f"collector.plugins.{mod}")
    cls = next(v for v in vars(module).values() if isinstance(v, type) and getattr(v, "type", None) == mod)
    plugin = cls(mk_source("X", mod), make_ctx().ctx)
    assert plugin.type == mod and plugin.ctx.live is None
