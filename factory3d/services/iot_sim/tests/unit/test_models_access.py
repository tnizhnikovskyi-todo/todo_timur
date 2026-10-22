"""R-28 (СКУД BioStar); SPEC §13.1, AC-16, AC-55."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from iot_sim.core.rng import det
from iot_sim.models.access import DEVICE_ID, EV_CARD, EV_DENIED, EV_FACE, verify_code

pytestmark = pytest.mark.unit

KYIV = ZoneInfo("Europe/Kyiv")
CODES = [
    "OP-SAW-1",
    "OP-SAW-2",
    "OP-SLIDE-1",
    "OP-NEST-1",
    "OP-EDGE-1",
    "OP-EDGE-2",
    "OP-CNC-3",
    "OP-CNC-1",
    "OP-CNC-2",
    "OP-BORE-1",
    "OP-CNC-4",
    "OP-DOWEL-1",
    "OP-SAND-1",
    "OP-AUTOSPRAY-1",
    "OP-HINGE-1",
    "OP-GLUE-1",
    "OP-PRESS-1",
    "OP-SPRAY-1",
    "OP-ASMLINE-1",
    "OP-ASM-1",
    "OP-ASM-2",
    "OP-ASM-3",
    "OP-ASM-4",
    "OP-ASM-6",
    "OP-PACK-1",
    "OP-PACK-2",
    "OP-BOX-1",
    "OP-PACKLINE-1",
] + [f"OP-W{i}" for i in range(1, 8)]


@pytest.fixture
def people():
    return [{"code": c, "barcode": c.replace("-", ""), "name": f"Працівник {c}", "group": "Виробництво"} for c in CODES]


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
        datetime(2026, 10, 12, 15, 30, tzinfo=KYIV)
        <= e["datetime"].astimezone(KYIV)
        < datetime(2026, 10, 12, 15, 50, tzinfo=KYIV)
        for e in outs
    )
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
    world.set_flag(
        "fire_drill",
        {"zone": "FA-CNC", "detector": "", "real": False, "t0": world.now().isoformat(), "phase": "active"},
    )
    for _ in range(30):
        world.step(1)
    assert sum(1 for e in ctl.events if e["code"] == 26368) == 1
    assert sum(1 for e in ctl.events if e["code"] == 20480 and e["door_id"] == 3) >= 1


# --- дві зміни: бригади A (07:00–15:30) і B (15:30–23:00) ------------------------------------------------------
def _set_time(world, hh: int, mm: int = 0) -> None:
    world.clock.set(datetime(2026, 10, 12, hh, mm))
    world.advance(10)


def _inside(ctl) -> set[str]:
    """Хто в будівлі за журналом ACR-IN: останній прохід — вхід (``tna_key`` 1)."""
    last = {}
    for e in sorted((e for e in ctl.events if e["device"] == "ACR-IN" and e["user_id"]), key=lambda e: e["id"]):
        last[e["user_id"]] = e["tna_key"]
    return {u for u, k in last.items() if k == "1"}


def _crew_times(ctl, people):
    """{barcode: (хв входу, хв виходу)} за розкладом доби."""
    out: dict[str, list[int]] = {}
    for _ts, it in ctl.schedule:
        if it["device"] == "ACR-IN" and it["tna"]:
            t = it["when"].astimezone(KYIV)
            out.setdefault(it["user"]["barcode"], [0, 0])[0 if it["tna"] == "1" else 1] = t.hour * 60 + t.minute
    return out


@pytest.fixture
def two_shifts(world, people):
    from datetime import time

    world.shift.shifts = ((time(7, 0), time(15, 30)), (time(15, 30), time(23, 0)))
    world.shift.end = time(23, 0)
    world.people = people
    world.clock.set(datetime(2026, 10, 12, 5, 0))
    world.step(1)
    return world.devices["ACCESS"].model.ctl


def test_two_shifts_split_into_crews(world, people, two_shifts):
    ctl = two_shifts
    times = _crew_times(ctl, people)
    crew_b = {b for b, (t_in, _t_out) in times.items() if t_in >= 15 * 60}
    assert len(times) == 35 and len(crew_b) == 35 // 2  # про половину людей — бригада B
    duty = {c.replace("-", "") for c in ("OP-W1", "OP-W2", "OP-W3", "OP-W5", "OP-W7")}
    assert not duty & crew_b  # чергові ролі — бригада A
    for p in people:
        key, m = p["code"], det(p["code"]) % 20
        t_in, t_out = times[p["barcode"]]
        if p["barcode"] in crew_b:
            assert (t_in, t_out) == (15 * 60 + 10 + m, 23 * 60 + m)
        else:
            assert (t_in, t_out) == (6 * 60 + 40 + m, 15 * 60 + 30 + m)
        assert key  # ключ людини — code


@pytest.mark.parametrize(
    ("hh", "mm"),
    [(10, 0), (15, 40), (16, 0), (23, 30)],
)
def test_two_shifts_who_is_inside(world, people, two_shifts, hh, mm):
    ctl = two_shifts
    _set_time(world, hh, mm)
    times = _crew_times(ctl, people)
    now = hh * 60 + mm
    expected = {b for b, (t_in, t_out) in times.items() if t_in <= now < t_out}
    inside = _inside(ctl)
    assert inside == expected
    assert ctl.on_site == len(inside) == world.signals["access/turnstiles/TURNSTILES/on_site"].value
    crew_b = {b for b, (t_in, _o) in times.items() if t_in >= 15 * 60}
    if (hh, mm) == (10, 0):
        assert inside and not inside & crew_b and len(inside) == 35 - len(crew_b)  # лише бригада A
    elif (hh, mm) == (15, 40):
        assert crew_b <= inside and inside - crew_b  # B повністю + ті з A, хто ще не вийшов (det mod 20 > 10)
        assert len(inside) > len(crew_b)
    elif (hh, mm) == (16, 0):
        assert inside == crew_b  # A вийшла до 15:50
    else:
        assert inside == set() and ctl.on_site == 0  # B вийшла до 23:20


def test_two_shifts_evacuation_takes_everyone_inside(world, people, two_shifts):
    from iot_sim.core.scenarios_evac import FireEvacuationParams, people_on_site, plan_evacuation

    ctl = two_shifts
    _set_time(world, 15, 50)
    inside = _inside(ctl)
    assert len(inside) >= 17  # на 15:50 — уся бригада B
    on_site = people_on_site(world)
    assert {p["barcode"] for p in on_site} == inside
    plan = plan_evacuation(on_site, FireEvacuationParams(stuck=0, wrong_exit_pct=0))
    assert {r["barcode"] for r in plan} == inside


def test_one_shift_unchanged(world, people):
    """Без списку змін (одна зміна 07:00–15:30): усі в A — вхід 06:40…07:00, вихід 15:30…15:50, як раніше."""
    world.people = people
    world.clock.set(datetime(2026, 10, 12, 5, 0))
    world.step(1)
    ctl = world.devices["ACCESS"].model.ctl
    times = _crew_times(ctl, people)
    assert len(times) == 35
    for p in people:
        m = det(p["code"]) % 20
        assert times[p["barcode"]] == [6 * 60 + 40 + m, 15 * 60 + 30 + m]
    for hh, mm, n in ((10, 0, 35), (15, 40, None), (16, 0, 0), (23, 30, 0)):
        _set_time(world, hh, mm)
        inside = _inside(ctl)
        if n is not None:
            assert len(inside) == n
        else:  # 15:40: частина вже вийшла (det mod 20 ≤ 10), решта ще в будівлі
            assert 0 < len(inside) < 35


# --- люди з'являються пізніше за старт емулятора (follow_odoo / відновлення знімка) ----------------------------
def _per_user(ctl, tna: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for e in ctl.events:
        if e["device"] == "ACR-IN" and e["user_id"] and e["tna_key"] == tna:
            out[e["user_id"]] = out.get(e["user_id"], 0) + 1
    return out


def _two_shifts_no_people(world) -> None:
    from datetime import time

    world.shift.shifts = ((time(7, 0), time(15, 30)), (time(15, 30), time(23, 0)))
    world.shift.end = time(23, 0)
    world.clock.set(datetime(2026, 10, 12, 5, 0))
    world.step(1)
    assert world.people == [] and world.devices["ACCESS"].model.ctl.events == []


def test_people_arrive_after_start_build_full_day(world, people):
    _two_shifts_no_people(world)
    ctl = world.devices["ACCESS"].model.ctl
    world.people = people  # як follow_odoo: список людей приходить після старту емулятора
    _set_time(world, 12, 0)
    times = _crew_times(ctl, people)
    crew_b = {b for b, (t_in, _o) in times.items() if t_in >= 15 * 60}
    assert len(times) == 35 and crew_b
    inside = _inside(ctl)
    assert inside and inside == set(times) - crew_b and ctl.on_site == len(inside)  # бригада A вже всередині
    first = min(e["datetime"] for e in entries(ctl)).astimezone(KYIV)
    assert (first.hour, first.minute) >= (6, 40) and first.hour < 7  # доганяння з оригінальними мітками часу
    _set_time(world, 15, 40)
    assert crew_b <= _inside(ctl)  # бригада B увійшла о 15:10–15:30
    for e in entries(ctl):
        if e["user_id"] in crew_b:
            assert (
                datetime(2026, 10, 12, 15, 10, tzinfo=KYIV)
                <= e["datetime"]
                < datetime(2026, 10, 12, 15, 30, tzinfo=KYIV)
            )
    assert ctl.on_site == len(_inside(ctl))
    assert set(_per_user(ctl, "1").values()) == {1}


def test_unchanged_or_grown_people_no_duplicates(world, people):
    _two_shifts_no_people(world)
    ctl = world.devices["ACCESS"].model.ctl
    world.people = people[:30]
    _set_time(world, 12, 0)
    n = len(ctl.events)
    world.people = [dict(p) for p in people[:30]]  # той самий склад новими об'єктами (оновлення з Odoo)
    world.advance(60)
    assert len(ctl.events) == n and set(_per_user(ctl, "1").values()) == {1}
    on_site = ctl.on_site
    world.people = people  # склад змінився: розклад перебудовано, видані події не повторюються
    world.advance(60)
    assert set(_per_user(ctl, "1").values()) == {1} and set(_per_user(ctl, "2").values()) <= {1}
    assert ctl.on_site >= on_site and ctl.on_site == len(_inside(ctl))


def test_restore_snapshot_with_people_builds_full_schedule(registry, world, people):
    import json

    from iot_sim.core.world import World

    world.people = people
    world.clock.set(datetime(2026, 10, 12, 12, 0))
    world.advance(10)
    a = world.devices["ACCESS"].model.ctl
    assert a.events and a.on_site > 0
    data = json.loads(json.dumps(world.snapshot()))
    b_world = World(registry, seed=world.seed, clock=type(world.clock)("2026-10-12T05:00:00"))
    assert b_world.people == []  # на сервері люди з'являються пізніше за пристрої
    b_world.restore(data)
    b = b_world.devices["ACCESS"].model.ctl
    assert len(b.schedule) == len(a.schedule) > 0 and b.ptr == a.ptr and len(b.events) == len(a.events)
    assert b.on_site == a.on_site
    b_world.advance(10)
    assert len(b.events) == len(a.events)  # знімок не дублює видані події
    _set_time(b_world, 15, 40)
    assert len(_per_user(b, "1")) == 35 and set(_per_user(b, "1").values()) == {1}
