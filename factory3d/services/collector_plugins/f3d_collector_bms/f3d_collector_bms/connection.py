"""TCP-сеанс HelvarNet і пул сеансів (SPEC td_bms §8.3, R-31, R-36)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable

from collector.core.errors import ConnectError

from .protocol import Frame, ProtocolError, key_of, parse_frame, split_stream

log = logging.getLogger("collector.plugin.helvarnet.connection")


class ConnectionClosedError(Exception):
    """Сокет закрито (роутером або нами) під час очікування відповіді."""


class HelvarConnection:
    """Один `asyncio.open_connection`; читач розбирає потік, запити серіалізуються й обмежуються токен-бакетом."""

    def __init__(self, host: str, port: int, timeout_s: float = 3.0, rate_per_s: int = 20) -> None:
        self.host = host
        self.port = port
        self.timeout_s = timeout_s
        self.rate_per_s = max(1, int(rate_per_s))
        self.opens = 0
        self.protocol_errors = 0
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._open_lock = asyncio.Lock()
        self._pending: tuple[tuple, asyncio.Future, bool] | None = None
        self._partial: dict[tuple, str] = {}
        self._listeners: list[Callable[[Frame], None]] = []
        self._tokens = float(self.rate_per_s)
        self._refilled: float | None = None

    # --- сеанс ---------------------------------------------------------------------------------
    @property
    def alive(self) -> bool:
        return self._writer is not None and self._task is not None and not self._task.done()

    async def ensure_open(self) -> None:
        """Відкриває сокет, якщо його немає (слухачі й бакет зберігаються між перепідключеннями)."""
        async with self._open_lock:
            if self.alive:
                return
            await self._teardown()
            try:
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), self.timeout_s
                )
            except (OSError, TimeoutError) as exc:
                self._reader = self._writer = None
                raise ConnectError(f"{type(exc).__name__}: {exc}"[:200]) from exc
            self.opens += 1
            self._partial.clear()
            self._task = asyncio.create_task(self._read_loop(self._reader))

    async def close(self) -> None:
        async with self._open_lock:
            await self._teardown()

    async def _teardown(self) -> None:
        task, writer = self._task, self._writer
        self._task = self._writer = self._reader = None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if writer is not None:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()
        self._fail_pending()

    def _fail_pending(self) -> None:
        pending, self._pending = self._pending, None
        if pending and not pending[1].done():
            pending[1].set_exception(ConnectionClosedError("connection closed"))

    # --- читач ---------------------------------------------------------------------------------
    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        buffer = b""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                buffer += data
                try:
                    frames, buffer = split_stream(buffer)
                except ProtocolError:
                    self.protocol_errors += 1
                    log.warning("helvarnet %s:%s: frame too long", self.host, self.port)
                    buffer = b""
                    continue
                for text in frames:
                    log.debug("<- %s", text)
                    self._dispatch(text)
        except (OSError, asyncio.IncompleteReadError):
            pass
        finally:
            self._writer_closed(reader)

    def _writer_closed(self, reader: asyncio.StreamReader) -> None:
        if self._reader is reader:
            self._fail_pending()
            writer = self._writer
            self._writer = None
            if writer is not None:
                with contextlib.suppress(Exception):
                    writer.close()

    def _dispatch(self, text: str) -> None:
        try:
            frame = parse_frame(text)
        except ProtocolError:
            self.protocol_errors += 1
            log.debug("bad frame %r", text[:80])
            return
        key = key_of(frame)
        if frame.kind == "partial":
            self._partial[key] = self._partial.get(key, "") + (frame.answer or "")
            return
        if frame.kind == "reply" and key in self._partial:
            frame.answer = self._partial.pop(key) + (frame.answer or "")
        if frame.kind == "push":
            for fn in list(self._listeners):
                try:
                    fn(frame)
                except Exception:  # noqa: BLE001 - слухач не повинен ламати читач
                    log.exception("push listener failed")
        pending = self._pending
        if pending is None or pending[1].done() or pending[0] != key:
            return
        if frame.kind == "push" and not pending[2]:
            return
        pending[1].set_result(frame)

    def add_push_listener(self, fn: Callable[[Frame], None]) -> None:
        if fn not in self._listeners:
            self._listeners.append(fn)

    def remove_push_listener(self, fn: Callable[[Frame], None]) -> None:
        if fn in self._listeners:
            self._listeners.remove(fn)

    # --- запити --------------------------------------------------------------------------------
    async def _take_token(self) -> None:
        cap = float(self.rate_per_s)
        while True:
            now = time.monotonic()
            if self._refilled is None:
                self._refilled = now
            self._tokens = min(cap, self._tokens + (now - self._refilled) * self.rate_per_s)
            self._refilled = now
            if self._tokens >= 1.0 - 1e-9:
                self._tokens -= 1.0
                return
            await asyncio.sleep((1.0 - self._tokens) / self.rate_per_s)

    async def request(self, text: str, key: tuple, timeout: float | None = None, accept_push: bool = False) -> Frame:
        """Надсилає кадр і чекає відповідь з тим самим ключем; `TimeoutError`, якщо відповіді немає."""
        timeout = self.timeout_s if timeout is None else timeout
        async with self._lock:
            writer = self._writer
            if not self.alive or writer is None:
                raise ConnectionClosedError("not connected")
            await self._take_token()
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self._pending = (key, fut, accept_push)
            try:
                log.debug("-> %s", text)
                writer.write(text.encode("latin-1"))
                await writer.drain()
                return await asyncio.wait_for(fut, timeout)  # type: ignore[no-any-return]
            except TimeoutError:  # TimeoutError — підклас OSError
                raise
            except OSError as exc:
                raise ConnectionClosedError(str(exc)) from exc
            finally:
                self._pending = None


class ConnectionPool:
    """`{(host, port): HelvarConnection}` з лічильником джерел; сеанс спільний для HN-LP-1…3 (A-03)."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, int], list] = {}

    def acquire(self, host: str, port: int, protocol: str = "tcp", timeout_s: float = 3.0, rate_per_s: int = 20):
        if protocol != "tcp":
            raise ConnectError("udp not supported")
        item = self._items.get((host, port))
        if item is None:
            item = self._items[(host, port)] = [HelvarConnection(host, port, timeout_s, rate_per_s), 0]
        item[1] += 1
        return item[0]

    async def release(self, host: str, port: int) -> None:
        item = self._items.get((host, port))
        if item is None:
            return
        item[1] -= 1
        if item[1] <= 0:
            del self._items[(host, port)]
            await item[0].close()

    def count(self, host: str, port: int) -> int:
        item = self._items.get((host, port))
        return item[1] if item else 0

    def reset(self) -> None:
        self._items.clear()


POOL = ConnectionPool()
