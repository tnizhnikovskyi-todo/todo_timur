"""AC-75…AC-77, AC-103: адаптер `woodstore` (опитування, події, курсори, команди CMD-02)."""

from __future__ import annotations

import json

import pytest
from collector.core.errors import NotSupported, PollError, WriteError
from conftest import until
from f3d_collector_mc.woodstore import WoodStoreAdapter

FEED = {
    "op": "feed",
    "stack": "PLT-03C",
    "target": "SAW-1",
    "sheets": 4,
    "product": "DSP16-ANT",
    "priority": 5,
    "ref": "WH/MO/00233",
}
FEED_TEXT = "feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233"
FEED_BODY = {
    "type": "feed",
    "source": "PLT-03C",
    "target": "SAW-1",
    "sheets": 4,
    "product": "DSP16-ANT",
    "lot": None,
    "priority": 5,
    "external_ref": "WH/MO/00233",
}


async def connect(rest_plugin, app, **params):
    """Плагін із зупиненими фоновими циклами: кроки адаптера тест викликає сам."""
    plugin = rest_plugin(app, "woodstore", **params)
    await plugin.connect()
    await plugin.adapter.stop()
    return plugin


def kinds(ctx, kind: str) -> list[dict]:
    return [e.payload for e in ctx.events if e.route == "mc_woodstore" and e.payload["kind"] == kind]


def sig(plugin, suffix: str):
    return next(s for s in plugin.source.signals if s.code.endswith(suffix))


def readings(plugin):
    return [s for s in plugin.source.signals if not s.address.get("cmd")]


async def test_poll_status(ctx, woodstore_app, rest_plugin):
    plugin = await connect(rest_plugin, woodstore_app)
    assert isinstance(plugin.adapter, WoodStoreAdapter)
    out = {r.code.rsplit("/", 1)[1]: r for r in await plugin.poll(readings(plugin))}
    assert out["state"].text == "moving"
    assert out["vacuum_kpa"].value == -71.9
    assert out["cycles_today"].value == 373.0
    assert out["job"].text == "wj-1"
    assert len(woodstore_app.calls_of("GET", "/api/v1/status")) == 1
    assert len(kinds(ctx, "status")) == 1
    assert kinds(ctx, "status")[0]["status"]["state"] == "moving"
    assert kinds(ctx, "status")[0]["source"] == "REST-WOODSTORE-T"
    await plugin.disconnect()


async def test_status_event_on_change(ctx, woodstore_app, rest_plugin):
    plugin = await connect(rest_plugin, woodstore_app)
    await plugin.poll(readings(plugin))
    await plugin.poll(readings(plugin))
    assert len(kinds(ctx, "status")) == 1  # хеш не змінився
    woodstore_app.set_status(state="idle", cycles_today=374)  # cycles_today у хеш не входить, state — входить
    woodstore_app.jobs["wj-1"]["state"] = "done"
    out = {r.code.rsplit("/", 1)[1]: r for r in await plugin.poll(readings(plugin))}
    assert len(kinds(ctx, "status")) == 2
    assert out["job"].text == "-"  # немає активних завдань -> default
    woodstore_app.set_status(cycles_today=375)
    await plugin.poll(readings(plugin))
    assert len(kinds(ctx, "status")) == 2
    await plugin.disconnect()


async def test_auth_failure_health(ctx, woodstore_app, rest_plugin):
    plugin = await connect(rest_plugin, woodstore_app, key_ref="F3D_CUTOPT_KEY")  # ключ не підходить -> 401
    with pytest.raises(PollError, match="HTTP 401"):
        await plugin.poll(readings(plugin))
    health = plugin.health()
    assert health.state == "error" and health.error == "auth"
    await plugin.disconnect()


async def test_events_cursor(ctx, woodstore_app, rest_plugin, tmp_path):
    plugin = await connect(rest_plugin, woodstore_app)
    adapter = plugin.adapter
    woodstore_app.add_events(250)
    await adapter.events_step()
    evs = kinds(ctx, "events")
    assert [len(e["items"]) for e in evs] == [200, 50]
    first_get = woodstore_app.calls_of("GET", "/api/v1/events")[0]
    assert "since" not in first_get[2]
    state_file = tmp_path / "woodstore_REST-WOODSTORE-T.json"
    assert json.loads(state_file.read_text())["last_event_id"] == 250
    woodstore_app.add_events(3)
    await adapter.events_step()
    assert woodstore_app.calls_of("GET", "/api/v1/events")[-1][2] == {"since": "250"}
    assert [len(e["items"]) for e in kinds(ctx, "events")] == [200, 50, 3]
    await adapter.events_step()  # нових немає -> подій немає
    assert len(kinds(ctx, "events")) == 3
    # курсор переживає перезапуск плагіна
    plugin2 = await connect(rest_plugin, woodstore_app)
    plugin2.adapter._load_state()
    assert plugin2.adapter.cursor["last_event_id"] == 253
    # невідомий курсор (410) -> скидання
    plugin2.adapter.cursor["last_event_id"] = 9999
    await plugin2.adapter.events_step()
    assert "last_event_id" not in plugin2.adapter.cursor
    await plugin.disconnect()
    await plugin2.disconnect()


async def test_stacks_hash_and_resend(ctx, woodstore_app, rest_plugin, vclock):
    plugin = await connect(rest_plugin, woodstore_app)
    adapter = plugin.adapter
    await adapter.stacks_step()
    evs = kinds(ctx, "stacks")
    assert len(evs) == 1 and len(evs[0]["items"]) == 27 and len(evs[0]["hash"]) == 64
    await adapter.stacks_step()
    assert len(kinds(ctx, "stacks")) == 1  # хеш не змінився
    woodstore_app.stacks[0]["qty"] = 12
    await adapter.stacks_step()
    assert len(kinds(ctx, "stacks")) == 2
    await vclock.tick(14 * 60)
    await adapter.stacks_step()
    assert len(kinds(ctx, "stacks")) == 2
    await vclock.tick(60)  # минуло 15 хв від останньої відправки
    await adapter.stacks_step()
    assert len(kinds(ctx, "stacks")) == 3
    await plugin.disconnect()


async def test_jobs_changed_only(ctx, woodstore_app, rest_plugin):
    plugin = await connect(rest_plugin, woodstore_app)
    adapter = plugin.adapter
    await adapter.jobs_step()
    assert [j["id"] for e in kinds(ctx, "jobs") for j in e["items"]] == ["wj-1"]
    assert "since" not in woodstore_app.calls_of("GET", "/api/v1/jobs")[-1][2]
    woodstore_app.set_job("wj-2", "queued", created="2026-10-12T06:10:00Z")
    await adapter.jobs_step()
    assert woodstore_app.calls_of("GET", "/api/v1/jobs")[-1][2]["since"] == "2026-10-12T06:00:02Z"
    assert [j["id"] for j in kinds(ctx, "jobs")[-1]["items"]] == ["wj-2"]
    await adapter.jobs_step()  # (state, done) не змінились
    assert len(kinds(ctx, "jobs")) == 2
    woodstore_app.set_job("wj-2", "active", done=3, created="2026-10-12T06:10:00Z", started="2026-10-12T06:11:00Z")
    await adapter.jobs_step()
    assert [(j["id"], j["done"]) for j in kinds(ctx, "jobs")[-1]["items"]] == [("wj-2", 3)]
    await plugin.disconnect()


async def test_loops_run_on_clock(ctx, woodstore_app, rest_plugin, vclock):
    plugin = rest_plugin(woodstore_app, "woodstore")
    await plugin.connect()
    woodstore_app.add_events(2)
    await until(lambda: kinds(ctx, "stacks") and kinds(ctx, "jobs"))
    await until(lambda: len(woodstore_app.calls_of("GET", "/api/v1/events")) >= 1)
    n = len(woodstore_app.calls_of("GET", "/api/v1/events"))
    await vclock.tick(2)
    await until(lambda: len(woodstore_app.calls_of("GET", "/api/v1/events")) > n)
    assert 2 in vclock.sleeps and 30 in vclock.sleeps and 10 in vclock.sleeps
    await plugin.disconnect()


async def test_commands(ctx, woodstore_app, rest_plugin):
    plugin = await connect(rest_plugin, woodstore_app)
    cmd = sig(plugin, "/cmd")
    result = await plugin.call(cmd, FEED)
    assert result["state"] == "queued" and result["id"].startswith("wj-")
    post = woodstore_app.calls_of("POST", "/api/v1/jobs")[-1]
    assert post[3] == FEED_BODY
    await plugin.call(cmd, {**FEED, "stack": None})
    assert woodstore_app.calls_of("POST", "/api/v1/jobs")[-1][3]["source"] is None
    woodstore_app.conflict_next = True
    with pytest.raises(WriteError, match="CONFLICT: not enough sheets"):
        await plugin.call(cmd, FEED)
    assert await plugin.call(cmd, {"op": "cancel", "id": "wj-1"}) == {"id": "wj-1", "state": "cancelled"}
    assert woodstore_app.calls_of("DELETE", "/api/v1/jobs/wj-1")
    stack = {"op": "stack", "stack": "PLT-07C", "qty": 55, "product": "DSP16-SON", "lot": None}
    assert await plugin.call(cmd, stack) == {"id": "PLT-07C", "qty": 55}
    patch = woodstore_app.calls_of("PATCH", "/api/v1/stacks/PLT-07C")[-1]
    assert patch[3] == {"qty": 55, "product": "DSP16-SON", "lot": None, "reason": "odoo_inventory"}
    await plugin.disconnect()


async def test_commands_text_fallback(ctx, woodstore_app, rest_plugin):
    plugin = await connect(rest_plugin, woodstore_app)
    cmd = sig(plugin, "/cmd")
    result = await plugin.write(cmd, None, FEED_TEXT)
    assert result.startswith("wj-")
    assert woodstore_app.calls_of("POST", "/api/v1/jobs")[-1][3] == FEED_BODY
    assert await plugin.write(cmd, None, "cancel;wj-1") == "cancelled"
    assert await plugin.write(cmd, None, "stack;PLT-07C;55;DSP16-SON;-") == "stack PLT-07C=55"
    n = len(woodstore_app.calls)
    with pytest.raises(WriteError, match="bad_command: stack: відсутнє"):
        await plugin.call(cmd, {"op": "feed", "sheets": 4})
    with pytest.raises(WriteError, match="bad_command"):
        await plugin.write(cmd, None, "feed;x")
    assert len(woodstore_app.calls) == n  # HTTP-запитів немає
    with pytest.raises(NotSupported):
        await plugin.call(sig(plugin, "/state"), FEED)
    with pytest.raises(NotSupported):
        await plugin.write(sig(plugin, "/state"), None, FEED_TEXT)
    await plugin.disconnect()
