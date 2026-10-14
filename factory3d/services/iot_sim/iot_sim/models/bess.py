"""BESS LUNA2000 і баланс електроенергії (R-13).

Модель BESS рахується першою серед агрегатів (код ``BESS`` < ``Q1``), тому саме вона веде баланс:
``load = Σ p_now`` споживачів, ``gen = pv + chp``, ``surplus = gen − load``,
``bess_kw = clamp(surplus, −200, +200)`` з обмеженням за SOC (заряд при ``SOC < 100``, розряд при
``SOC > 10``), ``export = max(0, surplus − bess_kw)``, ``grid = max(0, load − gen − max(0, −bess_kw))``.
``bess_kw > 0`` — заряд. Острів (``blackout``): ``grid = export = 0``; до переключення ATyS у II розряд
``−min(200, P_crit)`` (лише при ``SOC > 10``), після — 0. ``grid_kw``/``export_kw`` належать пристрою
``EMS-1`` (пасивний) — пишемо їх за повним кодом сигналу.
"""
from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model
from iot_sim.models.meter import get, island, p_crit, put, total_load, update_rv_all

BESS_KW_MAX = 200.0
BESS_KWH = 387.0
SOC_MIN, SOC_MAX = 10.0, 100.0
ATS_POSITION = "infra/ats/position"


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@register_model("bess")
class Bess(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        self.charge_kwh = 0.0
        self.discharge_kwh = 0.0

    def balance(self) -> tuple[float, float, float]:
        """``(bess_kw, grid_kw, export_kw)`` за поточними значеннями сигналів."""
        w = self.world
        soc = float(self.val("bess_soc", 76.0))
        if island(w):
            crit = p_crit(w)
            switched = get(w, ATS_POSITION, 2) == 3
            bess = 0.0 if switched or soc <= SOC_MIN else -min(BESS_KW_MAX, crit)
            return bess, 0.0, 0.0
        load = total_load(w)
        gen = float(get(w, "infra/totals/pv_now")) + float(get(w, "infra/totals/chp_kw"))
        surplus = gen - load
        bess = clamp(surplus, -BESS_KW_MAX, BESS_KW_MAX)
        if (bess > 0 and soc >= SOC_MAX) or (bess < 0 and soc <= SOC_MIN):
            bess = 0.0
        export = max(0.0, surplus - bess)
        grid = max(0.0, load - gen - max(0.0, -bess))
        return bess, grid, export

    def tick(self, dt_s: float) -> None:
        update_rv_all(self.world)
        failed = self.device.fault is not None
        bess, grid, export = self.balance()
        if failed:
            bess = 0.0
        soc = float(self.val("bess_soc", 76.0))
        soc = clamp(soc + bess * dt_s / 3600.0 / BESS_KWH * 100.0, 0.0, SOC_MAX)
        self.set("bess_soc", soc)
        self.set("bess_kw", bess)
        put(self.world, "infra/totals/grid_kw", grid)
        put(self.world, "infra/totals/export_kw", export)
        self.charge_kwh += max(0.0, bess) * dt_s / 3600.0
        self.discharge_kwh += max(0.0, -bess) * dt_s / 3600.0
        self.set("kwh_charge_total", round(self.charge_kwh, 4))
        self.set("kwh_discharge_total", round(self.discharge_kwh, 4))
        self.set("state", 3 if failed else (2 if abs(bess) > 0.0 else 1))

    def get_state(self) -> dict[str, Any]:
        return {"charge_kwh": self.charge_kwh, "discharge_kwh": self.discharge_kwh}

    def set_state(self, d: dict[str, Any]) -> None:
        self.charge_kwh = float(d.get("charge_kwh", 0.0))
        self.discharge_kwh = float(d.get("discharge_kwh", 0.0))
