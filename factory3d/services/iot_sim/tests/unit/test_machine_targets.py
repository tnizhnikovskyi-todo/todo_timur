"""Цілі станів верстатів від Odoo (C-LP-01; SPEC API-26, R-LP-01…R-LP-05, AC-69…AC-73)."""

import csv
import json
from datetime import timedelta
from pathlib import Path

import pytest
from iot_sim.core.machine_targets import apply_targets, iso_utc, list_targets, machine_codes, real_epoch
from iot_sim.models.machine import ERROR, READY, WORKING, Machine
from iot_sim.models.meter import LINE_CONSUMERS

pytestmark = pytest.mark.unit

MC_MACHINES = Path(__file__).resolve().parents[4] / "odoo_addons/td_machine_connect/data/mc_machines.csv"


def st(world, code):
    return world.signals[f"workcenters/{code}/state"].value


def pw(world, code):
    return world.signals[f"energy/consumers/{code}/p_now"].value


def zero_noise(world):
    world.r = lambda code: 0.0


def put(world, code, state, reason=None, ttl=7200.0):
    return apply_targets(world, [(code, state, reason, real_epoch(world) + ttl)])


def events(world, device):
    return [e for e in world.events.ring if e.device == device]


def test_no_target_keeps_autonomous_behaviour(world):
    """Без цілі — як раніше: SAW-1 WORKING, SAW-3 READY (простій демо 10:30), енергія за R-02."""
    zero_noise(world)
    world.step(10)
    assert st(world, "SAW-1") == WORKING and st(world, "SAW-3") == READY
    assert pw(world, "SAW-1") == pytest.approx(12.18)
    assert list_targets(world) == []


def test_working_idle_down_follow_target(world):
    zero_noise(world)
    world.step(10)
    assert put(world, "SAW-3", "working") == {"ok": 1, "unknown": [], "expired": []}  # демо: був READY
    put(world, "SAW-1", "idle", "очікує матеріал")  # демо: був WORKING
    put(world, "SAW-2", "down", "spindle")
    world.step(1)  # один тік — стан і сигнали вже за ціллю
    nominal3 = world.signals["energy/consumers/SAW-3/p_now"].params["nominal"]
    assert st(world, "SAW-3") == WORKING and pw(world, "SAW-3") == pytest.approx(nominal3)
    rate1 = world.signals["energy/consumers/SAW-1/p_now"].params["rate"]
    assert st(world, "SAW-1") == READY and pw(world, "SAW-1") == pytest.approx(rate1)
    assert st(world, "SAW-2") == ERROR and pw(world, "SAW-2") == 0
    assert world.signals["workcenters/SAW-2/alarm"].value is True
    assert world.signals["workcenters/SAW-1/alarm"].value is False


def test_working_has_noise_idle_has_small_noise(world):
    world.step(10)
    put(world, "SAW-1", "working")
    world.step(1)
    r = world.r("energy/consumers/SAW-1/p_now")
    assert pw(world, "SAW-1") == pytest.approx(12.18 * (1 + 0.08 * r))


def test_down_reason_gives_message_and_event(world):
    world.step(10)
    put(world, "CNC-2", "down", "spindle")
    put(world, "SAW-2", "down", "Немає матеріалу")  # вільна причина Odoo → загальна помилка
    world.step(1)
    assert world.signals["workcenters/CNC-2/event"].value == "E0421"
    assert world.signals["workcenters/SAW-2/event"].value == "E0400"
    ev = [e for e in events(world, "CNC-2") if e.payload.get("target")]
    assert len(ev) == 1 and ev[0].kind == "fault" and ev[0].payload["message_id"] == "E0421"
    free = next(e for e in events(world, "SAW-2") if e.payload.get("target"))
    assert "Немає матеріалу" in free.message and free.payload["reason"] == "Немає матеріалу"
    world.step(5)  # без зміни цілі повторних подій немає
    assert len([e for e in events(world, "CNC-2") if e.payload.get("target")]) == 1
    put(world, "CNC-2", "working")  # відновлення
    world.step(1)
    assert st(world, "CNC-2") == WORKING and world.signals["workcenters/CNC-2/event"].value == ""
    assert events(world, "CNC-2")[-1].kind == "info"


def test_target_replaces_target_and_changes_event_on_reason(world):
    world.step(10)
    put(world, "SAW-2", "idle")
    world.step(1)
    assert st(world, "SAW-2") == READY
    put(world, "SAW-2", "working")
    world.step(1)
    assert st(world, "SAW-2") == WORKING
    assert [t["state"] for t in list_targets(world) if t["code"] == "SAW-2"] == ["working"]


def test_until_expiry_returns_to_autonomous(world):
    zero_noise(world)
    world.step(10)
    put(world, "SAW-1", "down", "generic", ttl=30)
    world.step(10)
    assert st(world, "SAW-1") == ERROR
    world.advance(10)  # 20 с < 30 с — ще діє
    assert st(world, "SAW-1") == ERROR
    world.advance(15)  # 35 с > until
    assert st(world, "SAW-1") == WORKING and pw(world, "SAW-1") == pytest.approx(12.18)
    assert world.flags["machine_targets"] == {}
    assert world.signals["workcenters/SAW-1/event"].value == ""
    assert "ціль Odoo знято" in events(world, "SAW-1")[-1].message


def test_until_in_the_past_removes_target(world):
    world.step(10)
    put(world, "SAW-1", "down")
    r = apply_targets(world, [("SAW-1", "idle", None, real_epoch(world) - 1)])
    assert r == {"ok": 0, "unknown": [], "expired": ["SAW-1"]}
    assert list_targets(world) == []
    world.step(1)
    assert st(world, "SAW-1") == WORKING


def test_until_uses_real_time_not_sim_time(world):
    """``until`` — настінний час Odoo: зсув sim-годинника його не зсуває (R-LP-04)."""
    world.step(10)
    put(world, "SAW-1", "idle", ttl=600)
    world.clock.set(world.now() + timedelta(days=3))  # sim-час стрибнув, реальний — майже ні
    world.step(1)
    assert st(world, "SAW-1") == READY
    assert 590 < list_targets(world)[0]["remaining_s"] <= 600


def test_unknown_and_non_machine_codes(world):
    """GANTRY-1 має іншу модель, ``NOPE`` не існує — потрапляють у ``unknown``, решта діє."""
    until = real_epoch(world) + 60
    r = apply_targets(
        world,
        [("SAW-1", "idle", None, until), ("NOPE", "idle", None, until), ("GANTRY-1", "down", None, until)]
        + [("NOPE", "idle", None, until)],
    )
    assert r == {"ok": 1, "unknown": ["NOPE", "GANTRY-1"], "expired": []}


def test_physical_fault_beats_working_target(world):
    world.step(10)
    put(world, "SAW-1", "working")
    world.fault("SAW-1", "spindle")
    world.step(1)
    assert st(world, "SAW-1") == ERROR and pw(world, "SAW-1") == 0
    assert world.signals["workcenters/SAW-1/event"].value == "E0421"
    world.clear("SAW-1")
    world.step(1)
    assert st(world, "SAW-1") == WORKING


def test_blocked_workcenter_ignored_when_target_present(world):
    world.workcenters["CNC-2"] = {"working_state": "blocked"}  # follow_odoo: РЦ заблоковано в Odoo
    world.step(10)
    assert st(world, "CNC-2") == ERROR
    put(world, "CNC-2", "working")
    world.step(1)
    assert st(world, "CNC-2") == WORKING


def test_idle_target_suppresses_synthetic_jobs(world):
    """Ціль не змішується із SIM-завданнями планувальника: ``job`` порожній, завдань не створюється."""
    put(world, "SAW-1", "idle")
    world.step(10)
    assert not [j for j in world.jobs if j.get("workcenter") == "SAW-1"]
    assert world.signals["workcenters/SAW-1/job"].value == ""
    put(world, "SAW-2", "working")  # SAW-2 вже мав SIM-завдання не створене: ціль з першого тіку
    world.step(10)
    assert st(world, "SAW-2") == WORKING and world.signals["workcenters/SAW-2/job"].value == ""


def test_target_after_sim_job_hides_job_but_state_is_target(world):
    world.step(10)  # планувальник створив SIM-завдання SAW-1 у progress
    assert world.signals["workcenters/SAW-1/job"].value.startswith("SIM-")
    put(world, "SAW-1", "idle")
    world.step(1)
    assert st(world, "SAW-1") == READY and world.signals["workcenters/SAW-1/job"].value == ""


def test_io_machine_bits_follow_target(world):
    world.step(10)
    assert world.devices["SLIDE-1"].model.driver == "io_machine"
    put(world, "SLIDE-1", "idle")
    world.step(1)
    assert st(world, "SLIDE-1") == 0 and world.signals["workcenters/SLIDE-1/alarm"].value == 0
    put(world, "SLIDE-1", "down")
    world.step(1)
    assert st(world, "SLIDE-1") == 0 and world.signals["workcenters/SLIDE-1/alarm"].value == 1
    put(world, "VSAW-1", "working")  # демо: простій
    world.step(1)
    assert st(world, "VSAW-1") == 1


def test_pieces_counter_runs_only_while_working_target(world):
    zero_noise(world)
    put(world, "SAW-3", "working")
    put(world, "SAW-1", "idle")
    world.advance(900)  # 15 хв; SAW: 2,2 хв/шт (SAW-3: 0,9 хв/шт)
    assert world.signals["workcenters/SAW-1/pieces_out"].value == 0
    assert world.signals["workcenters/SAW-3/pieces_out"].value == pytest.approx(16, abs=1)


def test_energy_aggregates_follow_targets(world):
    """Агрегати (лінія щита BW-1, струм) беруть p_now споживача — отже, ідуть за ціллю."""
    zero_noise(world)
    line = "energy/lines/BW-1/p_now"
    world.step(10)
    base = world.signals[line].value
    assert base == pytest.approx(sum(pw(world, c) for c in LINE_CONSUMERS["BW-1"]))
    i_base = world.signals["energy/lines/BW-1/i_now"].value
    put(world, "SAW-1", "down")
    world.step(1)
    assert world.signals[line].value == pytest.approx(base - 12.18, abs=0.01)
    assert world.signals["energy/lines/BW-1/i_now"].value < i_base
    rate = world.signals["energy/consumers/SAW-1/p_now"].params["rate"]
    put(world, "SAW-1", "idle")
    world.step(1)
    assert world.signals[line].value == pytest.approx(base - 12.18 + rate, abs=0.01)
    put(world, "SAW-1", "working")
    world.step(1)
    assert world.signals[line].value == pytest.approx(base, abs=0.01)


def test_kwh_integrates_target_power(world):
    zero_noise(world)
    kwh = "energy/consumers/SAW-1/kwh_total"
    world.advance(10)
    k0 = world.signals[kwh].value
    put(world, "SAW-1", "down")
    world.advance(1800)
    assert world.signals[kwh].value - k0 == pytest.approx(0, abs=0.01)
    put(world, "SAW-1", "working")
    world.advance(1800)  # 0,5 год · 12,18 кВт
    assert world.signals[kwh].value - k0 == pytest.approx(6.09, rel=0.02)


def test_snapshot_roundtrip_keeps_targets_and_events_not_repeated(world):
    world.step(10)
    put(world, "SAW-2", "down", "emergency")
    world.step(1)
    n = len([e for e in events(world, "SAW-2") if e.payload.get("target")])
    snap = json.loads(json.dumps(world.snapshot()))
    world.flags.clear()
    world.devices["SAW-2"].model.tgt_key = None
    world.restore(snap)
    assert [t["code"] for t in list_targets(world)] == ["SAW-2"]
    world.step(1)
    assert st(world, "SAW-2") == ERROR
    assert len([e for e in events(world, "SAW-2") if e.payload.get("target")]) == n  # без повтору після відновлення


def test_list_targets_shape(world):
    world.step(10)
    put(world, "SAW-3", "working", "demo", ttl=120)
    world.step(1)
    (item,) = list_targets(world)
    assert item["code"] == "SAW-3" and item["state"] == "working" and item["reason"] == "demo"
    assert item["machine_state"] == "WORKING" and item["p_now_kw"] > 0
    assert 110 < item["remaining_s"] <= 120 and item["until"].endswith("Z")
    assert item["until"] == iso_utc(real_epoch(world) + item["remaining_s"])


def test_codes_match_odoo_machine_catalog(world):
    """Код ``td.machine.code`` (= ``mrp.workcenter.td_code``) дорівнює коду пристрою емулятора: усі 35 демо-верстатів
    є моделями ``machine``/``io_machine`` і приймають цілі; зайвих верстатів в емуляторі немає (таблиці відповідності
    не потрібно)."""
    codes = machine_codes(world)
    assert len(codes) == 35
    assert all(isinstance(world.devices[c].model, Machine) for c in codes)
    if not MC_MACHINES.is_file():  # сервіс зібрано окремо від Odoo-модулів
        pytest.skip("mc_machines.csv недоступний")
    with MC_MACHINES.open(encoding="utf-8") as fh:
        odoo_codes = [r["code"] for r in csv.DictReader(fh)]
    assert len(odoo_codes) == 35 and set(odoo_codes) == set(codes)
    r = apply_targets(world, [(c, "idle", None, real_epoch(world) + 60) for c in odoo_codes])
    assert r["ok"] == 35 and r["unknown"] == []
    world.step(1)
    assert all(st(world, c) in (0, READY) for c in odoo_codes)  # io_machine: DI «в роботі» = 0 при READY
