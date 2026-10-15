"""Час: utcnow(), parse_iso(), to_iso_z(); годинник Clock/SystemClock (SPEC §13.0.2)."""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Protocol


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_iso(value: str) -> datetime:
    """ISO 8601 (суфікс `Z` або ±hh:mm) -> tz-aware UTC; без зони вважається UTC. ValueError при помилці."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso_z(dt: datetime) -> str:
    """tz-aware datetime -> `2026-10-14T06:10:00Z` (мілісекунди лише якщо ненульові)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    dt = dt.astimezone(UTC)
    if dt.microsecond:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
    async def sleep(self, s: float) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return utcnow()

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, s: float) -> None:
        await asyncio.sleep(s)
