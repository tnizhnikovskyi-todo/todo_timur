"""R-29, R-30 (двір: фури, шлагбауми, LPR, ваги); SPEC §13.1, AC-17, AC-18, AC-53, AC-54."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from iot_sim.models.yard import (
    DEMO_BOOKINGS,
    cargo_kg,
    gen_plate,
    to_cyr,
    to_lat,
    unit_mass,
)

pytestmark = pytest.mark.unit

KYIV = ZoneInfo("Europe/Kyiv")
IN = {"batch": "BATCH/IN/00001", "truck": "TRUCK-IN-1", "dock": "DOCK-W1", "plate": None, "type": "incoming",
      "picking": "WH/IN/00128", "partner": "Постачальник плит (демо)",
      "lines": [{"product": "DSP16-SON", "qty": 120}, {"product": "DSP16-WHT", "qty": 80}]}
OUT = {"batch": "BATCH/OUT/00004", "truck": "TRUCK-OUT-1", "dock": "DOCK-E2", "plate": "АА4512КТ",
       "type": "outgoing", "picking": "WH/OUT/00413", "partner": "Меблі Дім (демо)",
       "lines": [{"product": "PAL-FG", "qty": 12}]}


def v(world, code):
    return world.signals[code].value


def gate(world, g, leaf):
    return v(world, f"yard/gates/{g}/{leaf}")


def ctl_of(world):
    return world.devices["TRUCK-SCALE"].model.ctl


@pytest.fixture
def yard(world):
    world.trucks.extend([dict(IN), dict(OUT)])
    world.step(1)
    return ctl_of(world)


def arrive(world, booking, **kw):
    world.post("yard", {"kind": "truck_arrival", "booking": booking, "plate": None, "at": None,
                        "unload_min": kw.pop("unload_min", 1), "run_id": kw.pop("run_id", "r-1")})
    world.step(0)
    return ctl_of(world).trucks[-1]


def test_truck_state_machine(world, yard):
    t0 = world.clock.epoch()
    tr = arrive(world, "BATCH/IN/00001")
    assert tr["state"] == "at_gate" and tr["dock"] == "DOCK-W1" and tr["gross_kg"] == 25200
    assert gate(world, "GATE-W", "loop") == 1 and gate(world, "GATE-W", "state") == 0
    world.step(1)
    assert gate(world, "GATE-W", "state") == 0 and gate(world, "GATE-W", "loop") == 1  # стріла відкривається
    world.advance(5)  # t0 + 6
    assert tr["state"] == "weigh_in" and gate(world, "GATE-W", "state") == 1
    assert gate(world, "GATE-W", "loop") == 0 and gate(world, "GATE-W", "passes_today") == 1
    world.advance(30)  # 15 с після звільнення петлі шлагбаум закривається
    assert gate(world, "GATE-W", "state") == 0
    assert ctl_of(world).gates["GATE-W"]["state"] == "closed"
    world.advance(30)
    world.advance(30)  # t0 + 96
    assert tr["state"] == "to_dock"
    world.advance(150)
    assert tr["state"] == "at_dock"
    world.advance(30)
    assert 40 < tr["unloaded_pct"] < 60  # unload_min = 1
    world.advance(100)
    assert tr["state"] in ("to_exit", "weigh_out")
    world.advance(150)
    assert tr["state"] == "at_gate_out" or tr["state"] == "left"
    world.advance(30)
    assert tr["state"] == "left" and gate(world, "GATE-E", "passes_today") == 1
    states = [s for s, _ in tr["history"]]
    assert states == ["expected", "at_gate", "weigh_in", "to_dock", "at_dock", "to_exit", "weigh_out",
                      "at_gate_out", "left"]
    times = dict(tr["history"])
    assert times["at_gate"] - t0 == 0 and times["weigh_in"] - t0 == 5 and times["to_dock"] - t0 == 65
    assert times["at_dock"] - t0 == 245 and times["to_exit"] - times["at_dock"] == 60
    assert times["weigh_out"] - times["to_exit"] == 120 and times["left"] - times["at_gate_out"] == 5
    assert world.run_results["r-1"] == {"gross_kg": 25200, "tare_kg": 14000, "dock": "DOCK-W1",
                                        "unloaded_pct": 100}
    cams = [p["carState"] for p in world.devices["CAM-05"].model.outbox]
    assert cams == ["new"]
    out = list(world.devices["CAM-06"].model.outbox)
    assert [p["carState"] for p in out] == ["new", "lost"] and out[0]["carMoveDirection"] == "out"
    assert out[0]["GEOtarget"] == "GATE-E" and out[0]["sensorProviderID"] == "CAM-06"
    assert any(e.kind == "yard" for e in world.events.ring)


def test_no_booking_rejected(world):
    world.post("yard", {"kind": "truck_no_booking", "plate": "AA1234KT", "gate": "GATE-W", "wait_min": 10,
                        "run_id": "r-2"})
    world.step(0)
    tr = ctl_of(world).trucks[-1]
    assert tr["state"] == "rejected" and not tr["booked"] and tr["plate"] == "АА1234КТ"
    p = next(iter(world.devices["CAM-05"].model.outbox))
    assert p["plateList"] == "" and p["plateListMode"] == "none" and p["plateListDescription"] == ""
    assert p["plateText"] == "AA1234KT" and p["carState"] == "new"
    assert v(world, "yard/lpr/CAM-05/plate") == "AA1234KT"
    ev = [e for e in world.events.ring if e.kind == "yard" and e.payload.get("level") == "warn"]
    assert ev and ev[0].message == "Фура АА1234КТ без бронювання біля воріт в'їзду"
    world.advance(540)  # 9 хв — стоїть на петлі, стріла закрита (DI0 = 0)
    assert tr["state"] == "rejected" and gate(world, "GATE-W", "state") == 0 and gate(world, "GATE-W", "loop") == 1
    world.advance(70)
    assert tr["state"] == "left" and gate(world, "GATE-W", "loop") == 0
    assert [x["carState"] for x in world.devices["CAM-05"].model.outbox][-1] == "lost"
    assert gate(world, "GATE-W", "passes_today") == 0  # не в'їхала


def test_no_booking_admitted_and_gate_e(world):
    world.post("yard", {"kind": "truck_no_booking", "plate": "KA7777AA", "gate": "GATE-E", "wait_min": 10})
    world.step(0)
    tr = ctl_of(world).trucks[-1]
    assert tr["state"] == "rejected" and gate(world, "GATE-E", "loop") == 1
    assert next(iter(world.devices["CAM-06"].model.outbox))["plateListMode"] == "none"
    world.post("yard", {"kind": "truck_arrival", "booking": True, "plate": "KA7777AA"})
    world.advance(10)
    assert tr["state"] in ("at_gate", "weigh_in") and tr["booked"] is True


def test_scale_weights(world, yard):
    world.step(10)
    w, stable, over = ctl_of(world).scale()
    assert w in (-20.0, 0.0, 20.0) and stable and not over  # без машини 0 ± 20
    arrive(world, "BATCH/IN/00001")
    world.advance(5)  # weigh_in: динамічна фаза 3 с
    world.advance(1)
    assert v(world, "yard/scale/TRUCK-SCALE/stable") == 0
    assert 0 < v(world, "yard/scale/TRUCK-SCALE/weight_kg") < 25200
    world.advance(3)
    assert v(world, "yard/scale/TRUCK-SCALE/stable") == 1
    assert abs(v(world, "yard/scale/TRUCK-SCALE/weight_kg") - 25200) <= 20  # брутто
    assert v(world, "yard/scale/TRUCK-SCALE/weight_kg") % 20 == 0
    world.advance(60 + 180 + 60 + 120 + 10)  # до weigh_out (тара)
    for _ in range(40):
        world.step(5)
        if ctl_of(world).trucks[-1]["state"] == "weigh_out":
            break
    world.advance(5)
    assert abs(v(world, "yard/scale/TRUCK-SCALE/weight_kg") - 14000) <= 20


def test_scale_overload_and_outgoing(world):
    big = dict(OUT, truck="TRUCK-OUT-9", cargo_kg=50000, batch="BATCH/OUT/00009", plate="АА0001КТ")
    world.trucks.append(big)
    arrive(world, "BATCH/OUT/00009")
    tr = ctl_of(world).trucks[-1]
    world.advance(10)  # outgoing: у weigh_in — тара
    assert abs(v(world, "yard/scale/TRUCK-SCALE/weight_kg") - 14000) <= 20
    tr["state"], tr["t"] = "weigh_out", world.clock.epoch() - 10  # outgoing: у weigh_out — брутто 64 000
    world.step(1)
    assert v(world, "yard/scale/TRUCK-SCALE/weight_kg") > 60000
    assert world.devices["TRUCK-SCALE"].model.overload is True


def test_lpr_payload(world, yard):
    world.clock.set(datetime(2026, 10, 14, 8, 15, 5, 507000))
    arrive(world, "BATCH/OUT/00004")
    p = list(world.devices["CAM-05"].model.outbox)[-1]
    assert p["plateUnicode"] == "АА4512КТ" and p["plateText"] == "AA4512KT" and p["plateASCII"] == "AA4512KT"
    assert p["capture_timestamp"] == "1791954905507" == p["frame_timestamp"]
    assert p["capture_ts"] == "1791954905507000000" and p["datetime"] == "20261014 081505507"
    assert p["plateList"] == "f3d_bookings" and p["plateListMode"] == "allow"
    assert p["plateListDescription"].startswith("BATCH/OUT/00004 DOCK-E2")
    assert p["GEOtarget"] == "GATE-W" and p["sensorProviderID"] == "CAM-05" and p["carMoveDirection"] == "in"
    assert p["plateCountry"] == "UKR" and p["carState"] == "new"
    assert v(world, "yard/lpr/CAM-05/plate") == "AA4512KT"


def test_plate_from_bookings(world, yard):
    out = arrive(world, "BATCH/OUT/00004")
    assert out["id"] == "TRUCK-OUT-1" and out["plate"] == "АА4512КТ"
    tin = arrive(world, "BATCH/IN/00001", run_id="r-3")
    assert tin["id"] == "TRUCK-IN-1" and tin["plate"] != "АА4512КТ"
    assert tin["plate"] == gen_plate("TRUCK-IN-1")  # детермінований
    assert re.fullmatch(r"AA\d{4}[ABEIKMHOPCTX]{2}", to_lat(tin["plate"]))
    assert to_cyr(to_lat(tin["plate"])) == tin["plate"]
    assert tin["plate"] != gen_plate("TRUCK-IN-2")
    adhoc = arrive(world, "WH/IN/00999", run_id="r-4")  # невідоме бронювання -> фура без номера в API
    assert adhoc["id"].startswith("TRUCK-IN-") and adhoc["gross_kg"] == 14000 + 11200


def test_hold_channels(world):
    ctl = ctl_of(world)
    world.force("yard/gates/GATE-W/cmd_hold", 1)  # DO4
    world.advance(1)
    world.advance(6)
    assert gate(world, "GATE-W", "state") == 1 and gate(world, "GATE-E", "state") == 0
    world.advance(120)
    assert gate(world, "GATE-W", "state") == 1  # тримається, поки DO4 = 1
    world.force("yard/gates/GATE-W/cmd_hold", 0)
    world.force("yard/gates/GATE-E/cmd_hold", 1)  # DO5 — лише GATE-E
    world.advance(1)
    world.advance(6)
    assert gate(world, "GATE-E", "state") == 1
    world.advance(40)  # GATE-W: 15 с після звільнення + закриття
    assert gate(world, "GATE-W", "state") == 0 and gate(world, "GATE-E", "state") == 1
    world.force("yard/gates/GATE-E/cmd_hold", 0)
    world.advance(40)
    assert gate(world, "GATE-E", "state") == 0 and ctl.gates["GATE-E"]["state"] == "closed"


def test_drill_holds_both_gates(world):
    world.set_flag("fire_drill", {"zone": "FA-CNC", "detector": "", "real": False,
                                  "t0": world.now().isoformat(), "phase": "active"})
    for _ in range(11):
        world.step(1)
    assert gate(world, "GATE-W", "cmd_hold") == 0 and gate(world, "GATE-E", "cmd_hold") == 0
    world.step(1)  # +12 с: DO4 = DO5 = 1 (X-47)
    assert gate(world, "GATE-W", "cmd_hold") == 1 and gate(world, "GATE-E", "cmd_hold") == 1
    for _ in range(8):
        world.step(1)
    assert gate(world, "GATE-W", "state") == 1 and gate(world, "GATE-E", "state") == 1
    world.clear_flag("fire_drill")
    for _ in range(31):
        world.step(1)
    assert gate(world, "GATE-W", "cmd_hold") == 0 and gate(world, "GATE-E", "cmd_hold") == 0
    world.advance(30)
    assert gate(world, "GATE-W", "state") == 0 and gate(world, "GATE-E", "state") == 0


def test_cmd_open_close_and_manual_gate(world):
    world.settings = type("S", (), {"yard_autogate": False})()
    arrive(world, "BATCH/IN/00001")
    tr = ctl_of(world).trucks[-1]
    world.advance(30)
    assert tr["state"] == "at_gate" and gate(world, "GATE-W", "state") == 0  # чекає DO0
    world.force("yard/gates/GATE-W/cmd_open", 1)  # DO0
    world.advance(1)
    assert v(world, "yard/gates/GATE-W/cmd_open") == 0  # імпульс прийнято
    world.advance(5)
    assert tr["state"] == "weigh_in" and gate(world, "GATE-W", "state") == 1
    world.force("yard/gates/GATE-W/cmd_close", 1)  # DO2: закрити примусово
    world.advance(10)
    assert gate(world, "GATE-W", "state") == 0 and ctl_of(world).gates["GATE-W"]["state"] in ("closing", "closed")
    world.force("yard/gates/GATE-E/cmd_open", 1)  # відкриття без фури закривається само
    world.advance(1)
    world.advance(8)
    assert gate(world, "GATE-E", "state") == 1
    world.advance(30)
    assert gate(world, "GATE-E", "state") == 0


def test_bookings_schedule_and_follow_odoo(world):
    world.set_mode("follow_odoo")
    sched = world.now() + __import__("datetime").timedelta(minutes=20)
    world.trucks.append(dict(IN, scheduled=sched.isoformat(), progress=0.6))
    world.trucks.append({"batch": "BATCH/IN/00002", "truck": "TRUCK-IN-2", "type": "incoming"})  # без часу
    world.step(1)
    tr = ctl_of(world).trucks[0]
    assert tr["state"] == "at_gate" and len(ctl_of(world).trucks) == 1  # прибуття = scheduled − 20 хв
    world.advance(300)
    assert tr["state"] == "at_dock" and tr["unloaded_pct"] == 60.0  # прогрес stock.picking з Odoo
    world.trucks[0]["progress"] = 1.0
    world.advance(10)
    assert tr["state"] in ("to_exit", "weigh_out") and tr["unloaded_pct"] == 100.0


def test_demo_bookings_with_shift_flag(world):
    world.step(1)
    assert ctl_of(world).trucks == []
    world.set_flag("shift", {"trucks": True})
    world.advance(10)
    ids = {t["id"] for t in ctl_of(world).trucks}
    assert ids == {"TRUCK-IN-1", "TRUCK-OUT-1"} and len(world.trucks) == len(DEMO_BOOKINGS)
    tin = next(t for t in ctl_of(world).trucks if t["id"] == "TRUCK-IN-1")
    assert tin["state"] in ("weigh_in", "to_dock", "at_dock", "to_exit", "weigh_out", "at_gate_out", "left")


def test_cargo_and_masses():
    assert unit_mass("DSP16-SON") == 56 and unit_mass("MDF18-X") == 70 and unit_mass("HDF3") == 12
    assert unit_mass("ДСП 16 мм") == 56 and unit_mass("PAL-FG") == 420 and unit_mass("EB2-SON") == 0.5
    assert cargo_kg({"cargo_kg": 100}) == 100 and cargo_kg({}) == 11200
    assert cargo_kg({"lines": [{"product": "X", "qty": 10, "kg": 1.2}]}) == 12.0
    assert cargo_kg(IN) == 11200


def test_daily_reset_prune_and_snapshot(world, yard):
    arrive(world, "BATCH/IN/00001")
    world.advance(20)
    assert gate(world, "GATE-W", "passes_today") == 1
    scale = world.devices["TRUCK-SCALE"].model
    state = scale.get_state()
    assert state["passes"]["GATE-W"] == 1 and world.devices["GATE-W"].model.get_state() == {}
    ctl_of(world).gates["GATE-W"]["passes"] = 0
    scale.set_state(state)
    assert ctl_of(world).gates["GATE-W"]["passes"] == 1
    scale.set_state({})
    world.clock.set(datetime(2026, 10, 13, 9, 0, tzinfo=KYIV))
    world.advance(10)
    assert gate(world, "GATE-W", "passes_today") == 0
    c = ctl_of(world)
    c.trucks.extend([dict(c.trucks[0], state="left") for _ in range(250)])
    world.advance(10)
    assert len(c.trucks) <= 101
