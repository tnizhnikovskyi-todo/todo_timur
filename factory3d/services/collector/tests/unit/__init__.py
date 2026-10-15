"""Спільні помічники юніт-тестів ядра: фейковий плагін, конфіг-фабрики, годинник з лімітом сліпів."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Sequence
from datetime import timedelta
from typing import Any, ClassVar

from conftest import T0, VirtualClock

from collector.core.errors import NotSupported
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins.base import SourcePlugin


class CountingClock(VirtualClock):
    """VirtualClock, що пише всі sleep() і кидає CancelledError після `max_sleeps`."""

    def __init__(self, max_sleeps: int = 1000) -> None:
        super().__init__()
        self.sleeps: list[float] = []
        self.max_sleeps = max_sleeps

    async def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        if len(self.sleeps) >= self.max_sleeps:
            raise asyncio.CancelledError
        await super().sleep(s)


def mk_signal(
    code: str,
    kind: str = "gauge",
    period_s: int = 10,
    scale: float = 1.0,
    write: bool = False,
    address: dict | None = None,
    source: str = "S",
) -> SignalCfg:
    return SignalCfg(
        code=code,
        kind=kind,
        unit="",
        period_s=period_s,
        scale=scale,
        write_enabled=write,
        states=None,
        decimals=2,
        address=address or {},
        source_code=source,
    )


def mk_source(
    code: str = "S",
    type_: str = "fake",
    signals: Sequence[SignalCfg] = (),
    write: bool = False,
    params: dict | None = None,
) -> SourceCfg:
    return SourceCfg(
        code=code, type=type_, read_enabled=True, write_enabled=write, params=params or {}, signals=tuple(signals)
    )


def sig_json(
    code: str,
    kind: str = "gauge",
    period_s: int = 10,
    scale: float = 1.0,
    write: bool = False,
    address: dict | None = None,
) -> dict:
    return {
        "code": code,
        "kind": kind,
        "unit": "",
        "period_s": period_s,
        "scale": scale,
        "write_enabled": write,
        "states": None,
        "decimals": 2,
        "address": address or {"a": 1},
    }


def src_json(
    code: str,
    type_: str = "fake",
    signals: list[dict] | None = None,
    write: bool = False,
    params: dict | None = None,
    read: bool = True,
) -> dict:
    return {
        "code": code,
        "type": type_,
        "read_enabled": read,
        "write_enabled": write,
        "params": params or {},
        "signals": signals or [],
    }


class FakePlugin(SourcePlugin):
    """Програмований плагін. `script` для poll: список елементів — list[Reading], виняток або callable;
    коли список вичерпано, кидає CancelledError (зупиняє цикл у тесті)."""

    type: ClassVar[str] = "fake"
    address_schema: ClassVar[dict] = {}
    params_schema: ClassVar[dict] = {}
    instances: ClassVar[list[FakePlugin]] = []

    def __init__(self, source: SourceCfg, ctx: Any) -> None:
        super().__init__(source, ctx)
        self.script: list[Any] = []
        self.connects = 0
        self.disconnects = 0
        self.polls: list[list[str]] = []
        self.writes: list[tuple] = []
        self.calls: list[tuple] = []
        self.write_result = "ok"
        self.write_exc: Exception | None = None
        self.call_result: Any = {}
        self.call_supported = True
        self.hang = False
        FakePlugin.instances.append(self)

    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        return [f"{s.code}: bad address" for s in source.signals if s.address.get("bad")]

    async def connect(self) -> None:
        self.connects += 1

    async def disconnect(self) -> None:
        self.disconnects += 1

    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        self.polls.append([s.code for s in signals])
        if not self.script:
            raise asyncio.CancelledError
        item = self.script.pop(0)
        if callable(item):
            item = item()
            if inspect.isawaitable(item):
                item = await item
        if isinstance(item, BaseException):
            raise item
        return list(item)

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        if self.hang:
            await asyncio.Event().wait()
        self.writes.append((signal.code, value, text))
        if self.write_exc:
            raise self.write_exc
        return self.write_result

    async def call(self, signal: SignalCfg, payload: dict) -> dict:
        if not self.call_supported:
            raise NotSupported("call")
        if self.hang:
            await asyncio.Event().wait()
        self.calls.append((signal.code, payload))
        return self.call_result  # type: ignore[no-any-return]

    def health(self) -> Health:
        return Health(state="online")


def reading(code: str, value: float | None = 1.0, text: str | None = None, q: str = "good") -> Reading:
    return Reading(code=code, ts=T0, value=value, text=text, q=q)


__all__ = [
    "T0",
    "Callable",
    "CountingClock",
    "FakePlugin",
    "VirtualClock",
    "mk_signal",
    "mk_source",
    "reading",
    "sig_json",
    "src_json",
    "timedelta",
]
