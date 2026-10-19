"""Витратомір стисненого повітря AIR-MAIN (W3, SPEC §8.1; unit 75): витрата, тиск і лічильник магістралі.

``act = clamp((load − load_min)/(load_ref − load_min), 0, 1,3)``, ``load = equipment/COMPRESSOR/load``;
``flow = leak + leak_extra + (q_ref − leak)·act`` м³/хв; ``leak_extra`` — прапор ``air_leak`` (сценарій ``air_leak``:
число
або ``{"leak_extra": …}``, м³/хв). ``pressure = equipment/COMPRESSOR/pressure_bar − drop``; ``m3_total += flow·dt/60`` з
квантом 0,1 норм. м³ (залишок переноситься). Приклад: ``load = 66`` → 9,8 м³/хв, ``load = 25`` (ніч) → 1,6.

Параметри пристрою (``devices.yaml``): ``leak`` 1,6, ``q_ref`` 9,8, ``load_ref`` 66, ``load_min`` 25, ``drop`` 0,1.
Фаза ``aggregate``: компресор уже порахував ``load`` і тиск цього тіка.
"""

from __future__ import annotations

import math
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model
from iot_sim.models.meter import get
from iot_sim.models.water import flag_extra

M3_START = 6420.0
QUANT_M3 = 0.1
ACT_MAX = 1.3
LOAD = "equipment/COMPRESSOR/load"
PRESSURE = "equipment/COMPRESSOR/pressure_bar"


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@register_model("air")
class Air(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        p = self.device.params
        self.leak = float(p.get("leak", 1.6))
        self.q_ref = float(p.get("q_ref", 9.8))
        self.load_ref = float(p.get("load_ref", 66.0))
        self.load_min = float(p.get("load_min", 25.0))
        self.drop = float(p.get("drop", 0.1))
        self.pulses = 0
        self.frac = 0.0
        self.set("m3_total", M3_START)

    def flow(self) -> float:
        """Витрата магістралі, м³/хв, за завантаженням компресора і витоком сценарію."""
        span = self.load_ref - self.load_min
        act = clamp((float(get(self.world, LOAD)) - self.load_min) / span, 0.0, ACT_MAX) if span > 0 else 0.0
        extra = flag_extra(self.world, "air_leak", "leak_extra")
        return self.leak + extra + (self.q_ref - self.leak) * act

    def tick(self, dt_s: float) -> None:
        flow = self.flow()
        self.frac += flow * dt_s / 60.0 / QUANT_M3
        n = math.floor(self.frac)
        self.frac -= n
        self.pulses += n
        self.set("flow_m3min", flow)
        self.set("pressure_bar", float(get(self.world, PRESSURE)) - self.drop)
        self.set("m3_total", round(M3_START + self.pulses * QUANT_M3, 1))

    def get_state(self) -> dict[str, Any]:
        return {"pulses": self.pulses, "frac": self.frac}

    def set_state(self, d: dict[str, Any]) -> None:
        self.pulses = int(d.get("pulses", 0))
        self.frac = float(d.get("frac", 0.0))
