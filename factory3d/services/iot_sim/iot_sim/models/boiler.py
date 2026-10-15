"""Котельня BOILER (R-10): бункер брикетів і кількість котлів.

``need = heat_total_vent − chp_heat``; ``need ≤ 0 → 0``, ``need ≤ 0,85·495 → 1``, інакше ``2`` котли
(прапор ``boiler_force_on`` ≥ 0 перекриває). ``silo_fill ← silo_fill − rate·(1 + 0,3·r)·dt_min·k_fire``,
``k_fire = boilers_on`` (0 → лише ``0,1·rate`` на обігрів шнека); ``≤ limit (15)`` → ``nominal (95)`` і
подія «Бункер поповнено». ``supply_c`` — R-01 (78; при ``boilers_on = 0`` — 65), ``return_c = supply − 20·load``
(мінімум 7 К), ``heat_kw = min(need, 495·boilers_on)``. ``state``: 1 standby / 2 K1 / 3 K1+K2 / 4 fault.
"""
from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model, noise_step
from iot_sim.models.meter import get

BOILER_KW = 495.0
SINGLE_LIMIT = 0.85 * BOILER_KW
SUPPLY_ON, SUPPLY_OFF = 78.0, 65.0
SILO_REFILL = 95.0
SILO_RATE = 0.02
SILO_LIMIT = 15.0


def heat_total_vent(world: Any) -> float:
    return sum(float(s.value) for c, s in world.signals.items()
               if c.startswith("ventilation/units/") and c.endswith("/heat_kw"))


@register_model("boiler")
class Boiler(Model):
    def attach(self) -> None:
        self.boilers_on = 0
        self.need = 0.0
        self.refills = 0

    def _boilers(self, need: float) -> int:
        force = self.world.flags.get("boiler_force_on")
        if isinstance(force, int) and not isinstance(force, bool) and force >= 0:
            return min(2, force)
        if need <= 0:
            return 0
        return 1 if need <= SINGLE_LIMIT else 2

    def tick(self, dt_s: float) -> None:
        w = self.world
        failed = self.device.fault is not None
        self.need = heat_total_vent(w) - float(get(w, "infra/chp/heat_kw"))
        self.boilers_on = 0 if failed else self._boilers(self.need)
        silo = self.sig("silo_fill")
        rate = float(silo.params.get("rate") or SILO_RATE)
        limit = float(silo.params.get("limit") or SILO_LIMIT)
        k_fire = self.boilers_on if self.boilers_on else 0.1
        v = float(silo.value) - rate * (1 + 0.3 * self.r("silo_fill")) * self.dt_min * k_fire
        if v <= limit:
            v = float(silo.params.get("nominal") or SILO_REFILL)
            self.refills += 1
            self.world.events.emit("info", "Бункер поповнено", device=self.device.code,
                                   payload={"silo_fill": v})
        self.set("silo_fill", v)
        nominal = SUPPLY_ON if self.boilers_on else SUPPLY_OFF
        supply = noise_step(float(self.val("supply_c")), nominal, 0.4, self.r("supply_c"),
                            self.dt_min)
        heat = min(max(0.0, self.need), BOILER_KW * self.boilers_on)
        load = heat / (2 * BOILER_KW)
        self.set("supply_c", supply)
        self.set("return_c", supply - max(7.0, 20.0 * load))
        self.set("heat_kw", heat)
        self.set("state", 4 if failed else 1 + self.boilers_on)
        p_nom = float(self.sig("p_now").params.get("nominal") or 10.0)
        self.set("p_now", p_nom * (0.8 + 0.2 * self.boilers_on))
        self.set("check", "дефіцит тепла" if self.need > 2 * BOILER_KW or failed else "норма")

    def get_state(self) -> dict[str, Any]:
        return {"boilers_on": self.boilers_on, "refills": self.refills}

    def set_state(self, d: dict[str, Any]) -> None:
        self.boilers_on = int(d.get("boilers_on", 0))
        self.refills = int(d.get("refills", 0))
