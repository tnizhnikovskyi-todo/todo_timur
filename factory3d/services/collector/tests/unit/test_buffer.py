"""AC-72: SQLite-буфер."""
from __future__ import annotations

import os

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
    assert b.dropped_total >= 10_000 and b.dropped_total % 10_000 == 0
    assert dropped % 10_000 == 0
    assert os.path.getsize(path) <= 1024 * 1024
    first = (await b.take(1))
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
    (_, got), = await b.take_results(10)
    assert got.id == 5 and got.data == {"a": 1}
    # старші за 7 діб — видаляються
    vclock.advance(8 * 86400)
    await b.purge_old_aux()
    assert await b.count_events() == 0 and await b.count_results() == 0
    await b.close()
