"""SQLite-буфер показань, подій і результатів команд (SPEC §8.3.4, R-19)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from datetime import timedelta
from pathlib import Path
from typing import Any

import aiosqlite

from collector.core.types import CommandResult, PushEvent, Reading
from collector.util.timeutil import Clock, SystemClock, parse_iso, to_iso_z

log = logging.getLogger("collector.buffer")

DROP_BATCH = 10_000
LIMIT_CHECK_S = 60.0
KEEP_AUX_DAYS = 7

_SCHEMA = """
CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, code TEXT, ts TEXT, value REAL, text TEXT, q TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, event_id TEXT UNIQUE, route TEXT, ts TEXT, remote TEXT,
    headers TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, cmd_id INTEGER, state TEXT, ts TEXT, result TEXT,
    error TEXT, data TEXT);
"""


class Buffer:
    def __init__(self, path: str | Path, max_mb: int = 200, clock: Clock | None = None, metrics: Any = None) -> None:
        self.path = Path(path)
        self.max_bytes = int(max_mb) * 1024 * 1024
        self.clock: Clock = clock or SystemClock()
        self.metrics = metrics
        self.dropped_total = 0
        self._db: aiosqlite.Connection | None = None
        self._last_check = float("-inf")

    async def open(self) -> aiosqlite.Connection:
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = aiosqlite.connect(self.path)
            conn.daemon = True  # потік БД не блокує вихід процесу, якщо close() не викликано
            db = await conn
            await db.execute("PRAGMA auto_vacuum=INCREMENTAL")  # діє лише для нового файлу
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.executescript(_SCHEMA)
            await db.commit()
            self._db = db
        return self._db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    # --- readings ---
    async def put_many(self, readings: Iterable[Reading]) -> int:
        rows = [(r.code, to_iso_z(r.ts), r.value, r.text, r.q) for r in readings]
        if not rows:
            return 0
        db = await self.open()
        await db.executemany("INSERT INTO readings(code, ts, value, text, q) VALUES (?,?,?,?,?)", rows)
        await db.commit()
        if self.clock.monotonic() - self._last_check >= LIMIT_CHECK_S:
            await self.enforce_limit()
        return len(rows)

    async def take(self, limit: int) -> list[tuple[int, Reading]]:
        """Найстаріші `limit` показань (FIFO) разом з id; видаляються лише через ack()."""
        db = await self.open()
        async with db.execute("SELECT id, code, ts, value, text, q FROM readings ORDER BY id LIMIT ?", (limit,)) as cur:
            rows = await cur.fetchall()
        return [(r[0], Reading(code=r[1], ts=parse_iso(r[2]), value=r[3], text=r[4], q=r[5])) for r in rows]

    async def ack(self, ids: Iterable[int]) -> None:
        await self._delete("readings", ids)

    async def count(self) -> int:
        return await self._count("readings")

    # --- events ---
    async def put_event(self, ev: PushEvent) -> bool:
        """False, якщо event_id уже є (дублікат)."""
        db = await self.open()
        cur = await db.execute(
            "INSERT OR IGNORE INTO events(event_id, route, ts, remote, headers, payload) VALUES (?,?,?,?,?,?)",
            (ev.event_id, ev.route, to_iso_z(ev.ts), ev.remote, json.dumps(ev.headers), json.dumps(ev.payload)),
        )
        await db.commit()
        return cur.rowcount > 0

    async def take_events(self, limit: int) -> list[tuple[int, PushEvent]]:
        db = await self.open()
        async with db.execute(
            "SELECT id, event_id, route, ts, remote, headers, payload FROM events ORDER BY id LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [
            (
                r[0],
                PushEvent(
                    event_id=r[1],
                    route=r[2],
                    ts=parse_iso(r[3]),
                    remote=r[4],
                    headers=json.loads(r[5]),
                    payload=json.loads(r[6]),
                ),
            )
            for r in rows
        ]

    async def ack_events(self, ids: Iterable[int]) -> None:
        await self._delete("events", ids)

    async def count_events(self) -> int:
        return await self._count("events")

    # --- results ---
    async def put_result(self, res: CommandResult) -> None:
        db = await self.open()
        await db.execute(
            "INSERT INTO results(cmd_id, state, ts, result, error, data) VALUES (?,?,?,?,?,?)",
            (
                res.id,
                res.state,
                to_iso_z(res.ts),
                res.result,
                res.error,
                None if res.data is None else json.dumps(res.data),
            ),
        )
        await db.commit()

    async def take_results(self, limit: int) -> list[tuple[int, CommandResult]]:
        db = await self.open()
        async with db.execute(
            "SELECT id, cmd_id, state, ts, result, error, data FROM results ORDER BY id LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [
            (
                r[0],
                CommandResult(
                    id=r[1],
                    state=r[2],
                    ts=parse_iso(r[3]),
                    result=r[4],
                    error=r[5],
                    data=None if r[6] is None else json.loads(r[6]),
                ),
            )
            for r in rows
        ]

    async def ack_results(self, ids: Iterable[int]) -> None:
        await self._delete("results", ids)

    async def count_results(self) -> int:
        return await self._count("results")

    # --- службове ---
    async def _count(self, table: str) -> int:
        db = await self.open()
        async with db.execute(f"SELECT COUNT(*) FROM {table}") as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def _delete(self, table: str, ids: Iterable[int]) -> None:
        ids = list(ids)
        if not ids:
            return
        db = await self.open()
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            marks = ",".join("?" * len(chunk))
            await db.execute(f"DELETE FROM {table} WHERE id IN ({marks})", chunk)
        await db.commit()

    async def size_bytes(self) -> int:
        db = await self.open()
        async with db.execute("PRAGMA page_count") as cur:
            pages = (await cur.fetchone() or (0,))[0]
        async with db.execute("PRAGMA page_size") as cur:
            psize = (await cur.fetchone() or (4096,))[0]
        return int(pages) * int(psize)

    async def file_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal"):
            p = Path(str(self.path) + suffix)
            if p.exists():
                total += os.path.getsize(p)
        return total

    async def _pragma(self, sql: str) -> None:
        db = await self.open()
        async with db.execute(sql) as cur:
            await cur.fetchall()  # incremental_vacuum виконується покроково при читанні рядків

    async def _shrink(self) -> None:
        await self._pragma("PRAGMA wal_checkpoint(TRUNCATE)")
        await self._pragma("PRAGMA incremental_vacuum")
        await self._pragma("PRAGMA wal_checkpoint(TRUNCATE)")

    async def enforce_limit(self) -> int:
        """Ліміт розміру: видаляє найстаріші readings партіями по 10 000. Повертає кількість видалених."""
        self._last_check = self.clock.monotonic()
        db = await self.open()
        await self._shrink()
        dropped = 0
        while await self.size_bytes() > self.max_bytes:
            cur = await db.execute(
                "DELETE FROM readings WHERE id IN (SELECT id FROM readings ORDER BY id LIMIT ?)", (DROP_BATCH,)
            )
            await db.commit()
            n = cur.rowcount
            if n <= 0:
                break
            dropped += n
            await self._shrink()
        if dropped:
            self.dropped_total += dropped
            if self.metrics is not None:
                self.metrics.buffer_dropped.inc(dropped)
            log.warning("buffer limit exceeded: dropped %d oldest readings", dropped)
        await self.purge_old_aux()
        return dropped

    async def purge_old_aux(self) -> None:
        """events/results лімітом не викидаються, лише старші 7 діб."""
        db = await self.open()
        cutoff = to_iso_z(self.clock.now() - timedelta(days=KEEP_AUX_DAYS))
        await db.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        await db.execute("DELETE FROM results WHERE ts < ?", (cutoff,))
        await db.commit()
