"""Типи ядра колектора (SPEC §8.3.1, CT-02)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SignalCfg:
    code: str
    kind: str
    unit: str
    period_s: int
    scale: float  # застосовує лише ядро (R-02, X-63); плагін НЕ множить
    write_enabled: bool
    states: list[str] | None
    decimals: int
    address: dict
    source_code: str


@dataclass(frozen=True)
class SourceCfg:
    code: str
    type: str
    read_enabled: bool
    write_enabled: bool
    params: dict
    signals: tuple[SignalCfg, ...]


@dataclass(frozen=True)
class Reading:
    code: str
    ts: datetime  # tz-aware UTC
    value: float | None = None
    text: str | None = None
    q: str = "good"


@dataclass
class Health:
    state: str  # "online" | "offline" | "error"
    error: str | None = None
    last_ok: datetime | None = None
    stats: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Command:
    id: int
    code: str
    source: str
    value: float | None
    text: str | None
    address: dict
    expires_at: datetime
    payload: dict | None = None  # CR-01 (X-03): не None -> ядро викликає plugin.call(), а не write()


@dataclass(frozen=True)
class CommandResult:
    id: int
    state: str
    ts: datetime
    result: str | None = None
    error: str | None = None
    data: dict | None = None  # CR-01: dict, який повернув call()


@dataclass(frozen=True)
class PushEvent:
    event_id: str
    route: str
    ts: datetime
    remote: str
    headers: dict
    payload: dict
