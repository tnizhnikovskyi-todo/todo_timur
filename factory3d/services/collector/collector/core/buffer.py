"""SQLite-буфер показань, подій і результатів команд (SPEC §8.3.4, R-19).

Модель доступу (інцидент стенда: «database table is locked», буфер 209 МБ / 3 млн рядків, `/health` брехав):

* одне з'єднання aiosqlite (один потік БД), а кожна операція виконується повністю — запит, читання курсора, commit —
  під `asyncio.Lock`. Так задачі (опитування, Emitter, Pusher, обслуговування, HTTP push) ніколи не переплітають
  курсори й транзакції на спільному з'єднанні; саме переплетення `take()` (відкритий SELECT) з
  `PRAGMA incremental_vacuum` давало SQLITE_LOCKED «database table is locked»;
* WAL + `busy_timeout` — для інших процесів (CLI `test-source`/`drain-buffer` поруч із демоном); тимчасові
  «locked/busy» повторюються з наростаючою паузою, не тримаючи Lock під час очікування;
* обрізання за лімітом — короткими транзакціями (≤ `DROP_BATCH` рядків за раз, Lock відпускається між партіями),
  до 90 % ліміту, за «корисним» обсягом (сторінки без вільного списку), а не за розміром файлу;
  вільні сторінки віддаються ОС порціями `incremental_vacuum(N)`;
* лічильник рядків `readings` ведеться в пам'яті (O(1) для `/health`, метрик і статусу); точний `recount()` —
  при відкритті та в обслуговуванні.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import sqlite3
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import aiosqlite

from collector.core.types import CommandResult, PushEvent, Reading
from collector.util.timeutil import Clock, SystemClock, parse_iso, to_iso_z

log = logging.getLogger("collector.buffer")

T = TypeVar("T")

DROP_BATCH = 10_000  # максимум рядків в одній транзакції видалення
MIN_DROP = 100
TRIM_TARGET = 0.9  # обрізання до 90 % ліміту (гістерезис: не обрізати щохвилини)
KEEP_AUX_DAYS = 7
BUSY_TIMEOUT_MS = 5_000
BUSY_RETRIES = 5
BUSY_RETRY_S = 0.05
VACUUM_PAGES = 1_000  # сторінок за один крок incremental_vacuum
MAX_SHRINK_STEPS = 2_000
WAL_LIMIT_BYTES = 64 * 1024 * 1024

_SCHEMA = """
CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY, code TEXT, ts TEXT, value REAL, text TEXT, q TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, event_id TEXT UNIQUE, route TEXT, ts TEXT, remote TEXT,
    headers TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, cmd_id INTEGER, state TEXT, ts TEXT, result TEXT,
    error TEXT, data TEXT);
"""


def _transient(exc: sqlite3.Error) -> bool:
    """SQLITE_BUSY «database is locked» і SQLITE_LOCKED «database table is locked» — тимчасові."""
    msg = str(exc).lower()
    return "locked" in msg or "busy" in msg


async def _identity(db: aiosqlite.Connection) -> aiosqlite.Connection:
    return db


class Buffer:
    def __init__(self, path: str | Path, max_mb: int = 200, clock: Clock | None = None, metrics: Any = None) -> None:
        self.path = Path(path)
        self.max_bytes = int(max_mb) * 1024 * 1024
        self.clock: Clock = clock or SystemClock()
        self.metrics = metrics
        self.dropped_total = 0
        self.busy_retries = 0
        self._db: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()
        self._rows = 0  # лічильник readings (див. docstring модуля)

    # --- з'єднання й серіалізація ---
    async def _connect(self) -> aiosqlite.Connection:
        """Відкриває БД; викликається лише під `_lock`."""
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = aiosqlite.connect(self.path, timeout=BUSY_TIMEOUT_MS / 1000)
            conn.daemon = True  # потік БД не блокує вихід процесу, якщо close() не викликано
            db = await conn
            try:
                await db.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
                await db.execute("PRAGMA auto_vacuum=INCREMENTAL")  # діє лише для нового файлу
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA synchronous=NORMAL")
                await db.execute(f"PRAGMA journal_size_limit={WAL_LIMIT_BYTES}")
                await db.executescript(_SCHEMA)
                await db.commit()
                async with db.execute("SELECT COUNT(*) FROM readings") as cur:
                    row = await cur.fetchone()
                self._rows = int(row[0]) if row else 0
            except BaseException:
                await db.close()
                raise
            self._db = db
        return self._db

    async def _run(self, fn: Callable[[aiosqlite.Connection], Awaitable[T]]) -> T:
        """Виконує `fn(db)` під Lock; транзакція при помилці відкочується; тимчасове locked/busy — повтор."""
        delay = BUSY_RETRY_S
        for attempt in range(BUSY_RETRIES):
            try:
                async with self._lock:
                    db = await self._connect()
                    try:
                        return await fn(db)
                    except BaseException:
                        with contextlib.suppress(Exception):
                            await db.rollback()
                        raise
            except sqlite3.OperationalError as exc:
                if attempt == BUSY_RETRIES - 1 or not _transient(exc):
                    raise
                self.busy_retries += 1
                log.warning("buffer busy (%s), retry %d/%d", exc, attempt + 1, BUSY_RETRIES - 1)
                await asyncio.sleep(delay)  # без Lock: інші задачі не чекають на нас
                delay = min(delay * 2, 1.0)
        raise AssertionError("unreachable")

    async def open(self) -> aiosqlite.Connection:
        return await self._run(_identity)

    async def close(self) -> None:
        async with self._lock:
            if self._db is not None:
                await self._db.close()
                self._db = None

    # --- readings ---
    @property
    def rows(self) -> int:
        """Кількість readings у буфері без звернення до БД (для /health, метрик, статусу)."""
        return self._rows

    async def put_many(self, readings: Iterable[Reading]) -> int:
        """Один INSERT-пакет = одна коротка транзакція. Ліміт розміру тут не перевіряється (це `enforce_limit`
        з задачі обслуговування): обрізання не повинне гальмувати цикл опитування."""
        rows = [(r.code, to_iso_z(r.ts), r.value, r.text, r.q) for r in readings]
        if not rows:
            return 0

        async def op(db: aiosqlite.Connection) -> None:
            await db.executemany("INSERT INTO readings(code, ts, value, text, q) VALUES (?,?,?,?,?)", rows)
            await db.commit()
            self._rows += len(rows)

        await self._run(op)
        return len(rows)

    async def take(self, limit: int, newest: bool = False) -> list[tuple[int, Reading]]:
        """`limit` показань разом з id (за зростанням id); видаляються лише через ack().

        За замовчуванням найстаріші (FIFO); `newest=True` — найновіші (політика «спершу живі дані», коли відправник
        відстає від опитування; див. `Pusher`)."""
        order = "DESC" if newest else "ASC"

        async def op(db: aiosqlite.Connection) -> list[Any]:
            async with db.execute(
                f"SELECT id, code, ts, value, text, q FROM readings ORDER BY id {order} LIMIT ?", (limit,)
            ) as cur:
                return list(await cur.fetchall())

        rows = await self._run(op)
        if newest:
            rows.reverse()
        return [(r[0], Reading(code=r[1], ts=parse_iso(r[2]), value=r[3], text=r[4], q=r[5])) for r in rows]

    async def oldest_ts(self) -> datetime | None:
        """Мітка часу найстарішого показання (за id) — вік черги відправки."""

        async def op(db: aiosqlite.Connection) -> Any:
            async with db.execute("SELECT ts FROM readings ORDER BY id LIMIT 1") as cur:
                return await cur.fetchone()

        row = await self._run(op)
        return parse_iso(row[0]) if row else None

    async def ack(self, ids: Iterable[int]) -> int:
        """Видаляє рівно ці показання (одна транзакція); повертає кількість видалених."""
        return await self._delete("readings", ids)

    async def count(self) -> int:
        if self._db is None:
            await self.open()
        return self._rows

    async def recount(self) -> int:
        """Точний COUNT(*) і синхронізація лічильника (інший процес міг змінити файл)."""

        async def op(db: aiosqlite.Connection) -> int:
            async with db.execute("SELECT COUNT(*) FROM readings") as cur:
                row = await cur.fetchone()
            self._rows = int(row[0]) if row else 0
            return self._rows

        return await self._run(op)

    # --- events ---
    async def put_event(self, ev: PushEvent) -> bool:
        """False, якщо event_id уже є (дублікат)."""

        async def op(db: aiosqlite.Connection) -> bool:
            cur = await db.execute(
                "INSERT OR IGNORE INTO events(event_id, route, ts, remote, headers, payload) VALUES (?,?,?,?,?,?)",
                (ev.event_id, ev.route, to_iso_z(ev.ts), ev.remote, json.dumps(ev.headers), json.dumps(ev.payload)),
            )
            await db.commit()
            return cur.rowcount > 0

        return await self._run(op)

    async def take_events(self, limit: int) -> list[tuple[int, PushEvent]]:
        rows = await self._select(
            "SELECT id, event_id, route, ts, remote, headers, payload FROM events ORDER BY id LIMIT ?", limit
        )
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
        async def op(db: aiosqlite.Connection) -> None:
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

        await self._run(op)

    async def take_results(self, limit: int) -> list[tuple[int, CommandResult]]:
        rows = await self._select(
            "SELECT id, cmd_id, state, ts, result, error, data FROM results ORDER BY id LIMIT ?", limit
        )
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
    async def _select(self, sql: str, limit: int) -> list[Any]:
        async def op(db: aiosqlite.Connection) -> list[Any]:
            async with db.execute(sql, (limit,)) as cur:
                return list(await cur.fetchall())

        return await self._run(op)

    async def _count(self, table: str) -> int:
        async def op(db: aiosqlite.Connection) -> int:
            async with db.execute(f"SELECT COUNT(*) FROM {table}") as cur:
                row = await cur.fetchone()
            return int(row[0]) if row else 0

        return await self._run(op)

    async def _delete(self, table: str, ids: Iterable[int]) -> int:
        ids = list(ids)
        if not ids:
            return 0

        async def op(db: aiosqlite.Connection) -> int:
            deleted = 0
            for i in range(0, len(ids), 500):
                chunk = ids[i : i + 500]
                marks = ",".join("?" * len(chunk))
                cur = await db.execute(f"DELETE FROM {table} WHERE id IN ({marks})", chunk)
                deleted += max(cur.rowcount, 0)
            await db.commit()  # усі шматки — однією транзакцією: або всі, або жодного
            if table == "readings":
                self._rows = max(0, self._rows - deleted)
            return deleted

        return await self._run(op)

    async def _pragma_int(self, sql: str) -> int:
        async def op(db: aiosqlite.Connection) -> int:
            async with db.execute(sql) as cur:
                row = await cur.fetchone()
            return int(row[0]) if row else 0

        return await self._run(op)

    async def _pragma(self, sql: str) -> None:
        async def op(db: aiosqlite.Connection) -> None:
            async with db.execute(sql) as cur:
                await cur.fetchall()  # incremental_vacuum виконується покроково при читанні рядків

        await self._run(op)

    async def size_bytes(self) -> int:
        """Розмір БД (сторінки файлу з урахуванням вільних)."""
        pages = await self._pragma_int("PRAGMA page_count")
        psize = await self._pragma_int("PRAGMA page_size") or 4096
        return pages * psize

    async def used_bytes(self) -> int:
        """Корисний обсяг: сторінки без вільного списку (саме він порівнюється з лімітом)."""
        pages = await self._pragma_int("PRAGMA page_count")
        free = await self._pragma_int("PRAGMA freelist_count")
        psize = await self._pragma_int("PRAGMA page_size") or 4096
        return max(0, pages - free) * psize

    async def file_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal"):
            p = Path(str(self.path) + suffix)
            if p.exists():
                total += os.path.getsize(p)
        return total

    async def _shrink(self, trimmed: bool = False) -> None:
        """Віддає вільні сторінки ОС порціями (кожна — окрема коротка транзакція) і скидає WAL.

        TRUNCATE-checkpoint чекає на інших власників БД (busy_timeout), тому — лише після обрізання/стиснення;
        зазвичай достатньо PASSIVE (не блокує)."""
        free = await self._pragma_int("PRAGMA freelist_count")
        vacuumed = False
        for _ in range(MAX_SHRINK_STEPS):
            if free <= 0:
                break
            await self._pragma(f"PRAGMA incremental_vacuum({VACUUM_PAGES})")
            left = await self._pragma_int("PRAGMA freelist_count")
            if left >= free:  # файл створено без auto_vacuum: сторінки лише перевикористовуються
                break
            vacuumed = True
            free = left
            await asyncio.sleep(0)
        await self._pragma(f"PRAGMA wal_checkpoint({'TRUNCATE' if trimmed or vacuumed else 'PASSIVE'})")

    async def _delete_oldest(self, n: int) -> int:
        """Видаляє `n` найстаріших readings за rowid однією короткою транзакцією."""

        async def op(db: aiosqlite.Connection) -> int:
            cur = await db.execute(
                "DELETE FROM readings WHERE id <= COALESCE("
                "(SELECT id FROM readings ORDER BY id LIMIT 1 OFFSET ?), (SELECT MAX(id) FROM readings))",
                (n - 1,),
            )
            await db.commit()
            deleted = max(cur.rowcount, 0)
            self._rows = max(0, self._rows - deleted)
            return deleted

        return await self._run(op)

    async def enforce_limit(self) -> int:
        """Ліміт розміру: якщо корисний обсяг > ліміту, видаляє найстаріші readings до 90 % ліміту партіями
        (кожна — окрема коротка транзакція, Lock відпускається між партіями). Повертає кількість видалених."""
        used = await self.used_bytes()
        target = int(self.max_bytes * TRIM_TARGET)
        dropped = 0
        if used > self.max_bytes:
            while used > target and self._rows > 0:
                per_row = max(1.0, used / self._rows)
                n = min(DROP_BATCH, max(MIN_DROP, math.ceil((used - target) / per_row)))
                deleted = await self._delete_oldest(n)
                if deleted <= 0:
                    break
                dropped += deleted
                used = await self.used_bytes()
                await asyncio.sleep(0)
        await self._shrink(trimmed=dropped > 0)
        if dropped:
            self.dropped_total += dropped
            if self.metrics is not None:
                self.metrics.buffer_dropped.inc(dropped)
            log.warning("buffer limit exceeded: dropped %d oldest readings", dropped)
        await self.purge_old_aux()
        return dropped

    async def purge_old_aux(self) -> None:
        """events/results лімітом не викидаються, лише старші 7 діб."""
        cutoff = to_iso_z(self.clock.now() - timedelta(days=KEEP_AUX_DAYS))

        async def op(db: aiosqlite.Connection) -> None:
            await db.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            await db.execute("DELETE FROM results WHERE ts < ?", (cutoff,))
            await db.commit()

        await self._run(op)
