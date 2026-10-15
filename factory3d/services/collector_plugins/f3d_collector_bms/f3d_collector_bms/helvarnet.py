"""Плагін `helvarnet`: освітлення Helvar Imagine 950 / DALI (SPEC factory3d_bms §8, R-31…R-37)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import statistics
import time
from datetime import UTC, datetime
from importlib import resources
from typing import Any, ClassVar

from collector.core.errors import ConnectError, NotSupported, PollError, WriteError
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins._common import validate_source
from collector.plugins.base import PluginContext, SourcePlugin

from .connection import POOL, ConnectionClosedError, ConnectionPool, HelvarConnection
from .protocol import (
    Frame,
    HelvarError,
    ProtocolError,
    build_command,
    build_query,
    decode_level,
    expand_devices,
    key_for,
)

DEFAULT_MASK = 0x0800000E
BIT_MISSING = 0x4
EMERGENCY_GROUP = 40
QUERY_ORDER = ("router", "level", "scene", "power", "faults", "faulty")
FADE_RE = re.compile(r"fade\s*=\s*([0-9]+(?:\.[0-9]+)?)")
EWMA_ALPHA = 0.3
WARN_EVERY_S = 60.0
SWEEP_REUSE_S = 1.0
MAX_FAULTY_TEXT = 64


def _load(name: str) -> dict:
    text = resources.files("f3d_collector_bms").joinpath("schemas", name).read_text(encoding="utf-8")
    return json.loads(text)  # type: ignore[no-any-return]


def sample_positions(length: int, sample: int) -> list[int]:
    """R-32: `[0, len//2, len-1]` для sample=3; для інших — рівномірно, унікальні, по порядку."""
    if length <= 0:
        return []
    if sample <= 1:
        return [0]
    out = []
    for i in range(sample):
        idx = 0 if i == 0 else (length - 1 if i == sample - 1 else i * length // (sample - 1))
        if idx not in out:
            out.append(idx)
    return sorted(out)


def faulty_text(addresses: list[str]) -> str:
    """R-34: адреси без `@` через `,`, ≤ 64 символів із суфіксом `+N`; порожньо -> `—`."""
    if not addresses:
        return "—"
    full = ",".join(addresses)
    if len(full) <= MAX_FAULTY_TEXT:
        return full
    n = len(addresses)
    for k in range(n - 1, 0, -1):
        text = ",".join(addresses[:k]) + f"+{n - k}"
        if len(text) <= MAX_FAULTY_TEXT:
            return text
    return f"+{n}"


def _signal_check(addr: dict, params: dict) -> list[str]:
    devices = addr.get("devices")
    if devices:
        try:
            expand_devices(devices)
        except ValueError as exc:
            return [f"devices: {exc}"]
    return []


class HelvarNetPlugin(SourcePlugin):
    type: ClassVar[str] = "helvarnet"
    version: ClassVar[str] = "0.1.0"
    address_schema: ClassVar[dict] = _load("address.helvarnet.json")
    params_schema: ClassVar[dict] = _load("params.helvarnet.json")
    push_mode: ClassVar[bool] = False
    pool: ClassVar[ConnectionPool] = POOL
    verify_extra_s: ClassVar[float] = 1.0  # R-37: перевірка запису через fade_s + 1 с

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        super().__init__(source, ctx)
        p = source.params or {}
        self.host: str = p.get("host", "")
        self.port: int = int(p.get("port", 50000))
        self.protocol: str = p.get("protocol", "tcp")
        self.timeout_s: float = float(p.get("timeout_s", 3))
        self.cluster: int = int(p.get("cluster", 1))
        self.router: int = int(p.get("router", 1))
        self.proto_version: int = int(p.get("version", 2))
        self.rate_per_s: int = int(p.get("rate_per_s", 20))
        self.push: bool = bool(p.get("push", True))
        self.membership_ttl_s: float = float(p.get("membership_ttl_s", 3600))
        self._conn: HelvarConnection | None = None
        self._acquired = False
        self._members: dict[int, tuple[float, list[str], bool]] = {}
        self._missing: dict[int, set[str]] = {}
        self._faulty_count: dict[int, int] = {}
        self._sweeps: dict[tuple, tuple[float, tuple[int, list[str]]]] = {}
        self._fails = 0
        self._router_ok: bool | None = None
        self._router_error: str | None = None
        self._last_ok: datetime | None = None
        self._last_ok_mono: float | None = None
        self._warned: dict[str, float] = {}
        self.queries = 0
        self.errors = 0
        self.timeouts = 0
        self.push_count = 0
        self.push_ignored = 0
        self.reconnects = 0
        self.latency_ms: float | None = None

    @property
    def version_in_use(self) -> int:
        return self.proto_version

    # ------------------------------------------------------------------ валідація
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        return validate_source(source, cls.address_schema, cls.params_schema, signal_check=_signal_check)

    # ------------------------------------------------------------------ службове
    def _metric(self, name: str, **labels: str) -> Any:
        metric = getattr(self.ctx.metrics, name, None)
        if metric is None:
            return None
        with contextlib.suppress(Exception):
            return metric.labels(source=self.source.code, **labels)
        return None

    def _inc(self, name: str, **labels: str) -> None:
        m = self._metric(name, **labels)
        if m is not None:
            with contextlib.suppress(Exception):
                m.inc()

    def _warn(self, kind: str, msg: str, *args: object) -> None:
        now = time.monotonic()
        if now - self._warned.get(kind, -WARN_EVERY_S) >= WARN_EVERY_S:
            self._warned[kind] = now
            self.ctx.log.warning(msg, *args)

    def _count_error(self, code: str) -> None:
        self.errors += 1
        self._inc("collector_helvarnet_errors_total", code=code)

    # ------------------------------------------------------------------ з'єднання
    async def connect(self) -> None:
        self.ctx.allowlist(self.host)
        if self.protocol != "tcp":
            raise ConnectError("udp not supported")
        conn = self.pool.acquire(self.host, self.port, self.protocol, self.timeout_s, self.rate_per_s)
        self._acquired = True
        self._conn = conn
        try:
            await conn.ensure_open()
            await self._negotiate_version(conn)
        except BaseException:
            await self.disconnect()
            raise
        if self.push:
            conn.add_push_listener(self._on_push)

    async def _negotiate_version(self, conn: HelvarConnection) -> None:
        for _ in range(2):
            text = build_query(self.proto_version, 191)
            try:
                frame = await conn.request(text, key_for(191), self.timeout_s)
            except TimeoutError as exc:
                raise ConnectError("timeout on C:191") from exc
            except ConnectionClosedError as exc:
                raise ConnectError(f"connection lost: {exc}") from exc
            if frame.kind == "error":
                code = self._code(frame)
                if code == 18 and self.proto_version == 2:
                    self.proto_version = 1
                    continue
                raise ConnectError(str(HelvarError(code)))
            with contextlib.suppress(TypeError, ValueError):
                reported = int(frame.answer or "")
                if reported in (1, 2):
                    self.proto_version = reported
            self._mark_ok()
            return
        raise ConnectError("incompatible HelvarNet version")

    async def disconnect(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.remove_push_listener(self._on_push)
        if self._acquired:
            self._acquired = False
            await self.pool.release(self.host, self.port)

    async def _ensure(self) -> HelvarConnection:
        conn = self._conn
        if conn is None:
            raise PollError("not connected")
        if not conn.alive:
            try:
                await conn.ensure_open()
            except ConnectError as exc:
                raise PollError(f"reconnect failed: {exc}") from exc
            self.reconnects += 1
            self._fails = 0
        return conn

    @staticmethod
    def _code(frame: Frame) -> int:
        try:
            return int(frame.answer or "")
        except ValueError:
            return -1

    def _mark_ok(self) -> None:
        self._last_ok = datetime.now(UTC)
        self._last_ok_mono = time.monotonic()

    async def _ask(
        self, cmd: int, group: int | None = None, address: str | None = None, extra: dict | None = None
    ) -> Frame:
        conn = self._conn
        if conn is None:
            raise PollError("not connected")
        text = build_query(self.proto_version, cmd, group, address, extra)
        self.queries += 1
        self._inc("collector_helvarnet_queries_total", cmd=str(cmd))
        started = time.monotonic()
        try:
            frame = await conn.request(text, key_for(cmd, group, address), self.timeout_s)
        except TimeoutError:
            self.timeouts += 1
            self._fails += 1
            self._count_error("timeout")
            if self._fails >= 3:
                await conn.close()
                raise PollError("3 consecutive timeouts") from None
            raise
        except ConnectionClosedError as exc:
            self._count_error("closed")
            self._fails += 1
            raise PollError(f"connection lost: {exc}") from exc
        self._fails = 0
        elapsed = time.monotonic() - started
        ms = elapsed * 1000.0
        self.latency_ms = ms if self.latency_ms is None else EWMA_ALPHA * ms + (1 - EWMA_ALPHA) * self.latency_ms
        hist = self._metric("collector_helvarnet_latency_seconds")
        if hist is not None:
            with contextlib.suppress(Exception):
                hist.observe(elapsed)
        self._mark_ok()
        if frame.kind == "error":
            code = self._code(frame)
            self._count_error(str(code))
            raise HelvarError(code)
        return frame

    # ------------------------------------------------------------------ склад групи (R-35)
    async def _members_of(self, group: int, addr: dict) -> list[str]:
        now = time.monotonic()
        cached = self._members.get(group)
        if cached and cached[0] > now:
            return cached[1]
        members: list[str] = []
        try:
            frame = await self._ask(164, group=group)
            members = [m.strip() for m in (frame.answer or "").split(",") if m.strip().startswith("@")]
        except (HelvarError, TimeoutError):
            members = []
        if members:
            self._members[group] = (now + self.membership_ttl_s, members, True)
            return members
        devices = addr.get("devices")
        if devices:
            try:
                members = expand_devices(devices)
            except ValueError:
                members = []
            if members:
                self._members[group] = (now + min(self.membership_ttl_s, 60.0), members, False)
                return members
        self._warn(f"members{group}", "склад групи G:%s невідомий", group)
        return []

    # ------------------------------------------------------------------ опитування (R-32…R-35)
    async def poll(self, signals) -> list[Reading]:
        await self._ensure()
        by_query: dict[str, list[SignalCfg]] = {q: [] for q in QUERY_ORDER}
        results: dict[str, Reading] = {}
        for sg in signals:
            addr = sg.address if isinstance(sg.address, dict) else {}
            query = addr.get("query", "level")
            if query not in by_query or (query != "router" and not isinstance(addr.get("group"), int)):
                results[sg.code] = self._bad(sg.code)
                continue
            by_query[query].append(sg)
        cache: dict[tuple, Any] = {}
        for query in QUERY_ORDER:
            for sg in by_query[query]:
                try:
                    results[sg.code] = await self._read(sg, query, cache)
                except (HelvarError, TimeoutError, ProtocolError, ValueError) as exc:
                    self.ctx.log.debug("signal %s: %s", sg.code, exc)
                    results[sg.code] = self._bad(sg.code)
        return [results[sg.code] for sg in signals if sg.code in results]

    @staticmethod
    def _bad(code: str, text: str | None = None) -> Reading:
        return Reading(code=code, ts=datetime.now(UTC), value=None, text=text, q="bad")

    @staticmethod
    def _ok(code: str, value: float | None = None, text: str | None = None) -> Reading:
        return Reading(code=code, ts=datetime.now(UTC), value=value, text=text, q="good")

    async def _read(self, sg: SignalCfg, query: str, cache: dict) -> Reading:
        a = sg.address
        scale = float(a.get("scale", 1))
        if query == "router":
            return await self._read_router(sg, a, cache)
        group = a["group"]
        if query == "level":
            value = await self._level(group, a)
            return self._bad(sg.code) if value is None else self._ok(sg.code, value * scale)
        if query == "power":
            frame = await self._ask(161, group=group)
            return self._ok(sg.code, float(frame.answer or "") * scale)
        if query == "scene":
            block = int(a.get("block", 1))
            frame = await self._ask(109, group=group, extra={"B": block} if block != 1 else None)
            return self._ok(sg.code, float(int(frame.answer or "")) * scale)
        sweep = await self._sweep(group, a, cache)
        if sweep is None:
            return self._bad(sg.code)
        count, addresses = sweep
        if query == "faults":
            return self._ok(sg.code, float(count))
        return self._ok(sg.code, None, faulty_text(addresses))

    async def _level(self, group: int, a: dict) -> float | None:
        members = await self._members_of(group, a)
        missing = self._missing.setdefault(group, set())
        candidates = [m for m in members if m not in missing]
        levels: list[int] = []
        for idx in sample_positions(len(candidates), int(a.get("sample", 3))):
            addr = candidates[idx]
            try:
                frame = await self._ask(152, address=addr)
            except HelvarError as exc:
                if exc.code == 11:
                    missing.add(addr)
                continue
            except TimeoutError:
                continue
            levels.append(decode_level(frame.answer or ""))
        if not levels:
            return None
        return float(statistics.median_low(levels))

    async def _sweep(self, group: int, a: dict, cache: dict) -> tuple[int, list[str]] | None:
        mask = int(a.get("mask", DEFAULT_MASK))
        key = ("sweep", group, mask)
        if key in cache:
            return cache[key]  # type: ignore[no-any-return]
        old = self._sweeps.get(key)
        if old and time.monotonic() - old[0] < SWEEP_REUSE_S:
            return old[1]
        members = await self._members_of(group, a)
        if not members:
            cache[key] = None
            return None
        missing = self._missing.setdefault(group, set())
        faulty: list[str] = []
        for addr in members:
            try:
                frame = await self._ask(110, address=addr)
                state = int(frame.answer or "")
            except HelvarError as exc:
                if exc.code == 11:
                    faulty.append(addr)
                    missing.add(addr)
                continue
            except (TimeoutError, ValueError):
                continue
            if state & mask:
                faulty.append(addr)
            if state & BIT_MISSING:
                missing.add(addr)
            else:
                missing.discard(addr)
        cached_members = self._members.get(group)
        if a.get("devices") and cached_members and cached_members[2]:
            known = set(members)
            for dev in expand_devices(a["devices"]):
                if dev not in known:
                    faulty.append(dev)
                    missing.add(dev)
        self._faulty_count[group] = len(faulty)
        result = (len(faulty), [d.lstrip("@") for d in faulty])
        cache[key] = result
        self._sweeps[key] = (time.monotonic(), result)
        self._inc_faulty_gauge()
        return result

    def _inc_faulty_gauge(self) -> None:
        gauge = self._metric("collector_helvarnet_faulty_devices")
        if gauge is not None:
            with contextlib.suppress(Exception):
                gauge.set(sum(self._faulty_count.values()))

    async def _read_router(self, sg: SignalCfg, a: dict, cache: dict) -> Reading:
        m = re.match(r"^@(\d+)\.(\d+)", a.get("device", ""))
        cluster, router = (int(m.group(1)), int(m.group(2))) if m else (self.cluster, self.router)
        key = ("routers", cluster)
        if key not in cache:
            frame = await self._ask(102, address=f"@{cluster}")
            routers: set[int] = set()
            for token in (frame.answer or "").split(","):
                parts = token.strip().lstrip("@").split(".")
                with contextlib.suppress(ValueError):
                    routers.add(int(parts[1] if len(parts) > 1 else parts[0]))
            cache[key] = routers
        present = router in cache[key]
        self._router_ok = present
        if not present:
            self._router_error = f"router @{cluster}.{router} not in cluster"
            return self._bad(sg.code, "offline")
        self._router_error = None
        state = "fault" if any(n > 0 for n in self._faulty_count.values()) else "ok"
        return self._ok(sg.code, None, state)

    # ------------------------------------------------------------------ push (R-36)
    def _on_push(self, frame: Frame) -> None:
        if not self.push:
            return
        if frame.cmd == 13:
            field, query = "L", "level"
        elif frame.cmd == 11:
            field, query = "S", "scene"
        else:
            self.push_ignored += 1
            self._inc("collector_helvarnet_push_ignored_total")
            return
        try:
            group = int(frame.params["G"])
            value = float(frame.params[field])
        except (KeyError, ValueError):
            self.push_ignored += 1
            self._inc("collector_helvarnet_push_ignored_total")
            return
        self.push_count += 1
        self._inc("collector_helvarnet_push_total", cmd=str(frame.cmd))
        for sg in self.source.signals:
            a = sg.address
            if isinstance(a, dict) and a.get("query", "level") == query and a.get("group") == group:
                self.ctx.emit(Reading(code=sg.code, ts=datetime.now(UTC), value=value))

    # ------------------------------------------------------------------ запис (R-37)
    async def subscribe(self) -> None:
        raise NotSupported("subscribe")

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        a = signal.address if isinstance(signal.address, dict) else {}
        query = a.get("query", "level")
        if query not in ("level", "scene"):
            raise NotSupported(f"write for query {query}")
        group = a.get("group")
        groups = {s.address.get("group") for s in self.source.signals if isinstance(s.address, dict)}
        if group is None or group == EMERGENCY_GROUP or group not in groups:
            raise NotSupported(f"write to group {group}")
        match = FADE_RE.search(text or "")
        fade = float(match.group(1)) if match else float(a.get("fade_s", 2.0))
        if not 0 <= fade <= 90:
            raise WriteError("fade out of range 0..90")
        fade_cs = round(fade * 100)
        if value is None:
            raise WriteError("value required")
        try:
            if query == "level":
                target = round(value)
                frame_text = build_command(self.proto_version, 13, group, level=target, fade_cs=fade_cs)
                cmd, label = 13, f"L{target}"
            else:
                target = round(value)
                frame_text = build_command(
                    self.proto_version, 11, group, scene=target, block=int(a.get("block", 1)), fade_cs=fade_cs
                )
                cmd, label = 11, f"S{target}"
        except ValueError as exc:
            raise WriteError(str(exc)) from exc
        conn = self._conn
        if conn is None:
            raise WriteError("not connected")
        try:
            await conn.ensure_open()
            frame = await conn.request(frame_text, key_for(cmd, group), self.timeout_s, accept_push=True)
        except TimeoutError:
            frame = None
        except (ConnectError, ConnectionClosedError) as exc:
            raise WriteError(f"connection lost: {exc}") from exc
        head = f"C{cmd} G{group} {label} F{fade_cs}"
        if frame is not None:
            if frame.kind == "error":
                code = self._code(frame)
                if code != 0:
                    raise WriteError(str(HelvarError(code)))
            return f"{head} ack"
        await asyncio.sleep(fade + self.verify_extra_s)
        await self._verify(group, a, query, target)
        return f"{head} verified"

    async def _verify(self, group: int, a: dict, query: str, target: int) -> None:
        try:
            if query == "level":
                members = await self._members_of(group, a)
                if not members:
                    raise WriteError("no ack, group membership unknown")
                frame = await self._ask(152, address=members[0])
                now = decode_level(frame.answer or "")
                if abs(now - target) > 2:
                    raise WriteError(f"no ack, level now {now}")
            else:
                frame = await self._ask(109, group=group)
                now = int(frame.answer or "")
                if now != target:
                    raise WriteError(f"no ack, scene now {now}")
        except (HelvarError, TimeoutError, PollError, ValueError, ProtocolError) as exc:
            raise WriteError(f"no ack, verification failed: {exc}") from exc

    # ------------------------------------------------------------------ стан (§8.6)
    def health(self) -> Health:
        conn = self._conn
        stats = {
            "queries": self.queries,
            "errors": self.errors,
            "timeouts": self.timeouts,
            "push": self.push_count,
            "latency_ms": None if self.latency_ms is None else round(self.latency_ms, 1),
            "devices_faulty": sum(self._faulty_count.values()),
            "version": self.proto_version,
        }
        if conn is None or not conn.alive:
            return Health(state="offline", error="no TCP session", last_ok=self._last_ok, stats=stats)
        if self._router_ok is False:
            return Health(state="error", error=self._router_error, last_ok=self._last_ok, stats=stats)
        if self._fails >= 3:
            return Health(state="error", error="3 consecutive failures", last_ok=self._last_ok, stats=stats)
        max_period = max((s.period_s for s in self.source.signals), default=30)
        fresh = self._last_ok_mono is not None and time.monotonic() - self._last_ok_mono <= 2 * max_period
        if fresh:
            return Health(state="online", last_ok=self._last_ok, stats=stats)
        return Health(state="error", error="no successful query", last_ok=self._last_ok, stats=stats)
