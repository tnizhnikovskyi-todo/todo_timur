import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from iot_sim.core import snapshot
from iot_sim.core.clock import FakeClock
from iot_sim.core.events import RING_SIZE, CursorGone, EventBus, ulid
from iot_sim.core.world import World
from iot_sim.models import MODELS
from iot_sim.models.base import AGGREGATE, Model, NoiseModel

SEED = 20261012
KYIV = ZoneInfo("Europe/Kyiv")


def noisy(world: World) -> World:
    for dev in world.devices.values():
        dev.model = NoiseModel(dev, world)
        dev.model.attach()
    return world


def values(world: World) -> dict:
    return {c: (s.value, s.status) for c, s in world.signals.items()}


class Integrator(Model):
    """Тестова модель: hours += dt/3600 (R-06) — інваріантна до кроку."""

    def tick(self, dt_s):
        self.set("hours", self.val("hours") + dt_s / 3600)


def test_world_builds_devices_and_signals(world):
    assert len(world.signals) == 1205 and len(world.devices) >= 184
    pv = world.devices["PV-INV"]
    assert "PV-INV-3/p_kw" in pv.signals and "p_kw" not in pv.signals  # колізія листів
    s = world.signals["energy/consumers/SAW-1/p_now"]
    assert s.value == 12.18 and s.status == "ok" and s.device == "SAW-1"
    assert s.ts == datetime(2026, 10, 12, 10, 30, tzinfo=KYIV)
    assert world.devices["SAW-1"].unit_id == 11
    assert world.now() == s.ts and world.mode == "scenario"


def test_determinism_two_worlds(registry):
    a = noisy(World(registry, seed=SEED, clock=FakeClock("2026-10-12T10:30:00")))
    b = noisy(World(registry, seed=SEED, clock=FakeClock("2026-10-12T10:30:00")))
    c = noisy(World(registry, seed=SEED + 1, clock=FakeClock("2026-10-12T10:30:00")))
    for w in (a, b, c):
        w.advance(3600)
    assert values(a) == values(b)  # AC-05
    assert values(a) != values(c)
    assert a.now() == datetime(2026, 10, 12, 11, 30, tzinfo=KYIV)


def test_factor_invariance(registry):
    """AC-06: інтеграл по dt_sim не залежить від factor/розбиття кроків."""
    res = []
    for factor, real_dt, n in ((1.0, 10.0, 360), (6.0, 1.0, 600)):
        w = World(registry, seed=SEED, clock=FakeClock("2026-10-12T10:30:00", factor=factor))
        dev = w.devices["FL-1"]
        dev.model = Integrator(dev, w)
        for _ in range(n):
            w.tick_real(real_dt)
        res.append((dev.signals["hours"].value, w.now()))
    assert res[0][0] == pytest.approx(res[1][0], rel=1e-3)
    assert res[0][1] == res[1][1]


def test_tick_order_hooks_and_callbacks(world):
    order = []

    class Src(Model):
        def tick(self, dt):
            order.append(("src", self.device.code))

    class Agg(Src):
        phase = AGGREGATE

        def tick(self, dt):
            order.append(("agg", self.device.code))

    world.devices["ZZ"] = world.devices["SAW-1"].__class__("ZZ", "x", None, None, None, None, {})
    for code, cls in (("SAW-1", Agg), ("SAW-2", Src), ("ZZ", Src)):
        dev = world.devices[code]
        dev.model = cls(dev, world)
    for st in ("planner", "balance", "post"):
        world.add_hook(st, lambda w, dt, st=st: order.append((st, dt)))
    world.on_tick(lambda w: order.append(("tick", w.tick_count)))
    world.step(5)
    kinds = [o[0] for o in order if o[0] not in ("tick",)]
    assert kinds[0] == "planner"
    assert kinds.index("balance") > max(i for i, k in enumerate(kinds) if k in ("src", "agg"))
    assert kinds.index("agg") > kinds.index("src")  # агрегати — після джерел
    assert order[-1] == ("tick", 1) and ("post", 5) in order
    assert [o[1] for o in order if o[0] == "src"] == ["SAW-2", "ZZ"]  # детермінований порядок


def test_advance_substeps(world):
    seen = []
    world.add_hook("planner", lambda w, dt: seen.append(dt))
    world.advance(25)
    assert seen == [10, 10, 5]
    assert world.now() == datetime(2026, 10, 12, 10, 30, 25, tzinfo=KYIV)


def test_minute_noise_independent_of_step(registry):
    rs = []
    for step in (1, 10, 60):
        w = World(registry, seed=SEED, clock=FakeClock("2026-10-12T10:30:00"))
        seq = []
        for _ in range(180 // step):
            w.step(step)
            seq.append(w.r("a/b"))
        rs.append(seq[-1])
    assert rs[0] == rs[1] == rs[2]


def test_signal_set_held_and_force(world):
    s = world.signals["equipment/FL-2/battery"]
    now = world.now()
    s.force(10.0, now, hold_s=60)
    assert not s.set(50.0, now) and s.value == 10.0
    world.advance(61)
    assert s.set(50.0, world.now()) and s.value == 50.0
    world.force("equipment/FL-2/battery", 20.0)  # без утримання
    assert s.held_until is None and s.set(21.0, world.now())


def test_status_warn_and_non_numeric(world):
    s = world.signals["ventilation/units/RV-01/filter_dp_pa"]
    assert s.params["threshold"] == 250 and s.params["alarm"] == "above"
    s.value = 240
    assert s.evaluate() == "warn"
    s.value = "text"
    assert s.evaluate() == "ok"
    s.value = True
    assert s.evaluate() == "ok"
    w = world.signals["equipment/COMPRESSOR/pressure_bar"]
    w.params["alarm"], w.params["threshold"] = "above", 7.0
    w.value = 6.5
    assert w.evaluate() == "warn"
    w.value = 7.5
    assert w.evaluate() == "alarm" and "до 7" in w.norm_text()


def test_flags_inbox_modes(world):
    world.set_flag("x", {"a": 1})
    assert world.flag("x") == {"a": 1} and world.flag("y", 5) == 5
    world.clear_flag("x")
    world.clear_flag("x")
    assert world.flag("x") is None
    world.post("yard", {"k": 1})
    world.post("yard", {"k": 2})
    assert [m["k"] for m in world.drain("yard")] == [1, 2] and world.drain("yard") == []
    world.set_mode("follow_odoo")
    assert world.mode == "follow_odoo"
    with pytest.raises(ValueError):
        world.set_mode("zzz")


async def test_sleep_resolves_in_sim_time(world):
    fut = world.sleep(30)
    fired = []
    world.call_later(5, lambda: fired.append(1))
    world.advance(20)
    assert fired == [1] and not fut.done()
    world.advance(10)
    await asyncio.wait_for(fut, 1)


def test_fault_and_clear_via_world(world):
    world.fault("CNC-2", "spindle")
    assert world.devices["CNC-2"].fault == "spindle"
    world.clear("CNC-2")
    assert world.devices["CNC-2"].fault is None


def test_shift_calendar(world):
    sh = world.shift
    assert sh.in_shift(world.now()) and not sh.in_lunch(world.now())  # пн 10:30
    lunch = world.now().replace(hour=11, minute=45)
    assert sh.in_lunch(lunch)
    assert not sh.in_shift(world.now().replace(hour=16))
    assert not sh.in_shift(world.now() + timedelta(days=6))  # неділя
    assert sh.shift_start(lunch).hour == 7


def test_events_bus():
    t = datetime(2026, 1, 1, tzinfo=KYIV)
    bus = EventBus(lambda: t, size=5)
    got = []
    bus.subscribe(got.append)
    for i in range(8):
        bus.emit("info", f"m{i}", device="D" if i % 2 else None)
    assert len(bus.ring) == 5 and bus.counts["info"] == 8 and len(got) == 8
    evs, cur = bus.since(4)
    assert [e.message for e in evs] == ["m4", "m5", "m6", "m7"] and cur == 8
    assert [e.message for e in bus.since(4, limit=2)[0]] == ["m4", "m5"]
    assert [e.message for e in bus.since(4, device="D")[0]] == ["m5", "m7"]
    assert bus.since(8) == ([], 8)
    with pytest.raises(CursorGone):
        bus.since(1)
    with pytest.raises(ValueError):
        bus.emit("bogus", "x")
    e = bus.last("info")
    assert e.id.startswith("e-") and len(e.id) == 28 and e.to_dict()["kind"] == "info"
    assert bus.last("fire") is None and RING_SIZE == 10_000


def test_ulid_unique_monotonic(monkeypatch):
    ids = [ulid() for _ in range(200)]
    assert len(set(ids)) == 200 and all(len(i) == 26 for i in ids)
    monkeypatch.setattr("iot_sim.core.events.time.time", lambda: 1.0)
    a, b = ulid(), ulid()  # той самий мс — лічильник у випадковій частині
    assert a < b or a[:10] == b[:10]


def test_snapshot_roundtrip(registry, tmp_path):
    a = noisy(World(registry, seed=SEED, clock=FakeClock("2026-10-12T10:30:00")))
    a.set_flag("pv_cf", 0.3)
    a.jobs.append({"id": "SIM-00001"})
    a.maintenance_closed.add("RV-05")
    a.advance(300)
    a.fault("CNC-2", "spindle")
    a.signals["equipment/FL-2/battery"].force(18.0, a.now(), hold_s=600)
    data = json.loads(json.dumps(a.snapshot()))
    path = snapshot.save(a, tmp_path / "state")
    loaded = snapshot.load(tmp_path / "state")
    assert path.exists() and loaded["sim_now"] == data["sim_now"]

    b = noisy(World(registry, seed=SEED, clock=FakeClock("2026-01-01T00:00:00")))
    b.restore(loaded)
    assert b.now() == a.now() and values(b) == values(a)  # AC-48
    assert b.flags == {"pv_cf": 0.3} and b.jobs == [{"id": "SIM-00001"}]
    assert b.maintenance_closed == {"RV-05"} and b.devices["CNC-2"].fault == "spindle"
    assert b.signals["equipment/FL-2/battery"].held_until == a.signals["equipment/FL-2/battery"].held_until
    a.advance(120)
    b.advance(120)
    assert values(a) == values(b)  # шум продовжується з того ж місця


def test_snapshot_rejects_bad_and_old(registry, tmp_path, caplog, world):
    d = tmp_path / "s"
    assert snapshot.load(d) is None  # немає файлу
    d.mkdir()
    (d / snapshot.FILENAME).write_text("{not json")
    assert snapshot.load(d) is None
    (d / snapshot.FILENAME).write_text(json.dumps({"version": 1}))
    assert snapshot.load(d) is None
    snapshot.save(world, d)
    assert snapshot.load(d) is not None
    data = json.loads((d / snapshot.FILENAME).read_text())
    data["saved_at"] -= 25 * 3600
    (d / snapshot.FILENAME).write_text(json.dumps(data))
    assert snapshot.load(d) is None  # старший за 24 год
    assert snapshot.load(d, max_age_s=10**9) is not None
    data["signals"]["no/such/signal"] = [1, None, "ok", None]
    data["devices"]["NOSUCH"] = {}
    world.restore(data)  # невідомі коди ігноруються


def test_models_module_registry_untouched():
    assert "passive" in MODELS


def test_reset_models_restores_counters_and_rng(world):
    """API-17 reset: лічильники моделей (pieces_acc/Relative*) і ГПВЧ — початкові (ТП-07: повторюваність)."""
    world.set_flag("shift", {"speed": 2.0, "lines": ["A"], "trucks": False, "people": False})
    world.advance(600)
    m = world.devices["SAW-1"].model
    assert m.pieces_acc > 0 and world._rngs
    world.reset_models()
    assert m.pieces_acc == 0 and m.relative["PiecesOut"] == 0 and not world._rngs


def test_reset_models_resets_yard_controller(world):
    """API-17 reset: ворота/фури двору — початкові (відкриті після fire_drill ворота не переживають reset)."""
    from iot_sim.models.yard import ctl

    world.advance(2)
    c = ctl(world)
    c.gates["GATE-W"]["state"] = "open"
    world.reset_models()
    assert ctl(world).gates["GATE-W"]["state"] == "closed" and ctl(world) is not c
