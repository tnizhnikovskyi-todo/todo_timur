from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from iot_sim.core.clock import FakeClock, FakeRealTime, SimClock

KYIV = ZoneInfo("Europe/Kyiv")


def test_factor_monotonic():
    rt = FakeRealTime()
    c = SimClock(factor=10, sim_t0=datetime(2026, 10, 12, 10, 30, tzinfo=KYIV), real_time=rt)
    t0 = c.now()
    rt.advance(6)
    assert (c.now() - t0).total_seconds() == pytest.approx(60)
    c.set_factor(60)  # не стрибає
    assert (c.now() - t0).total_seconds() == pytest.approx(60)
    rt.advance(1)
    assert (c.now() - t0).total_seconds() == pytest.approx(120)
    with pytest.raises(ValueError):
        c.set_factor(61)


def test_set_time():
    rt = FakeRealTime()
    c = SimClock(real_time=rt)
    c.set(datetime(2026, 1, 1, 12, 0))  # naive -> Київ
    assert c.now().hour == 12 and c.now().tzinfo is not None
    rt.advance(30)
    assert c.now().minute == 0 and c.now().second == 30
    assert c.minute_index() == int(datetime(2026, 1, 1, 12, 0, 30, tzinfo=KYIV).timestamp() // 60)


def test_default_start_is_real_time():
    assert SimClock().now().tzinfo is not None


def test_dst_transition():
    """25.10.2026 04:00 → 03:00 (SPEC §11 помилково каже 26.10; остання неділя жовтня — 25.10): UTC-хвилини монотонні, без дублів."""
    c = FakeClock(datetime(2026, 10, 25, 2, 50, tzinfo=KYIV))
    seen, hours = [], []
    for _ in range(80):  # 80 хвилин
        c.advance(60)
        seen.append(c.minute_index())
        hours.append(c.now().hour)
    assert len(set(seen)) == 80 and seen == sorted(seen)
    assert hours.count(3) >= 61  # година 03:xx повторюється (EEST -> EET)


def test_fake_clock_advance_and_factor():
    c = FakeClock("2026-10-12T10:30:00", factor=2)
    c.advance(120)
    assert c.now() == datetime(2026, 10, 12, 10, 32, tzinfo=KYIV)
