import asyncio

import pytest

from iot_sim.core.scenarios import (
    SCENARIOS,
    Scenario,
    ScenarioConflict,
    ScenarioParamsError,
    ScenarioRunner,
    UnknownScenario,
)

MIN_PARAMS = {
    "shift": {}, "machine_fault": {"device": "CNC-2", "reason": "spindle"}, "blackout": {},
    "filter_clogged": {"device": "RV-05"}, "truck_no_booking": {},
    "truck_arrival": {"booking": "BATCH/IN/00001"}, "fire_drill": {}, "spark": {},
    "access_event": {}, "battery_low": {"device": "FL-2"}, "compressor_fault": {},
    "pv_cloudy": {}, "boiler_refill": {}, "genset_test": {}, "lighting_scene": {"level": 50},
}


async def settle(n=6):
    for _ in range(n):
        await asyncio.sleep(0)


@pytest.fixture
def runner(world):
    return ScenarioRunner(world)


def states(world, run):
    return [e.payload["state"] for e in world.events.since(0, kind="scenario")[0]
            if e.run_id == run.id]


def test_registry_of_15(runner):
    assert len(SCENARIOS) == 15 and set(MIN_PARAMS) == set(runner.scenarios)
    lst = runner.list()
    assert [x["name"] for x in lst][:3] == ["shift", "machine_fault", "blackout"]
    by = {x["name"]: x for x in lst}
    assert by["blackout"]["duration_s"] == 600 and by["fire_drill"]["duration_s"] == 300
    assert by["pv_cloudy"]["duration_s"] == 1800 and by["shift"]["duration_s"] == 0
    assert "device" in by["machine_fault"]["params_schema"]["properties"]
    assert all(x["title_uk"] and x["group"] for x in lst)
    assert issubclass(SCENARIOS[0], Scenario) and Scenario().conflicts(None) == set()


@pytest.mark.parametrize("name", sorted(MIN_PARAMS))
async def test_each_scenario_start_stop(world, runner, name):
    run = runner.start(name, MIN_PARAMS[name], run_ref="odoo-1")
    assert run.id.startswith("r-") and run.run_ref == "odoo-1"
    await settle()
    world.advance(1)
    await settle()
    run = await runner.stop(run.id)
    assert run.state in ("stopped", "done") and run.error is None
    assert world.flags == {}  # cleanup відкотив усе
    assert states(world, run)[0] == "started" and states(world, run)[-1] == run.state
    assert runner.active() == []
    assert run.to_dict()["name"] == name


async def test_conflict_409(world, runner):
    r1 = runner.start("machine_fault", {"device": "CNC-2"})
    with pytest.raises(ScenarioConflict, match=r"device CNC-2 busy by run r-"):
        runner.start("machine_fault", {"device": "CNC-2"})
    runner.start("machine_fault", {"device": "CNC-3"})  # інший пристрій — паралельно
    runner.start("filter_clogged", {"device": "RV-05"})
    with pytest.raises(ScenarioConflict) as ei:
        runner.start("fire_drill", {})  # конфліктує з усім safety/bms
    assert ei.value.status == 409 and "busy by run" in str(ei.value)
    runner.start("pv_cloudy", {})
    for name in ("blackout", "genset_test"):  # усе енергетичне
        with pytest.raises(ScenarioConflict):
            runner.start(name, {})
    await runner.stop(r1.id)
    runner.start("machine_fault", {"device": "CNC-2"})  # після stop — можна
    await runner.stop_all()
    assert runner.active() == []


async def test_conflict_groups_and_tags(runner):
    runner.start("fire_drill", {})
    for name, params in (("spark", {}), ("filter_clogged", {"device": "AHU-1"}),
                         ("boiler_refill", {}), ("lighting_scene", {})):
        with pytest.raises(ScenarioConflict):
            runner.start(name, params)
    runner.start("shift", {})  # production — не safety/bms
    await runner.stop_all()
    runner.start("lighting_scene", {"group": "all", "level": 10})
    with pytest.raises(ScenarioConflict, match="lt:"):
        runner.start("lighting_scene", {"group": "LT-CUT", "scene": 3})
    await runner.stop_all()
    runner.start("lighting_scene", {"group": "LT-CUT", "level": 10})
    runner.start("lighting_scene", {"group": "LT-FG", "level": 10})
    with pytest.raises(ScenarioConflict):
        runner.start("lighting_scene", {"group": "all"})
    await runner.stop_all()
    runner.start("compressor_fault", {})
    with pytest.raises(ScenarioConflict):
        runner.start("blackout", {})
    await runner.stop_all()
    runner.start("truck_no_booking", {"gate": "GATE-E"})
    runner.start("truck_arrival", {"booking": "B"})  # GATE-W
    with pytest.raises(ScenarioConflict, match="loop:GATE-W"):
        runner.start("truck_no_booking", {})
    await runner.stop_all()


async def test_params_validation(world, runner):
    bad = [("machine_fault", {}), ("machine_fault", {"device": "NOPE-1"}),
           ("machine_fault", {"device": "CNC-2", "reason": "x"}),
           ("filter_clogged", {"device": "RV-26"}), ("filter_clogged", {"device": "RV-00"}),
           ("blackout", {"genset_load_kw": 600}), ("blackout", {"zzz": 1}),
           ("blackout", {"duration_s": -1}), ("shift", {"speed": 5}), ("shift", {"lines": ["Z"]}),
           ("truck_arrival", {}), ("truck_arrival", {"booking": ""}),
           ("fire_drill", {"zone": "cnc"}), ("spark", {"count": 6}),
           ("access_event", {"device": "X"}), ("access_event", {"code": 5}),
           ("battery_low", {"device": "FL-X"}), ("battery_low", {"device": "FL-1", "level_pct": 101}),
           ("pv_cloudy", {"cf": 0.01}), ("boiler_refill", {"force_on": 3}),
           ("lighting_scene", {"scene": 17}), ("lighting_scene", {"scene": 1, "level": 5}),
           ("lighting_scene", {"group": "x"}), ("lighting_scene", {"fault_device": "bad"})]
    for name, params in bad:
        with pytest.raises(ScenarioParamsError) as ei:
            runner.start(name, params)
        assert ei.value.status == 422 and ei.value.errors, (name, params)
    with pytest.raises(UnknownScenario):
        runner.start("nope", {})
    with pytest.raises(UnknownScenario):
        await runner.stop("r-nope")
    assert runner.active() == []
    # коректні межі
    ok = runner.start("lighting_scene", {"group": "LT-CUT", "fault_device": "@1.2.3.4", "level": 0})
    assert ok.params["fault_device"] == "@1.2.3.4"
    await runner.stop_all()


async def test_shift_unavailable_in_follow_odoo(world, runner):
    world.set_mode("follow_odoo")
    with pytest.raises(ScenarioConflict, match="shift недоступний у follow_odoo"):
        runner.start("shift", {})
    run = runner.start("machine_fault", {"device": "CNC-2"})  # інші дозволені
    await runner.stop(run.id)


async def test_natural_completion_and_timeline(world, runner):
    run = runner.start("pv_cloudy", {"cf": 0.25, "duration_s": 60})
    assert world.flags["pv_cf"] == 0.25 and run.ends == world.now().replace() + (run.ends - world.now())
    world.advance(30)
    await settle()
    assert run.state == "running"
    world.advance(31)
    await settle()
    assert run.state == "done" and world.flags == {}
    assert states(world, run) == ["started", "done"]


async def test_machine_fault_auto_clear_and_stop_rollback(world, runner):
    run = runner.start("machine_fault", {"device": "CNC-2", "auto_clear_s": 30})
    await settle()
    assert world.devices["CNC-2"].fault == "generic"
    world.advance(31)
    await settle()
    assert world.devices["CNC-2"].fault is None and run.state == "done"
    assert [s["step"] for s in run.timeline] == ["fault", "auto_clear"]
    run = runner.start("machine_fault", {"device": "CNC-2", "reason": "power"})
    await settle()
    assert world.devices["CNC-2"].fault == "power"
    await runner.stop(run.id)
    assert world.devices["CNC-2"].fault is None and run.state == "stopped"
    run = runner.start("machine_fault", {"device": "GANTRY-1", "duration_s": 10})
    await settle()
    world.advance(11)
    await settle()
    assert run.state == "done" and world.devices["GANTRY-1"].fault is None


async def test_blackout_and_genset_flags(world, runner):
    """Виклики API-F та регістри — на моделях/протоколах; тут — прапори для них."""
    run = runner.start("blackout", {"chp_island": True, "genset_load_kw": 100.0, "duration_s": 120})
    f = world.flags["blackout"]
    assert f["amf_master"] == "hgm" and f["phase"] == "outage" and f["chp_island"] is True
    assert f["genset"] is True and f["genset_load_kw"] == 100.0 and f["restore_delay_s"] == 60
    await settle()
    world.advance(121)
    await settle()
    assert run.state == "done" and "blackout" not in world.flags
    assert [s["step"] for s in run.timeline] == ["mains_lost", "mains_restored"]
    world.settings = type("S", (), {"genset_amf_master": "ats"})()
    runner.start("blackout", {})
    assert world.flags["blackout"]["amf_master"] == "ats"
    await runner.stop_all()
    runner.start("blackout", {"amf_master": "hgm"})
    assert world.flags["blackout"]["amf_master"] == "hgm"
    await runner.stop_all()
    runner.start("genset_test", {"test_on_load": True})
    assert world.flags["genset_test"] == {"on_load": True, "phase": "running"}
    await runner.stop_all()


async def test_filter_clogged_ramp_and_restore(world, runner):
    code = "ventilation/units/RV-05/filter_dp_pa"
    sig = world.signals[code]
    start = sig.value
    run = runner.start("filter_clogged", {"device": "RV-05", "ramp_min": 1})
    await settle()
    assert world.flags["filter_clogged"] == {"RV-05": 285.0}
    for _ in range(6):
        world.advance(10)
        await settle()
    assert sig.value == pytest.approx(285.0, abs=0.1) and sig.held_until is None
    assert start != 285.0
    await runner.stop(run.id)
    assert sig.value == sig.params["nominal"]
    for dev, code, target in (("DUST-1", "equipment/DUST-1/filter_dp_kpa", 1.9),
                              ("FA-FAC", "fire/groups/FA-FAC/dust", 92.0)):
        run = runner.start("filter_clogged", {"device": dev, "ramp_min": 0})
        await settle()
        assert world.signals[code].value == target
        await runner.stop(run.id)


async def test_filter_clogged_stop_during_ramp(world, runner):
    run = runner.start("filter_clogged", {"device": "RV-05", "ramp_min": 2, "value": 300})
    await settle()
    await runner.stop(run.id)
    assert run.state == "stopped" and world.flags == {}


async def test_signal_driven_scenarios(world, runner):
    run = runner.start("battery_low", {"device": "FL-2", "level_pct": 15})
    assert world.signals["equipment/FL-2/battery"].value == 15
    assert world.flags["battery_low"] == {"FL-2": 15}
    await runner.stop(run.id)
    assert "battery_low" not in world.flags
    runner.start("boiler_refill", {"level_pct": 90, "force_on": 2})
    assert world.signals["equipment/BOILER/silo_fill"].value == 90
    assert world.flags["boiler_force_on"] == 2
    await runner.stop_all()
    runner.start("boiler_refill", {})
    assert "boiler_force_on" not in world.flags  # -1 = авто
    await runner.stop_all()


async def test_posted_commands(world, runner):
    posted: dict[str, list] = {}
    orig = world.post

    def spy(topic, payload):  # моделі двору/СКУД/іскрогасіння самі забирають inbox — фіксуємо виклики
        posted.setdefault(topic, []).append(payload)
        orig(topic, payload)

    world.post = spy
    runner.start("spark", {"count": 3, "interval_s": 10, "fault": True})
    await settle()
    for _ in range(3):
        world.advance(10)
        await settle()
    sparks = posted["spark"]
    assert [m["index"] for m in sparks] == [0, 1, 2] and sparks[0]["fault"] is True
    run = runner.start("access_event", {"user": "U1", "code": 4867})
    await settle()
    assert run.state == "done" and posted["access"][0]["code"] == 4867
    runner.start("truck_no_booking", {"plate": "AA1234KT", "wait_min": 1})
    await settle()
    msg = posted["yard"][0]
    assert msg["kind"] == "truck_no_booking" and msg["plate"] == "AA1234KT"
    world.advance(61)
    await settle()
    await runner.stop_all()


async def test_truck_arrival_result_and_fire_drill_result(world, runner):
    run = runner.start("truck_arrival", {"booking": "BATCH/IN/00001", "unload_min": 1})
    await settle()
    world.run_results[run.id] = {"gross_kg": 25200, "tare_kg": 14000, "dock": "DOCK-W1",
                                 "unloaded_pct": 100}
    for _ in range(20):
        world.advance(30)
        await settle()
    assert run.state == "done" and run.result["gross_kg"] == 25200
    assert [s["step"] for s in run.timeline] == [
        "at_gate", "weigh_in", "to_dock", "at_dock", "to_exit", "weigh_out", "left"]
    run = runner.start("fire_drill", {"zone": "FA-CNC", "duration_s": 40})
    assert world.flags["fire_drill"]["phase"] == "active"
    for _ in range(6):
        world.advance(10)
        await settle()
    assert run.state == "done" and run.result["doors_s"] == 12 and world.flags == {}
    assert [s["step"] for s in run.timeline][:6] == [
        "alarm", "sounders", "vent_stop", "dampers", "doors", "machines"]
    run = runner.start("fire_drill", {"duration_s": 300})
    await settle()
    world.advance(5)
    await settle()
    await runner.stop(run.id)
    assert run.state == "stopped" and run.timeline[-1]["step"] == "restoring"
    run = runner.start("truck_arrival", {"booking": "X", "plate": "AA1", "unload_min": 1,
                                         "at": "2026-10-12T11:00:00+03:00"})
    await settle()
    await runner.stop(run.id)  # зупинка під час розвантаження
    assert run.state == "stopped"


async def test_failed_scenario(world, runner, monkeypatch):
    async def boom(self, ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(runner.scenarios["pv_cloudy"].__class__, "run", boom)
    run = runner.start("pv_cloudy", {})
    await settle()
    assert run.state == "failed" and run.error == "boom"
    assert world.events.last("error").message == "Сценарій pv_cloudy: boom"
    assert runner.active() == []
    assert (await runner.stop(run.id)).state == "failed"


async def test_restore_runs_closes_as_stopped(world, runner):
    run = runner.start("pv_cloudy", {"cf": 0.4})
    data = world.snapshot()
    assert run.id in data["runs"] and data["runs"][run.id]["owned_flags"] == [["pv_cf", None]]
    await runner.stop(run.id)
    world.set_flag("pv_cf", 0.4)
    runner2 = ScenarioRunner(world)
    runner2.restore_runs(data["runs"])
    assert world.flags == {} and runner2.runs[run.id].state == "stopped"
    assert states(world, runner2.runs[run.id])[-1] == "stopped"


async def test_shift_flag_defaults(world, runner):
    runner.start("shift", {"date": "2026-10-13", "speed": 2})
    f = world.flags["shift"]
    assert f["date"] == "2026-10-13" and f["lines"] == list("ABCDF") and f["speed"] == 2
    await runner.stop_all()
    runner.start("shift", {})
    assert world.flags["shift"]["date"] == "2026-10-12"
    await runner.stop_all()
    world.flags.setdefault("a", {})["k"] = 1
    from iot_sim.core.scenarios import clear_flags
    clear_flags(world, [("a", "zz"), ("missing", "k"), ("a", "k")])
    assert "a" not in world.flags
