"""Плагін `sics`: автоваги за MT-SICS (SPEC td_yard §8, R-13, R-14)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from typing import Any, ClassVar

from collector.core.errors import ConnectError, NotSupported, PollError, WriteError
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins.base import PluginContext, SourcePlugin

try:  # jsonschema — лише у test/colector-образі; без нього — ручна перевірка
    from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    Draft202012Validator = None

NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
ERRORS = {"ES", "ET", "EL"}
STATUSES = {"A", "I", "+", "-", "–", "L"}
UNIT_TO_KG = {"kg": 1.0, "g": 0.001, "t": 1000.0, "lb": 0.45359237}
STATUS_TEXT = {"I": "busy", "+": "overload", "-": "underload", "–": "underload", "L": "logic"}
WRITE_CMDS = ("Z", "T", "TAC")
WARN_EVERY_S = 60.0


def _load(name: str) -> dict:
    text = resources.files("f3d_collector_yard").joinpath("schemas", name).read_text(encoding="utf-8")
    return json.loads(text)  # type: ignore[no-any-return]


@dataclass
class Frame:
    kind: str  # weight | status | error | empty
    id: str = ""
    status: str = ""
    value: float | None = None
    unit: str = ""
    text: str = ""
    raw: str = ""


def parse_line(raw: bytes | str, default_unit: str = "kg") -> Frame:
    """R-13: розбір одного рядка відповіді SICS."""
    line = raw.decode("ascii", errors="replace") if isinstance(raw, bytes) else raw
    line = line.strip("\r\n ")
    if not line:
        return Frame("empty", raw=line)
    tokens = line.split()
    if len(tokens) == 1 and tokens[0] in ERRORS:
        return Frame("error", id=tokens[0], raw=line)
    if len(tokens) >= 3 and tokens[1] in ("S", "D") and NUMBER.match(tokens[2]):
        unit = tokens[3] if len(tokens) >= 4 else default_unit
        return Frame("weight", tokens[0], tokens[1], float(tokens[2]), unit, raw=line)
    if len(tokens) >= 2 and tokens[1] in STATUSES:
        return Frame("status", tokens[0], tokens[1], text=" ".join(tokens[2:]).strip('"'), raw=line)
    return Frame("error", id="?", raw=line)


def to_kg(value: float, unit: str) -> float | None:
    """Значення в кг; невідома одиниця -> None."""
    factor = UNIT_TO_KG.get((unit or "").lower())
    return None if factor is None else value * factor


def frame_readings(frame: Frame, signals, ts: datetime) -> list[Reading]:
    """Показання сигналів із кадру `S` (таблиця §8.5)."""
    out: list[Reading] = []
    for sg in signals:
        addr = sg.address or {}
        field = addr.get("field")
        if field not in ("weight", "stable"):
            continue
        value: float | None = None
        q, text = "good", None
        if frame.kind == "weight":
            if field == "stable":
                value = 1.0 if frame.status == "S" else 0.0
            else:
                kg = to_kg(frame.value, frame.unit)  # type: ignore[arg-type]
                if kg is None:
                    q, text = "bad", "unit %s" % frame.unit
                else:
                    value = kg * float(addr.get("scale", 1)) + float(addr.get("offset", 0))
        else:
            q, text = "bad", STATUS_TEXT.get(frame.status, "status %s" % frame.status)
        out.append(Reading(sg.code, ts, value, text, q))
    return out


def _manual_errors(schema: dict, inst: Any, prefix: str) -> list[str]:
    """Запасна перевірка без jsonschema: обов'язкові ключі, зайві ключі, enum, межі."""
    if not isinstance(inst, dict):
        return [prefix + "(root): має бути об'єктом"]
    errs = [prefix + "%s: обов'язковий ключ" % k for k in schema.get("required", []) if k not in inst]
    props = schema.get("properties", {})
    for key, val in inst.items():
        spec = props.get(key)
        if spec is None:
            errs.append(prefix + "%s: невідомий ключ" % key)
            continue
        if "enum" in spec and val not in spec["enum"]:
            errs.append(prefix + "%s: значення поза переліком" % key)
        if "not" in spec and val == spec["not"].get("const") and not isinstance(val, bool):
            errs.append(prefix + "%s: недопустиме значення" % key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            if "minimum" in spec and val < spec["minimum"]:
                errs.append(prefix + "%s: менше за мінімум" % key)
            if "maximum" in spec and val > spec["maximum"]:
                errs.append(prefix + "%s: більше за максимум" % key)
        if spec.get("type") == "object":
            errs += _manual_errors(spec, val, prefix + key + ".")
    return errs


def _schema_errors(schema: dict, inst: Any, prefix: str) -> list[str]:
    if Draft202012Validator is None:
        return _manual_errors(schema, inst, prefix)
    validator = Draft202012Validator(schema)
    out = []
    for err in sorted(validator.iter_errors(inst), key=lambda e: list(map(str, e.path))):
        out.append("%s%s: %s" % (prefix, ".".join(str(p) for p in err.path) or "(root)", err.message[:200]))
    return out


class SicsPlugin(SourcePlugin):
    type: ClassVar[str] = "sics"
    version: ClassVar[str] = "0.1.0"
    push_mode: ClassVar[bool] = False
    address_schema: ClassVar[dict] = _load("address.sics.json")
    params_schema: ClassVar[dict] = _load("params.sics.json")

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        super().__init__(source, ctx)
        p = source.params or {}
        self.host: str = p.get("host", "")
        self.port: int = int(p.get("port", 4001))
        self.mode: str = p.get("mode", "stream")
        self.period_s: float = float(p.get("period_s", 1))
        self.timeout_s: float = float(p.get("timeout_s", 5))
        self.unit: str = p.get("unit", "kg")
        self.reset_on_connect: bool = bool(p.get("reset_on_connect", True))
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._stream_task: asyncio.Task | None = None
        self._stream_error: str | None = None
        self._latest: Frame | None = None
        self._latest_ts: datetime | None = None
        self._returned_ts: datetime | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._device: str | None = None
        self._connected = False
        self._connects = 0
        self._last_ok: datetime | None = None
        self._warned: dict[str, float] = {}
        self.frames = 0
        self.errors = 0
        self.reconnects = 0
        self.consecutive_errors = 0

    # ------------------------------------------------------------------ валідація
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        errs = _schema_errors(cls.params_schema, source.params, "params.")
        for sg in source.signals:
            if not sg.address:
                continue
            errs += ["%s: %s" % (sg.code, e) for e in _schema_errors(cls.address_schema, sg.address, "")]
        return errs

    # ------------------------------------------------------------------ службове
    def _inc(self, name: str, **labels: str) -> None:
        metric = getattr(self.ctx.metrics, name, None)
        if metric is not None:
            with contextlib.suppress(Exception):
                metric.labels(type="sics", source=self.source.code, **labels).inc()

    def _warn(self, kind: str, msg: str) -> None:
        now = time.monotonic()
        if now - self._warned.get(kind, -WARN_EVERY_S) >= WARN_EVERY_S:
            self._warned[kind] = now
            self.ctx.log.warning(msg)

    def _count_error(self, kind: str) -> None:
        self.errors += 1
        self._inc("collector_sics_errors_total", kind=kind)

    async def _send(self, cmd: str) -> None:
        assert self._writer is not None
        self._writer.write(cmd.encode("ascii") + b"\r\n")
        await self._writer.drain()

    async def _readline(self, timeout: float) -> bytes:
        assert self._reader is not None
        line = await asyncio.wait_for(self._reader.readline(), timeout)
        if not line:
            raise ConnectionError("з'єднання закрито пристроєм")
        return line

    def _close_transport(self) -> None:
        self._connected = False
        writer, self._writer = self._writer, None
        if writer is not None:
            with contextlib.suppress(Exception):
                writer.close()

    # ------------------------------------------------------------------ з'єднання
    async def connect(self) -> None:
        self.ctx.allowlist(self.host)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout_s
            )
        except (OSError, TimeoutError) as exc:
            raise ConnectError("SICS %s:%s: немає з'єднання" % (self.host, self.port)) from exc
        self._connected = True
        self._stream_error = None
        self._latest = self._latest_ts = self._returned_ts = None
        self._pending.clear()
        try:
            if self.reset_on_connect:
                await self._reset()
            if self.mode == "stream":
                await self._send("SIR")
                self._stream_task = asyncio.create_task(self._stream_loop())
        except (OSError, ConnectionError) as exc:
            self._close_transport()
            raise ConnectError("SICS %s:%s: з'єднання перервано" % (self.host, self.port)) from exc
        if self._connects:
            self.reconnects += 1
            self._inc("collector_sics_reconnects_total")
        self._connects += 1
        self.ctx.log.info("SICS %s:%s: підключено, пристрій %s", self.host, self.port, self._device)

    async def _reset(self) -> None:
        """`@`: читаємо до `I4 …` або `ES` не довше timeout_s (діалект без `@` — не помилка)."""
        await self._send("@")
        deadline = time.monotonic() + self.timeout_s
        try:
            while (remaining := deadline - time.monotonic()) > 0:
                frame = parse_line(await self._readline(remaining), self.unit)
                if frame.id == "I4":
                    self._device = frame.text
                    return
                if frame.id == "ES":
                    return
        except TimeoutError:
            self._warn("reset", "SICS: немає відповіді на @")

    async def disconnect(self) -> None:
        task, self._stream_task = self._stream_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        writer = self._writer
        self._close_transport()
        if writer is not None:
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    # ------------------------------------------------------------------ потік SIR
    async def _stream_loop(self) -> None:
        try:
            while True:
                line = await self._readline(self.timeout_s)
                frame = parse_line(line, self.unit)
                if frame.kind == "empty":
                    continue
                if frame.id == "S" and frame.kind in ("weight", "status"):
                    self._latest, self._latest_ts = frame, datetime.now(UTC)
                    self.frames += 1
                    self._inc("collector_sics_frames_total")
                elif frame.kind == "error" and frame.id == "?":
                    self._count_error("frame")
                    self._warn("frame", "SICS: нерозпізнаний рядок %r" % frame.raw[:60])
                else:
                    self._resolve(frame)
        except TimeoutError:
            self._stream_error = "SICS: немає кадрів %s с" % self.timeout_s
        except (OSError, ConnectionError):
            self._stream_error = "SICS: з'єднання закрито пристроєм"
        except asyncio.CancelledError:
            raise
        self._warn("stream", self._stream_error or "SICS: потік перервано")
        self._close_transport()

    def _resolve(self, frame: Frame) -> None:
        if frame.kind == "error":
            futures = [f for f in self._pending.values() if not f.done()]
            fut = futures[0] if futures else None
        else:
            fut = self._pending.get(frame.id)
        if fut is not None and not fut.done():
            fut.set_result(frame)

    # ------------------------------------------------------------------ опитування
    async def poll(self, signals: Any) -> list[Reading]:
        try:
            if self.mode == "stream":
                frame, ts = self._poll_stream()
            else:
                frame, ts = await self._poll_si()
        except PollError:
            self.consecutive_errors += 1
            self._count_error("poll")
            raise
        self.consecutive_errors = 0
        if frame is None:
            return []
        return frame_readings(frame, signals, ts)

    def _poll_stream(self) -> tuple[Frame | None, datetime]:
        if self._stream_error:
            raise PollError(self._stream_error)
        if not self._connected:
            raise PollError("SICS: немає з'єднання")
        now = datetime.now(UTC)
        if self._latest_ts is None or (now - self._latest_ts).total_seconds() > self.timeout_s:
            raise PollError("SICS: немає кадрів %s с" % self.timeout_s)
        if self._latest_ts == self._returned_ts:
            return None, now
        self._returned_ts = self._latest_ts
        self._last_ok = now
        return self._latest, self._latest_ts

    async def _poll_si(self) -> tuple[Frame | None, datetime]:
        if not self._connected:
            raise PollError("SICS: немає з'єднання")
        loop = asyncio.get_running_loop()
        async with self._lock:
            deadline = loop.time() + self.timeout_s
            try:
                await self._send("SI")
                for _ in range(3):
                    frame = parse_line(await self._readline(max(deadline - loop.time(), 0.001)), self.unit)
                    if frame.kind == "error" and frame.id in ERRORS:
                        raise PollError("SICS: помилка %s на SI" % frame.id)
                    if frame.id == "S" and frame.kind in ("weight", "status"):
                        now = datetime.now(UTC)
                        self.frames += 1
                        self._last_ok = now
                        self._inc("collector_sics_frames_total")
                        return frame, now
            except TimeoutError as exc:
                self._close_transport()
                raise PollError("SICS: немає відповіді на SI за %s с" % self.timeout_s) from exc
            except (OSError, ConnectionError) as exc:
                self._close_transport()
                raise PollError("SICS: з'єднання втрачено") from exc
            raise PollError("SICS: немає кадру S у відповіді на SI")

    # ------------------------------------------------------------------ запис
    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        cmd = ((signal.address or {}).get("write") or {}).get("cmd")
        if cmd not in WRITE_CMDS:
            raise NotSupported("SICS: запис дозволено лише Z/T/TAC")
        if not getattr(self.ctx.settings, "write_enabled", False):
            raise WriteError("запис вимкнено")
        if not self._connected:
            raise WriteError("SICS: немає з'єднання")
        stream = self.mode == "stream"
        async with self._lock:
            try:
                if stream:
                    fut = asyncio.get_running_loop().create_future()
                    self._pending[cmd] = fut
                await self._send(cmd)
                frame = await (self._await_stream(fut) if stream else self._await_reply(cmd))
            except TimeoutError as exc:
                raise WriteError("SICS: немає відповіді на %s за %s с" % (cmd, self.timeout_s)) from exc
            except (OSError, ConnectionError) as exc:
                self._close_transport()
                raise WriteError("SICS: з'єднання втрачено") from exc
            finally:
                self._pending.pop(cmd, None)
                if stream and self._connected:
                    with contextlib.suppress(OSError, ConnectionError):
                        await self._send("SIR")  # будь-яка команда скасовує SIR (MT-SICS §4.9)
        if frame.kind == "error":
            raise WriteError("SICS: помилка %s на %s" % (frame.id, cmd))
        ok = frame.status == ("S" if cmd == "T" else "A")
        if not ok:
            raise WriteError("SICS %s %s: команду не виконано" % (cmd, frame.status))
        return " ".join(frame.raw.split())

    async def _await_stream(self, fut: asyncio.Future) -> Frame:
        return await asyncio.wait_for(fut, self.timeout_s)  # type: ignore[no-any-return]

    async def _await_reply(self, cmd: str) -> Frame:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout_s
        while True:
            frame = parse_line(await self._readline(max(deadline - loop.time(), 0.001)), self.unit)
            if frame.id == cmd or (frame.kind == "error" and frame.id in ERRORS):
                return frame

    # ------------------------------------------------------------------ стан
    def health(self) -> Health:
        now = datetime.now(UTC)
        limit = max(3 * self.period_s, self.timeout_s)
        last = self._latest_ts if self.mode == "stream" else self._last_ok
        age = (now - self._latest_ts).total_seconds() if self._latest_ts else None
        stats = {
            "frames": self.frames,
            "errors": self.errors,
            "reconnects": self.reconnects,
            "mode": self.mode,
            "device": self._device,
            "last_frame_age_s": age,
        }
        if self.consecutive_errors >= 3:
            return Health("error", self._stream_error or "SICS: повторні помилки опитування", last, stats)
        fresh = last is not None and (now - last).total_seconds() <= limit
        if self._connected and fresh:
            return Health("online", None, last, stats)
        return Health("offline", self._stream_error, last, stats)
