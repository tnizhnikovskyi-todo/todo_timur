"""AC-79, AC-101 (mqtt): плагін mqtt на фейковому paho-клієнті; `-m broker` — на справжньому брокері."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime

import pytest

from collector.core.errors import NotSupported, WriteError
from collector.plugins.mqtt import MqttPlugin, topic_matches

from . import mk_signal, mk_source

TOPIC = "f3d/mobile/FL-1/telemetry"
BODY = {"battery_pct": 57.1, "hours": 2069.8, "x": 112.4, "state": "to_charge", "ts": "2026-10-14T08:15:03+03:00"}


def _sigs(**over):
    def a(path, **kw):
        return {"topic": TOPIC, "path": path, "ts_path": "$.ts", "device": "FL-1", **kw}

    return [
        mk_signal("equipment/FL-1/battery", address=a("$.battery_pct"), **over),
        mk_signal("equipment/FL-1/hours", kind="counter", address=a("$.hours")),
        mk_signal("equipment/FL-1/x", address=a("$.x")),
        mk_signal("equipment/FL-1/state", kind="state", address=a("$.state", map={"to_charge": "busy"})),
    ]


PARAMS = {
    "host": "iot-sim",
    "client_id": "f3d",
    "topics": ["f3d/mobile/+/telemetry"],
    "status_topic": "f3d/mobile/{device}/status",
    "username": "u",
    "password_ref": "F3D_MQTT_PASSWORD",
}


async def _start(make_ctx, fake_mqtt, signals=None, params=None, monkeypatch=None):
    box = make_ctx(secrets=lambda name: "pw")
    p = MqttPlugin(mk_source("MQ", "mqtt", signals or _sigs(), params=params or PARAMS), box.ctx)
    await p.connect()
    await p.subscribe()
    cl = fake_mqtt.instances[-1]
    cl.connect_ok()
    return p, box, cl


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_telemetry_mapping(make_ctx, fake_mqtt):
    p, box, cl = await _start(make_ctx, fake_mqtt)
    assert box.allowed == ["iot-sim"]
    assert cl.subscribed == [[("f3d/mobile/+/telemetry", 1), ("f3d/mobile/+/status", 1)]]
    cl.deliver(TOPIC, json.dumps(BODY).encode())
    await _settle()
    r = {x.code.rsplit("/", 1)[1]: x for x in box.readings}
    assert r["battery"].value == 57.1 and r["hours"].value == 2069.8 and r["x"].value == 112.4
    assert r["state"].text == "busy" and r["state"].value is None
    assert all(x.ts == datetime(2026, 10, 14, 5, 15, 3, tzinfo=UTC) and x.q == "good" for x in r.values())
    assert p.health().state == "online" and p.health().stats["messages"] == 1
    await p.disconnect()


async def test_retain_uncertain(make_ctx, fake_mqtt, vclock):
    p, box, cl = await _start(make_ctx, fake_mqtt)
    cl.deliver(TOPIC, json.dumps(BODY).encode(), retain=True)
    await _settle()
    assert len(box.readings) == 4
    assert all(x.q == "uncertain" and x.ts == vclock.now() for x in box.readings)
    await p.disconnect()


async def test_bad_json(make_ctx, fake_mqtt):
    p, box, cl = await _start(make_ctx, fake_mqtt)
    cl.deliver(TOPIC, b"not json{")
    await _settle()
    assert len(box.readings) == 4
    assert all(x.q == "bad" and x.value is None and x.text is None for x in box.readings)
    await p.disconnect()


async def test_missing_path_metric(make_ctx, fake_mqtt):
    p, box, cl = await _start(make_ctx, fake_mqtt)
    body = {k: v for k, v in BODY.items() if k != "battery_pct"}
    cl.deliver(TOPIC, json.dumps(body).encode())
    await _settle()
    assert [x.code.rsplit("/", 1)[1] for x in box.readings] == ["hours", "x", "state"]
    assert box.metrics.mqtt_missing_path.labels("MQ")._value.get() == 1
    await p.disconnect()


async def test_status_offline_device(make_ctx, fake_mqtt):
    p, box, cl = await _start(make_ctx, fake_mqtt)
    cl.deliver("f3d/mobile/FL-1/status", b'{"online": false}')
    await _settle()
    h = p.health()
    assert h.state == "online" and h.stats["offline_devices"] == ["FL-1"]
    cl.deliver("f3d/mobile/FL-1/status", b'{"online": true}')
    await _settle()
    assert p.health().stats["offline_devices"] == []
    cl.deliver("f3d/mobile/FL-2/status", b"offline")  # LWT простим рядком
    await _settle()
    assert p.health().stats["offline_devices"] == ["FL-2"]
    assert box.readings == []
    await p.disconnect()


async def test_disconnect_states(make_ctx, fake_mqtt):
    p, _, cl = await _start(make_ctx, fake_mqtt)
    assert p.health().state == "online"
    cl.drop()
    assert p.health().state == "offline"
    cl.connect_ok(rc=5)
    assert p.health().state == "error"
    cl.connect_ok(rc=0)
    assert p.health().state == "online"
    await p.disconnect()


async def test_address_scale_not_signal_scale(make_ctx, fake_mqtt):
    sg = mk_signal("energy/p_kw", scale=1000.0, address={"topic": TOPIC, "path": "$.p_w", "scale": 0.001, "offset": 0})
    p, box, cl = await _start(make_ctx, fake_mqtt, [sg])
    cl.deliver(TOPIC, b'{"p_w": 3402}')
    await _settle()
    assert box.readings[0].value == pytest.approx(3.402)  # signal.scale застосовує ядро (Emitter), не плагін
    await p.disconnect()


async def test_write_template_and_unsupported(make_ctx, fake_mqtt):
    sg = mk_signal(
        "equipment/FL-1/cmd",
        write=True,
        kind="state",
        address={
            "topic": TOPIC,
            "path": "$.s",
            "write": {"topic": "f3d/mobile/FL-1/cmd", "template": '{"go": "{text}", "n": {value}}'},
        },
    )
    ro = mk_signal("equipment/FL-1/ro", address={"topic": TOPIC, "path": "$.s"})
    p, _, cl = await _start(make_ctx, fake_mqtt, [sg, ro])
    assert await p.write(sg, 2.0, 'a"b') == "published f3d/mobile/FL-1/cmd"
    assert cl.published == [("f3d/mobile/FL-1/cmd", '{"go": "a\\"b", "n": 2}')]
    with pytest.raises(NotSupported):
        await p.write(ro, 1.0, None)
    cl.drop()
    with pytest.raises(WriteError):
        await p.write(sg, 1.0, None)
    await p.disconnect()


async def test_missing_secret_is_connect_error(make_ctx, fake_mqtt):
    from collector.core.errors import ConnectError

    box = make_ctx(secrets=lambda name: (_ for _ in ()).throw(KeyError(name)))
    p = MqttPlugin(mk_source("MQ", "mqtt", _sigs(), params=PARAMS), box.ctx)
    with pytest.raises(ConnectError, match="F3D_MQTT_PASSWORD"):
        await p.connect()


def test_topic_matches():
    assert topic_matches("a/+/c", "a/b/c") and not topic_matches("a/+/c", "a/b/d")
    assert topic_matches("a/#", "a/b/c") and topic_matches("a/#", "a")
    assert not topic_matches("a/b", "a/b/c") and not topic_matches("a/b/c", "a/b")


def test_validate():
    ok = mk_source("MQ", "mqtt", _sigs(), params=PARAMS)
    assert MqttPlugin.validate(ok) == []
    bad = mk_source(
        "MQ",
        "mqtt",
        [mk_signal("equipment/x/y", address={"topic": "a/+/b", "path": "battery"})],
        params={"host": "h", "client_id": "bad id", "topics": ["a/#/b"], "password": "x"},
    )
    text = "\n".join(MqttPlugin.validate(bad))
    assert "client_id" in text and "#" in text and "секрети" in text and "topic" in text and "path" in text


@pytest.mark.broker
async def test_broker_roundtrip(make_ctx, mqtt_broker):
    import paho.mqtt.client as mqtt

    host, port = mqtt_broker
    box = make_ctx()
    params = {"host": host, "port": port, "client_id": "f3dtest", "topics": [TOPIC]}
    p = MqttPlugin(mk_source("MQ", "mqtt", _sigs(), params=params), box.ctx)
    await p.connect()
    await p.subscribe()
    pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="f3dpub")
    pub.connect(host, port)
    pub.loop_start()
    try:
        deadline = time.monotonic() + 5
        while not box.readings and time.monotonic() < deadline:
            pub.publish(TOPIC, json.dumps(BODY), qos=1)
            await asyncio.sleep(0.3)
        assert any(r.code.endswith("/battery") and r.value == 57.1 for r in box.readings)
    finally:
        pub.loop_stop()
        await p.disconnect()


@pytest.mark.broker
async def test_broker_reconnect(make_ctx, mqtt_broker):
    host, port = mqtt_broker
    box = make_ctx()
    params = {"host": host, "port": port, "client_id": "f3dtest2", "topics": [TOPIC]}
    p = MqttPlugin(mk_source("MQ", "mqtt", _sigs(), params=params), box.ctx)
    await p.connect()
    await p.subscribe()
    try:
        for _ in range(50):
            if p.health().state == "online":
                break
            await asyncio.sleep(0.1)
        assert p.health().state == "online"
    finally:
        await p.disconnect()
