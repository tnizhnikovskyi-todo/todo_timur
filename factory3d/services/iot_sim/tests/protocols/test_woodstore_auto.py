"""Авто-завдання порталу (вау №19, R-18) і фази руху в ``GET /status`` — ``protocols/woodstore_auto.py``."""

import pytest
from iot_sim.models.machine import WORKING
from iot_sim.protocols.woodstore_api import WoodStore
from iot_sim.protocols.woodstore_auto import MAX_PER_REF, MAX_SHEETS, MIN_SHEETS, phase_state

pytestmark = pytest.mark.unit

TARGETS = ("SAW-1", "SAW-2", "SAW-3", "NEST-1")


@pytest.fixture
def store(world, monkeypatch):
    monkeypatch.delenv("SIM_WOODSTORE_AUTOFEED", raising=False)
    return WoodStore(world, sheet_period_s=60)


def _work(world, code="SAW-1", order="WH/MO/00231"):
    """РЦ у WORKING з активним завданням (``order`` — назва МО, як у ``follow_odoo``)."""
    model = world.devices[code].model
    model.current_state = WORKING
    model.world.jobs[:] = [j for j in world.jobs if j.get("workcenter") != code]
    world.jobs.append({"id": 1, "workcenter": code, "state": "progress", "order": order, "qty": 14})
    return model


def test_phase_state_cycle_order():
    # період 60 с: до 33 с портал чекає, далі 10+4+10+3 с руху
    assert phase_state(0, 60) == "idle" and phase_state(32.9, 60) == "idle"
    assert phase_state(33.5, 60) == "moving"
    assert phase_state(44.0, 60) == "picking"
    assert phase_state(48.0, 60) == "moving"
    assert phase_state(58.0, 60) == "placing"
    # короткий період стискає цикл, не втрачаючи фаз
    assert [phase_state(x, 10) for x in (0.1, 4.0, 6.0, 9.5)] == ["moving", "picking", "moving", "placing"]
    assert phase_state(1, 0) == "placing"


def test_working_machine_gets_feed_with_mo_ref(world, store):
    """РЦ у WORKING без завдання порталу → feed на 2…5 листів із `external_ref` = МО РЦ."""
    for code in TARGETS:
        world.devices[code].model.current_state = 0
    _work(world, "SAW-1", "WH/MO/00231")
    store.auto.on_tick(world)
    jobs = list(store.jobs.values())
    assert len(jobs) == 1
    job = jobs[0]
    assert job["type"] == "feed" and job["target"] == "SAW-1" and job["external_ref"] == "WH/MO/00231"
    assert MIN_SHEETS <= job["sheets"] <= MAX_SHEETS and job["source"] and job["product"]
    assert job["priority"] == 3
    # завдання в черзі вже є — нового не додає
    store.auto.on_tick(world)
    assert len(store.jobs) == 1
    # вибір плити детермінований за назвою МО
    store2 = WoodStore(world, sheet_period_s=60, auto_feed=True)
    store2.auto.on_tick(world)
    assert next(iter(store2.jobs.values()))["product"] == job["product"]


def test_idle_machines_get_nothing(world, store):
    for code in TARGETS:
        world.devices[code].model.current_state = 0
    store.auto.on_tick(world)
    assert not store.jobs


def test_auto_feed_runs_through_stacks_and_events(world, store):
    """Завдання виконується як звичайне: листи, події, `qty` стосу зменшується, status показує фази."""
    for code in TARGETS:
        world.devices[code].model.current_state = 0
    _work(world, "SAW-2", "WH/MO/00240")
    store.on_tick(world)  # створює і одразу запускає (queued → active)
    job = next(iter(store.jobs.values()))
    assert job["state"] == "active" and job["target"] == "SAW-2"
    stack = store.stacks[job["source"]]
    before = stack["qty"]
    seen = set()
    for _ in range(job["sheets"] * 60 + 2):
        world.clock.advance(1)
        store.on_tick(world)
        seen.add(store.portal_state())
        if job["state"] == "done":
            break
    assert job["state"] == "done" and job["done"] == job["sheets"]
    assert stack["qty"] == before - job["sheets"]
    assert {"idle", "moving", "picking", "placing"} <= seen
    types = [e["type"] for e in store.events]
    assert types.count("sheet_placed") == job["sheets"] and "job_finished" in types
    assert all(e["job"] == job["id"] for e in store.events if e["type"] == "sheet_placed")


def test_cap_per_mo_and_switch(world, store):
    """Під одну МО авто-режим подає не більше MAX_PER_REF листів; інша МО знову отримує завдання."""
    for code in TARGETS:
        world.devices[code].model.current_state = 0
    _work(world, "SAW-1", "WH/MO/00250")
    store.auto.fed["WH/MO/00250"] = MAX_PER_REF
    store.auto.on_tick(world)
    assert not store.jobs
    _work(world, "SAW-1", "WH/MO/00251")
    store.auto.on_tick(world)
    assert len(store.jobs) == 1


def test_disabled_by_env(world, store, monkeypatch):
    monkeypatch.setenv("SIM_WOODSTORE_AUTOFEED", "0")
    for code in TARGETS:
        world.devices[code].model.current_state = 0
    _work(world, "SAW-1", "WH/MO/00231")
    store.auto.on_tick(world)
    assert not store.jobs


def test_status_idle_without_job(world, store):
    assert store.portal_state() == "idle"


def test_default_stacks_match_odoo_layout(world, monkeypatch):
    """Стенд: 27 стосів PLT-01A…PLT-09C (9 × 3), 23 з листами — як стоси td_machine_connect; товари з демо Odoo."""
    store = WoodStore(world, auto_feed=False)
    assert len(store.stacks) == 27 and sum(1 for s in store.stacks.values() if s["qty"] > 0) == 23
    assert set(store.stacks) == {f"PLT-{r:02d}{c}" for r in range(1, 10) for c in "ABC"}
    b = store.stacks["PLT-01B"]
    assert (b["product"], b["lot"], b["qty"], b["row"], b["col"]) == ("DSP16-WNG", "DSP16-WNG-2610-114", 45, 1, 2)
    assert store.stacks["PLT-01A"]["product"] is None and store.stacks["PLT-01A"]["qty"] == 0
    monkeypatch.setenv("SIM_WOODSTORE_STACKS", "/nonexistent.json")
    assert len(WoodStore(world, auto_feed=False).stacks) == 36  # немає каталогу — синтетичні стоси, як раніше
