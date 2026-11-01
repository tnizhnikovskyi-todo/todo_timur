"""Регресії рев'ю колектора 0.2.0 (виправлення 0.2.1): отруєна голова черги, HTTP 413, помилки з'єднання,
зупинка Emitter, ліміт черги в пам'яті, вік черги від вставки, пауза між пакетами при зупинці, VACUUM старого файлу."""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sqlite3
from datetime import timedelta
from types import SimpleNamespace

import aiohttp
import pytest
from conftest import T0, TOKEN

from collector.core import odoo_client, scheduler
from collector.core.buffer import Buffer
from collector.core.odoo_client import OdooClient, OdooError, Pusher, StatusReporter
from collector.core.scheduler import Emitter
from collector.core.types import PushEvent

from .test_push_backlog import RecordingClient, _async, _mk, _pusher

# --- 1. отруєний рядок на голові FIFO ---


def _fail_on(code: str, status: int = 500):
    def fail(readings):
        if any(r.code == code for r in readings):
            raise OdooError(status, "boom")

    return fail


async def _run_until_empty(p: Pusher, buffer, vclock, steps: int = 200) -> None:
    for _ in range(steps):
        if not await buffer.count():
            return
        vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
        await p.push_once()


async def test_poison_at_fifo_head_is_dropped_without_prior_success(buffer, vclock, caplog):
    """Отруєне показання ПЕРШЕ в черзі: жодного успішного пакета поки пакет зменшено ще не було, але Odoo живий
    (`/health`) -> голову відкинуто з логом code/ts, решта доходить, лічильник росте."""
    client = RecordingClient()
    client.fail = _fail_on("bad")
    p = _pusher(client, buffer, vclock, push_max=8)
    await buffer.put_many([_mk(0, code="bad")] + [_mk(i) for i in range(1, 8)])
    with caplog.at_level(logging.ERROR, logger="collector.odoo"):
        await _run_until_empty(p, buffer, vclock)
    assert await buffer.count() == 0
    sent = [r.code for b in client.batches for r in b]
    assert "bad" not in sent and len(sent) == 7
    assert p.poisoned_total == 1
    msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("bad" in m and "2026-10-14T06:00:00Z" in m for m in msgs), msgs


async def test_poison_head_not_dropped_while_odoo_down(buffer, vclock):
    client = RecordingClient()
    client.fail = _fail_on("bad")
    client.health_ok = False  # push 500 на це показання, але й /health не відповідає: не відкидати
    p = _pusher(client, buffer, vclock, push_max=1, stale_after_s=0)  # лише FIFO (без «живих» пакетів)
    await buffer.put_many([_mk(0, code="bad"), _mk(1)])
    await _run_until_empty(p, buffer, vclock, steps=40)
    assert await buffer.count() == 2 and p.poisoned_total == 0


async def test_poison_head_does_not_block_live_data_when_behind(buffer, vclock):
    """Черга відстає, голова отруєна: після невдачі наступна спроба — «жива» (найновіші), а не та сама голова."""
    client = RecordingClient()
    client.fail = _fail_on("bad")
    p = _pusher(client, buffer, vclock, push_max=4, stale_after_s=600)
    await buffer.put_many([_mk(0, code="bad")] + [_mk(i, code=f"old/{i}") for i in range(1, 6)])
    vclock.advance(7200)
    await buffer.put_many([_mk(i, code=f"live/{i}") for i in range(3)])
    assert await p.push_once() == "retry"  # голова: bad + 3 старі
    vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
    assert await p.push_once() == "ok", "після невдачі голови мав піти пакет живих даних"
    assert {f"live/{i}" for i in range(3)} <= {r.code for r in client.batches[0]}
    await _run_until_empty(p, buffer, vclock)
    sent = [r.code for b in client.batches for r in b]
    assert await buffer.count() == 0 and "bad" not in sent and len(sent) == 8 and p.poisoned_total == 1


async def test_status_reports_poisoned_total(buffer, vclock):
    client = RecordingClient()
    client.fail = _fail_on("bad")
    p = _pusher(client, buffer, vclock, push_max=2)
    await buffer.put_many([_mk(0, code="bad"), _mk(1)])
    await _run_until_empty(p, buffer, vclock)
    reg = SimpleNamespace(sources={}, errors={}, plugins={}, write_enabled=False, etag="e")
    body = await StatusReporter(client, reg, buffer, None, clock=vclock, pusher=p).build()
    assert body["buffer"]["poisoned_total"] == 1


# --- 2. HTTP 413: пакет не видаляється ---


async def test_413_too_many_readings_halves_batch_and_never_acks(buffer, vclock):
    """Ліміт Odoo (td.telemetry.push_max_readings) менший за push_max колектора: пакет ділиться, дані не губляться."""
    client = RecordingClient()

    def fail(readings):
        if len(readings) > 10:
            raise OdooError(413, "too_many_readings")

    client.fail = fail
    p = _pusher(client, buffer, vclock, push_max=100)
    await buffer.put_many([_mk(i) for i in range(35)])
    assert await p.push_once() == "retry"
    assert await buffer.count() == 35 and client.batches == [] and p.server_limit == 17
    await _run_until_empty(p, buffer, vclock)
    sent = [r.code for b in client.batches for r in b]
    assert await buffer.count() == 0 and len(sent) == 35 == len(set(sent))
    assert max(len(b) for b in client.batches) <= 10 and p.poisoned_total == 0


async def test_413_limit_recovers_when_odoo_raises_it(buffer, vclock, monkeypatch):
    monkeypatch.setattr(odoo_client, "LIMIT_PROBE_OK", 2)
    client = RecordingClient()
    odoo_limit = {"n": 8}

    def fail(readings):
        if len(readings) > odoo_limit["n"]:
            raise OdooError(413, "too_many_readings")

    client.fail = fail
    p = _pusher(client, buffer, vclock, push_max=64)
    await buffer.put_many([_mk(i) for i in range(400)])
    for _ in range(6):
        vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
        await p.push_once()
    assert p.server_limit is not None and p.server_limit <= 8
    odoo_limit["n"] = 1000  # адмін збільшив параметр
    await _run_until_empty(p, buffer, vclock)
    assert await buffer.count() == 0 and p.server_limit is None
    assert max(len(b) for b in client.batches) == 64


async def test_413_on_single_reading_is_poison_not_endless_retry(buffer, vclock):
    client = RecordingClient()
    client.fail = _fail_on("huge", status=413)
    p = _pusher(client, buffer, vclock, push_max=8)
    await buffer.put_many([_mk(0, code="huge")] + [_mk(i) for i in range(1, 4)])
    await _run_until_empty(p, buffer, vclock)
    sent = [r.code for b in client.batches for r in b]
    assert await buffer.count() == 0 and "huge" not in sent and len(sent) == 3 and p.poisoned_total == 1


# --- 3. зменшення пакета лише для 5xx/таймаутів, а не для «connection refused» ---


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def test_connection_refused_does_not_halve_batch(fake_odoo, buffer, vclock):
    """Рестарт Odoo (connection refused) не зменшує пакет: після повернення Odoo йде повний пакет."""
    client = OdooClient(f"http://127.0.0.1:{_free_port()}", TOKEN, collector="COL-T", clock=vclock)
    p = Pusher(client, buffer, push_max=100, push_interval_s=5, clock=vclock)
    await buffer.put_many([_mk(i) for i in range(100)])
    try:
        for _ in range(8):
            vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
            assert await p.push_once() == "retry"
        client.base_url = fake_odoo.url  # Odoo повернувся
        vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
        assert await p.push_once() == "ok"
        pushes = [c for c in fake_odoo.calls if c[1].endswith("/push")]
        assert len(pushes[0][2]["readings"]) == 100
    finally:
        await client.close()


class _RaisingSession:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    def request(self, *a, **kw):
        raise self.exc


async def test_error_classification_shrinkable(vclock):
    async def err(exc) -> OdooError:
        c = OdooClient("http://127.0.0.1:1", TOKEN, session=_RaisingSession(exc), clock=vclock)  # type: ignore[arg-type]
        with pytest.raises(OdooError) as ei:
            await c.request("POST", "/x")
        return ei.value

    assert (await err(aiohttp.ServerDisconnectedError())).shrinkable
    assert (await err(TimeoutError())).shrinkable
    assert not (await err(aiohttp.ClientOSError(104, "reset"))).shrinkable
    refused = OdooClient(f"http://127.0.0.1:{_free_port()}", TOKEN, clock=vclock)
    try:
        with pytest.raises(OdooError) as ei:
            await refused.request("GET", "/x")
    finally:
        await refused.close()
    assert ei.value.status is None and not ei.value.shrinkable
    assert OdooError(500).shrinkable and OdooError(504).shrinkable and OdooError(408).shrinkable
    assert not OdooError(403).shrinkable


@pytest.mark.parametrize(("timeout_like", "halved"), [(False, False), (True, True)])
async def test_batch_halves_only_for_timeouts(buffer, vclock, timeout_like, halved):
    client = RecordingClient()
    state = {"fail": True}

    def fail(readings):
        if state["fail"]:
            raise OdooError(None, "x", timeout_like=timeout_like)

    client.fail = fail
    p = _pusher(client, buffer, vclock, push_max=20)
    await buffer.put_many([_mk(i) for i in range(20)])
    for _ in range(5):
        vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
        assert await p.push_once() == "retry"
    state["fail"] = False
    vclock.advance(max(p.retry_at - vclock.monotonic(), 0) + 0.1)
    assert await p.push_once() == "ok"
    assert (len(client.batches[0]) < 20) is halved


# --- 4/5. Emitter: зупинка не губить батч, ліміт черги в пам'яті ---


@pytest.mark.parametrize("target", ["put_many", "put_event"])
@pytest.mark.parametrize("exc", [asyncio.CancelledError, RuntimeError])
async def test_emitter_flush_keeps_batch_on_cancel_or_any_error(buffer, monkeypatch, exc, target):
    em = Emitter(buffer, {}, None)
    em.emit(_mk(1))
    em.emit(_mk(2))
    em.emit_event(PushEvent("e1", "lpr", T0, "10.0.0.1", {}, {"a": 1}))
    real = getattr(buffer, target)

    async def boom(*a, **k):
        raise exc()

    monkeypatch.setattr(buffer, target, boom)
    with pytest.raises(exc):
        await em.flush()
    assert len(em._events) == 1 and len(em._readings) == (2 if target == "put_many" else 0)
    monkeypatch.setattr(buffer, target, real)
    await em.flush()
    assert await buffer.count() == 2 and await buffer.count_events() == 1


def test_pending_cap_default_is_bounded():
    assert 1 <= scheduler.MAX_PENDING <= 50_000 and scheduler.MAX_PENDING_EVENTS <= 10_000


async def test_emitter_drops_oldest_beyond_cap_loudly(buffer, monkeypatch, caplog):
    monkeypatch.setattr(scheduler, "MAX_PENDING", 50)

    def disk_full(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(buffer, "put_many", _async(disk_full))
    em = Emitter(buffer, {}, None)
    for i in range(80):
        em.emit(_mk(i))
    with caplog.at_level(logging.ERROR, logger="collector.scheduler"):
        assert await em.flush() == 0
    assert len(em._readings) == 50 and em._readings[0].value == 30.0 and em._readings[-1].value == 79.0
    assert em.dropped_total == 30
    assert any(r.levelno == logging.ERROR and "dropped 30" in r.getMessage() for r in caplog.records)


# --- 6. вік черги — від вставки в буфер ---


async def test_device_clock_in_the_past_does_not_keep_queue_behind(buffer, vclock):
    client = RecordingClient()
    p = _pusher(client, buffer, vclock, push_max=10, stale_after_s=600)
    await buffer.put_many([_mk(i, age_s=400 * 86400) for i in range(25)])  # `ts` з годинника пристрою — торік
    while await buffer.count():
        assert await p.push_once() == "ok" and p.behind is False
    assert [r.value for b in client.batches for r in b] == [float(i) for i in range(25)]  # FIFO
    await buffer.put_many([_mk(1)])
    vclock.advance(700)  # а справді застояні в буфері рядки — «відстає»
    assert await p.push_once() == "ok" and p.behind is True


async def test_old_buffer_file_without_insert_time_is_migrated(tmp_path, vclock):
    path = tmp_path / "old.sqlite"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE readings(id INTEGER PRIMARY KEY, code TEXT, ts TEXT, value REAL, text TEXT, q TEXT)")
    stamp = (T0 - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    con.executemany("INSERT INTO readings(code, ts, value, q) VALUES ('c', ?, 1.0, 'good')", [(stamp,)] * 3)
    con.commit()
    con.close()
    b = Buffer(path, clock=vclock)
    assert await b.oldest_inserted_at() == T0 - timedelta(hours=1)  # NULL -> за `ts`
    await b.put_many([_mk(1)])
    assert await b.count() == 4
    await b.close()
    cols = {r[1] for r in sqlite3.connect(path).execute("PRAGMA table_info(readings)")}
    assert "ins" in cols


# --- 7. пауза між пакетами при зупинці та drain-buffer ---


async def test_shutdown_flush_spaces_and_caps_pushes(settings, vclock):
    from collector.core.app import SHUTDOWN_PUSHES, Collector

    app = Collector(settings, clock=vclock)
    client = RecordingClient()
    client.clock = vclock
    app.pusher.client = client  # type: ignore[assignment]
    app.pusher.push_max = 100
    await app.buffer.put_many([_mk(i) for i in range(1000)])
    try:
        await app._flush()
    finally:
        await app.client.close()
        await app.buffer.close()
    assert len(client.batches) == SHUTDOWN_PUSHES, "кількість пакетів при зупинці не обмежена"
    gaps = [b - a for a, b in zip(client.times, client.times[1:], strict=False)]
    assert gaps and all(g >= app.pusher.backlog_gap_s - 1e-6 for g in gaps), gaps


async def test_drain_buffer_keeps_gap_between_pushes(fake_odoo, settings, monkeypatch):
    import time

    from collector.__main__ import drain_buffer

    settings.push_max = 100
    settings.push_backlog_gap_s = 0.3
    b = Buffer(settings.buffer_dir / "buffer.sqlite", 10)
    await b.put_many([_mk(i) for i in range(300)])
    await b.close()
    stamps: list[float] = []
    real_push = OdooClient.push

    async def spy(self, readings):
        stamps.append(time.monotonic())
        return await real_push(self, readings)

    monkeypatch.setattr(OdooClient, "push", spy)
    assert await drain_buffer(settings) == 0
    assert len(stamps) == 3
    assert all(b - a >= 0.28 for a, b in zip(stamps, stamps[1:], strict=False)), stamps


# --- 8. одноразовий VACUUM файлу без auto_vacuum ---


def _old_file(path, keep: int = 5, junk: int = 20_000) -> int:
    con = sqlite3.connect(path)  # auto_vacuum=0, як у файлі до 0.2.0
    con.execute("CREATE TABLE readings(id INTEGER PRIMARY KEY, code TEXT, ts TEXT, value REAL, text TEXT, q TEXT)")
    con.executemany(
        "INSERT INTO readings(code, ts, value, text, q) VALUES ('c', '2026-10-14T06:00:00Z', 1.0, ?, 'good')",
        [("x" * 200,)] * junk,
    )
    con.commit()
    con.execute("DELETE FROM readings WHERE id > ?", (keep,))
    con.commit()
    con.close()
    return os.path.getsize(path)


def _auto_vacuum(path) -> int:
    con = sqlite3.connect(path)
    try:
        return con.execute("PRAGMA auto_vacuum").fetchone()[0]
    finally:
        con.close()


async def test_old_file_without_auto_vacuum_is_vacuumed_once(tmp_path):
    path = tmp_path / "old.sqlite"
    before = _old_file(path)
    assert before > 3_000_000 and _auto_vacuum(path) == 0
    b = Buffer(path)
    assert await b.count() == 5
    await b.close()
    assert _auto_vacuum(path) == 2 and os.path.getsize(path) < before / 10


async def test_vacuum_skipped_for_big_buffer_or_tight_disk(tmp_path, monkeypatch):
    from collector.core import buffer as buffer_mod

    path = tmp_path / "old.sqlite"
    before = _old_file(path)
    monkeypatch.setattr(buffer_mod, "VACUUM_MAX_ROWS", 3)  # рядків 5 > 3: не «майже порожній»
    b = Buffer(path)
    await b.open()
    await b.close()
    assert _auto_vacuum(path) == 0 and os.path.getsize(path) >= before
    monkeypatch.setattr(buffer_mod, "VACUUM_MAX_ROWS", 10_000)
    monkeypatch.setattr(buffer_mod.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))  # диск майже повний
    b = Buffer(path)
    await b.open()
    await b.close()
    assert _auto_vacuum(path) == 0 and os.path.getsize(path) >= before


async def test_new_buffer_file_is_incremental_and_not_vacuumed(tmp_path):
    b = Buffer(tmp_path / "new.sqlite")
    await b.open()
    await b.close()
    assert _auto_vacuum(tmp_path / "new.sqlite") == 2
