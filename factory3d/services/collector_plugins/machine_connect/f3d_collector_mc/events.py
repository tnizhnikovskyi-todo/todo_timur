"""Події PushEvent (§7.1), метрики пакета й спільні помічники."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from collector.core.types import PushEvent
from prometheus_client import Counter

MAX_EVENT_BYTES = 256 * 1024


def canonical_json(obj: Any) -> str:
    """Канонічний JSON для event_id: відсортовані ключі, без пробілів, UTF-8 без екранування."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_id(route: str, source_code: str, payload: dict) -> str:
    """sha256 hex від `route \\n source \\n canonical_json(payload)` (§7.1)."""
    raw = f"{route}\n{source_code}\n{canonical_json(payload)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_event(route: str, source_code: str, payload: dict, ts: datetime | None = None) -> PushEvent:
    """PushEvent для `ctx.emit_event`: `remote` = код джерела, `headers={}`."""
    return PushEvent(
        event_id=event_id(route, source_code, payload),
        route=route,
        ts=ts or datetime.now(UTC),
        remote=source_code,
        headers={},
        payload=payload,
    )


def inc_metric(ctx: Any, name: str, **labels: str) -> None:
    """Лічильник `collector_mc_*_total` у реєстрі метрик ядра (створюється при першому використанні)."""
    metrics = getattr(ctx, "metrics", None)
    registry = getattr(metrics, "registry", None)
    if registry is None:
        return
    cache = metrics.__dict__.setdefault("_mc_counters", {})
    base = name.removesuffix("_total")
    counter = cache.get(base)
    if counter is None:
        counter = cache[base] = Counter(base, f"Лічильник {base}", sorted(labels), registry=registry)
    counter.labels(**labels).inc()


def state_dir(ctx: Any) -> Path:
    """Каталог курсорів адаптерів: `settings.mc_state_dir`, інакше F3D_MC_STATE_DIR, інакше каталог буфера."""
    settings = ctx.settings
    value = (
        getattr(settings, "mc_state_dir", None)
        or os.environ.get("F3D_MC_STATE_DIR")
        or getattr(settings, "buffer_dir", ".")
    )
    return Path(value)
