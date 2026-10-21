"""Цільові стани верстатів від Odoo (контракт C-LP-01 «Живе виробництво»; SPEC §7.2 API-26, R-LP-01…R-LP-05).

``td_live_production`` (через ``td_iot_sim``) шле ``POST /api/v1/machines/targets``: список
``{"code", "state": "working|idle|down", "reason", "until"}``. Поки ціль діє, модель верстата (``machine``,
``io_machine``) бере стан із неї (``working`` → WORKING, ``idle`` → READY, ``down`` → ERROR із повідомленням за
``reason``); навантаження, лічильники, події й сигнали ідуть за цим станом. Без цілі — автономна поведінка (R-14…R-17).

Сховище — ``world.flags["machine_targets"]`` (код → запис): тому ціль переживає рестарт зі знімком, а ``reset`` її
прибирає. ``until`` — **реальний** (настінний) час UTC, як його бачить Odoo: звіряється з реальним годинником
сервісу, а не з sim-часом (інакше зсув ``POST /time`` розійшовся б з Odoo). Запис, що прострочився, прибирається
ліниво (при читанні). Наступне оновлення того ж коду замінює ціль; ``until`` у минулому — знімає її.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from iot_sim.core.world import World

FLAG = "machine_targets"
STATES = ("working", "idle", "down")


@dataclass(frozen=True)
class Target:
    code: str
    state: str
    reason: str | None
    until: float  # епоха UTC, с
    set_at: str


def real_epoch(world: World) -> float:
    """Реальний (настінний) час сервісу, с; у тестах — підроблений годинник ``FakeClock``."""
    real = getattr(world.clock, "_real", None)
    return float(real()) if callable(real) else time.time()


def iso_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat().replace("+00:00", "Z")


def to_epoch(value: datetime) -> float:
    """``until`` → епоха UTC; без зони вважається UTC (контракт C-LP-01: ISO UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def is_machine(world: World, code: str) -> bool:
    from iot_sim.models.machine import Machine

    dev = world.devices.get(code)
    return dev is not None and isinstance(dev.model, Machine)


def machine_codes(world: World) -> list[str]:
    return sorted(c for c in world.devices if is_machine(world, c))


def _records(world: World) -> dict[str, dict[str, Any]]:
    rec = world.flags.get(FLAG)
    if not isinstance(rec, dict):
        rec = world.flags[FLAG] = {}
    return rec


def active_target(world: World, code: str) -> Target | None:
    """Чинна ціль верстата або ``None`` (немає / ``until`` минув — запис прибирається)."""
    rec = world.flags.get(FLAG)
    if not isinstance(rec, dict):
        return None
    item = rec.get(code)
    if item is None:
        return None
    if item["until"] <= real_epoch(world):
        del rec[code]
        return None
    return Target(code, item["state"], item.get("reason"), item["until"], item.get("set_at", ""))


def apply_targets(world: World, items: list[tuple[str, str, str | None, float]]) -> dict[str, Any]:
    """Прийняти цілі ``(code, state, reason, until_epoch)``: невідомий код — у ``unknown`` (решта діє),
    ``until`` у минулому — у ``expired`` (чинну ціль цього коду знято). Повертає ``{"ok", "unknown", "expired"}``."""
    now = real_epoch(world)
    records = _records(world)
    ok, unknown, expired = 0, [], []
    for code, state, reason, until in items:
        if not is_machine(world, code):
            if code not in unknown:
                unknown.append(code)
            continue
        if until <= now:
            records.pop(code, None)
            expired.append(code)
            continue
        records[code] = {
            "state": state,
            "reason": reason or None,
            "until": until,
            "set_at": world.now().isoformat(),
        }
        ok += 1
    return {"ok": ok, "unknown": unknown, "expired": expired}


def list_targets(world: World) -> list[dict[str, Any]]:
    """Чинні цілі (для ``GET``): код, стан, причина, ``until`` (ISO UTC), залишок, стан моделі зараз."""
    from iot_sim.models.machine import STATE_NAMES

    now = real_epoch(world)
    out = []
    for code in sorted(world.flags.get(FLAG) or {}):
        tgt = active_target(world, code)
        if tgt is None:
            continue
        model: Any = world.devices[code].model
        out.append(
            {
                "code": code,
                "state": tgt.state,
                "reason": tgt.reason,
                "until": iso_utc(tgt.until),
                "remaining_s": round(tgt.until - now, 1),
                "set_at": tgt.set_at,
                "machine_state": STATE_NAMES[model.current_state],
                "p_now_kw": round(float(getattr(model, "p_now", 0.0) or 0.0), 3),
            }
        )
    return out
