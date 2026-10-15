"""Вода (R-21): витрата ``q`` і імпульсний лічильник ADAM-6050 DI8 (10 л/імп).

``q = 2,1 м³/год`` у зміні, ``0,3`` поза нею, ``+1,5`` під час роботи фарбування (SPRAY-1/AUTOSPRAY-1 у стані
WORKING); імпульси ``n = floor(q·dt/3600·100)`` (залишок переноситься); ``m3_total = 18 642 + Σ n/100``;
``flow_m3h`` — ковзне середнє ``q`` за 5 хв.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model

M3_START = 18642.0
Q_SHIFT, Q_OFF, Q_PAINT = 2.1, 0.3, 1.5
WINDOW_S = 300.0
PAINT_MACHINES = ("SPRAY-1", "AUTOSPRAY-1")


def is_working(world, code: str) -> bool:
    """Верстат WORKING: за ``world.workcenters[code]["state"]``, інакше — за потужністю > 50 % номіналу."""
    wc = world.workcenters.get(code)
    if wc and "state" in wc:
        return str(wc["state"]).upper() == "WORKING"
    s = world.signals.get(f"energy/consumers/{code}/p_now")
    if s is None:
        return False
    return float(s.value) > 0.5 * float(s.params.get("nominal") or 0.0) > 0


@register_model("water")
class Water(Model):
    def attach(self) -> None:
        self.pulses = 0
        self.frac = 0.0
        self.samples: deque[tuple[float, float]] = deque()
        self.set("m3_total", M3_START)

    def flow(self) -> float:
        q = Q_SHIFT if self.world.shift.in_shift(self.world.now()) else Q_OFF
        if any(is_working(self.world, c) for c in PAINT_MACHINES):
            q += Q_PAINT
        return q

    def tick(self, dt_s: float) -> None:
        q = self.flow()
        self.frac += q * dt_s / 3600.0 * 100.0
        n = math.floor(self.frac)
        self.frac -= n
        self.pulses += n
        self.set("m3_total", M3_START + self.pulses / 100.0)
        self.samples.append((dt_s, q))
        span = sum(d for d, _ in self.samples)
        while span - self.samples[0][0] >= WINDOW_S:
            span -= self.samples.popleft()[0]
        if span > 0:  # тік dt = 0 (world.step(0)) не дає вікна усереднення
            self.set("flow_m3h", sum(d * v for d, v in self.samples) / span)

    def get_state(self) -> dict[str, Any]:
        return {"pulses": self.pulses, "frac": self.frac}

    def set_state(self, d: dict[str, Any]) -> None:
        self.pulses = int(d.get("pulses", 0))
        self.frac = float(d.get("frac", 0.0))
