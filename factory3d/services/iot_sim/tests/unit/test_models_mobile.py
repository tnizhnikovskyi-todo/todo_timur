"""R-05, R-06, R-19 (mobile); SPEC §13.1, AC-08."""
import math
from datetime import datetime

import pytest
from iot_sim.models import mobile
from iot_sim.models.mobile import point_in_polygon, set_zones, zone_at, zones

pytestmark = pytest.mark.unit


def val(world, code, leaf):
    return world.signals[f"equipment/{code}/{leaf}"].value


def zero_noise(world):
    world.r = lambda code: 0.0


def run_until(world, pred, max_s=36000, step=10.0):
    t = 0.0
    while not pred() and t < max_s:
        world.step(step)
        t += step
    return t


def test_drain_cycle(world):
    zero_noise(world)
    m = world.devices["FL-2"].model
    world.advance(10)
    assert m.mstate == "busy"
    world.advance(3590)  # 60 хв: 33,9 − 0,15·60 = 24,9
    assert val(world, "FL-2", "battery") == pytest.approx(24.9, abs=0.05)
    run_until(world, lambda: m.mstate == "to_charge")
    assert m.mstate == "to_charge" and val(world, "FL-2", "battery") <= 20 and val(world, "FL-2", "state") == "busy"
    run_until(world, lambda: m.mstate == "charging")
    assert m.mstate == "charging" and val(world, "FL-2", "state") == "charging"
    b0 = val(world, "FL-2", "battery")
    world.advance(600)  # 10 хв · 0,6 %/хв
    assert val(world, "FL-2", "battery") - b0 == pytest.approx(6.0, abs=0.05)
    run_until(world, lambda: m.mstate != "charging")
    assert val(world, "FL-2", "battery") == pytest.approx(95.0, abs=0.01)
    assert m.mstate == "busy"  # idle (95 %) -> повертається до завдання в тому ж тіку
    kinds = [e["type"] for e in m.outbox]
    assert kinds[:4] == ["task_start", "low_battery", "charge_start", "charge_end"]


def test_charge_time(world):
    zero_noise(world)
    world.force("equipment/FL-2/battery", 0.0, 0)
    m = world.devices["FL-2"].model
    m.battery = 0.0
    m._set_state("charging")
    t = run_until(world, lambda: m.mstate != "charging", max_s=3 * 3600)
    assert t / 60 == pytest.approx(95 / (4 * 0.15), abs=0.3)  # ≈ 158 хв


def test_route_to_charge(world):
    zero_noise(world)
    m = world.devices["FL-2"].model
    world.advance(10)
    world.force("equipment/FL-2/battery", 18.0, 0)  # S-10: battery_low
    m.battery = 18.0
    world.advance(10)
    assert m.mstate == "to_charge"
    d0 = math.dist(m.pos, zones()["Z-CHG"]["centroid"])
    run_until(world, lambda: m.mstate == "charging")
    chg = zones()["Z-CHG"]
    x, y = val(world, "FL-2", "x"), val(world, "FL-2", "y")
    assert point_in_polygon(x, y, chg["polygon"]) and zone_at(x, y) == "Z-CHG" and m.zone == "Z-CHG"
    assert d0 > 5
    t = m.telemetry()
    assert t["state"] == "charging" and t["charging"] and t["zone"] == "Z-CHG" and t["task"] is None


def test_hours_only_when_busy(world):
    zero_noise(world)
    m = world.devices["FL-2"].model
    world.advance(10)
    h0 = val(world, "FL-2", "hours")
    world.advance(600)
    assert val(world, "FL-2", "hours") - h0 == pytest.approx(600 / 3600, abs=0.01)  # busy
    m.mstate, h1 = "charging", m.hours
    world.advance(300)
    assert m.hours == h1  # charging — не росте
    m.mstate = "idle"
    world.clock.set(datetime(2026, 10, 12, 18, 0))
    world.advance(300)
    assert m.hours == h1 and m.mstate == "idle"  # поза зміною idle


def test_route_motion_and_zones(world):
    zero_noise(world)
    m = world.devices["FL-1"].model  # Z-POST <-> Z-FG
    a, b = zones()["Z-POST"]["centroid"], zones()["Z-FG"]["centroid"]
    assert m.pos == a
    world.advance(10)
    speeds = set()
    seen_dwell = False
    for _ in range(400):
        world.step(5)
        speeds.add(round(m.speed_ms, 2))
        seen_dwell |= m.dwell > 0
    assert 1.67 in speeds and 0.0 in speeds and seen_dwell
    assert math.dist(a, b) / 1.6667 > 10  # маршрут довший за крок
    assert 0 <= m.heading < 360
    # без зон у ``Z-FG`` — точка має бути в одному з полігонів маршруту
    assert m.zone in {None, "Z-POST", "Z-FG"} or m.zone.startswith("Z-")


def test_tugger_pingpong(world):
    zero_noise(world)
    m = world.devices["TUGGER-1"].model
    legs = []
    for _ in range(1500):
        world.step(10)
        if not legs or legs[-1] != m.leg:
            legs.append(m.leg)
    assert {0, 1, 2} <= set(legs)  # HW -> PRE -> ASM і назад


def test_charger_trucks_stay(world):
    m = world.devices["FL-C1"].model
    world.advance(300)
    assert m.mstate == "busy" and m.speed_ms == 0.0 and m.zone == "Z-CHG"


def test_faults(world):
    m = world.devices["FL-3"].model
    world.advance(10)
    world.fault("FL-3", "comm")
    b = val(world, "FL-3", "battery")
    world.advance(60)
    assert m.mstate == "offline" and val(world, "FL-3", "state") == "offline"
    assert val(world, "FL-3", "battery") == b
    world.clear("FL-3")
    world.advance(10)
    assert m.mstate == "busy"
    world.fault("FL-3", "generic")
    world.advance(10)
    assert m.mstate == "fault" and m.telemetry()["faults"] == ["generic"]
    world.clear("FL-3")
    world.advance(10)
    assert m.mstate == "busy"


def test_state_roundtrip_and_zones_override(world):
    m = world.devices["FL-1"].model
    world.advance(100)
    d = m.get_state()
    pos = m.pos
    m.pos = (0.0, 0.0)
    m.set_state(d)
    assert tuple(m.pos) == tuple(pos)
    set_zones([{"code": "Z-TEST", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]]}])
    try:
        assert zone_at(5, 5) == "Z-TEST" and zone_at(50, 50) is None
    finally:
        set_zones(None)
    assert mobile.zones()["Z-CHG"]["polygon"]


def test_battery_low_scenario_flag_drives_model(world):
    """ТК-04/AC-08: прапор сценарію battery_low (без ручного m.battery) переводить FL-2 у to_charge."""
    zero_noise(world)
    m = world.devices["FL-2"].model
    world.advance(10)
    world.flags.setdefault("battery_low", {})["FL-2"] = 18.0
    world.advance(10)
    assert m.mstate == "to_charge" and m.battery < 20
    assert "FL-2" not in world.flags.get("battery_low", {})
