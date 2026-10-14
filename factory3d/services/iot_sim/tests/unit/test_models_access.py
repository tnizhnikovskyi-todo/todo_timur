"""R-28 (СКУД BioStar); SPEC §13.1, AC-16, AC-55."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from iot_sim.core.rng import det
from iot_sim.models.access import DEVICE_ID, EV_CARD, EV_DENIED, EV_FACE, verify_code

pytestmark = pytest.mark.unit

KYIV = ZoneInfo("Europe/Kyiv")
CODES = (["OP-SAW-1", "OP-SAW-2", "OP-SLIDE-1", "OP-NEST-1", "OP-EDGE-1", "OP-EDGE-2", "OP-CNC-3", "OP-CNC-1",
          "OP-CNC-2", "OP-BORE-1", "OP-CNC-4", "OP-DOWEL-1", "OP-SAND-1", "OP-AUTOSPRAY-1", "OP-HINGE-1",
          "OP-GLUE-1", "OP-PRESS-1", "OP-SPRAY-1", "OP-ASMLINE-1", "OP-ASM-1", "OP-ASM-2", "OP-ASM-3",
          "OP-ASM-4", "OP-ASM-6", "OP-PACK-1", "OP-PACK-2", "OP-BOX-1", "OP-PACKLINE-1"]
         + [f"OP-W{i}" for i in range(1, 8)])


@pytest.fixture
def people():
    return [{"code": c, "barcode": c.replace("-", ""), "name": f"Працівник {c}", "group": "Виробництво"}
            for c in CODES]


@pytest.fixture
def ctl(world, people):
    assert len(people) == 35
    world.people = people
    world.step(1)
    return world.devices["ACCESS"].model.ctl


def entries(ctl):
    return [e for e in ctl.events if e["device"] == "ACR-IN" and e["tna_key"] == "1"]


def test_checkin_schedule(world, ctl):
    ev = entries(ctl)
    assert len(ev) == 35 and len({e["user_id"] for e in ev}) == 35
    for e in ev:
        t = e["datetime"].astimezone(KYIV)
        assert t.date() == datetime(2026, 10, 12).date()
        assert datetime(2026, 10, 12, 6, 40, tzinfo=KYIV) <= t < datetime(2026, 10, 12, 7, 0, tzinfo=KYIV)
        assert e["tna_key"] == "1" and e["device_id"] == "5390001"
    ids = [e["id"] for e in ctl.events]
    assert ids == sorted(ids)  # id і datetime зростають разом
    dts = [e["datetime"] for e in ctl.events]
    assert dts == sorted(dts)


def test_event_codes(world, ctl):
    assert {e["code"] for e in entries(ctl)} <= {EV_CARD, EV_FACE} and len({e["code"] for e in entries(ctl)}) == 2
    door = {e["code"] for e in ctl.events if e["door_id"] == 1 and e["device"] is None}
    assert door == {20480, 20992, 21248}  # двері TURN-1 після входу; не належать зчитувачу
    # AC-16: пошук за device_id.id=5390001 + код входу -> рівно 35
    rows, total = ctl.search(device_id=DEVICE_ID["ACR-IN"])
    assert total == 35 and all(r["code"] in (EV_CARD, EV_FACE) for r in rows)
    r1, _ = ctl.search(device_id="ACR-IN", code=EV_CARD)
    assert all(e["code"] == EV_CARD for e in r1)
    rows, total = ctl.search(user_id="OPSAW1")
    assert total >= 1 and all(r["user_id"] == "OPSAW1" for r in rows)
    t0 = datetime(2026, 10, 12, 6, 40, tzinfo=KYIV)
    _, in_window = ctl.search(start=t0, end=t0 + timedelta(minutes=5), device_id="ACR-IN")
    assert 0 < in_window < 35
    assert world.signals["access/readers/ACR-IN/last_event"].value in (EV_CARD, EV_FACE)
    assert world.signals["access/events"].value == len(ctl.events)
    assert world.signals["access/turnstiles/TURNSTILES/on_site"].value == 35 == ctl.on_site


def test_det_parity(ctl):
    for e in entries(ctl):
        code = next(p["code"] for p in ctl.world.people if p["barcode"] == e["user_id"])
        assert (e["code"] == EV_CARD) == (det(code) % 2 == 0) == (verify_code(code) == EV_CARD)
        minute = e["datetime"].astimezone(KYIV).minute
        assert minute == 40 + det(code) % 20 - (60 if 40 + det(code) % 20 >= 60 else 0)


def test_search_order_offset_hint(ctl):
    full, total = ctl.search(device_id="ACR-IN", limit=100)
    p1, tot = ctl.search(device_id="ACR-IN", limit=10, offset=0)
    p2, _ = ctl.search(device_id="ACR-IN", limit=10, offset=10)
    assert tot == total == 35 and len(p1) == len(p2) == 10
    assert [r["datetime"] for r in p1 + p2] == sorted(r["datetime"] for r in p1 + p2)
    assert len({r["id"] for r in p1 + p2}) == 20
    h2, _ = ctl.search(device_id="ACR-IN", limit=10, hint=p1[-1]["hint"])  # без offset
    assert [r["id"] for r in h2] == [r["id"] for r in p2]
    assert [r["id"] for r in full[:20]] == [r["id"] for r in p1 + p2]
    desc, _ = ctl.search(device_id="ACR-IN", limit=100, descending=True)
    assert [r["id"] for r in desc] == [r["id"] for r in reversed(full)]
    assert ctl.search(device_id="ACR-IN", hint="h-unknown", limit=3)[0][0]["id"] == full[0]["id"]


def test_exit_and_roles_after_shift(world, ctl):
    assert [e for e in ctl.events if e["tna_key"] == "2"] == []
    roles = {(e["user_id"], e["device"]) for e in ctl.events if e["device"] in ("ACR-ELEC", "ACR-PAINT")}
    assert ("OPW1", "ACR-ELEC") in roles and ("OPW2", "ACR-PAINT") in roles  # 09:51, 10:20
    elec = next(e for e in ctl.events if e["device"] == "ACR-ELEC")
    assert elec["datetime"].astimezone(KYIV).strftime("%H:%M") == "09:51"
    world.clock.set(datetime(2026, 10, 12, 16, 30))
    world.advance(10)
    outs = [e for e in ctl.events if e["tna_key"] == "2"]
    assert len(outs) == 35 and all(
        datetime(2026, 10, 12, 15, 30, tzinfo=KYIV) <= e["datetime"].astimezone(KYIV)
        < datetime(2026, 10, 12, 15, 50, tzinfo=KYIV) for e in outs)
    assert ctl.on_site == 0 and world.signals["access/turnstiles/TURNSTILES/on_site"].value == 0


def test_access_event_scenario_topic(world, ctl):
    n = len(ctl.events)
    world.post("access", {"device": "ACR-SRV", "user": "OPW7", "code": EV_CARD, "tna_key": "", "door_open": True})
    world.step(1)
    new = ctl.events[n:]
    assert [e["code"] for e in new] == [EV_CARD, 20480, 20992, 21248]
    assert new[0]["device"] == "ACR-SRV" and new[0]["user_id"] == "OPW7" and new[0]["door_id"] == 5
    world.post("access", {"device": "ACR-ELEC", "user": "", "code": EV_DENIED, "tna_key": "", "door_open": True})
    world.step(1)
    denied = ctl.events[-1]
    assert denied["code"] == EV_DENIED and denied["user_id"] is not None  # випадковий працівник
    assert world.events.last("access").payload["code"] == EV_DENIED  # 6400 -> подія
    world.post("access", {})
    world.step(1)
    assert ctl.events[-4]["device"] == "ACR-IN"  # за замовчуванням ACR-IN, 4102
    assert world.signals["access/readers/ACR-ELEC/last_event"].value == EV_DENIED


def test_weekend_and_no_people(world):
    world.clock.set(datetime(2026, 10, 17, 10, 0))  # субота
    world.people = [{"code": "OP-W1", "barcode": "OPW1", "name": "x", "group": "g"}]
    world.step(1)
    assert world.devices["ACCESS"].model.ctl.events == []
    world.clock.set(datetime(2026, 10, 19, 6, 0))  # понеділок
    world.step(1)
    assert world.devices["ACCESS"].model.ctl.events == []  # ще до 06:40
    world.advance(3600)
    assert len(world.devices["ACCESS"].model.ctl.events) >= 4


def test_snapshot_roundtrip(world, ctl):
    acc = world.devices["ACCESS"].model
    state = acc.get_state()
    assert world.devices["ACR-IN"].model.get_state() == {}
    n = len(ctl.events)
    ctl.events.clear()
    ctl.on_site = 0
    acc.set_state(state)
    assert len(ctl.events) == n and ctl.on_site == 35
    acc.set_state({})
    assert ctl.events[0]["datetime"].tzinfo is not None
    world.step(10)
    assert len(ctl.events) == n  # розклад не дублюється


def test_fire_drill_doors_once(world, ctl):
    world.set_flag("fire_drill", {"zone": "FA-CNC", "detector": "", "real": False,
                                  "t0": world.now().isoformat(), "phase": "active"})
    for _ in range(30):
        world.step(1)
    assert sum(1 for e in ctl.events if e["code"] == 26368) == 1
    assert sum(1 for e in ctl.events if e["code"] == 20480 and e["door_id"] == 3) >= 1
