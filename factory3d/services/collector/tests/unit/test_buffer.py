"""AC-72: SQLite-буфер."""

from __future__ import annotations

import asyncio
import os
import sqlite3
import threading

from conftest import T0

from collector.core.buffer import Buffer
from collector.core.types import CommandResult, PushEvent, Reading


def _r(i: int, text: str | None = None) -> Reading:
    return Reading(code=f"equipment/A/c{i}", ts=T0, value=None if text else float(i), text=text)


async def test_fifo_take_ack(buffer):
    await buffer.put_many([_r(i) for i in range(10)])
    rows = await buffer.take(4)
    assert [r.code for _, r in rows] == [f"equipment/A/c{i}" for i in range(4)]
    ids = [i for i, _ in rows]
    assert ids == sorted(ids)
    await buffer.ack(ids)
    assert await buffer.count() == 6
    assert [r.value for _, r in await buffer.take(1)] == [4.0]


async def test_persist_after_reopen(tmp_path):
    path = tmp_path / "b.sqlite"
    b1 = Buffer(path, max_mb=200)
    await b1.put_many([_r(i) for i in range(10)])
    await b1.ack([i for i, _ in await b1.take(4)])
    await b1.close()
    b2 = Buffer(path, max_mb=200)
    rows = await b2.take(100)
    assert len(rows) == 6 and rows[0][1].code == "equipment/A/c4"
    assert rows[0][1].ts == T0
    await b2.close()


async def test_size_limit_drops_oldest(tmp_path):
    path = tmp_path / "b.sqlite"
    b = Buffer(path, max_mb=1)
    for k in range(3):
        await b.put_many([_r(k * 10_000 + i, text="x" * 64) for i in range(10_000)])
    dropped = await b.enforce_limit()
    assert dropped > 0 and b.dropped_total == dropped
    assert await b.count() == 30_000 - dropped
    assert await b.used_bytes() <= 0.9 * 1024 * 1024  # обрізання до 90 % ліміту (гістерезис)
    assert os.path.getsize(path) <= 1024 * 1024
    first = await b.take(1)
    assert not first or first[0][1].code != "equipment/A/c0"
    await b.close()


async def test_events_results_not_dropped(tmp_path, vclock):
    b = Buffer(tmp_path / "b.sqlite", max_mb=1, clock=vclock)
    ev = PushEvent("e" * 64, "lpr", T0, "10.0.0.1", {"content-type": "a"}, {"plate": "AA"})
    assert await b.put_event(ev) is True
    assert await b.put_event(ev) is False  # дублікат event_id
    await b.put_result(CommandResult(id=5, state="done", ts=T0, result="ok", data={"a": 1}))
    for k in range(3):
        await b.put_many([_r(k * 10_000 + i, text="x" * 64) for i in range(10_000)])
    await b.enforce_limit()
    assert await b.count_events() == 1 and await b.count_results() == 1
    ((_, got),) = await b.take_results(10)
    assert got.id == 5 and got.data == {"a": 1}
    # старші за 7 діб — видаляються
    vclock.advance(8 * 86400)
    await b.purge_old_aux()
    assert await b.count_events() == 0 and await b.count_results() == 0
    await b.close()


def _w(i: int) -> Reading:
    return Reading(code=f"equipment/A/c{i % 300}", ts=T0, value=float(i), text=None)


async def test_concurrent_tasks_no_table_locked(tmp_path):
    """Інцидент: `database table is locked`. take() (відкритий курсор) і incremental_vacuum у різних задачах на одному
    з'єднанні раніше давали SQLITE_LOCKED; тепер усі операції серіалізовані й виконуються цілком."""
    b = Buffer(tmp_path / "b.sqlite", max_mb=1)
    errors: list[BaseException] = []
    await b.put_many([_r(i, text="x" * 64) for i in range(20_000)])

    async def guard(coro):
        try:
            await coro
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    async def writer():
        for k in range(40):
            await guard(b.put_many([_r(k * 1000 + i, text="x" * 64) for i in range(500)]))
            await asyncio.sleep(0)

    async def pusher():
        for _ in range(60):

            async def step():
                rows = await b.take(300)
                await b.ack([i for i, _ in rows[:100]])
                await b.count()

            await guard(step())
            await asyncio.sleep(0)

    async def maintenance():
        for _ in range(15):
            await guard(b.enforce_limit())
            await asyncio.sleep(0)

    await asyncio.gather(writer(), pusher(), pusher(), maintenance())
    assert errors == []
    assert await b.count() == await b.recount()
    await b.close()


async def test_two_connections_two_threads_write_and_ack(tmp_path):
    """Два з'єднання (як демон і CLI `drain-buffer`) у двох потоках: писання vs ack/обрізання. WAL + busy_timeout."""
    path = tmp_path / "b.sqlite"
    errors: list[BaseException] = []
    produced = 40 * 200

    def writer():
        async def go():
            b = Buffer(path, max_mb=1)
            for k in range(40):
                await b.put_many([_r(k * 1000 + i, text="y" * 64) for i in range(200)])
            await b.close()

        try:
            asyncio.run(go())
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    def acker():
        async def go():
            b = Buffer(path, max_mb=1)
            for _ in range(60):
                rows = await b.take(150)
                await b.ack([i for i, _ in rows])
                await b.enforce_limit()
                await asyncio.sleep(0.005)
            await b.close()

        try:
            asyncio.run(go())
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer), threading.Thread(target=acker)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=50)
    assert errors == []
    check = Buffer(path, max_mb=1)
    left = await check.count()
    await check.close()
    assert 0 <= left <= produced
    con = sqlite3.connect(path)
    assert con.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == left
    con.close()


async def test_busy_is_retried_not_raised(tmp_path, monkeypatch):
    """Тимчасове locked/busy повторюється; не-тимчасова помилка піднімається одразу."""
    b = Buffer(tmp_path / "b.sqlite")
    await b.open()
    calls = {"n": 0}

    async def flaky(db):
        calls["n"] += 1
        if calls["n"] < 3:
            raise sqlite3.OperationalError("database table is locked")
        return "ok"

    monkeypatch.setattr("collector.core.buffer.BUSY_RETRY_S", 0.001)
    assert await b._run(flaky) == "ok" and b.busy_retries == 2

    async def broken(db):
        raise sqlite3.OperationalError("no such table: nope")

    try:
        await b._run(broken)
    except sqlite3.OperationalError as exc:
        assert "no such table" in str(exc)
    else:
        raise AssertionError("must raise")
    await b.close()


async def test_rows_counter_is_real(tmp_path):
    """`/health` показував 66 при 3 млн рядків: лічильник має збігатися з COUNT(*) після put/ack/обрізання/reopen."""
    path = tmp_path / "b.sqlite"
    b = Buffer(path, max_mb=1)
    assert b.rows == 0
    await b.put_many([_w(i) for i in range(1000)])
    assert b.rows == 1000
    await b.ack([i for i, _ in await b.take(300)])
    assert b.rows == 700 == await b._count("readings")
    await b.put_many([_r(i, text="x" * 64) for i in range(20_000)])
    await b.enforce_limit()
    assert b.rows == await b._count("readings") and b.rows < 20_700
    await b.close()
    b2 = Buffer(path, max_mb=1)
    assert await b2.count() == await b2._count("readings")  # відновлення при відкритті
    # зміна файлу іншим процесом -> recount
    con = sqlite3.connect(path)
    con.execute("DELETE FROM readings")
    con.commit()
    con.close()
    assert await b2.recount() == 0 == b2.rows
    await b2.close()


async def test_trim_in_short_batches(tmp_path, monkeypatch):
    """Обрізання: партії ≤ DROP_BATCH рядків, кожна окремою транзакцією; Lock вільний між партіями."""
    b = Buffer(tmp_path / "b.sqlite", max_mb=2)
    for k in range(6):
        await b.put_many([_r(k * 10_000 + i, text="x" * 64) for i in range(10_000)])
    sizes: list[int] = []
    orig = b._delete_oldest

    async def spy(n):
        sizes.append(n)
        assert not b._lock.locked()  # між партіями Lock відпущено
        return await orig(n)

    monkeypatch.setattr(b, "_delete_oldest", spy)
    dropped = await b.enforce_limit()
    assert dropped > 0 and len(sizes) >= 2 and max(sizes) <= 10_000
    assert not b._lock.locked()
    rows = await b.take(1)
    assert rows and rows[0][0] > 1  # зрізано саме найстаріше
    await b.close()


async def test_take_newest_and_oldest_ts(tmp_path):
    b = Buffer(tmp_path / "b.sqlite")
    assert await b.oldest_ts() is None
    await b.put_many([_w(i) for i in range(10)])
    newest = await b.take(3, newest=True)
    assert [r.value for _, r in newest] == [7.0, 8.0, 9.0]  # за зростанням id
    assert await b.oldest_ts() == T0
    await b.close()
