"""Димовидалення D+H CPS-M1 (SMOKE-CTRL; R-27, SPEC §8.11.3, ADAM-6050 u85 DI4…DI6).

* DI4 (``state``) — клапани відкриті: 1, якщо ``drill_view`` тримає крок ``dampers`` (тривога/навчання, R-25)
  або ``DO0`` отримав імпульс (``world.post("smoke", {"cmd": "open"})``; ``close`` — DO1); команда виконується
  за 60 с (відкриття) / 90 с (закриття після скидання). Каскад R-25 ставить/знімає DI4 одразу (кроки +9 с / відкат).
* DI5 (``fault``) — несправність щита: ``fault()`` або 72 год роботи від АКБ.
* DI6 (``battery``) — 1 під час ``blackout`` (фаза ``outage``).
``Model.set`` поважає ``held_until``: запис споживача/сценарію зверху (force) має пріоритет.
"""

from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.facp import drill_view

OPEN_S = 60.0
CLOSE_S = 90.0
BATTERY_S = 72 * 3600.0


@register_model("smoke")
class Smoke(Model):
    def attach(self) -> None:
        self.open = False
        self.cmd_open = False
        self.timer = 0.0  # залишок ходу клапанів до зміни стану за командою DO0/DO1
        self.pending: bool | None = None
        self.battery_s = 0.0

    def tick(self, dt_s: float) -> None:
        w = self.world
        for cmd in w.drain("smoke"):
            want = cmd.get("cmd") == "open"
            if want != self.cmd_open:
                self.cmd_open = want
                self.pending, self.timer = want, OPEN_S if want else CLOSE_S
        if self.pending is not None:
            self.timer -= dt_s
            if self.timer <= 0:
                self.open, self.pending = self.pending, None
        view = drill_view(w)
        drill = bool(view and view["steps"]["dampers"])
        bo = w.flags.get("blackout")
        on_battery = isinstance(bo, dict) and bo.get("phase") == "outage"
        self.battery_s = self.battery_s + dt_s if on_battery else 0.0
        self.set("state", int(self.open or drill))
        self.set("fault", int(self.device.fault not in (None, "comm") or self.battery_s >= BATTERY_S))
        self.set("battery", int(on_battery))

    def get_state(self) -> dict[str, Any]:
        return {"open": self.open, "cmd_open": self.cmd_open, "battery_s": self.battery_s}

    def set_state(self, d: dict[str, Any]) -> None:
        self.open = bool(d.get("open"))
        self.cmd_open = bool(d.get("cmd_open"))
        self.battery_s = d.get("battery_s", 0.0)
