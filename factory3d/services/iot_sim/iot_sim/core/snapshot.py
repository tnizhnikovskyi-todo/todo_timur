"""Знімок стану (SPEC §8.2.3, §11): JSON ``Signal.value/ts/status/held_until``, стани моделей,
``World`` (прапори, завдання, фури, черги), ``clock`` (``sim_now``), шумові генератори, активні запуски.

``save()`` пише атомарно (tmp + rename); ``load()`` повертає ``None`` для пошкодженого/старого
(> 24 год реального часу) знімка — тоді старт від каталогу.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from iot_sim.core.world import World

log = logging.getLogger("iot_sim.snapshot")
VERSION = 1
MAX_AGE_S = 24 * 3600
FILENAME = "snapshot.json"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def dump(world: World) -> dict[str, Any]:
    runs = {
        rid: r.to_dict()
        for rid, r in world.runs.items()
        if getattr(r, "state", "") in ("running", "queued", "stopping")
    }
    return {
        "version": VERSION,
        "saved_at": time.time(),
        "sim_now": world.now().isoformat(),
        "factor": world.clock.factor,
        "seed": world.seed,
        "minute0": world.minute0,
        "catalog_hash": world.registry.catalog_hash,
        "signals": {c: [s.value, _iso(s.ts), s.status, _iso(s.held_until)] for c, s in world.signals.items()},
        "devices": {c: d.model.to_dict() for c, d in world.devices.items()},
        "rng": {c: r.to_dict() for c, r in world._rngs.items()},
        "world": {
            "mode": world.mode,
            "flags": world.flags,
            "workcenters": world.workcenters,
            "jobs": world.jobs,
            "trucks": world.trucks,
            "people": world.people,
            "balance": world.balance,
            "maintenance_closed": sorted(world.maintenance_closed),
            "tick_count": world.tick_count,
        },
        "runs": runs,
    }


def restore(world: World, data: dict[str, Any]) -> None:
    from iot_sim.core.rng import Rng

    world.clock.set(datetime.fromisoformat(data["sim_now"]))
    for code, (value, ts, status, held) in data["signals"].items():
        sig = world.signals.get(code)
        if sig is None:  # сигнал зник з каталогу — ігноруємо
            continue
        sig.value, sig.ts, sig.status, sig.held_until = value, _dt(ts), status, _dt(held)  # type: ignore[assignment]
    w = data["world"]  # стан світу (люди тощо) — ДО моделей: AccessCtl.set_state будує розклад доби з world.people
    world.mode = w["mode"]
    world.flags = w["flags"]
    world.workcenters, world.jobs = w["workcenters"], w["jobs"]
    world.trucks, world.people, world.balance = w["trucks"], w["people"], w["balance"]
    world.maintenance_closed = set(w["maintenance_closed"])
    world.tick_count = w.get("tick_count", 0)
    world.minute0 = data.get("minute0", world.minute0)
    for code, d in data["devices"].items():
        dev = world.devices.get(code)
        if dev is not None:
            dev.model.from_dict(d)
    world._rngs = {}
    for code, d in data.get("rng", {}).items():
        rng = Rng(world.seed, code)
        rng.from_dict(d)
        world._rngs[code] = rng


def save(world: World, state_dir: str | Path) -> Path:
    d = Path(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / FILENAME
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(dump(world), ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load(state_dir: str | Path, max_age_s: float = MAX_AGE_S) -> dict[str, Any] | None:
    path = Path(state_dir) / FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["version"] != VERSION or not {"signals", "devices", "world", "sim_now"} <= data.keys():
            raise ValueError("bad structure")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        log.warning("snapshot ignored (corrupt): %s", exc)
        return None
    age = time.time() - data["saved_at"]
    if age > max_age_s:
        log.warning("snapshot ignored (too old: %.0f s)", age)
        return None
    log.info("restored snapshot from %s (age %.0f s)", data["sim_now"], age)
    return data  # type: ignore[no-any-return]
