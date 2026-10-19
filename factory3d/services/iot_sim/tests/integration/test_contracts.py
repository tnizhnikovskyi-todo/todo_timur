"""Контракти «протокол <-> модель <-> ядро» (World + моделі + сервер у пам'яті, без мережі)."""

import logging
import re
from pathlib import Path

from iot_sim.config import Settings
from iot_sim.core.registry import Registry
from iot_sim.core.world import BOUNDED_TOPICS, World

SRC = Path(__file__).resolve().parents[2] / "iot_sim"


def _topics(pattern: str) -> set[str]:
    out: set[str] = set()
    for f in SRC.rglob("*.py"):
        if f.name == "world.py":
            continue
        out |= set(re.findall(pattern, f.read_text(encoding="utf-8")))
    return out


def test_every_posted_topic_is_drained_or_bounded():
    posted = _topics(r"\.post\(\s*\"([a-z_]+)\"")
    posted |= {"modbus_cmd", "yard", "boiler"}  # тема обчислюється в modbus_maps/__init__, bacnet_server
    drained = _topics(r"drain\(\s*\"([a-z_]+)\"")
    orphan = posted - drained - set(BOUNDED_TOPICS)
    assert not orphan, f"теми без споживача: {orphan}"


def test_undrained_topic_queue_is_bounded(world):
    for i in range(BOUNDED_TOPICS["hvac"] + 50):
        world.post("hvac", {"i": i})
    assert len(world.drain("hvac")) == BOUNDED_TOPICS["hvac"]
    world.post("yard", {"kind": "x"})  # теми з моделлю-споживачем не обрізаються
    assert world.inbox["yard"].maxlen is None


def test_yard_lpr_event_reaches_lpr_pusher(world):
    """yard: emit("yard", payload={"lpr":…}) -> LprPusher._on_event -> тіло Axis."""
    from iot_sim.protocols.lpr_push import LprPusher

    pusher = LprPusher(world, url="http://127.0.0.1:1/x")
    pusher._loop = object()
    sent = []
    pusher._spawn = lambda body, ev: sent.append((body, ev.device))
    world.events.subscribe(pusher._on_event)
    world.post("yard", {"kind": "truck_no_booking"})
    for _ in range(200):
        world.advance(10)
        if sent:
            break
    assert sent, "yard не видав подію з payload['lpr']"
    body, dev = sent[0]
    assert dev in ("CAM-05", "CAM-06") and body["plateText"] and body["sensorProviderID"] == dev


def test_access_events_reach_biostar(world):
    """access: emit("access", device, payload{user_id,event_code,door,tna_key}) -> BioStarStore."""
    from iot_sim.protocols.biostar_api import BioStarApi

    srv = BioStarApi(world, password="x", cert_dir="/nonexistent")
    world.people = [{"barcode": "OPSAW1", "name": "Operator"}]
    before = len(srv.store.events)
    world.post("access", {"device": "ACR-IN", "user": "OPSAW1", "code": 4102, "tna_key": "1"})
    world.advance(1)
    new = srv.store.events[before:]
    assert any(
        e["user_id"] == "OPSAW1" and e["code"] == 4102 and e["tna_key"] == "1" and e["device"] == "5390001" for e in new
    )


def test_mobile_signals_feed_mqtt_telemetry(world):
    from iot_sim.protocols.mqtt_publisher import MqttPublisher

    pub = MqttPublisher(world, client_factory=lambda: object())
    world.advance(60)
    world.flags["mobile"] = {"FL-1": {"zone": "Z-WH"}}
    tel = pub.telemetry("FL-1")
    assert 0 < tel["battery_pct"] <= 100 and tel["hours"] > 0
    assert tel["state"] and "x" in tel and "y" in tel
    assert world.signals["equipment/FL-1/state"].value == tel["state"] or tel["state"] in ("fault", "offline")


def test_sics_reads_yard_scale_signals(world):
    from iot_sim.protocols.sics_server import SicsServer

    srv = SicsServer(world, port=0)
    sig = world.devices["TRUCK-SCALE"].signals
    assert {"weight_kg", "stable"} <= set(sig)
    sig["weight_kg"].set(21500.0, world.now())
    sig["stable"].set(False, world.now())
    assert srv._gross() == 21500.0 and srv._stable() is False


def test_follow_odoo_data_drives_models(world):
    """follow_odoo заповнює world.* у своєму форматі; моделі їх читають."""
    code = next(c for c, d in world.devices.items() if d.driver == "machine")
    world.workcenters = {code: {"state": "ERROR", "blocked": True, "job": None, "qty_produced": 0.0}}
    world.jobs = [{"id": "WO00013", "wo_id": 13, "workcenter": code, "state": "ready", "name": "X"}]
    world.people = [{"name": "A", "barcode": "OPSAW1", "job": None, "shift": None}]
    world.trucks = [
        {
            "code": "TRUCK-IN-1",
            "batch": "WH/BATCH/1",
            "type": "incoming",
            "plate": None,
            "dock": "DOCK-W1",
            "scheduled": "2026-10-12T07:40:00Z",
            "state": "assigned",
            "progress": 0.0,
        }
    ]
    world.maintenance_closed.add("nothing")
    world.advance(30)
    assert world.devices[code].model.flags.get("ExternalEmergency") is not None
    yard = next(d.model for d in world.devices.values() if d.driver == "yard" and hasattr(d.model, "ctl"))
    assert any(t["id"] == "TRUCK-IN-1" for t in yard.ctl.trucks)


def test_modbus_ctx_respects_write_accept(world):
    from iot_sim.protocols.modbus_maps import Ctx

    world.settings = Settings(write_accept=False, _env_file=None)
    assert Ctx(world).write_accept is False
    world.settings = Settings(_env_file=None)
    assert Ctx(world).write_accept is True


def test_bacnet_write_accept_flag(world):
    from iot_sim.protocols.bacnet_server import BacnetServer

    srv = BacnetServer(world, address="127.0.0.1/8:47999")
    assert srv._write_accept() is True
    world.settings = Settings(write_accept=False, _env_file=None)
    assert srv._write_accept() is False


def test_short_key_collision_is_explicit(registry, clock, caplog):
    with caplog.at_level(logging.WARNING, logger="iot_sim.world"):
        w = World(registry, seed=1, clock=clock)
    dev = w.devices["AHU-1"]
    a, b = "ventilation/units/AHU-1/p_now", "energy/consumers/AHU-1/p_now"
    assert dev.by_code[a].code == a and dev.by_code[b].code == b  # обидва за повним кодом
    first = next(s.code for s in registry.signals if s.code in (a, b))
    assert dev.signals["AHU-1/p_now"].code == first  # короткий — першому за каталогом
    assert any("AHU-1" in r.message and "p_now" in r.message for r in caplog.records)
    assert isinstance(registry, Registry)
