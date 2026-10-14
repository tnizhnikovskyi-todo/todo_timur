"""Події емулятора (SPEC §8.2.4): ``Event`` і ``EventBus`` (кільцевий буфер 10 000, API-19)."""
from __future__ import annotations

import os
import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

KINDS = ("scenario", "fault", "alarm", "info", "error", "command", "access", "yard", "fire")
RING_SIZE = 10_000
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ulid_last = [0, 0]


def ulid() -> str:
    """ULID (26 символів Crockford base32), монотонний у межах процесу."""
    ms = int(time.time() * 1000)
    if ms <= _ulid_last[0]:
        ms = _ulid_last[0]
        rnd = _ulid_last[1] + 1
    else:
        rnd = int.from_bytes(os.urandom(10), "big")
    _ulid_last[0], _ulid_last[1] = ms, rnd
    n = (ms << 80) | (rnd & ((1 << 80) - 1))
    return "".join(_CROCKFORD[(n >> (5 * i)) & 31] for i in range(25, -1, -1))


class CursorGone(Exception):
    """API-19: курсор ``next`` витіснено з кільця → 410 Gone."""


@dataclass
class Event:
    """``id`` "e-<ulid>", ``ts`` — sim-час, ``kind`` ∈ KINDS, ``message`` — українською,
    ``seq`` — порядковий номер у шині (курсор API-19)."""

    id: str
    ts: datetime
    kind: str
    message: str
    device: str | None = None
    run_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "ts": self.ts.isoformat(), "kind": self.kind,
                "device": self.device, "run_id": self.run_id, "message": self.message,
                "payload": self.payload}


class EventBus:
    """``emit()`` -> Event; підписники (лог, API-03, протоколи) отримують подію синхронно."""

    def __init__(self, now: Callable[[], datetime], size: int = RING_SIZE) -> None:
        self._now = now
        self.ring: deque[Event] = deque(maxlen=size)
        self.counts: Counter[str] = Counter()  # iot_sim_events_total{kind}
        self.subscribers: list[Callable[[Event], None]] = []
        self.seq = 0

    def subscribe(self, fn: Callable[[Event], None]) -> None:
        self.subscribers.append(fn)

    def emit(self, kind: str, message: str, device: str | None = None,
             run_id: str | None = None, payload: dict | None = None) -> Event:
        if kind not in KINDS:
            raise ValueError(f"unknown event kind {kind!r}")
        self.seq += 1
        ev = Event(f"e-{ulid()}", self._now(), kind, message, device, run_id,
                   dict(payload or {}), self.seq)
        self.ring.append(ev)
        self.counts[kind] += 1
        for fn in list(self.subscribers):
            fn(ev)
        return ev

    def since(self, cursor: int = 0, limit: int = 1000, kind: str | None = None,
              device: str | None = None) -> tuple[list[Event], int]:
        """Події з ``seq > cursor`` і новий курсор. ``CursorGone``, якщо курсор витіснено."""
        if self.ring and cursor and cursor < self.ring[0].seq - 1:
            raise CursorGone(cursor)
        out = [e for e in self.ring if e.seq > cursor
               and (kind is None or e.kind == kind) and (device is None or e.device == device)]
        out = out[:limit]
        return out, (out[-1].seq if out else cursor)

    def last(self, kind: str | None = None) -> Event | None:
        for e in reversed(self.ring):
            if kind is None or e.kind == kind:
                return e
        return None
