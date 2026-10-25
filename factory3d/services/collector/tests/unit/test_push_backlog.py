"""Інцидент «буфер завис»: відправка завжди просувається, черга не заважає живим даним, /health не бреше."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import timedelta

import aiohttp
import pytest
from conftest import T0

from collector.core.odoo_client import OdooError, Pusher
from collector.core.types import PushEvent, Reading


class RecordingClient:
    """Підміна OdooClient: записує пакети; `fail(readings)` може кинути OdooError."""

    collector = "COL-T"

    def __init__(self) -> None:
        self.batches: list[list[Reading]] = []
        self.times: list[float] = []  # віртуальний час кожної відправки (якщо задано clock)
        self.clock = None
        self.fail = None

    async def push(self, readings):
        readings = list(readings)
        if self.fail is not None:
            self.fail(readings)
        self.batches.append(readings)
        if self.clock is not None:
            self.times.append(self.clock.monotonic())
        return {}


def _mk(i: int, age_s: float = 0, code: str | None = None) -> Reading:
    return Reading(code=code or f"equipment/A/c{i}", ts=T0 - timedelta(seconds=age_s), value=float(i))


def _pusher(client, buffer, vclock, **kw) -> Pusher:
    kw.setdefault("push_max", 100)
    return Pusher(client, buffer, push_interval_s=5, clock=vclock, **kw)


def _locked(*args, **kwargs):
    raise sqlite3.OperationalError("database table is locked")


async def test_ack_failure_does_not_resend_batch(buffer, vclock, monkeypatch):
    """Odoo прийняв, але видалити не вдалося (locked): наступний крок спершу видаляє, а не шле пакет вдруге."""
    client = RecordingClient()
    p = _pusher(client, buffer, vclock)
    await buffer.put_many([_mk(i) for i in range(5)])
    real_ack = buffer.ack
    monkeypatch.setattr(buffer, "ack", _async(_locked))
    assert await p.push_once() == "retry"
    assert len(client.batches) == 1 and await buffer.count() == 5
    monkeypatch.setattr(buffer, "ack", real_ack)
    vclock.advance(p.retry_at - vclock.monotonic() + 0.1)
    assert await p.push_once() == "empty"
    assert len(client.batches) == 1, "той самий пакет відправлено вдруге"
    assert await buffer.count() == 0


def _async(fn):
    async def inner(*a, **kw):
        return fn(*a, **kw)

    return inner


async def test_take_error_is_retried_not_fatal(buffer, vclock, monkeypatch):
    client = RecordingClient()
    p = _pusher(client, buffer, vclock)
    await buffer.put_many([_mk(i) for i in range(3)])
    real_take = buffer.take
    monkeypatch.setattr(buffer, "take", _async(_locked))
    assert await p.push_once() == "retry"
    assert client.batches == []
    monkeypatch.setattr(buffer, "take", real_take)
    assert await p.push_once() == "wait"
    vclock.advance(p.retry_at - vclock.monotonic() + 0.1)
    assert await p.push_once() == "ok"
    assert len(client.batches[0]) == 3 and await buffer.count() == 0


async def test_run_loop_survives_unexpected_error(buffer, vclock, monkeypatch):
    client = RecordingClient()
    p = _pusher(client, buffer, vclock)
    await buffer.put_many([_mk(i) for i in range(3)])
    calls = {"n": 0}
    real = p.push_once

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return await real()

    monkeypatch.setattr(p, "push_once", flaky)
    task = asyncio.create_task(p.run())
    try:
        await asyncio.wait_for(_until(lambda: client.batches), 10)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert calls["n"] >= 2 and await buffer.count() == 0


async def _until(cond, step: float = 0.005):
    while not cond():
        await asyncio.sleep(step)


async def test_stuck_backlog_live_data_flows(buffer, vclock):
    """Хвіст на 2 год позаду: живі показання доходять за 2-й пакет (а не після всієї черги), далі пакети
    чергуються (живі/найстаріші), і все видаляється рівно один раз."""
    client = RecordingClient()
    p = _pusher(client, buffer, vclock, stale_after_s=600)
    await buffer.put_many([_mk(i, age_s=7200 - i) for i in range(450)])
    live = [_mk(1000 + i, code=f"live/{i}") for i in range(50)]
    await buffer.put_many(live)
    assert await p.push_once() == "ok" and p.behind is True
    assert [r.code for r in client.batches[0]][:2] == ["equipment/A/c0", "equipment/A/c1"]  # найстаріші
    assert await p.push_once() == "ok"
    sent_live = {r.code for r in client.batches[1] if r.code.startswith("live/")}
    assert sent_live == {f"live/{i}" for i in range(50)}, "живі дані не пріоритетні при відставанні"
    while await buffer.count():
        assert await p.push_once() == "ok"
    codes = [r.code for b in client.batches for r in b]
    assert len(codes) == 500 and len(set(codes)) == 500  # рівно один раз
    assert await p.push_once() == "empty"
    assert p.behind is False


async def test_new_live_rows_overtake_old_backlog_each_cycle(buffer, vclock):
    client = RecordingClient()
    p = _pusher(client, buffer, vclock, push_max=10, stale_after_s=600)
    await buffer.put_many([_mk(i, age_s=5000) for i in range(100)])
    for turn in range(4):
        await buffer.put_many([_mk(0, code=f"live/{turn}/{k}") for k in range(3)])
        await p.push_once()  # старі
        await p.push_once()  # живі
        assert {f"live/{turn}/{k}" for k in range(3)} <= {r.code for r in client.batches[-1]}


async def test_no_backlog_policy_is_plain_fifo(buffer, vclock):
    client = RecordingClient()
    p = _pusher(client, buffer, vclock, push_max=4, stale_after_s=600)
    await buffer.put_many([_mk(i) for i in range(10)])
    while await buffer.count():
        assert await p.push_once() == "ok"
    assert [r.value for b in client.batches for r in b] == [float(i) for i in range(10)]
    assert p.behind is False


async def test_backlog_sent_in_several_batches_per_interval(buffer, vclock):
    """Є черга -> наступний пакет через backlog_gap_s, а не через push_interval_s (у межах ліміту Odoo 60/хв)."""
    client = RecordingClient()
    client.clock = vclock
    p = _pusher(client, buffer, vclock, push_max=100, backlog_gap_s=1.25)
    await buffer.put_many([_mk(i) for i in range(1000)])
    task = asyncio.create_task(p.run())
    try:
        await asyncio.wait_for(_until(lambda: len(client.batches) >= 10), 20)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    gaps = [b - a for a, b in zip(client.times, client.times[1:], strict=False)][:9]
    assert gaps and all(g == pytest.approx(1.25) for g in gaps), gaps  # а не push_interval_s = 5 с
    assert 60.0 / p.backlog_gap_s < 60  # < 60 пакетів/хв (ліміт Odoo)


async def test_poison_single_reading_dropped_after_bisect(buffer, vclock):
    """Пакет з «отруєним» показанням (HTTP 500) ділиться навпіл; здорові дойдуть, отруєне відкинуто."""
    client = RecordingClient()

    def fail(readings):
        if any(r.code == "bad" for r in readings):
            raise OdooError(500, "boom")

    client.fail = fail
    p = _pusher(client, buffer, vclock, push_max=8)
    await buffer.put_many([_mk(i) for i in range(3)] + [_mk(0, code="bad")] + [_mk(i) for i in range(4, 8)])
    for _ in range(60):
        if not await buffer.count():
            break
        vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
        await p.push_once()
    assert await buffer.count() == 0
    sent = [r.code for b in client.batches for r in b]
    assert "bad" not in sent and len(sent) == 7


async def test_global_odoo_500_does_not_empty_buffer(buffer, vclock):
    client = RecordingClient()

    def fail(readings):
        raise OdooError(500, "db down")

    client.fail = fail
    p = _pusher(client, buffer, vclock, push_max=4)
    await buffer.put_many([_mk(i) for i in range(10)])
    for _ in range(40):
        vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
        await p.push_once()
    assert await buffer.count() == 10


async def test_emitter_keeps_readings_when_buffer_locked(buffer, monkeypatch):
    from collector.core.scheduler import Emitter

    em = Emitter(buffer, {}, None)
    em.emit(_mk(1))
    em.emit(_mk(2))
    em.emit_event(PushEvent("e1", "lpr", T0, "10.0.0.1", {}, {"a": 1}))
    real_put = buffer.put_many
    monkeypatch.setattr(buffer, "put_many", _async(_locked))
    assert await em.flush() == 0
    assert len(em._readings) == 2 and len(em._events) == 1
    monkeypatch.setattr(buffer, "put_many", real_put)
    assert await em.flush() == 3
    assert await buffer.count() == 2 and await buffer.count_events() == 1


# --- Collector: конфіг Odoo, /health, супервізор ---


async def test_odoo_config_wins_over_env(settings, fake_odoo):
    from collector.core.app import Collector

    assert settings.push_interval_s == 5 and settings.push_max == 1000  # env/умовчання
    fake_odoo.config = {
        "read_enabled": True,
        "write_enabled": False,
        "sources": [],
        "collector": {"code": "COL-T", "push_interval_s": 2, "push_max": 2000},
    }
    app = Collector(settings)
    assert app.pusher.push_interval_s == 5 and app.pusher.push_max == 1000
    try:
        await app.registry.load()
        assert app.pusher.push_interval_s == 2 and app.pusher.push_max == 2000
        app.registry.collector = {"push_max": 5000}  # Odoo не більше 2000; інтервал — з env, якщо Odoo мовчить
        await app._on_config()
        assert app.pusher.push_max == 2000 and app.pusher.push_interval_s == 5
    finally:
        await app.registry.close()
        await app.client.close()
        await app.buffer.close()


async def test_health_and_gauge_report_real_rows(settings):
    from collector.core.app import Collector

    settings.metrics_port = 0
    app = Collector(settings)
    await app.metrics_server.start()
    try:
        await app.buffer.put_many([_mk(i) for i in range(250)])
        await app.buffer.ack([i for i, _ in await app.buffer.take(50)])
        url = f"http://127.0.0.1:{app.metrics_server.port}/health"
        async with aiohttp.ClientSession() as s, s.get(url) as r:
            body = await r.json()
        assert body["buffer_rows"] == 200 == await app.buffer._count("readings")
        assert app.metrics.registry.get_sample_value("collector_buffer_rows") == 200
        assert await _status_rows(app) == 200
    finally:
        await app.metrics_server.stop()
        await app.buffer.close()


async def _status_rows(app) -> int:
    from collector.core.odoo_client import StatusReporter

    rep = StatusReporter(app.client, app.registry, app.buffer, app.scheduler)
    return (await rep.build())["buffer"]["rows"]


async def test_supervisor_restarts_crashed_task(settings, vclock):
    from collector.core.app import Collector

    app = Collector(settings, clock=vclock)
    runs = {"n": 0}

    async def flaky():
        runs["n"] += 1
        if runs["n"] < 3:
            raise sqlite3.OperationalError("database table is locked")

    await asyncio.wait_for(app._supervised("t", flaky), 10)
    assert runs["n"] == 3
    await app.client.close()
    await app.buffer.close()


async def test_maintenance_survives_buffer_error(settings, monkeypatch):
    from collector.core.app import Collector

    app = Collector(settings)
    monkeypatch.setattr(app.buffer, "enforce_limit", _async(_locked))
    await app._maintenance_once()  # не піднімає виняток
    await app.client.close()
    await app.buffer.close()
