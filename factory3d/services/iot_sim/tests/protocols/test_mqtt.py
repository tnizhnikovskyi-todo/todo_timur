"""P-06: MQTT-телематика (SPEC §8.8) на моку paho-клієнта (брокер не потрібен)."""

import json

import pytest
from iot_sim.protocols.mqtt_publisher import BUFFER_S, MqttPublisher, parse_mqtt_url


class FakeClient:
    def __init__(self):
        self.published = []
        self.will = None
        self.calls = []

    def username_pw_set(self, u, p):
        self.calls.append(("auth", u, p))

    def will_set(self, topic, payload, qos=0, retain=False):
        self.will = (topic, json.loads(payload), qos, retain)

    def reconnect_delay_set(self, **kw):
        pass

    def connect_async(self, host, port, keepalive=60):
        self.calls.append(("connect", host, port))

    def loop_start(self):
        self.calls.append(("loop_start",))

    def loop_stop(self):
        self.calls.append(("loop_stop",))

    def disconnect(self):
        self.calls.append(("disconnect",))

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, json.loads(payload), qos, retain))

    def by(self, suffix):
        return [p for p in self.published if p[0].endswith(suffix)]


class Mono:
    t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
async def pub(world):
    client, mono = FakeClient(), Mono()
    p = MqttPublisher(world, url="mqtt://iot_sim:pw@broker:1883", client_factory=lambda: client, clock=mono)
    p.fake, p.mono = client, mono
    await p.start()
    yield p
    await p.stop()


def connect(p):
    p._on_connect(p.fake, None, None, 0)


def test_parse_url():
    assert parse_mqtt_url("mqtt://u:p%40@mosquitto:1884") == {
        "host": "mosquitto",
        "port": 1884,
        "user": "u",
        "password": "p@",
        "tls": False,
    }
    assert parse_mqtt_url("mqtt://mosquitto")["port"] == 1883


async def test_start_configures_client_and_lwt(pub):
    assert ("auth", "iot_sim", "pw") in pub.fake.calls and ("connect", "broker", 1883) in pub.fake.calls
    topic, body, qos, retain = pub.fake.will
    assert topic == "f3d/mobile/_all/status" and body == {"online": False} and qos == 1 and retain
    assert pub.codes == ["FL-1", "FL-2", "FL-3", "FL-4", "FL-5", "FL-C1", "FL-C2", "TUGGER-1"]


async def test_status_retained_on_connect(pub):
    connect(pub)
    st = pub.fake.by("/FL-1/status")
    assert len(st) == 1
    topic, body, qos, retain = st[0]
    assert topic == "f3d/mobile/FL-1/status" and qos == 1 and retain is True
    assert body["code"] == "FL-1" and body["online"] is True and body["gateway"] == "sim" and body["fw"]
    assert len(pub.fake.by("/status")) == 8


async def test_telemetry_topic_payload_qos(pub, world):
    connect(pub)
    pub.fake.published.clear()
    pub.tick()
    tel = pub.fake.by("/FL-1/telemetry")
    assert len(tel) == 1
    topic, body, qos, retain = tel[0]
    assert topic == "f3d/mobile/FL-1/telemetry" and qos == 1 and retain is False
    for k in ("ts", "code", "state", "battery_pct", "hours", "x", "y", "faults"):
        assert k in body
    assert body["code"] == "FL-1" and body["battery_pct"] == pytest.approx(
        world.devices["FL-1"].signals["battery"].value, abs=0.06
    )
    assert body["state"] in ("idle", "busy", "to_charge", "charging", "offline", "fault")
    assert 0 <= body["battery_pct"] <= 100 and isinstance(body["faults"], list)


async def test_period_5s_and_1s_when_moving(pub, world):
    connect(pub)
    pub.tick()
    pub.fake.published.clear()
    pub.mono.t += 1
    pub.tick()
    assert pub.fake.by("/FL-1/telemetry") == []  # у спокої — раз на 5 с
    pub.mono.t += 4
    pub.tick()
    assert len(pub.fake.by("/FL-1/telemetry")) == 1
    world.flags["mobile"] = {"FL-1": {"speed_kmh": 6.2}}
    pub.fake.published.clear()
    pub.mono.t += 1
    pub.tick()
    assert len(pub.fake.by("/FL-1/telemetry")) == 1  # у русі — раз на 1 с
    assert pub.fake.by("/FL-1/telemetry")[0][1]["speed_kmh"] == 6.2


async def test_state_change_publishes_now_and_events(pub, world):
    connect(pub)
    pub.tick()
    sig = world.devices["FL-2"].signals["state"]
    pub.fake.published.clear()
    sig.force("charging", world.now())
    pub.mono.t += 0.1
    pub.tick()
    tel = pub.fake.by("/FL-2/telemetry")
    assert len(tel) == 1 and tel[0][1]["state"] == "charging"
    ev = pub.fake.by("/FL-2/event")
    assert [e[1]["type"] for e in ev] == ["charge_start"] and ev[0][2] == 1 and ev[0][3] is False
    sig.force("busy", world.now())
    pub.mono.t += 0.1
    pub.tick()
    assert "charge_end" in [e[1]["type"] for e in pub.fake.by("/FL-2/event")]


async def test_fault_and_low_battery_and_task_events(pub, world):
    connect(pub)
    pub.tick()
    pub.fake.published.clear()
    world.devices["FL-3"].signals["battery"].force(15.0, world.now())
    world.fault("FL-3", "generic")
    pub.mono.t += 0.1
    pub.tick()
    types = [e[1]["type"] for e in pub.fake.by("/FL-3/event")]
    assert "fault" in types and "low_battery" in types
    assert pub.fake.by("/FL-3/telemetry")[-1][1]["faults"] == ["generic"]
    world.flags["mobile"] = {"FL-4": {"task": "WH/SFP/00201"}}
    pub.mono.t += 0.1
    pub.tick()
    assert [e[1]["type"] for e in pub.fake.by("/FL-4/event")] == ["task_start"]
    world.flags["mobile"] = {}
    pub.mono.t += 0.1
    pub.tick()
    assert [e[1]["type"] for e in pub.fake.by("/FL-4/event")] == ["task_start", "task_end"]


async def test_heartbeat_qos0_every_60s(pub):
    connect(pub)
    pub.tick()
    hb = pub.fake.by("/_all/heartbeat")
    assert len(hb) == 1 and hb[0][2] == 0 and hb[0][3] is False and "FL-1" in hb[0][1]["online"]
    pub.mono.t += 30
    pub.tick()
    assert len(pub.fake.by("/_all/heartbeat")) == 1
    pub.mono.t += 31
    pub.tick()
    assert len(pub.fake.by("/_all/heartbeat")) == 2


async def test_buffer_while_offline_then_flush(pub):
    pub.tick()  # брокера немає: усе в буфері
    assert pub.fake.published == [] and pub.health()["buffered"] > 0
    n = pub.health()["buffered"]
    connect(pub)
    assert pub.health()["buffered"] == 0 and len(pub.fake.by("/telemetry")) == 8
    assert len(pub.fake.published) >= n


async def test_buffer_drops_older_than_10_minutes(pub):
    pub.tick()
    first = pub.health()["buffered"]
    pub.mono.t += BUFFER_S + 1
    pub.tick()
    assert pub.dropped >= first and pub.health()["dropped"] == pub.dropped
    connect(pub)
    assert pub.health()["buffered"] == 0


async def test_disconnect_then_reconnect_restores_retained_status(pub):
    connect(pub)
    pub.fake.published.clear()
    pub._on_disconnect(pub.fake, None)
    assert pub.health()["connected"] is False
    connect(pub)
    assert len(pub.fake.by("/status")) == 8 and all(p[3] for p in pub.fake.by("/status"))


async def test_stop_publishes_offline_status(world):
    client = FakeClient()
    p = MqttPublisher(world, client_factory=lambda: client, clock=Mono())
    await p.start()
    p._on_connect(client, None, None, 0)
    client.published.clear()
    await p.stop()
    off = client.by("/status")
    assert len(off) == 8 and all(o[1]["online"] is False and o[3] for o in off)
    assert ("disconnect",) in client.calls and ("loop_stop",) in client.calls


async def test_status_republished_on_comm_fault_and_clear(pub, world):
    """AC-40: після fault comm FL-3 → status online=false (retained); після clear — true."""
    connect(pub)
    pub.tick()
    n0 = len(pub.fake.by("/FL-3/status"))
    world.fault("FL-3", "comm")
    pub.tick()
    st = pub.fake.by("/FL-3/status")
    assert len(st) == n0 + 1 and st[-1][1]["online"] is False and st[-1][3] is True
    world.clear("FL-3")
    pub.tick()
    assert pub.fake.by("/FL-3/status")[-1][1]["online"] is True


async def test_telemetry_state_to_charge_from_model(pub, world):
    """AC-08: telemetry.state = to_charge (сигнал state віддає його як busy)."""
    m = world.devices["FL-2"].model
    m._set_state("to_charge")
    world.devices["FL-2"].signals["state"].force("busy", world.now())
    assert pub.telemetry("FL-2")["state"] == "to_charge"
