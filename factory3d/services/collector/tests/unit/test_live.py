"""AC-236: LiveCache і подача показань із Scheduler/Emitter після масштабу ядра (C-40)."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from conftest import T0, VirtualClock

from collector.core.live import LiveCache
from collector.core.scheduler import Emitter, Scheduler
from collector.core.types import Reading

from . import CountingClock, FakePlugin, mk_signal, mk_source, reading


def test_update_get_snapshot():
    live = LiveCache(VirtualClock())
    assert live.get("a") is None and live.age_s("a") is None
    live.update([reading("a", 1.0), reading("b", 2.0)])
    live.update([reading("a", 3.0)])  # один рядок на код: перемагає останнє
    assert live.get("a").value == 3.0
    assert live.snapshot(["a", "b", "c"]) == {"a": live.get("a"), "b": live.get("b"), "c": None}


def test_age_by_clock():
    clock = VirtualClock()
    live = LiveCache(clock)
    live.update([Reading("a", T0, 1.0)])
    assert live.age_s("a") == 0.0
    clock.advance(42)
    assert live.age_s("a") == pytest.approx(42.0)
    assert live.age_s("a", T0 + timedelta(seconds=5)) == pytest.approx(5.0)  # явний `now`


def test_note_write_last_write():
    clock = VirtualClock()
    live = LiveCache(clock)
    assert live.last_write("w") is None
    live.note_write("w", 2.0, T0)
    clock.advance(10)
    live.note_write("x", "VEL")
    assert live.last_write("w") == (2.0, T0)
    assert live.last_write("x") == ("VEL", clock.now())


async def test_scheduler_feeds_live_after_scale(buffer):
    src = mk_source(signals=[mk_signal("equipment/A/x", scale=0.5)])
    plugin = FakePlugin(src, None)
    plugin.script = [[reading("equipment/A/x", 10.0)]]
    live = LiveCache()
    sched = Scheduler(buffer, clock=CountingClock(max_sleeps=2), rand=lambda: 0.0, live=live)
    with pytest.raises(asyncio.CancelledError):
        await sched.loop_poll(src, 10, list(src.signals), plugin)
    assert live.get("equipment/A/x").value == 5.0  # масштаб ядра застосовано до кешу


async def test_emitter_feeds_live_after_scale(buffer):
    sig = mk_signal("equipment/A/x", scale=2.0)
    live = LiveCache()
    em = Emitter(buffer, {sig.code: sig}, live=live)
    em.emit(reading(sig.code, 3.0))
    assert live.get(sig.code).value == 6.0


async def test_without_live_unchanged(buffer):
    sig = mk_signal("equipment/A/x", scale=2.0)
    em = Emitter(buffer, {sig.code: sig})
    em.emit(reading(sig.code, 3.0))
    assert em.live is None and await em.flush() == 1
    assert Scheduler(buffer).live is None
