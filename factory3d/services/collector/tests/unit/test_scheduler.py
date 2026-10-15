"""AC-71, AC-101: планувальник, бекоф, джиттер, масштаб ядра."""
from __future__ import annotations

import asyncio

import pytest

from collector.core.buffer import Buffer
from collector.core.errors import PollError
from collector.core.metrics import Metrics
from collector.core.scheduler import Emitter, Scheduler, apply_signal_scale

from . import CountingClock, FakePlugin, mk_signal, mk_source, reading


def _src():
    return mk_source(signals=[mk_signal("equipment/A/x", period_s=10), mk_signal("equipment/A/y", period_s=10),
                              mk_signal("equipment/A/z", period_s=60)])


async def _run(sched, src, plugin, period=10):
    sigs = sched.group_signals(src)[period]
    with pytest.raises(asyncio.CancelledError):
        await sched.loop_poll(src, period, sigs, plugin)


def test_groups_by_period(buffer):
    groups = Scheduler.group_signals(_src())
    assert sorted(groups) == [10, 60]
    assert [s.code for s in groups[10]] == ["equipment/A/x", "equipment/A/y"]


async def test_start_source_creates_task_per_group(buffer):
    clock = CountingClock(max_sleeps=1)
    sched = Scheduler(buffer, clock=clock, rand=lambda: 0.5)
    tasks = sched.start_source(_src(), FakePlugin(_src(), None))
    assert len(tasks) == 2
    await sched.stop()


async def test_initial_jitter(buffer):
    clock = CountingClock()
    plugin = FakePlugin(_src(), None)
    sched = Scheduler(buffer, clock=clock, rand=lambda: 0.3)
    await _run(sched, _src(), plugin, 10)
    assert clock.sleeps[0] == pytest.approx(3.0)
    clock2 = CountingClock()
    await _run(Scheduler(buffer, clock=clock2, rand=lambda: 0.5), _src(), FakePlugin(_src(), None), 60)
    assert clock2.sleeps[0] == pytest.approx(30.0)


async def test_backoff_and_error_state(buffer):
    clock = CountingClock(max_sleeps=9)
    plugin = FakePlugin(_src(), None)
    plugin.script = [PollError("x")] * 9
    sched = Scheduler(buffer, clock=clock, rand=lambda: 0.0)
    await _run(sched, _src(), plugin)
    assert clock.sleeps[:8] == [0.0, 1, 2, 4, 8, 16, 30, 30]
    assert sched.health("S").state == "error"
    assert sched.health("S").error == "x"


async def test_success_resets(buffer):
    clock = CountingClock(max_sleeps=7)
    plugin = FakePlugin(_src(), None)
    plugin.script = [PollError("x")] * 3 + [[reading("equipment/A/x")], PollError("x")]
    sched = Scheduler(buffer, clock=clock, rand=lambda: 0.0)
    await _run(sched, _src(), plugin)
    assert clock.sleeps[:6] == [0.0, 1, 2, 4, 10, 1]
    assert sched.health("S").state == "online" or sched.health("S").stats["errors"] == 4
    assert sched.health("S").stats["polls"] == 1


async def test_overrun_metric(buffer, vclock):
    metrics = Metrics(vclock)
    plugin = FakePlugin(_src(), None)
    plugin.script = [lambda: (vclock.advance(15), [reading("equipment/A/x")])[1]]
    sched = Scheduler(buffer, metrics=metrics, clock=vclock, rand=lambda: 0.0)
    await _run(sched, _src(), plugin)
    assert metrics.registry.get_sample_value("collector_poll_overrun_total", {"source": "S"}) == 1


async def test_core_applies_signal_scale_once(buffer, vclock):
    src = mk_source(signals=[
        mk_signal("equipment/A/p1", scale=1.0), mk_signal("equipment/A/p2", scale=2.0),
        mk_signal("equipment/A/st", kind="state", scale=5.0), mk_signal("equipment/A/bad", scale=3.0)])
    plugin = FakePlugin(src, None)
    plugin.script = [[reading("equipment/A/p1", 3.402), reading("equipment/A/p2", 3.402),
                      reading("equipment/A/st", None, text="busy"), reading("equipment/A/bad", None, q="bad")]]
    sched = Scheduler(buffer, clock=vclock, rand=lambda: 0.0)
    await _run(sched, src, plugin)
    rows = [r for _, r in await buffer.take(10)]
    assert [r.value for r in rows] == [pytest.approx(3.402), pytest.approx(6.804), None, None]
    assert rows[2].text == "busy" and rows[3].q == "bad"


async def test_emit_applies_signal_scale(buffer):
    sigs = {"equipment/A/p2": mk_signal("equipment/A/p2", scale=2.0),
            "equipment/A/st": mk_signal("equipment/A/st", kind="state", scale=5.0)}
    em = Emitter(buffer, sigs)
    em.emit(reading("equipment/A/p2", 3.402))
    em.emit(reading("equipment/A/st", None, text="busy"))
    em.emit(reading("equipment/A/unknown", 7.0))
    assert await em.flush() == 3
    vals = [r.value for _, r in await buffer.take(10)]
    assert vals == [pytest.approx(6.804), None, 7.0]


def test_apply_scale_counter_and_unknown(caplog):
    sigs = {"c": mk_signal("c", kind="counter", scale=0.01)}
    out = apply_signal_scale([reading("c", 100.0), reading("zz", 1.0)], sigs)
    assert out[0].value == pytest.approx(1.0) and out[1].value == 1.0
    assert "unknown signal" in caplog.text


async def test_buffer_fixture_used(buffer: Buffer):
    assert await buffer.count() == 0
