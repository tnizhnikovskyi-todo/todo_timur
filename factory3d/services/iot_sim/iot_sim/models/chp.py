"""КГУ TEDOM Quanto D800 NG (R-12).

У штатному стані КГУ **в резерві** (``state = 0``, ``P_el = heat = gas = 0``): запуск — прапор світу ``chp_run``
(``world.set_flag("chp_run", True)``) або запис ненульового «Load setpoint» у HR 40007 (Modbus u72; 0 — зупинка);
зупинка проходить через охолодження (60 с), запуск — через ``starting`` (60 с). Далі, поки КГУ в роботі:
``load = 0,5`` вдень (``sun > 0,05``), ``1,0`` вночі і при ``outdoor_c < 0``; ``P_el = 800·load ± 4·r``,
``heat = 497 / 856``, ``gas = 109 / 199``, ``hours += dt/3600``, ``state = 2``. Острів (``blackout``):
``chp_island=false`` — ``state`` 2 → 4 (cooling down, 60 с) → 0, ``P_el = heat = 0``; після повернення
мережі 1 (starting, 60 с) → 2; ``chp_island=true`` — лишається в роботі:
``P_el = min(800·load ± 4·r, max(0, P_crit − pv_now))``.
"""
from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.meter import blackout, get, island, p_crit
from iot_sim.models.pv import sun_factor

P_NOM_KW = 800.0
RUN, STARTING, COOLING, STOPPED, FAULT = 2, 1, 4, 0, 3
TRANSITION_S = 60.0


@register_model("chp")
class Chp(Model):
    def attach(self) -> None:
        self.first = True
        self.hold_s = 0.0
        self.kwh = 0.0
        self.hours = float(self.val("hours", 0.0) or 0.0)

    def wanted(self) -> bool:
        """КГУ запущено командою (``chp_run``); за замовчуванням — резерв."""
        return bool(self.world.flags.get("chp_run", False))

    def _island_stops(self) -> bool:
        b = blackout(self.world)
        return island(self.world) and not (b or {}).get("chp_island", False)

    def _advance_state(self, state: int, dt_s: float) -> int:
        if self.device.fault is not None:
            return FAULT
        if state == FAULT:  # збій усунено
            state = RUN if self.wanted() else STOPPED
        if self._island_stops() or not self.wanted():
            if state in (RUN, STARTING):
                self.hold_s = TRANSITION_S
                return COOLING
        elif not island(self.world) and state == STOPPED:
            self.hold_s = TRANSITION_S
            return STARTING
        if state in (COOLING, STARTING):
            self.hold_s -= dt_s
            if self.hold_s <= 0:
                return STOPPED if state == COOLING else RUN
        return state

    def tick(self, dt_s: float) -> None:
        w = self.world
        state = int(self.val("state", RUN))
        if self.first:  # старт сервісу: штатно резерв, без «охолодження» з початкового номіналу каталогу
            self.first = False
            if state == RUN and not self.wanted():
                state = STOPPED
        state = self._advance_state(state, dt_s)
        sun = sun_factor(w)
        outdoor = float(get(w, "ventilation/totals/outdoor_c", 9.0))
        half = sun > 0.05 and outdoor >= 0
        p = P_NOM_KW * (0.5 if half else 1.0) + 4.0 * self.r("chp_kw")
        heat, gas = (497.0, 109.0) if half else (856.0, 199.0)
        if state != RUN:
            p = heat = gas = 0.0
        elif island(w):
            # у острові СЕС = 0 (R-11); pv_now поточного тіку ще міг не оновитися
            p = min(p, max(0.0, p_crit(w)))
        self.hours += dt_s / 3600.0 if state == RUN else 0.0
        self.kwh += p * dt_s / 3600.0
        self.set("state", state)
        self.set("chp_kw", p)
        self.set("heat_kw", heat)
        self.set("gas_m3h", gas)
        self.set("hours", self.hours)
        self.set("kwh_total", round(self.kwh, 4))

    def get_state(self) -> dict[str, Any]:
        return {"hold_s": self.hold_s, "kwh": self.kwh, "hours": self.hours}

    def set_state(self, d: dict[str, Any]) -> None:
        self.hold_s = float(d.get("hold_s", 0.0))
        self.kwh = float(d.get("kwh", 0.0))
        self.hours = float(d.get("hours", self.hours))
