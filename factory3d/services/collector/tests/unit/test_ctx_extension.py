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


# --- тонкі методи клієнта Odoo для API-24/API-25 (C-40, SPEC 8.1.2) ------------------------------------------------
@pytest.fixture
async def energy_odoo():
    from aiohttp import web
    from aiohttp.test_utils import TestServer

    state = {"etag": "abc", "version": 17, "posts": [], "status": 200}

    async def config(request):
        hdr = {"ETag": f'"{state["etag"]}"', "X-Config-Version": str(state["version"])}
        if request.headers.get("If-None-Match", "").strip('"') == state["etag"]:
            return web.Response(status=304, headers=hdr)
        return web.json_response({"schema": 1, "config_version": state["version"], "etag": state["etag"]}, headers=hdr)

    async def report(request):
        state["posts"].append((request.headers.get("Authorization"), await request.json()))
        if state["status"] != 200:
            return web.json_response({"error": "rate_limited"}, status=state["status"], headers={"Retry-After": "10"})
        return web.json_response({"accepted_actions": 1, "accepted_events": 0, "rejected": [], "config_version": 17})

    app = web.Application()
    app.router.add_get("/td/energy/automation/config", config)
    app.router.add_post("/td/energy/automation/state", report)
    server = TestServer(app)
    await server.start_server()
    state["url"] = str(server.make_url("")).rstrip("/")
    yield state
    await server.close()


async def test_automation_config_200_304_and_version_header(energy_odoo, vclock):
    from collector.core.odoo_client import OdooClient

    client = OdooClient(energy_odoo["url"], "t" * 43, collector="COL-T", clock=vclock)
    try:
        cfg, version = await client.automation_config(None)
        assert cfg["etag"] == "abc" and cfg["config_version"] == 17 and version == 17
        energy_odoo["version"] = 18  # config_version змінився без зміни змісту: 304 несе лише заголовок (A-64)
        cfg, version = await client.automation_config("abc")
        assert cfg is None and version == 18
        energy_odoo["etag"] = "def"
        cfg, version = await client.automation_config("abc")
        assert cfg["etag"] == "def" and version == 18
    finally:
        await client.close()


async def test_automation_state_posts_body_with_bearer_and_maps_429(energy_odoo, vclock):
    from collector.core.odoo_client import OdooClient, OdooError

    client = OdooClient(energy_odoo["url"], "t" * 43, collector="COL-T", clock=vclock)
    try:
        resp = await client.automation_state({"collector": "COL-T", "actions": [], "events": []})
        assert resp["accepted_actions"] == 1
        auth, body = energy_odoo["posts"][0]
        assert auth == f"Bearer {'t' * 43}" and body["collector"] == "COL-T"
        energy_odoo["status"] = 429
        with pytest.raises(OdooError) as e:
            await client.automation_state({"collector": "COL-T"})
        assert e.value.status == 429 and e.value.retry_after == 10.0
    finally:
        await client.close()
