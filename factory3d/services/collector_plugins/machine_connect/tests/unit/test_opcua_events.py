"""AC-72: события и тревоги OPC UA -> EV-01 (`mc_opcua`)."""

from __future__ import annotations

import logging
import re

from conftest import until
from f3d_collector_mc.events import event_id

REQUIRED = {"kind", "source", "machine", "time", "category", "text"}


async def start(make_opcua, **kw):
    plugin = make_opcua("SAW-T", events=True, **kw)
    await plugin.connect()
    await plugin.subscribe()
    return plugin


async def test_alarm_event_payload(ctx, ua_server, make_opcua):
    await start(make_opcua)
    await ua_server.fire_event("alarm", "E0421", 5, "Помилка шпинделя осі Z", "Spindle error axis Z")
    await until(lambda: ctx.events, timeout=3)
    assert len(ctx.events) == 1
    ev = ctx.events[0]
    assert ev.route == "mc_opcua" and ev.remote == "UA-SAW-T" and ev.headers == {}
    p = ev.payload
    assert REQUIRED <= set(p)
    assert (p["kind"], p["source"], p["machine"]) == ("alarm", "UA-SAW-T", "SAW-T")
    assert (p["category"], p["message_id"], p["message_name"]) == (5, "E0421", "SpindleOverload")
    assert p["active"] is True and p["acked"] is False
    assert p["text"] == "Помилка шпинделя осі Z"
    assert p["texts"] == {"uk": "Помилка шпинделя осі Z", "en": "Spindle error axis Z"}
    assert p["path"] == ["SAW-T", "Spindle", "Z"] and p["group"] == "Drive"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", p["time"])
    assert 1 <= p["severity"] <= 1000 and len(p["text"]) <= 256
    assert ev.event_id == event_id("mc_opcua", "UA-SAW-T", p)
    assert len(ev.event_id) == 64


async def test_plain_event_kind(ctx, ua_server, make_opcua):
    await start(make_opcua)
    await ua_server.fire_event("event", "I0007", 2, "Зміна інструмента", "Tool change")
    await until(lambda: ctx.events, timeout=3)
    assert ctx.events[0].payload["kind"] == "event"
    assert ctx.events[0].payload["category"] == 2
    assert (
        ctx.metrics.registry.get_sample_value(
            "collector_mc_opcua_events_total", {"source": "UA-SAW-T", "kind": "event"}
        )
        == 1
    )


async def test_event_dedup_id(ctx, ua_server, make_opcua):
    await start(make_opcua)
    await ua_server.fire_event("alarm", "E0421", 5, "Помилка", "Error")
    await until(lambda: len(ctx.events) == 1, timeout=3)
    first = ctx.events[0]
    # однаковий вміст -> однаковий event_id (дедуплікація в Odoo), інший вміст -> інший
    from f3d_collector_mc.events import make_event

    assert make_event("mc_opcua", "UA-SAW-T", dict(first.payload)).event_id == first.event_id
    assert make_event("mc_opcua", "UA-SAW-T", {**first.payload, "text": "інше"}).event_id != first.event_id
    assert make_event("mc_opcua", "UA-OTHER", dict(first.payload)).event_id != first.event_id


async def test_unknown_event_type_fallback(ctx, ua_server, make_opcua, caplog):
    caplog.set_level(logging.WARNING)
    # неіснуючий URI Woodworking: типи не знайдено -> BaseEventType із WARNING
    plugin = make_opcua("SAW-T", events=True)
    sig = next(s for s in plugin.source.signals if s.address.get("events"))
    object.__setattr__(sig, "address", {**sig.address, "ww_uri": "http://example.org/other/"})
    await plugin.connect()
    await plugin.subscribe()
    assert any("Woodworking event types not found" in r.getMessage() for r in caplog.records)
    await ua_server.fire_event("alarm", "E1", 5, "Помилка", "Error")
    await until(lambda: ctx.events, timeout=3)
    assert ctx.events[0].payload["machine"] == "SAW-T"
