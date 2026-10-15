"""Фейковий роутер HelvarNet (SPEC factory3d_bms §8.8): asyncio TCP-сервер на вільному порту."""

from __future__ import annotations

import asyncio
import contextlib
from collections import Counter

from f3d_collector_bms.protocol import ProtocolError, parse_frame, split_stream

PARTIAL_CHUNK = 40


def _range(prefix: str, first: int, last: int) -> list[str]:
    return [f"{prefix}.{d}" for d in range(first, last + 1)]


def default_routers() -> dict[int, dict]:
    """Склад груп за Додатком A.1 (скорочено): LP-2 G:12 `@1.2.1.1-27`, G:19, G:16 (91 адреса)."""
    return {
        1: {"groups": {1: _range("@1.1.1", 1, 4)}},
        2: {
            "groups": {
                12: _range("@1.2.1", 1, 27),
                19: _range("@1.2.1", 28, 30),
                16: _range("@1.2.3", 1, 64) + _range("@1.2.4", 1, 27),
            }
        },
        3: {"groups": {21: _range("@1.3.1", 1, 4)}},
    }


class FakeHelvarRouter:
    def __init__(
        self,
        routers: dict[int, dict] | None = None,
        version: int = 2,
        push: bool = True,
        latency_ms: float = 0,
        ack: bool = True,
        partial: bool = False,
        delay_s: float = 0.0,
        drop_after: int | None = None,
        watts: int = 126,
    ) -> None:
        self.routers = routers if routers is not None else default_routers()
        self.version = version
        self.push = push
        self.latency_ms = latency_ms
        self.ack = ack
        self.partial = partial
        self.delay_s = delay_s
        self.drop_after = drop_after
        self.watts = watts
        self.groups: dict[int, list[str]] = {}
        for router in self.routers.values():
            self.groups.update(router.get("groups", {}))
        self.devices = {a for members in self.groups.values() for a in members}
        self.levels: dict[str, int] = {}
        self.states: dict[str, int] = {}
        self.scenes: dict[int, int] = {}
        self.error_codes: dict[tuple, int] = {}
        self.received: list[str] = []
        self.queries: Counter[int] = Counter()
        self.connections = 0
        self.frames_sent = 0
        self.port = 0
        self._drop_done = False
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self._tasks: set[asyncio.Task] = set()

    # --- управління станом ------------------------------------------------------------------
    def fail(self, cmd: int, key=None, code: int = 11) -> None:
        """Відповідати `!…=<code>#` на запит cmd з ключем (група або адреса); key=None — на будь-який."""
        self.error_codes[(cmd, key)] = code

    def set_level(self, group: int, level: int) -> None:
        for addr in self.groups[group]:
            self.levels[addr] = level

    def level_of(self, addr: str) -> int:
        return self.levels.get(addr, 100)

    async def send_push(self, text: str) -> None:
        for writer in list(self._writers):
            with contextlib.suppress(Exception):
                writer.write(text.encode("latin-1"))
                await writer.drain()

    # --- життєвий цикл ----------------------------------------------------------------------
    async def start(self) -> FakeHelvarRouter:
        self._server = await asyncio.start_server(self._client, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
        for task in list(self._tasks):
            task.cancel()
        for writer in list(self._writers):
            with contextlib.suppress(Exception):
                writer.close()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._server is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), 2)
            self._server = None

    # --- обмін ------------------------------------------------------------------------------
    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        self._writers.add(writer)
        task = asyncio.current_task()
        if task is not None:
            self._tasks.add(task)
        sent = [0]
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
                    buffer = b""
                    continue
                for text in frames:
                    if not await self._handle(text, writer, sent):
                        return
        except (asyncio.CancelledError, ConnectionError):
            pass
        finally:
            self._writers.discard(writer)
            if task is not None:
                self._tasks.discard(task)
            with contextlib.suppress(Exception):
                writer.close()

    async def _send(self, writer: asyncio.StreamWriter, text: str, sent: list[int]) -> bool:
        writer.write(text.encode("latin-1"))
        await writer.drain()
        sent[0] += 1
        self.frames_sent += 1
        if self.drop_after is not None and not self._drop_done and sent[0] >= self.drop_after:
            self._drop_done = True
            writer.close()
            return False
        return True

    async def _handle(self, text: str, writer: asyncio.StreamWriter, sent: list[int]) -> bool:
        try:
            req = parse_frame(text)
        except ProtocolError:
            return True
        self.received.append(text)
        self.queries[req.cmd] += 1
        if self.latency_ms or self.delay_s:
            await asyncio.sleep(self.latency_ms / 1000 + self.delay_s)
        body = text[1:-1]
        v = req.version or 2
        group = int(req.params["G"]) if "G" in req.params else None
        key = group if group is not None else req.address

        def error(code: int) -> str:
            return f"!{body}={code}#"

        if v > self.version:
            return await self._send(writer, error(18), sent)
        code = self.error_codes.get((req.cmd, key)) or self.error_codes.get((req.cmd, None))
        if code:
            return await self._send(writer, error(code), sent)
        cmd = req.cmd
        if cmd in (13, 11):
            return await self._write_cmd(req, body, v, group, writer, sent)
        answer: str | None = None
        if cmd == 101:
            answer = "1"
        elif cmd == 102:
            answer = ",".join(str(r) for r in sorted(self.routers))
        elif cmd in (103, 165):
            answer = "0"
        elif cmd == 191:
            answer = str(self.version)
        elif cmd in (104, 110, 152):
            if req.address not in self.devices:
                return await self._send(writer, error(11), sent)
            if cmd == 104:
                answer = "1537"
            elif cmd == 110:
                answer = str(self.states.get(req.address, 0))
            else:
                answer = str(self.levels.get(req.address, 100))
        elif cmd in (109, 161, 164):
            if group not in self.groups:
                return await self._send(writer, error(1), sent)
            if cmd == 109:
                answer = str(self.scenes.get(group, 0))
            elif cmd == 161:
                total = 0.0
                for addr in self.groups[group]:
                    raw = self.levels.get(addr, 100)
                    total += 0 if raw & 0x80000000 else self.watts * min(100, raw & 0x7F) / 100
                answer = str(round(total))
            else:
                answer = ",".join(self.groups[group])
        if answer is None:
            return await self._send(writer, error(15), sent)
        if cmd == 164 and self.partial and len(answer) > PARTIAL_CHUNK:
            chunks = [answer[i : i + PARTIAL_CHUNK] for i in range(0, len(answer), PARTIAL_CHUNK)]
            for chunk in chunks[:-1]:
                if not await self._send(writer, f"?{body}={chunk}$", sent):
                    return False
            answer = chunks[-1]
        return await self._send(writer, f"?{body}={answer}#", sent)

    async def _write_cmd(self, req, body: str, v: int, group: int | None, writer, sent: list[int]) -> bool:
        if group not in self.groups:
            return await self._send(writer, f"!{body}=1#", sent)
        fade = req.params.get("F", "0")
        if req.cmd == 13:
            level = int(req.params.get("L", "0"))
            self.set_level(group, level)
            push = f">V:{v},C:13,G:{group},L:{level},F:{fade}#"
        else:
            scene = int(req.params.get("S", "0"))
            self.scenes[group] = scene
            push = f">V:{v},C:11,G:{group},B:{req.params.get('B', '1')},S:{scene},F:{fade}#"
        if self.ack and req.params.get("A") == "1" and not await self._send(writer, f"!{body}=0#", sent):
            return False
        if self.push:
            await self.send_push(push)
        return True
