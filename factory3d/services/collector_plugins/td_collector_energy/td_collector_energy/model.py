"""Спільні типи рушія: запис, запит ресурсу, подія, вихід сценарію, середовище кроку (R-44)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import Config
from .inputs import Inputs

RESOURCES = ("bess", "chp", "shed", "pv", "vent", "light", "pfc", "qs", "air")
# пріоритет арбітражу (R-44 п.4): перекриття оператора > backup > peak > self > slots > chp > night > pfc
PRIORITY = ("backup", "peak", "self", "slots", "chp", "night", "pfc")
EVENT_KINDS = ("auto_step", "auto_release", "interlock", "override", "failsafe", "mode", "config")


@dataclass
class W:
    """Один запис: `target` — логічне ім'я (`cfg.signals`) або код сигналу (шлях із «/»)."""

    target: str
    value: float | None = None
    text: str | None = None


@dataclass
class Request:
    """Бажаний стан ресурсу від сценарію; `watchdog` — сигнал сторожового таймера (перезапис кожні `refresh_s`)."""

    resource: str
    writes: list[W]
    scenario: str = ""
    watchdog: str | None = None
    refresh_s: float | None = None


@dataclass
class Event:
    scenario: str | None
    kind: str
    text: str
    signal: str | None = None
    value: float | None = None
    result: str = "виконано"
    level: str = "info"

    def to_dict(self, now: datetime) -> dict[str, Any]:
        from collector.util.timeutil import to_iso_z

        return {
            "event_id": uuid.uuid4().hex,
            "ts": to_iso_z(now),
            "scenario": self.scenario or "",
            "kind": self.kind,
            "text": self.text[:256],
            "signal": self.signal,
            "value": self.value,
            "result": self.result,
        }


@dataclass
class Output:
    state: str = "off"  # off | armed | active | warn
    facts: dict[str, Any] = field(default_factory=dict)
    requests: list[Request] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)


@dataclass
class Env:
    """Усе, що крок сценарію бачить за тік (читає лише `inp`/`cfg`/`now`; стан — у `shared` і `scen`)."""

    inp: Inputs
    cfg: Config
    now: datetime
    shared: dict[str, Any]  # довговічний стан рушія (Store): `shed_list`, `chp`, `bess_owner`, `blocked_until`…
    scen: dict[str, dict[str, Any]]  # стан кожного сценарію (Store)
    overrides: dict[str, dict[str, Any]] = field(default_factory=dict)  # активні ручні перекриття оператора
    blocked: set[str] = field(default_factory=set)  # ресурси, закриті на цей тік (пожежа, відмова запису)
    outputs: dict[str, Output] = field(default_factory=dict)  # виходи вже виконаних у тіку сценаріїв

    @property
    def epoch(self) -> float:
        return self.now.timestamp()

    def state(self, code: str) -> dict[str, Any]:
        return self.scen.setdefault(code, {})

    def overridden(self, resource: str) -> bool:
        return resource in self.overrides

    def free(self, resource: str) -> bool:
        return resource not in self.overrides and resource not in self.blocked
