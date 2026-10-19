"""Корректор газу GAS-MAIN (W3, SPEC §8.1; unit 74): витрата і показання лічильника газу заводу.

``q = (BOILER + КГУ + сушарка + їдальня) · (1 + ε)`` м³/год: ``BOILER = equipment/BOILER/gas_m3h``, ``КГУ =
infra/chp/gas_m3h``, ``dry = dry_nom`` при роботі ``DRY-1`` (``models.water.is_working``), інакше 0, ``canteen = 1,0`` у будні
08:00–16:00 (київський час), інакше 0; ``ε = 0,01 + 0,004·r`` (``r`` — детермінований шум моделі, R-00). Прапор ``gas_extra``
(сценарій ``gas_overuse``: число ``extra_m3h`` або ``{"extra_m3h": …}``) додає ``extra_m3h`` м³/год вже після ``ε``.
``m3_total += q·dt/3600`` з квантом 0,01 м³ (залишок переноситься); ``flow_m3h = q``.

Фаза ``aggregate``: джерела (котельня, КГУ, верстати) вже порахували свої витрати цього тіка.
"""
from __future__ import annotations

import math
from datetime import time
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model
from iot_sim.models.meter import get
from iot_sim.models.water import flag_extra, is_working

M3_START = 31870.0
QUANT_M3 = 0.01
EPS0, EPS_AMP = 0.01, 0.004
DRY_NOM, CANTEEN = 6.0, 1.0
CANTEEN_FROM, CANTEEN_TO = time(8, 0), time(16, 0)
BOILER_GAS = "equipment/BOILER/gas_m3h"
CHP_GAS = "infra/chp/gas_m3h"


@register_model("gas")
class Gas(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        self.dry_nom = float(self.device.params.get("dry_nom", DRY_NOM))
        self.canteen_nom = float(self.device.params.get("canteen", CANTEEN))
        self.pulses = 0
        self.frac = 0.0
        self.q = 0.0
        self.set("m3_total", M3_START)

    def branches(self) -> dict[str, float]:
        """Гілки споживання газу, м³/год (без ``ε`` і ``gas_extra``)."""
        w = self.world
        now = w.now()
        canteen = now.weekday() < 5 and CANTEEN_FROM <= now.time() < CANTEEN_TO
        return {"boiler": float(get(w, BOILER_GAS)), "chp": float(get(w, CHP_GAS)),
                "dry": self.dry_nom if is_working(w, "DRY-1") else 0.0,
                "canteen": self.canteen_nom if canteen else 0.0}

    def tick(self, dt_s: float) -> None:
        eps = EPS0 + EPS_AMP * self.r("flow_m3h")
        q = sum(self.branches().values()) * (1.0 + eps) + flag_extra(self.world, "gas_extra", "extra_m3h")
        self.q = q
        self.frac += q * dt_s / 3600.0 / QUANT_M3
        n = math.floor(self.frac)
        self.frac -= n
        self.pulses += n
        self.set("m3_total", round(M3_START + self.pulses * QUANT_M3, 2))
        self.set("flow_m3h", q)

    def get_state(self) -> dict[str, Any]:
        return {"pulses": self.pulses, "frac": self.frac}

    def set_state(self, d: dict[str, Any]) -> None:
        self.pulses = int(d.get("pulses", 0))
        self.frac = float(d.get("frac", 0.0))
