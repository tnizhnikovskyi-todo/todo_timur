"""R-02, R-14…R-17 (machine, io_machine) і портал R-18 (gantry); SPEC §13.1, AC-07, AC-19, AC-63."""

import itertools
import re
from datetime import datetime

import pytest
from iot_sim.models import MODELS, load_all
from iot_sim.models.machine import (
    ERROR,
    OFFLINE,
    READY,
    STANDBY,
    WORKING,
    compute_state,
    isa95_state,
    job_order_id,
)

pytestmark = pytest.mark.unit


def sig(world, code):
    return world.signals[code].value


def wc(code, leaf):
    return f"workcenters/{code}/{leaf}"


def zero_noise(world):
    world.r = lambda code: 0.0


def expected_state(on, init, saving, error, cal, recipe):
    """Незалежний запис таблиці §7.7 (R-14)."""
    if not on:
        return OFFLINE
    if not init or saving or (not error and not cal):
        return STANDBY
    if error:
        return ERROR
    return WORKING if recipe else READY


@pytest.mark.parametrize("flags", list(itertools.product([False, True], repeat=6)))
def test_state_logic_table(flags):
    assert compute_state(*flags) == expected_state(*flags)


def test_models_registered():
    load_all()
    assert {"machine", "io_machine", "gantry"} <= set(MODELS)


def test_power_by_state(world):
    zero_noise(world)
    world.step(10)
    saw1 = world.devices["SAW-1"].model
    assert saw1.current_state == WORKING
    assert sig(world, "energy/consumers/SAW-1/p_now") == pytest.approx(12.18)  # nominal·(1 + noise·0)
    saw3 = world.devices["SAW-3"].model  # демо: READY (простій)
    assert saw3.current_state == READY
    rate = world.signals["energy/consumers/SAW-3/p_now"].params["rate"]
    assert sig(world, "energy/consumers/SAW-3/p_now") == pytest.approx(rate)
    world.workcenters["CNC-2"] = {"working_state": "blocked"}  # R-02: blocked -> 0
    world.step(10)
    assert sig(world, "energy/consumers/CNC-2/p_now") == 0
    assert sig(world, wc("CNC-2", "state")) == ERROR
    assert sig(world, wc("CNC-2", "alarm")) is True


def test_power_noise_formula(world):
    world.step(10)
    r = world.r("energy/consumers/SAW-1/p_now")
    assert sig(world, "energy/consumers/SAW-1/p_now") == pytest.approx(12.18 * (1 + 0.08 * r))


def test_io_machine_bits(world):
    world.step(10)
    assert sig(world, wc("VSAW-1", "state")) == 0  # демо: READY -> DI run = 0
    assert sig(world, wc("SLIDE-1", "state")) == 1  # WORKING -> DI run = 1
    assert sig(world, wc("SLIDE-1", "alarm")) == 0
    world.fault("SLIDE-1", "generic")
    world.step(10)
    assert sig(world, wc("SLIDE-1", "state")) == 0 and sig(world, wc("SLIDE-1", "alarm")) == 1
    assert world.devices["SLIDE-1"].model.driver == "io_machine"


def test_pieces_counter(world):
    zero_noise(world)
    world.advance(900)  # 15 хв WORKING, SAW: 2,2 хв/шт
    assert sig(world, wc("SAW-1", "pieces_out")) == 6
    assert sig(world, wc("SAW-3", "pieces_out")) == 0  # READY не рахує
    m = world.devices["SAW-1"].model
    assert m.relative["PiecesIn"] == 7  # +1 деталь на столі (WorkpiecePresent)


def test_machine_does_not_write_kwh(world):
    """kwh_total/kwh_shift потребителей ведёт meter (R-03), машина пишет только p_now."""
    zero_noise(world)
    assert world.devices["SAW-1"].model.driver == "machine"
    world.advance(3600)
    assert sig(world, "energy/consumers/SAW-1/kwh_total") == pytest.approx(12.18, rel=0.02)
    assert sig(world, "energy/consumers/SAW-1/p_now") == pytest.approx(12.18)


def test_fault_clear(world):
    world.advance(10)
    world.fault("SAW-1", "spindle")
    world.advance(10)
    m = world.devices["SAW-1"].model
    assert sig(world, wc("SAW-1", "state")) == ERROR
    assert sig(world, "energy/consumers/SAW-1/p_now") == 0
    assert m.flags["Error"] and m.flags["Alarm"]
    ev = [e for e in world.events.ring if e.payload.get("message_id") == "E0421"]
    assert ev and ev[0].device == "SAW-1" and ev[0].payload["category"] == "ERROR"
    assert sig(world, wc("SAW-1", "event")) == "E0421"
    world.clear("SAW-1")
    world.advance(10)
    assert sig(world, wc("SAW-1", "state")) == WORKING and sig(world, wc("SAW-1", "event")) == ""


@pytest.mark.parametrize(
    "reason,mid", [("emergency", "A0201"), ("power", "E0430"), ("generic", "E0400"), ("sensor", "A0202")]
)
def test_fault_messages(world, reason, mid):
    world.advance(10)
    world.fault("EDGE-1", reason)
    world.advance(10)
    assert any(e.payload.get("message_id") == mid for e in world.events.ring)
    assert world.devices["EDGE-1"].model.current_state == ERROR
    if reason == "emergency":
        assert world.devices["EDGE-1"].model.flags["Emergency"]


def test_comm_fault_offline(world):
    world.advance(10)
    world.fault("SAW-1", "comm")
    world.advance(10)
    assert sig(world, wc("SAW-1", "state")) == OFFLINE
    assert world.signals[wc("SAW-1", "state")].status == "stale"
    world.clear("SAW-1")
    world.advance(10)
    assert sig(world, wc("SAW-1", "state")) == WORKING


def test_blackout_power_absent(world):
    world.advance(10)
    world.set_flag("blackout", {"phase": "outage"})
    world.advance(10)
    m = world.devices["SAW-1"].model
    assert not m.flags["PowerPresent"] and m.current_state == ERROR
    world.flags["blackout"]["phase"] = "restoring"
    world.advance(10)
    assert m.flags["PowerPresent"] and m.current_state == WORKING


def test_external_emergency_in_drill(world):
    world.advance(10)
    t0 = world.now().isoformat()
    world.set_flag("fire_drill", {"zone": "FA-CUT", "detector": "", "real": False, "t0": t0, "phase": "active"})
    world.advance(10)
    assert world.devices["SAW-1"].model.current_state == WORKING  # < 20 с
    world.advance(12)
    assert world.devices["SAW-1"].model.flags["ExternalEmergency"]
    assert world.devices["SAW-1"].model.current_state == ERROR
    assert world.devices["CNC-1"].model.current_state == WORKING  # інша зона


def test_off_shift_states(world):
    world.clock.set(datetime(2026, 10, 12, 16, 0))  # після 15:30, без завдання
    world.advance(10)
    m = world.devices["SAW-1"].model
    assert m.current_state == OFFLINE and m.flags["EnergySaving"] and sig(world, wc("SAW-1", "mode")) == 5
    assert sig(world, "energy/consumers/SAW-1/p_now") == 0


def test_manual_mode(world):
    world.advance(10)
    assert world.devices["ASM-1"].model.mode == 3  # ASM-* — MANUAL
    assert world.devices["SAW-1"].model.mode == 1


def test_job_order_id_format(world):
    assert job_order_id({"wo_id": 13}) == "WO00013"
    assert job_order_id({"id": 94}) == "WO00094"
    assert job_order_id({"id": "cj-00077"}) == "cj-00077"
    assert job_order_id({"job_order_id": "cj-5", "wo_id": 3}) == "cj-5"
    assert job_order_id({"id": "abc"}) is None
    world.jobs.append(
        {
            "wo_id": 13,
            "workcenter": "SAW-1",
            "state": "progress",
            "name": "Розкрій",
            "qty": 20,
            "order": "WH/MO/00231",
            "origin": "odoo",
        }
    )
    world.advance(10)
    assert sig(world, wc("SAW-1", "job")) == "WO00013"
    synth = [j["id"] for j in world.jobs if j.get("origin") == "sim"]
    assert synth and all(re.fullmatch(r"SIM-\d{5}", j) for j in synth) and "SIM-00001" in synth
    assert len(set(synth)) == len(synth)
    jl = world.devices["SAW-1"].model.job_list()
    assert jl[0]["JobOrderID"] == "WO00013" and jl[0]["State"] == "Running"
    assert jl[0]["OrderNumbers"] == ["WH/MO/00231"]


def test_isa95_mapping():
    assert isa95_state({"state": "ready"}) == ("AllowedToStart", None)
    assert isa95_state({"state": "waiting"}) == ("NotAllowedToStart", None)
    assert isa95_state({"state": "progress"}) == ("Running", None)
    assert isa95_state({"state": "progress", "blocked": True}) == ("Interrupted", "Held")
    assert isa95_state({"state": "done"}) == ("Ended", "Completed")
    assert isa95_state({"state": "cancel"}) == ("Ended", "Cancelled")


def test_ready_job_started_by_planner(world):
    world.jobs.append({"wo_id": 94, "workcenter": "SAW-3", "state": "ready", "qty": 10, "origin": "odoo"})
    world.advance(10)
    assert world.devices["SAW-3"].model.current_state == WORKING
    assert sig(world, wc("SAW-3", "job")) == "WO00094"


def test_completed_job_stays_in_list(world):
    world.jobs.append(
        {
            "wo_id": 13,
            "workcenter": "SAW-1",
            "state": "progress",
            "origin": "sim",
            "qty": 4,
            "duration_expected": 1,
            "elapsed_s": 0.0,
        }
    )
    zero_noise(world)
    world.advance(90)
    m = world.devices["SAW-1"].model
    done = next(j for j in m.job_list() if j["JobOrderID"] == "WO00013")
    assert (done["State"], done["SubState"]) == ("Ended", "Completed")
    assert m.relative["RunsGood"] >= 1 and m.relative["RunsTotal"] >= 1
    assert any(e.payload.get("message_id") == "I0002" for e in world.events.ring)
    world.advance(3600)  # зміна триває — завершене лишається
    assert any(j["JobOrderID"] == "WO00013" for j in m.job_list())
    world.clock.set(datetime(2026, 10, 13, 7, 1))  # початок наступної зміни — прибирається
    world.advance(10)
    assert all(j["JobOrderID"] != "WO00013" for j in m.job_list())
    assert m.relative["PiecesOut"] <= 1  # Relative* обнулено, Absolute* ні
    assert m.values["PiecesOut"] > 0


def test_follow_odoo_qty_produced(world):
    world.set_mode("follow_odoo")
    world.jobs.append({"wo_id": 13, "workcenter": "SAW-1", "state": "progress", "qty": 80, "qty_produced": 25})
    world.advance(10)
    assert sig(world, wc("SAW-1", "pieces_out")) == 25
    assert world.devices["SAW-1"].model.relative["PiecesOut"] == 25
    assert world.devices["SAW-2"].model.active_job() is None  # follow_odoo: планувальник не створює завдань


def test_shift_speed_and_snapshot(world):
    world.set_flag("shift", {"speed": 2.0, "lines": ["A"], "trucks": False, "people": False})
    zero_noise(world)
    world.advance(450)
    assert sig(world, wc("SAW-1", "pieces_out")) == 6  # 450 с · 2 / (60·2,2)
    m = world.devices["SAW-1"].model
    dump = m.to_dict()
    other = type(m).__new__(type(m))
    other.__dict__.update(m.__dict__)
    m.pieces_acc = 0
    m.from_dict(dump)
    assert m.pieces_acc == pytest.approx(450 * 2 / (60 * 2.2))


# --- портал (R-18) ----------------------------------------------------------------------------
def test_gantry_feed_cycle(world):
    zero_noise(world)
    g = world.devices["GANTRY-1"].model
    qty0 = sum(s["qty"] for s in g.stacks.values())
    assert len(g.stacks) == 23 and g.stacks["PLT-01B"]["qty"] == 45
    seen = set()
    for _ in range(120):  # 20 хв
        world.step(10)
        seen.add(g.state)
    assert {"idle", "moving", "picking", "placing"} <= seen
    assert g.cycles_today >= 15 and sig(world, "equipment/GANTRY-1/cycles_today") == g.cycles_today
    assert sum(s["qty"] for s in g.stacks.values()) == qty0 - g.cycles_total
    kinds = {e["type"] for e in g.events}
    assert {"job_started", "sheet_placed", "job_finished"} <= kinds
    assert sig(world, "energy/consumers/GANTRY-1/p_now") > 0
    assert g.status()["cycles_total"] == g.cycles_total


def test_gantry_api_job_blocked_and_empty(world):
    g = world.devices["GANTRY-1"].model
    stack = next(s for s in g.stacks.values() if s["qty"] > 0)
    stack["qty"] = 2
    product = stack["product"]
    for s in g.stacks.values():
        if s is not stack and s["product"] == product:
            s["qty"] = 0
    job = g.add_job("SAW-1", 2, product)
    assert job["state"] == "queued" and job["id"] == "wj-00001"
    with pytest.raises(ValueError):
        g.add_job("SAW-1", 5000, product)
    g.set_aisle(g.aisle_of(stack), True)
    world.advance(30)
    assert g.state == "blocked" and sig(world, "equipment/GANTRY-1/state") == "blocked"
    g.set_aisle(g.aisle_of(stack), False)
    world.advance(120)
    assert stack["qty"] == 0
    assert any(e["type"] == "stack_empty" for e in g.events)
    j = next(x for x in g.jobs if x["id"] == job["id"])
    assert j["state"] in ("error", "done")
    assert not g.cancel_job("wj-99999")


def test_gantry_cancel_fault_and_midnight(world):
    g = world.devices["GANTRY-1"].model
    g.add_job("SAW-2", 3, g._default_product(), priority=9)
    world.advance(5)
    jid = g.jobs[-1]["id"] if g.jobs[-1]["priority"] == 9 else next(j["id"] for j in g.jobs if j["priority"] == 9)
    assert g.cancel_job(jid)
    world.advance(60)
    assert next(j for j in g.jobs if j["id"] == jid)["state"] == "cancelled"
    queued = g.add_job("SAW-2", 2, g._default_product(), priority=9)
    assert g.cancel_job(queued["id"]) and queued["state"] == "cancelled"
    world.fault("GANTRY-1", "generic")
    world.advance(10)
    assert g.state == "error" and sig(world, "energy/consumers/GANTRY-1/p_now") == 0
    world.clear("GANTRY-1")
    world.clock.set(datetime(2026, 10, 13, 10, 0))
    world.advance(10)
    assert g.cycles_today <= 3
    snap = g.get_state()
    g.set_state(snap)
    assert g.cycles_total == snap["cycles_total"]
    world.clock.set(datetime(2026, 10, 12, 18, 0))
    world.advance(10)
    assert g.state == "idle"


def test_gantry_vacuum_alarm(world):
    g = world.devices["GANTRY-1"].model
    world.force("equipment/GANTRY-1/vacuum_kpa", -55.0, hold_s=30)
    world.advance(10)
    assert g.val("vacuum_kpa") == -55.0
    assert world.signals["equipment/GANTRY-1/vacuum_kpa"].status in ("alarm", "warn")


def test_restore_keeps_relative_counters(world):
    """AC-48 (ТК-16): після відновлення знімка нова зміна не обнуляє Relative* (shift_key у знімку)."""
    world.set_flag("shift", {"speed": 2.0, "lines": ["A"], "trucks": False, "people": False})
    zero_noise(world)
    world.advance(450)
    m = world.devices["SAW-1"].model
    rel = m.relative["PiecesOut"]
    assert rel > 0 and m.shift_key is not None
    dump = m.to_dict()
    m.shift_key = None  # свіжий процес
    m.from_dict(dump)
    world.advance(2)
    assert m.relative["PiecesOut"] >= rel
