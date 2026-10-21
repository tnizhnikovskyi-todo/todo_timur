"""S-24 ``fire_evacuation``: план евакуації, проходи через двері виходів, «застряглий», відкат дверей."""

import asyncio
import itertools

import pytest
from iot_sim.core.scenarios import ScenarioParamsError, ScenarioRunner
from iot_sim.core.scenarios_evac import (
    EV_LOCKED,
    EXIT_GAP_S,
    FireEvacuationParams,
    catalog,
    fire_zone_to_td,
    people_on_site,
    plan_evacuation,
    zone_of,
)
from iot_sim.models.access import EV_UNLOCKED

pytestmark = pytest.mark.unit

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
def staffed(world, people):
    world.people = people
    world.step(1)
    return people


@pytest.fixture
def runner(world):
    return ScenarioRunner(world)


async def settle(n=6):
    for _ in range(n):
        await asyncio.sleep(0)


async def run_for(world, seconds, step=5):
    for _ in range(int(seconds / step)):
        world.advance(step)
        await settle()


def access_events(world):
    return world.devices["ACCESS"].model.ctl.events


def test_catalog_complete():
    cat = catalog()
    assert len(cat["exits"]) == 12 and len(cat["routes"]) == 32 and len(cat["operators"]) == 35
    assert cat["doors"]["EX-IN"] == "1" and sorted(cat["doors"].values(), key=int)[1] == "11"
    assert set(cat["operators"].values()) <= set(cat["routes"])


def test_fire_zone_to_td():
    assert fire_zone_to_td("FA-CNC") == "Z-CNC" and fire_zone_to_td("Z-CNC") == "Z-CNC"


def test_people_on_site_from_journal(world, staffed):
    assert len(people_on_site(world)) == 35  # 10:30 — усі вже зайшли (06:40…07:00)


def test_people_on_site_technical_zone_within_dwell(world, staffed):
    """10:30: OP-W2 у ЛФМ з 10:20 (10 хв) — у Z-FAC; OP-W1 в електрощитовій з 09:51 (39 хв) — вже в Z-HW."""
    zones = {p["code"]: zone_of(p, catalog()) for p in people_on_site(world)}
    assert zones["OP-W2"] == "Z-FAC" and zones["OP-W1"] == "Z-HW"
    assert zones["OP-CNC-1"] == "Z-CNC"
    plan = {
        r["code"]: r for r in plan_evacuation(people_on_site(world), FireEvacuationParams(stuck=0, wrong_exit_pct=0))
    }
    assert plan["OP-W2"]["assigned"] == catalog()["routes"]["Z-FAC"]["exit"]


def test_plan_stuck_wrong_and_queue(world, staffed):
    p = FireEvacuationParams(zone="FA-CNC")
    plan = plan_evacuation(staffed, p)
    assert plan == plan_evacuation(staffed, p)  # детермінований
    stuck = [r for r in plan if r["stuck"]]
    assert len(stuck) == 1 and stuck[0]["zone"] == "Z-CNC" and stuck[0]["t"] is None  # біля вогню
    wrong = [r for r in plan if r["wrong"]]
    assert wrong and all(r["exit"] != r["assigned"] and r["t"] for r in wrong)
    assert all(r["exit"] == r["assigned"] for r in plan if not r["wrong"])
    by_exit = {}
    for r in sorted((r for r in plan if r["t"] is not None), key=lambda r: r["t"]):
        by_exit.setdefault(r["exit"], []).append(r["t"])
    for times in by_exit.values():
        assert all(b - a >= EXIT_GAP_S - 0.11 for a, b in itertools.pairwise(times))  # пропускна здатність
    assert max(r["t"] for r in plan if r["t"]) < 120  # норматив 300 с значно перекрито


def test_plan_params(staffed):
    none = plan_evacuation(staffed, FireEvacuationParams(stuck=0, wrong_exit_pct=0))
    assert not any(r["stuck"] or r["wrong"] for r in none)
    assert sum(1 for r in plan_evacuation(staffed, FireEvacuationParams(stuck=3)) if r["stuck"]) == 3
    assert any(r["wrong"] for r in plan_evacuation(staffed, FireEvacuationParams(wrong_exit_pct=1)))  # хоча б одна
    assert plan_evacuation([], FireEvacuationParams()) == []


def test_params_validation(runner):
    for bad in ({"stuck": 4}, {"wrong_exit_pct": 101}, {"speed_mps": 0.1}, {"zone": "cnc"}, {"x": 1}):
        with pytest.raises(ScenarioParamsError):
            runner.validate("fire_evacuation", bad)


async def test_run_evacuates_and_restores(world, runner, staffed):
    ctl = world.devices["ACCESS"].model.ctl
    before = len(ctl.events)
    run = runner.start("fire_evacuation", {"zone": "FA-CNC", "duration_s": 150})
    await settle()
    assert world.flags["fire_drill"]["phase"] == "active" and world.flags["evacuation"]["people"] == 35
    await run_for(world, 100)
    mid = [e for e in ctl.events[before:] if e["tna_key"] == "2" and e["user_id"]]
    assert 0 < len(mid) <= 34
    await run_for(world, 120)
    assert run.state == "done" and run.error is None and world.flags == {}
    new = ctl.events[before:]
    outs = [e for e in new if e["tna_key"] == "2" and e["user_id"]]
    assert len(outs) == 34 and len({e["user_id"] for e in outs}) == 34  # усі, крім одного застряглого
    stuck = run.result["stuck"][0]
    assert stuck.replace("-", "") not in {e["user_id"] for e in outs}
    doors = {e["door_id"] for e in outs}
    assert doors <= {1, *range(11, 22)} and len(doors) > 3
    assert any(e["door_id"] == 1 for e in outs) or run.result["exits"].get("EX-IN", 0) == 0
    back = [e for e in new if e["tna_key"] == "1" and e["user_id"]]
    assert len(back) == 34 and run.result["returned"] == 34
    unlocked = {e["door_id"] for e in new if e["code"] == EV_UNLOCKED}
    locked = {e["door_id"] for e in new if e["code"] == EV_LOCKED}
    assert set(range(11, 22)) <= unlocked and set(range(1, 6)) <= locked and set(range(11, 22)) <= locked
    assert max(e["datetime"] for e in back) <= min(e["datetime"] for e in new if e["code"] == EV_LOCKED)
    assert run.result["people"] == 35 and run.result["evacuated"] == 34 and run.result["wrong_exit"]
    steps = [s["step"] for s in run.timeline]
    assert steps[:6] == ["alarm", "sounders", "vent_stop", "dampers", "doors", "machines"]
    assert "stuck" in steps and steps[-2:] == ["restoring", "doors_locked"]


async def test_stop_restores_at_once(world, runner, staffed):
    ctl = world.devices["ACCESS"].model.ctl
    before = len(ctl.events)
    run = runner.start("fire_evacuation", {"duration_s": 300})
    await settle()
    await run_for(world, 40)
    run = await runner.stop(run.id)
    await settle()
    assert run.state == "stopped" and run.error is None and world.flags == {}
    new = ctl.events[before:]
    assert {e["door_id"] for e in new if e["code"] == EV_LOCKED} >= set(range(1, 6))  # блокування знято одразу
    outs = [e["user_id"] for e in new if e["tna_key"] == "2" and e["user_id"]]
    back = [e["user_id"] for e in new if e["tna_key"] == "1" and e["user_id"]]
    assert outs and sorted(outs) == sorted(back)  # хто вийшов — повернувся


async def test_nobody_on_site(world, runner):
    world.people = []
    run = runner.start("fire_evacuation", {"duration_s": 40})
    await settle()
    await run_for(world, 80)
    assert run.state == "done" and run.result["people"] == 0 and run.result["stuck"] == []
