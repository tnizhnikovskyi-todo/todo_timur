"""Компресор Atlas Copco GA 37 VSD+ (R-08).

``load = clamp(25 + 60·P_prod/P_prod_max, 20, 100)``, де ``P_prod`` — Σ ``p_now`` верстатів
(``P_prod_max`` — Σ їхніх номіналів, тобто «усі в роботі» = 85 %); тиск — R-01 навколо ``6,81``, при
``load > 95`` номінал знижується на 0,02 бар/хв до 6,2 (і так само повертається); сценарій
``compressor_fault`` (``kind``): ``pressure_drop`` — номінал 5,5 і ``state = 3``; ``overtemp`` —
``temp_c = 115``, ``state = 3``; ``comm`` — Modbus unit 70 недоступний (``fault("comm")``).
``temp_c = 70 + 0,2·load + 0,3·r``.
"""
from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model, noise_step

P_NOM = 6.81
P_MIN_OVERLOAD = 6.2
P_FAULT = 5.5
OVERLOAD_PCT = 95.0
LOAD_NOISE = 3.0


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def production(world: Any) -> tuple[float, float]:
    """``(P_prod, P_prod_max)`` — потужність верстатів зараз і при номіналі."""
    now = pmax = 0.0
    for dev in world.devices.values():
        if dev.driver != "machine":
            continue
        s = world.signals.get(f"energy/consumers/{dev.code}/p_now")
        if s is None:
            continue
        now += float(s.value)
        pmax += float(s.params.get("nominal") or 0.0)
    return now, pmax


@register_model("compressor")
class Compressor(Model):
    def attach(self) -> None:
        self.nominal = P_NOM
        self.hours = float(self.val("hours", 0.0) or 0.0)
        self.comm_from_flag = False

    def _fault_kind(self) -> str | None:
        f = self.world.flags.get("compressor_fault")
        return str(f.get("kind", "pressure_drop")) if isinstance(f, dict) else None

    def _sync_comm(self, kind: str | None) -> None:
        if kind == "comm" and self.device.fault is None:
            self.comm_from_flag = True
            self.fault("comm")
        elif kind != "comm" and self.comm_from_flag:
            self.comm_from_flag = False
            self.clear()

    def tick(self, dt_s: float) -> None:
        kind = self._fault_kind()
        self._sync_comm(kind)
        prod, pmax = production(self.world)
        target = clamp(25.0 + 60.0 * prod / pmax, 20.0, 100.0) if pmax > 0 else 25.0
        load = clamp(noise_step(float(self.val("load")), target, LOAD_NOISE, self.r("load"),
                                self.dt_min), 20.0, 100.0)
        step = 0.02 * self.dt_min
        if kind == "pressure_drop":
            self.nominal = P_FAULT
        elif self.nominal == P_FAULT:  # сценарій знято: тиск повертається до норми
            self.nominal = P_NOM
        elif load > OVERLOAD_PCT:
            self.nominal = max(P_MIN_OVERLOAD, self.nominal - step)
        else:
            self.nominal = min(P_NOM, self.nominal + step)
        self.set("load", load)
        self.set("pressure_bar", noise_step(float(self.val("pressure_bar")), self.nominal, 0.05,
                                            self.r("pressure_bar"), self.dt_min))
        temp = 115.0 if kind == "overtemp" else 70.0 + 0.2 * load + 0.3 * self.r("temp_c")
        self.set("temp_c", temp)
        faulty = kind in ("pressure_drop", "overtemp") or self.device.fault == "generic"
        self.set("state", 3 if faulty else 1)
        if not faulty:
            self.hours += dt_s / 3600.0
            self.set("hours", self.hours)
        nominal_p = float(self.sig("p_now").params.get("nominal") or 50.2)
        self.set("p_now", noise_step(float(self.val("p_now")), nominal_p * (0.4 + 0.6 * load / 64.0),
                                     2.0, self.r("p_now"), self.dt_min))

    def get_state(self) -> dict[str, Any]:
        return {"nominal": self.nominal, "hours": self.hours, "comm_from_flag": self.comm_from_flag}

    def set_state(self, d: dict[str, Any]) -> None:
        self.nominal = float(d.get("nominal", P_NOM))
        self.hours = float(d.get("hours", self.hours))
        self.comm_from_flag = bool(d.get("comm_from_flag", False))
