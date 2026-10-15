"""Фейковий сервер MT-SICS для тестів (SPEC §8.7)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable, Iterable


class FakeSicsServer:
    def __init__(
        self,
        weights: list[tuple[str, float, str]] | Callable[[], tuple[str, float, str]],
        unit: str = "kg",
        rate_hz: float = 2.0,
        drop_after: int | None = None,
        reply_delay_s: float = 0.0,
        reset_reply: str = 'I4 A "FAKE-0001"',
        support_reset: bool = True,
        es_on: Iterable[str] = (),
    ) -> None:
        self.weights = weights
        self.unit = unit
        self.rate_hz = rate_hz
        self.drop_after = drop_after
        self.reply_delay_s = reply_delay_s
        self.reset_reply = reset_reply
        self.support_reset = support_reset
        self.es_on = set(es_on)  # команди, на які сервер відповідає ES (напр. TAC на емуляторі)
        self.received: list[str] = []
        self.port = 0
        self._index = 0
        self._frames_sent = 0
        self._server: asyncio.Server | None = None
        self._streams: set[asyncio.Task] = set()
        self._handlers: set[asyncio.Task] = set()

    async def start(self) -> FakeSicsServer:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        for task in list(self._streams) + list(self._handlers):
            task.cancel()
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()

    async def __aenter__(self) -> FakeSicsServer:
        return await self.start()

    async def __aexit__(self, *exc: object) -> None:
        await self.stop()

    def _next(self) -> tuple[str, float, str]:
        if callable(self.weights):
            return self.weights()
        item = self.weights[min(self._index, len(self.weights) - 1)]
        self._index += 1
        return item

    def _frame(self) -> str:
        status, value, unit = self._next()
        if status in ("I", "+", "-"):
            return f"S {status}\r\n"
        return f"S {status} {value:>10.0f} {unit or self.unit}\r\n"

    async def _reply(self, writer: asyncio.StreamWriter, text: str) -> None:
        if self.reply_delay_s:
            await asyncio.sleep(self.reply_delay_s)
        writer.write(text.encode("ascii"))
        await writer.drain()

    async def _stream(self, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                if self.drop_after is not None and self._frames_sent >= self.drop_after:
                    writer.close()
                    return
                writer.write(self._frame().encode("ascii"))
                self._frames_sent += 1
                await writer.drain()
                await asyncio.sleep(1.0 / self.rate_hz)
        except (asyncio.CancelledError, ConnectionError):
            return

    def _stop_streams(self) -> None:
        for task in list(self._streams):
            task.cancel()
        self._streams.clear()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        me = asyncio.current_task()
        if me is not None:
            self._handlers.add(me)
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                cmd = raw.decode("ascii", errors="replace").strip()
                self.received.append(cmd)
                self._stop_streams()  # будь-яка команда скасовує SIR
                if cmd in self.es_on:
                    await self._reply(writer, "ES\r\n")
                elif cmd == "SI":
                    await self._reply(writer, self._frame())
                    self._frames_sent += 1
                elif cmd == "SIR":
                    task = asyncio.create_task(self._stream(writer))
                    self._streams.add(task)
                    task.add_done_callback(self._streams.discard)
                elif cmd == "Z":
                    await self._reply(writer, "Z A\r\n")
                elif cmd == "T":
                    status, value, _unit = self._next() if not callable(self.weights) else self.weights()
                    await self._reply(writer, f"T S {value:>10.0f} kg\r\n")
                elif cmd == "TAC":
                    await self._reply(writer, "TAC A\r\n")
                elif cmd.startswith("TA"):
                    await self._reply(writer, "TA A          0 kg\r\n")
                elif cmd == "@":
                    await self._reply(writer, (self.reset_reply if self.support_reset else "ES") + "\r\n")
                else:
                    await self._reply(writer, "ES\r\n")
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            self._handlers.discard(me)
            self._stop_streams()
            with contextlib.suppress(Exception):
                writer.close()
