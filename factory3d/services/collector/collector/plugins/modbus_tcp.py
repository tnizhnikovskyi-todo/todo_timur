"""Плагін `modbus_tcp` (SPEC §8.5, R-20): пул клієнтів, групування блоків, декодування, запис, імпульс."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from struct import error as struct_error
from typing import Any, ClassVar

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from collector.core.errors import ConnectError, PollError, WriteError
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins._common import Ewma, ctx_clock, linear, load_schema, validate_source
from collector.plugins.base import PluginContext, SourcePlugin
from collector.util.codec import decode_bit, decode_registers, encode_registers, reg_count

log = logging.getLogger("collector.plugin.modbus_tcp")

MAX_BITS = 2000
RESET_ATTEMPTS = 3
RESET_RETRY_S = 0.5
_BITS_FC = (1, 2)
_NET_ERRORS = (ModbusException, TimeoutError, OSError)


@dataclass
class _PoolEntry:
    client: AsyncModbusTcpClient
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    refs: int = 0


class ConnectionPool:
    """Один клієнт на `(host, port)` для всіх джерел (кілька unit за одним шлюзом)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, int], _PoolEntry] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def acquire(self, host: str, port: int, timeout_s: float, retries: int) -> _PoolEntry:
        key = (host, port)
        entry = self._entries.get(key)
        if entry is None:
            client = AsyncModbusTcpClient(host, port=port, timeout=timeout_s, retries=retries)
            entry = self._entries[key] = _PoolEntry(client)
        entry.refs += 1
        return entry

    def release(self, host: str, port: int) -> None:
        entry = self._entries.get((host, port))
        if entry is None:
            return
        entry.refs -= 1
        if entry.refs <= 0:
            del self._entries[(host, port)]
            with contextlib.suppress(Exception):
                entry.client.close()


POOL = ConnectionPool()


@dataclass(frozen=True)
class _Need:
    unit: int
    fc: int
    addr: int
    count: int


def _err_text(rr: Any, fc: int, addr: int) -> str:
    code = getattr(rr, "exception_code", None)
    if code is not None:
        return f"modbus exception 0x{int(code):02X} (fc{fc} addr {addr})"
    return str(rr)


def _aggregate(agg: str | None, vals: list[float]) -> float:
    if agg == "max":
        return max(vals)
    if agg == "min":
        return min(vals)
    if agg == "sum":
        return sum(vals)
    if agg == "avg":
        return sum(vals) / len(vals)
    return vals[0]


class ModbusTcpPlugin(SourcePlugin):
    type: ClassVar[str] = "modbus_tcp"
    address_schema: ClassVar[dict] = load_schema("address.modbus_tcp")
    params_schema: ClassVar[dict] = load_schema("params.modbus_tcp")

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        super().__init__(source, ctx)
        p = source.params
        self.host: str = p.get("host", "")
        self.port: int = int(p.get("port", 502))
        self.unit: int = int(p.get("unit", 1))
        self.timeout_s: float = float(p.get("timeout_s", 3))
        self.retries: int = int(p.get("retries", 2))
        self.max_block: int = int(p.get("max_block", 125))
        self.gap_max: int = int(p.get("gap_max", 8))
        self.clock = ctx_clock(ctx)
        self.entry: _PoolEntry | None = None
        self.stats = {"polls": 0, "errors": 0, "readings": 0}
        self.latency = Ewma()
        self._last_ok: float | None = None
        self._last_error: str | None = None

    @property
    def client(self) -> AsyncModbusTcpClient:
        assert self.entry is not None
        return self.entry.client

    # --- валідація ---
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        return validate_source(source, cls.address_schema, cls.params_schema, cls._check_address)

    @staticmethod
    def _check_address(a: dict, params: dict) -> list[str]:
        errs: list[str] = []
        fc = a.get("fc")
        typ = a.get("type")
        if fc in _BITS_FC and typ not in (None, "bool"):
            errs.append("type: для fc 1/2 допустимий лише bool")
        if "bit" in a and (typ not in (None, "bool") or fc not in (3, 4)):
            errs.append("bit: лише з type=bool і fc 3/4")
        rng = a.get("range")
        if rng and rng[0] >= rng[1]:
            errs.append("range: lo має бути менше hi")
        w = a.get("write")
        if w:
            if "pulse_ms" in w and w.get("fc") not in (5, 6):
                errs.append("write.pulse_ms: лише з write.fc 5 або 6")
            if "addr" not in w and "addr" not in a:
                errs.append("write.addr: обов'язковий")
        t = typ or ("bool" if fc in _BITS_FC else "u16")
        cnt = a.get("count")
        if cnt is not None and t != "bool" and fc in (3, 4):
            width = reg_count(t)
            if cnt % width:
                errs.append(f"count: має бути кратним ширині типу ({width})")
            elif cnt > width and "agg" not in a:
                errs.append("count: більше ширини типу лише з agg")
        return errs

    # --- з'єднання ---
    async def connect(self) -> None:
        self.ctx.allowlist(self.host)
        if self.entry is None:
            self.entry = POOL.acquire(self.host, self.port, self.timeout_s, self.retries)
        await self._ensure_connected(ConnectError)

    async def _ensure_connected(self, exc: Any) -> None:
        assert self.entry is not None
        client = self.entry.client
        if client.connected:
            return
        try:
            ok = await client.connect()
        except _NET_ERRORS as e:
            raise exc(f"modbus connect to {self.host}:{self.port} failed: {e}") from e
        if not ok:
            raise exc(f"modbus connect to {self.host}:{self.port} failed")

    async def disconnect(self) -> None:
        if self.entry is not None:
            self.entry = None
            POOL.release(self.host, self.port)

    # --- читання ---
    def _unit_of(self, a: dict) -> int:
        return int(a.get("unit", self.unit))

    @staticmethod
    def _type_of(a: dict) -> str:
        if a.get("type"):
            return str(a["type"])
        return "bool" if a["fc"] in _BITS_FC else "u16"

    def _needs(self, sg: SignalCfg) -> list[_Need]:
        a = sg.address
        unit = self._unit_of(a)
        fc = int(a["fc"])
        if a.get("states") and "addr" not in a:
            return [_Need(unit, int(s.get("fc", fc)), int(s["addr"]), 1) for s in a["states"]]
        if fc in _BITS_FC:
            return [_Need(unit, fc, int(a["addr"]), int(a.get("count", 1)))]
        if "bit" in a:
            return [_Need(unit, fc, int(a["addr"]), 1)]
        typ = self._type_of(a)
        return [_Need(unit, fc, int(a["addr"]), int(a.get("count", reg_count(typ))))]

    def _blocks(self, needs: list[_Need]) -> list[_Need]:
        groups: dict[tuple[int, int], list[_Need]] = {}
        for n in needs:
            groups.setdefault((n.unit, n.fc), []).append(n)
        out: list[_Need] = []
        for (unit, fc), items in groups.items():
            limit = MAX_BITS if fc in _BITS_FC else self.max_block
            items.sort(key=lambda n: n.addr)
            start, end = items[0].addr, items[0].addr + items[0].count
            for n in items[1:]:
                new_end = max(end, n.addr + n.count)
                if n.addr - end <= self.gap_max and new_end - start <= limit:
                    end = new_end
                else:
                    out.append(_Need(unit, fc, start, end - start))
                    start, end = n.addr, n.addr + n.count
            out.append(_Need(unit, fc, start, end - start))
        return out

    async def _read_block(self, b: _Need) -> list[int] | str:
        """Значення блоку або текст помилки."""
        assert self.entry is not None
        client = self.entry.client
        fn = {1: client.read_coils, 2: client.read_discrete_inputs, 3: client.read_holding_registers,
              4: client.read_input_registers}[b.fc]
        try:
            async with self.entry.lock:
                rr = await fn(b.addr, count=b.count, slave=b.unit)
        except _NET_ERRORS as e:
            return f"fc{b.fc} unit {b.unit} addr {b.addr}: {e}"
        if rr.isError():
            return _err_text(rr, b.fc, b.addr)
        vals = [1 if x else 0 for x in rr.bits[: b.count]] if b.fc in _BITS_FC else list(rr.registers)
        if len(vals) < b.count:
            return f"fc{b.fc} unit {b.unit} addr {b.addr}: short response ({len(vals)} of {b.count})"
        return vals

    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        started = self.clock.monotonic()
        self.stats["polls"] += 1
        try:
            return await self._poll(signals)
        except PollError as e:
            self.stats["errors"] += 1
            self._last_error = str(e)
            raise
        finally:
            self.latency.add((self.clock.monotonic() - started) * 1000)

    async def _poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        if self.entry is None:
            raise PollError("not connected")
        await self._ensure_connected(PollError)
        sigs = [s for s in signals if s.address]
        needs: list[_Need] = []
        for s in sigs:
            needs += self._needs(s)
        blocks = self._blocks(needs)
        data: dict[tuple[int, int], list[tuple[int, int, list[int] | str]]] = {}
        errors: list[str] = []
        pending = list(blocks)
        reads = 0
        while pending:
            b = pending.pop(0)
            res = await self._read_block(b)
            if isinstance(res, str) and "exception 0x02" in res and b.count > 1:
                # у блоці є непризначені регістри (дірка між сигналами, gap_max): повторити по окремих сигналах
                parts = {(n.addr, n.count): n for n in needs
                         if n.unit == b.unit and n.fc == b.fc and b.addr <= n.addr and n.addr + n.count <= b.addr + b.count}
                if len(parts) > 1 or (parts and next(iter(parts)) != (b.addr, b.count)):
                    pending = list(parts.values()) + pending
                    continue
            if isinstance(res, str):
                errors.append(res)
            data.setdefault((b.unit, b.fc), []).append((b.addr, b.count, res))
            reads += 1
        if reads and len(errors) == reads:
            raise PollError(errors[0])
        ts = self.clock.now()
        out: list[Reading] = []
        for s in sigs:
            try:
                out.append(self._decode(s, ts, data))
            except (ValueError, KeyError, IndexError, TypeError, struct_error) as e:
                log.warning("decode %s: %s", s.code, e)
                out.append(Reading(code=s.code, ts=ts, q="bad"))
        self._last_ok = self.clock.monotonic()
        self._last_error = None
        self.stats["readings"] += len(out)
        return out

    @staticmethod
    def _slice(data: dict, need: _Need) -> list[int] | None:
        for start, count, res in data.get((need.unit, need.fc), []):
            if start <= need.addr and need.addr + need.count <= start + count:
                if isinstance(res, str):
                    return None
                return res[need.addr - start: need.addr - start + need.count]
        return None

    def _decode(self, sg: SignalCfg, ts: Any, data: dict) -> Reading:
        a = sg.address
        bad = Reading(code=sg.code, ts=ts, q="bad")
        if a.get("states") and "addr" not in a:
            for st in a["states"]:
                need = _Need(self._unit_of(a), int(st.get("fc", a["fc"])), int(st["addr"]), 1)
                vals = self._slice(data, need)
                if vals is None:
                    return bad
                if int(vals[0]) == int(st["eq"]):
                    return Reading(code=sg.code, ts=ts, text=str(st["text"]))
            return Reading(code=sg.code, ts=ts, q="uncertain")
        need = self._needs(sg)[0]
        vals = self._slice(data, need)
        if vals is None:
            return bad
        typ = self._type_of(a)
        fc = int(a["fc"])
        raws: list[float]
        if fc in _BITS_FC:
            raws = [float(v) for v in vals]
        elif "bit" in a:
            raws = [float(decode_bit(vals[0], int(a["bit"])))]
        elif typ == "bool":
            raws = [float(1 if vals[0] else 0)]
        else:
            w = reg_count(typ)
            wo, bo = a.get("wordorder", "big"), a.get("byteorder", "big")
            raws = [float(decode_registers(vals[i:i + w], typ, wo, bo)) for i in range(0, len(vals) - w + 1, w)]
        if sg.kind == "state":
            key = int(raws[0])
            amap = a.get("map") or {}
            if str(key) in amap:
                return Reading(code=sg.code, ts=ts, text=str(amap[str(key)]))
            return Reading(code=sg.code, ts=ts, text=str(key), q="uncertain")
        engs = [linear(r, a) for r in raws]
        agg = a.get("agg")
        eng = _aggregate(agg, engs)
        q = "good"
        rng = a.get("range")
        if rng and not (rng[0] <= eng <= rng[1]):
            q = "bad"
        return Reading(code=sg.code, ts=ts, value=float(eng), q=q)

    # --- запис ---
    def _write_target(self, signal: SignalCfg, value: float | None, text: str | None) -> tuple[int, int, int, Any]:
        a = signal.address
        w = a.get("write")
        if not w:
            raise WriteError("signal has no address.write")
        fc = int(w["fc"])
        addr = int(w.get("addr", a.get("addr", -1)))
        if addr < 0:
            raise WriteError("write address is not set")
        unit = self._unit_of(a)
        if fc == 5 and "pulse_ms" in w:
            return unit, fc, addr, True
        if text is not None and a.get("map") and text in a["map"].values():
            value = float(next(int(k) for k, v in a["map"].items() if v == text))
        elif text is not None and value is None:
            raise WriteError(f"text «{text}» немає в map")
        if value is None:
            raise WriteError("no value to write")
        if fc == 5:
            return unit, fc, addr, value != 0
        typ = self._type_of(a)
        raw = (float(value) - float(a.get("offset", 0))) / float(a.get("scale", 1))
        if typ not in ("f32", "f64"):
            raw = round(raw)
        try:
            regs = encode_registers(raw, typ, a.get("wordorder", "big"), a.get("byteorder", "big"))
        except Exception as e:  # struct.error тощо
            raise WriteError(f"cannot encode {raw} as {typ}: {e}") from e
        if fc == 6 and len(regs) != 1:
            raise WriteError("fc6 supports only 16-bit types")
        return unit, fc, addr, regs

    async def _send(self, unit: int, fc: int, addr: int, payload: Any) -> None:
        if self.entry is None:
            raise WriteError("not connected")
        await self._ensure_connected(WriteError)
        client = self.entry.client
        try:
            async with self.entry.lock:
                if fc == 5:
                    rr = await client.write_coil(addr, bool(payload), slave=unit)
                elif fc == 6:
                    rr = await client.write_register(addr, payload[0] if isinstance(payload, list) else payload,
                                                     slave=unit)
                else:
                    rr = await client.write_registers(addr, payload, slave=unit)
        except _NET_ERRORS as e:
            raise WriteError(f"fc{fc} addr {addr}: {e}") from e
        if rr.isError():
            raise WriteError(_err_text(rr, fc, addr))

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        unit, fc, addr, payload = self._write_target(signal, value, text)
        pulse = signal.address["write"].get("pulse_ms")
        if pulse:
            return await self._pulse(unit, fc, addr, int(pulse))
        await self._send(unit, fc, addr, payload)
        if fc == 5:
            return f"fc5 addr {addr} = {bool(payload)}"
        if fc == 6:
            return f"fc6 addr {addr} = {payload[0]}"
        return f"fc16 addr {addr} = {payload}"

    async def _pulse(self, unit: int, fc: int, addr: int, pulse_ms: int) -> str:
        on: Any = True if fc == 5 else [1]
        off: Any = False if fc == 5 else [0]
        first_error: Exception | None = None
        try:
            try:
                await self._send(unit, fc, addr, on)
            except WriteError as e:
                first_error = e
            else:
                await self.clock.sleep(pulse_ms / 1000)
        finally:
            reset = asyncio.ensure_future(self._reset(unit, fc, addr, off))
            await asyncio.shield(reset)
        if first_error is not None:
            raise first_error
        return f"fc{fc} addr {addr} pulse 1→0 {pulse_ms} ms"

    async def _reset(self, unit: int, fc: int, addr: int, off: Any) -> None:
        last: Exception | None = None
        for attempt in range(RESET_ATTEMPTS):
            try:
                await self._send(unit, fc, addr, off)
                return
            except WriteError as e:
                last = e
                if attempt < RESET_ATTEMPTS - 1:
                    await self.clock.sleep(RESET_RETRY_S)
        self.ctx.metrics.modbus_pulse_reset_failed.labels(self.source.code).inc()
        raise WriteError(f"pulse reset failed: {last}")

    # --- стан ---
    def health(self) -> Health:
        periods = [s.period_s for s in self.source.signals] or [10]
        window = 2 * max(periods)
        stats = {**self.stats, "latency_ms": self.latency.value}
        now = self.clock.monotonic()
        if self._last_error is not None and (self._last_ok is None or now - self._last_ok > window):
            return Health(state="offline", error=self._last_error, stats=stats)
        return Health(state="online", stats=stats)

