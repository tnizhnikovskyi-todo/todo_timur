"""Вода (R-21): витрата ``q`` і імпульсний лічильник ADAM-6050 DI8 (10 л/імп).

``q = 2,1 м³/год`` у зміні, ``0,3`` поза нею, ``+1,5`` під час роботи фарбування (SPRAY-1/AUTOSPRAY-1 у стані
WORKING); імпульси ``n = floor(q·dt/3600·100)`` (залишок переноситься); ``m3_total = 18 642 + Σ n/100``;
``flow_m3h`` — ковзне середнє ``q`` за 5 хв.

W3 (SPEC §8.1): підживлення котельні — ``boiler_m3_total += 0,0125·max(1, boilers_on)·dt/3600`` (квант 0,01 м³, залишок
переноситься; ``boilers_on`` = 1 при ``equipment/BOILER/state = 2``, 2 при ``3``, інакше 0), ``boiler_flow_m3h`` —
ковзне середнє за 5 хв; основна витрата ``q`` збільшується на цю підживлювальну. Прапор ``water_leak`` (сценарій
``water_leak``, число ``extra_m3h`` або ``{"extra_m3h": …}``) додає ``extra_m3h`` при ``23:00 ≤ t < 06:30`` (київський
час).
"""

from __future__ import annotations

import math
from collections import deque
from datetime import time
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model

M3_START = 18642.0
Q_SHIFT, Q_OFF, Q_PAINT = 2.1, 0.3, 1.5
WINDOW_S = 300.0
PAINT_MACHINES = ("SPRAY-1", "AUTOSPRAY-1")
BOILER_M3_START = 1205.0
BOILER_REFILL_M3H = 0.0125  # м³/год на один котел (мінімум — як на один)
LEAK_FROM, LEAK_TO = time(23, 0), time(6, 30)


def is_working(world: Any, code: str) -> bool:
    """Верстат WORKING: за ``world.workcenters[code]["state"]``, інакше — за потужністю > 50 % номіналу."""
    wc = world.workcenters.get(code)
    if wc and "state" in wc:
        return str(wc["state"]).upper() == "WORKING"
    s = world.signals.get(f"energy/consumers/{code}/p_now")
    if s is None:
        return False
    return float(s.value) > 0.5 * float(s.params.get("nominal") or 0.0) > 0


def flag_extra(world: Any, name: str, key: str) -> float:
    """Додатковий прибуток сценарію з прапора світу: число або ``{key: число}``; немає/некоректно -> 0."""
    v = world.flags.get(name)
    if isinstance(v, dict):
        v = v.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return 0.0
    return max(0.0, float(v))


def boilers_on(world: Any) -> int:
    """Кількість котлів у роботі за ``equipment/BOILER/state`` (1 standby, 2 K1, 3 K1+K2, 4 збій)."""
    s = world.signals.get("equipment/BOILER/state")
    try:
        state = round(float(s.value)) if s is not None else 1
    except (TypeError, ValueError):
        state = 1
    return {2: 1, 3: 2}.get(state, 0)


@register_model("water")
class Water(Model):
    def attach(self) -> None:
        self.pulses = 0
        self.frac = 0.0
        self.b_pulses = 0
        self.b_frac = 0.0
        self.samples: deque[tuple[float, float, float]] = deque()
        self.set("m3_total", M3_START)
        self.set("boiler_m3_total", BOILER_M3_START)

    def boiler_refill(self) -> float:
        """Підживлення котельні, м³/год: ``0,0125·max(1, boilers_on)``."""
        return BOILER_REFILL_M3H * max(1, boilers_on(self.world))

    def flow(self) -> float:
        """Основна витрата, м³/год: профіль + підживлення котельні + витік ``water_leak`` (23:00–06:30)."""
        now = self.world.now()
        q = Q_SHIFT if self.world.shift.in_shift(now) else Q_OFF
        if any(is_working(self.world, c) for c in PAINT_MACHINES):
            q += Q_PAINT
        t = now.time()
        if t >= LEAK_FROM or t < LEAK_TO:
            q += flag_extra(self.world, "water_leak", "extra_m3h")
        return q + self.boiler_refill()

    def tick(self, dt_s: float) -> None:
        q = self.flow()
        refill = self.boiler_refill()
        self.frac += q * dt_s / 3600.0 * 100.0
        n = math.floor(self.frac)
        self.frac -= n
        self.pulses += n
        self.set("m3_total", M3_START + self.pulses / 100.0)
        self.b_frac += refill * dt_s / 3600.0 * 100.0
        nb = math.floor(self.b_frac)
        self.b_frac -= nb
        self.b_pulses += nb
        self.set("boiler_m3_total", BOILER_M3_START + self.b_pulses / 100.0)
        self.samples.append((dt_s, q, refill))
        span = sum(d for d, _, _ in self.samples)
        while span - self.samples[0][0] >= WINDOW_S:
            span -= self.samples.popleft()[0]
        if span > 0:  # тік dt = 0 (world.step(0)) не дає вікна усереднення
            self.set("flow_m3h", sum(d * v for d, v, _ in self.samples) / span)
            self.set("boiler_flow_m3h", sum(d * b for d, _, b in self.samples) / span)

    def get_state(self) -> dict[str, Any]:
        return {"pulses": self.pulses, "frac": self.frac, "b_pulses": self.b_pulses, "b_frac": self.b_frac}

    def set_state(self, d: dict[str, Any]) -> None:
        self.pulses = int(d.get("pulses", 0))
        self.frac = float(d.get("frac", 0.0))
        self.b_pulses = int(d.get("b_pulses", 0))
        self.b_frac = float(d.get("b_frac", 0.0))
