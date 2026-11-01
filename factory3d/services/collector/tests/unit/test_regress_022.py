"""Регресії наскрізного прогону колектора 0.2.1 (виправлення 0.2.2): зупинка за SIGTERM при недоступних пристроях
не зависає; «отруєний» рядок знаходиться за секунди, а живі дані тим часом не стоять; невідомий сигнал — один лог."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Sequence
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from conftest import T0

from collector.core import app as app_mod
from collector.core.errors import ConnectError
from collector.core.odoo_client import OdooError, Pusher
from collector.core.scheduler import Emitter, Scheduler
from collector.core.types import Reading, SignalCfg

from . import FakePlugin, sig_json, src_json
from .test_push_backlog import RecordingClient

# --- 1. зупинка не зависає, якщо пристрій недоступний, а бібліотека ковтає скасування ---


async def _stubborn(release: asyncio.Event) -> None:
    """Імітує reconnect-цикл бібліотеки пристрою: скасування ігнорується, поки тест не скаже `release`."""
    while not release.is_set():
        try:
            await release.wait()
        except asyncio.CancelledError:
            continue


class StubbornPlugin(FakePlugin):
    """Пристрій недоступний: перший connect() падає (щоб запуск завершився), далі connect()/poll()/disconnect() висять
    і не реагують на скасування."""

    release: asyncio.Event

    async def connect(self) -> None:
        self.connects += 1
        if self.connects == 1:
            raise ConnectError("device down")
        await _stubborn(self.release)

    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        await _stubborn(self.release)
        return []

    async def disconnect(self) -> None:
        self.disconnects += 1
        await _stubborn(self.release)


@pytest_asyncio.fixture
async def release():
    ev = asyncio.Event()
    yield ev
    ev.set()  # відпускаємо «завислі» задачі, щоб цикл подій тесту закрився
    await asyncio.sleep(0.1)


async def _started_app(settings, fake_odoo, release, hang_core_task: bool = True):
    StubbornPlugin.release = release
    fake_odoo.config = {
        "read_enabled": True,
        "write_enabled": False,
        "sources": [src_json("S1", signals=[sig_json("equipment/A/x", period_s=1)], params={"host": "h1"})],
    }
    settings.metrics_port = 0
    app = app_mod.Collector(settings)
    app.registry.plugin_classes = {"fake": StubbornPlugin}
    await app.start()
    if hang_core_task:
        app._tasks.append(asyncio.create_task(_stubborn(release), name="f3d-stuck-core-task"))
    await asyncio.sleep(1.5)  # опитування стартують і застрягають у connect()
    return app


async def test_stop_is_bounded_when_pollers_and_transports_hang(settings, fake_odoo, release, caplog):
    """SIGTERM при недоступному пристрої: опитування застрягли в connect() і ігнорують скасування, disconnect()
    теж висить -> stop() вкладається в SHUTDOWN_TIMEOUT_S, а що можна — скинуто (буфер, пакет в Odoo)."""
    app = await _started_app(settings, fake_odoo, release)
    assert app.scheduler._tasks, "опитування мали стартувати"
    app.emitter.emit(Reading("equipment/A/x", T0, value=1.0))  # те, що можна скинути при зупинці
    t0 = time.monotonic()
    with caplog.at_level(logging.ERROR):
        await app.stop()
    elapsed = time.monotonic() - t0
    print(f"\nSHUTDOWN with hanging pollers+transports: {elapsed:.2f} s (limit {app_mod.SHUTDOWN_TIMEOUT_S:.0f} s)")
    assert elapsed < app_mod.SHUTDOWN_TIMEOUT_S, elapsed
    assert any("abandoned" in r.getMessage() for r in caplog.records)
    assert app._stopped_ok
    assert any(c[1].endswith("/push") for c in fake_odoo.calls), "скидання при зупинці не дійшло до Odoo"


async def test_run_exits_on_stop_signal_with_hanging_device(settings, fake_odoo, release):
    """Те саме через `Collector.run()`: сигнал зупинки -> `run()` повертається (а не «shutting down» без кінця)."""
    StubbornPlugin.release = release
    fake_odoo.config = {
        "read_enabled": True,
        "write_enabled": False,
        "sources": [src_json("S1", signals=[sig_json("equipment/A/x", period_s=1)], params={"host": "h1"})],
    }
    settings.metrics_port = 0
    app = app_mod.Collector(settings)
    app.registry.plugin_classes = {"fake": StubbornPlugin}
    runner = asyncio.create_task(app.run())
    await asyncio.sleep(1.5)
    t0 = time.monotonic()
    app._stop.set()
    assert await asyncio.wait_for(runner, app_mod.SHUTDOWN_TIMEOUT_S + 1) == 0
    print(f"\nrun() returned {time.monotonic() - t0:.2f} s after the stop signal")


async def test_scheduler_stop_with_timeout_abandons_stubborn_pollers(buffer, release):
    sched = Scheduler(buffer)
    task = asyncio.create_task(_stubborn(release), name="poll:S:1")
    sched._tasks["S"] = [task]
    await asyncio.sleep(0)  # задача дійшла до свого циклу, що ковтає скасування
    t0 = time.monotonic()
    stuck = await sched.stop(timeout=0.3)
    assert stuck == [task] and time.monotonic() - t0 < 1.0 and not sched._tasks


@pytest.mark.parametrize("stopped_ok, code", [(True, 0), (False, 1)])
async def test_hard_exit_watchdog_fires_if_process_is_still_alive(settings, monkeypatch, stopped_ok, code):
    """Страховка від потоків бібліотек, що не відпускають інтерпретатор після `stop()`."""
    called: list[int] = []
    fired = threading.Event()

    def hard_exit(c: int) -> None:
        called.append(c)
        fired.set()

    monkeypatch.setattr(app_mod, "HARD_EXIT_S", 0.2)
    app = app_mod.Collector(settings, hard_exit=hard_exit)
    app._stopped_ok = stopped_ok
    app._arm_watchdog()
    assert await asyncio.to_thread(fired.wait, 3.0)
    assert called == [code]
    await app.client.close()
    await app.buffer.close()


# --- 2. «отруєне» показання: швидка бісекція, живі дані не стоять ---

POISON = ("equipment/P/bad", T0 + timedelta(seconds=7))


class PoisonOdoo(RecordingClient):
    """Fake Odoo: HTTP 500 на кожен пакет, у якому є показання (code, ts) із `poison`; `/health` відповідає."""

    def __init__(self, vclock, poison=(POISON,), down_until: float = 0.0) -> None:
        super().__init__()
        self.vclock = vclock
        self.poison = set(poison)
        self.down_until = down_until  # до цього віртуального моменту 500 на все (глобальний збій), /health теж лежить
        self.attempts: list[tuple[float, int, bool]] = []  # (t, розмір, успіх)
        self.sent_ts: dict[tuple[str, datetime], int] = {}
        self.newest_sent = T0

    async def health(self):
        if self.vclock.monotonic() < self.down_until:
            raise OdooError(500, "db down")
        return {"ok": True}

    async def push(self, readings):
        readings = list(readings)
        t = self.vclock.monotonic()
        bad = t < self.down_until or any((r.code, r.ts) in self.poison for r in readings)
        self.attempts.append((t, len(readings), not bad))
        if bad:
            raise OdooError(500, "boom")
        for r in readings:
            self.sent_ts[(r.code, r.ts)] = self.sent_ts.get((r.code, r.ts), 0) + 1
            self.newest_sent = max(self.newest_sent, r.ts)
        return {}


class Sim:
    """Реальний `Pusher.run()` на віртуальному годиннику; кожна секунда `sleep()` додає в буфер `rate` нових показань
    (опитування тим часом працюють) і міряє «свіжість»: вік найновішого показання, яке вже прийняв Odoo."""

    def __init__(self, p, buffer, client, vclock, rate: int = 20, quiet_when=None) -> None:
        self.p, self.buffer, self.client, self.vclock, self.rate = p, buffer, client, vclock, rate
        self.quiet_when = quiet_when  # sim -> bool: коли істина, опитування «замовкають» (rate = 0) і черга дренується
        self.n = 0
        self.max_lag = 0.0
        self.drop_t: float | None = None
        self.produced = 0
        sim = self

        class _DropSpy(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if "poisoned reading dropped" in record.getMessage() and sim.drop_t is None:
                    sim.drop_t = sim.vclock.monotonic()

        logging.getLogger("collector.odoo").addHandler(_DropSpy())

    async def add(self, count: int, ts: datetime | None = None) -> None:
        base = ts or self.vclock.now()
        rows = [
            Reading(f"equipment/L/c{(self.n + i) % 40}", base + timedelta(milliseconds=i), value=float(self.n + i))
            for i in range(count)
        ]
        self.n += count
        await self.buffer.put_many(rows)
        self.produced += count

    async def tick_sleep(self, s: float) -> None:
        left = s
        while left > 1e-9:
            dt = min(1.0, left)
            self.vclock.advance(dt)
            left -= dt
            await self.add(int(self.rate * dt))
            if self.quiet_when is not None and self.quiet_when(self):
                self.rate = 0
            if self.drop_t is None:  # свіжість міряємо, поки рядок ще не відкинуто
                self.max_lag = max(self.max_lag, (self.vclock.now() - self.client.newest_sent).total_seconds())
        await asyncio.sleep(0)

    async def run_until(self, cond, limit_s: float) -> None:
        task = asyncio.create_task(self.p.run())
        try:
            while not cond() and self.vclock.monotonic() < limit_s:
                await asyncio.sleep(0.001)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def _sim(buffer, vclock, monkeypatch, client, **kw):
    p = Pusher(client, buffer, push_max=kw.pop("push_max", 1000), push_interval_s=5, clock=vclock)
    sim = Sim(p, buffer, client, vclock, **kw)
    monkeypatch.setattr(vclock, "sleep", sim.tick_sleep)
    return p, sim


@pytest.mark.parametrize("pos", [400, 0, 999])
async def test_poison_500_in_full_batch_is_bisected_fast_and_live_data_keeps_flowing(
    buffer, vclock, monkeypatch, pos, caplog
):
    """Інцидент 0.2.1: одне показання стабільно дає HTTP 500, у пакеті 1000 рядків, нові показання йдуть щосекунди.
    Було: 2 хв 26 с бісекції з бекофом, увесь цей час ЖИВІ дані стояли (CHP comm_lost, машини nodata).
    Тепер: рядок відкинуто за < 60 с, свіжість живих даних не гірша за ~15 с, жодне інше показання не втрачено."""
    client = PoisonOdoo(vclock)
    p, sim = _sim(
        buffer, vclock, monkeypatch, client, quiet_when=lambda s: s.drop_t and s.vclock.monotonic() >= s.drop_t + 20
    )
    rows = [Reading(f"equipment/H/c{i}", T0 + timedelta(milliseconds=i), value=1.0) for i in range(1000)]
    rows[pos] = Reading(*POISON, value=1.0)
    await buffer.put_many(rows)
    vclock.advance(7)  # показання «з минулого»: пакет з голови черги, а не «живі»
    client.newest_sent = vclock.now()
    with caplog.at_level(logging.ERROR, logger="collector.odoo"):
        await sim.run_until(lambda: sim.rate == 0 and buffer.rows <= 0, 300)
    t_drop = sim.drop_t or float("inf")
    fails = [a for a in client.attempts if not a[2]]
    print(
        f"\npoison@{pos}: dropped after {t_drop - 7:.0f} s virtual, max live freshness lag {sim.max_lag:.1f} s, "
        f"{len(fails)} failed / {len(client.attempts)} pushes before the drop"
    )
    assert p.poisoned_total == 1 and t_drop - 7 <= 60, t_drop
    assert sim.max_lag <= 15, sim.max_lag
    before_drop = [a for a in client.attempts if a[0] <= t_drop]
    rate = len(before_drop) / max(1.0, t_drop - 7) * 60
    assert rate <= 55, f"{rate:.0f} запитів/хв: ліміт Odoo 60/хв"
    assert any(
        "poisoned reading dropped" in r.getMessage() and "equipment/P/bad" in r.getMessage() for r in caplog.records
    )
    # нічого не втрачено, крім отруєного, і нічого не продубльовано
    assert POISON not in client.sent_ts and all(n == 1 for n in client.sent_ts.values())
    assert sum(client.sent_ts.values()) == 1000 - 1 + sim.produced and buffer.rows == 0


async def test_transient_500_on_big_batch_recovers_without_drops(buffer, vclock, monkeypatch):
    """Кілька HTTP 500 поспіль на великому пакеті (збій Odoo, не рядок): нічого не відкидається, черга розгрібається."""
    client = PoisonOdoo(vclock, poison=(), down_until=0.0)
    flaky = {"n": 2}
    real_push = client.push

    async def push(readings):
        if flaky["n"] > 0 and len(list(readings)) > 100:
            flaky["n"] -= 1
            raise OdooError(500, "hiccup")
        return await real_push(readings)

    client.push = push  # type: ignore[method-assign]
    p, sim = _sim(buffer, vclock, monkeypatch, client, rate=5, quiet_when=lambda s: s.vclock.monotonic() >= 60)
    await sim.add(1000, ts=T0)
    await sim.run_until(lambda: sim.rate == 0 and buffer.rows <= 0 and p._suspect_hi is None, 300)
    assert p.poisoned_total == 0 and p._suspect_hi is None
    assert sum(client.sent_ts.values()) == sim.produced == len(client.sent_ts)


async def test_global_500_outage_drops_nothing_and_does_not_hammer_odoo(buffer, vclock, monkeypatch):
    """Усе дає 500 і /health лежить 5 хв: рядки не відкидаються, паузи ростуть (≤ ~48 запитів/хв, далі рідше)."""
    client = PoisonOdoo(vclock, poison=(), down_until=300.0)
    p, sim = _sim(buffer, vclock, monkeypatch, client, rate=10, quiet_when=lambda s: s.vclock.monotonic() >= 400)
    await sim.add(500, ts=T0)
    await sim.run_until(lambda: sim.rate == 0 and buffer.rows <= 0, 1200)
    assert p.poisoned_total == 0
    during = [a for a in client.attempts if a[0] < 300]
    assert len(during) <= 48 * 5 and not any(a[2] for a in during)
    assert len(during) >= 6, "після збою мають лишатись повторні спроби"
    # Odoo ожив: усе (і накопичене) доходить, без втрат
    assert sum(client.sent_ts.values()) == sim.produced == len(client.sent_ts)


# --- 3. невідомий сигнал: одне попередження на код ---


async def test_unknown_signal_is_warned_once_per_code(buffer, caplog):
    em = Emitter(buffer, {})
    with caplog.at_level(logging.WARNING, logger="collector.scheduler"):
        for i in range(30):
            em.emit(Reading("energy_control/auto/heartbeat", T0 + timedelta(seconds=10 * i), value=float(i)))
        em.emit(Reading("energy_control/auto/other", T0, value=1.0))
    msgs = [r.getMessage() for r in caplog.records if "unknown signal" in r.getMessage()]
    assert len(msgs) == 2 and "heartbeat" in msgs[0] and "other" in msgs[1], msgs
    assert len(em._readings) == 31, "показання не губляться, лише попередження дедуплікується"
