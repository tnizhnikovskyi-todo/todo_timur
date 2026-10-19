"""Вентустановки RV-01…RV-25, AHU-1 і витяжні вентилятори EF-* (R-23, R-09; SPEC §8.10.2).

``k`` за режимом: VE 0,85; AQ (``AQ_ECO``) ``0,55 + det(code) mod 30/100``; REC 0,45; VEL 0,35; ST/Off 0
(``params["k"]`` пристрою перекриває). ``airflow = 8000·k`` (AHU-1: ``20000·0,85``), ``supply_c = 19,5 + det/10``
(поза зміною 16), ``heat = 116,8·k·(18 − outdoor)/33·f`` (``f``: AQ 0,3; VE/VEL/REC/EA/SA 0,8; ST/Off 0),
AHU-1: ``airflow·1,2/3600·(21 − outdoor)``; ``heating_valve`` — у % (``100·clamp(heat/116,8, 0, 1)``);
``p_now = 8,6·k³ + 0,1``; ``filter_dp`` — R-09, ``filter_extract = 0,8·filter_dp``.

Режим міняється за календарем лише при зміні періоду (зміна → режим зони, поза нею — VEL, 22:00–06:00 — ST; обід
без змін), тож запис ззовні (BACnet MSV:1) живе до наступної зміни періоду. У ``blackout`` некритичні установки
(усі, крім EF-ELEC/EF-CHG) зупиняються (``ST``). EF-CHG: ``enabled=False`` при ``charging_active`` довше 60 с →
стан ``stopped_charging`` і подія ``alarm`` (bms A-20, X-40).

ASSUMPTIONS: режим VE у зміні — RV-01…RV-04 (приймання/відвантаження), REC — RV-21/22, решта AQ (``params["mode"]``
перекриває); ``charging_active`` — прапор ``world.flags["ef_chg_charging"]`` або ``CHARGING p_now > 1 кВт``;
``outdoor_c`` (±3 °C, 9 °C о 10:30) веде RV-01.
"""

from __future__ import annotations

import math
from datetime import time
from typing import Any

from iot_sim.core.rng import det
from iot_sim.models import register_model
from iot_sim.models.base import Model, noise_step
from iot_sim.models.dust import Drift
from iot_sim.models.meter import consumer_p, get, island

VE, VEL, AQ, REC, EA, SA, ST, OFF = 1, 2, 3, 4, 5, 6, 7, 8
HEAT_NOM = 116.8
F_BY_MODE = {AQ: 0.3, VE: 0.8, VEL: 0.8, REC: 0.8, EA: 0.8, SA: 0.8, ST: 0.0, OFF: 0.0}
K_BY_MODE = {VE: 0.85, VEL: 0.35, REC: 0.45, EA: 0.45, SA: 0.45, ST: 0.0, OFF: 0.0}
VE_UNITS = ("RV-01", "RV-02", "RV-03", "RV-04")
REC_UNITS = ("RV-21", "RV-22")
CRITICAL_FANS = ("EF-ELEC", "EF-CHG")
NIGHT_FROM, NIGHT_TO = time(22, 0), time(6, 0)
ALARM_AFTER_S = 60.0


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@register_model("roofvent")
class Roofvent(Model):
    def attach(self) -> None:
        code = self.device.code
        self.is_fan = code.startswith("EF-")
        self.is_ahu = code == "AHU-1"
        self.det = det(code)
        self.drift = None if self.is_fan else Drift(self, "filter_dp_pa")
        self.period: str | None = None
        self.was_island = False
        self.enabled = True
        self.stopped_s = 0.0
        self.alarmed = False
        self.k = 0.0
        if not self.is_fan:
            self.update_mode(force=True)

    # --- режим за календарем -----------------------------------------------------------
    def zone_mode(self) -> int:
        forced = self.device.params.get("mode")
        if forced is not None:
            return int(forced)
        code = self.device.code
        if code in VE_UNITS or self.is_ahu:
            return VE
        return REC if code in REC_UNITS else AQ

    def _period(self) -> str | None:
        now = self.world.now()
        if now.time() >= NIGHT_FROM or now.time() < NIGHT_TO:
            return "night"
        if self.world.shift.in_shift(now):
            return None if self.world.shift.in_lunch(now) else "shift"
        return "off"

    def update_mode(self, force: bool = False) -> None:
        per = self._period()
        if per is None or (per == self.period and not force):
            return
        self.period = per
        self.sig("mode").force({"shift": self.zone_mode(), "off": VEL, "night": ST}[per], self.world.now())

    # --- параметри режиму ----------------------------------------------------------------
    def fraction(self, mode: int) -> float:
        if "k" in self.device.params and mode not in (ST, OFF):
            return float(self.device.params["k"])
        if mode == AQ:
            return 0.55 + (self.det % 30) / 100.0
        return K_BY_MODE.get(mode, 0.0)

    def running(self) -> bool:
        if self.device.fault is not None or not self.enabled:
            return False
        return not (island(self.world) and self.device.code not in CRITICAL_FANS)

    # --- тік --------------------------------------------------------------------------
    def tick(self, dt_s: float) -> None:
        if self.device.code == "RV-01":
            self._outdoor()
        if self.is_fan:
            self._tick_fan()
        else:
            self._tick_unit()

    def _outdoor(self) -> None:
        now = self.world.now()
        h = now.hour + now.minute / 60.0
        self.set("outdoor_c", 9.0 + 3.0 * math.sin(2 * math.pi * (h - 10.5) / 24.0))

    def _tick_unit(self) -> None:
        isl_stop = island(self.world) and self.device.code not in CRITICAL_FANS
        if isl_stop:
            self.sig("mode").force(ST, self.world.now())
            self.was_island = True
        elif self.was_island:
            self.was_island = False
            self.update_mode(force=True)
        else:
            self.update_mode()
        mode = int(self.val("mode", AQ))
        run = self.running() and mode not in (ST, OFF)
        self.k = self.fraction(mode) if run else 0.0
        in_shift = self.world.shift.in_shift(self.world.now())
        outdoor = float(get(self.world, "ventilation/totals/outdoor_c", 9.0))
        s_air, s_sup = self.sig("airflow_m3h"), self.sig("supply_c")
        if self.is_ahu:
            flow = 20000.0 * 0.85 if run else 0.0
            heat = max(0.0, flow * 1.2 / 3600.0 * (21.0 - outdoor))
        else:
            flow = 8000.0 * self.k
            heat = max(0.0, HEAT_NOM * self.k * (18.0 - outdoor) / 33.0 * F_BY_MODE.get(mode, 0.0))
        self.set(
            "airflow_m3h",
            noise_step(float(s_air.value), flow, s_air.params.get("noise") or 0.0, self.r("airflow_m3h"), self.dt_min)
            if run
            else 0.0,
        )
        sup_nom = (19.5 + (self.det % 10) / 10.0) if in_shift else 16.0
        self.set("supply_c", noise_step(float(s_sup.value), sup_nom, 0.2, self.r("supply_c"), self.dt_min))
        self.set(
            "indoor_c",
            noise_step(
                float(self.val("indoor_c")), 17.5 + (self.det % 10) / 10.0, 0.1, self.r("indoor_c"), self.dt_min
            ),
        )
        self.set("heat_kw", heat)
        self.set("heating_valve", round(100.0 * clamp(heat / HEAT_NOM, 0.0, 1.0)))
        fan_kw = 8.6 * self.k**3 + 0.1 if run else 0.0
        now = self.world.now()
        self.world.signals[f"ventilation/units/{self.device.code}/p_now"].set(fan_kw, now)
        cons = self.world.signals.get(f"energy/consumers/{self.device.code}/p_now")
        if cons is not None:  # AHU-1 — власний лічильник PM5560
            cons.set(9.3 * flow / 17000.0, now)
        assert self.drift is not None
        self.drift.step(run)
        self.set("filter_extract_dp_pa", 0.8 * float(self.val("filter_dp_pa")))
        if self.device.fault is not None:
            state = "fault"
        else:
            state = "running" if run else "stopped"
        self.set("state", state)

    def charging_active(self) -> bool:
        flag = self.world.flags.get("ef_chg_charging")
        if flag is not None:
            return bool(flag)
        return consumer_p(self.world, "CHARGING") > 1.0

    def _tick_fan(self) -> None:
        run = self.running()
        s = self.sig("airflow_m3h")
        nominal = float(s.params.get("nominal") or 0.0) if run else 0.0
        self.set(
            "airflow_m3h",
            noise_step(float(s.value), nominal, s.params.get("noise") or 0.0, self.r("airflow_m3h"), self.dt_min)
            if run
            else 0.0,
        )
        cons = self.world.signals.get(f"energy/consumers/{self.device.code}/p_now")
        if cons is not None:
            p_nom = float(cons.params.get("nominal") or 0.0)
            cons.set(
                noise_step(
                    float(cons.value),
                    p_nom if run else 0.0,
                    cons.params.get("noise") or 0.0,
                    self.world.r(cons.code),
                    self.dt_min,
                ),
                self.world.now(),
            )
        state = "fault" if self.device.fault is not None else ("running" if run else "stopped")
        if self.device.code == "EF-CHG" and state == "stopped" and self.charging_active():
            self.stopped_s += self.dt_s
            if self.stopped_s > ALARM_AFTER_S:
                state = "stopped_charging"
                if not self.alarmed:
                    self.alarmed = True
                    self.world.events.emit(
                        "alarm",
                        "EF-CHG: не працює під час заряджання — водень!",
                        device=self.device.code,
                        payload={"state": state},
                    )
        else:
            self.stopped_s = 0.0
            self.alarmed = False
        self.set("state", state)

    def on_clear(self) -> None:
        if self.drift is not None:
            self.drift.reset()

    def get_state(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "enabled": self.enabled,
            "stopped_s": self.stopped_s,
            "alarmed": self.alarmed,
            "clogged": self.drift.clogged if self.drift is not None else False,
        }

    def set_state(self, d: dict[str, Any]) -> None:
        self.period = d.get("period")
        self.enabled = bool(d.get("enabled", True))
        self.stopped_s = float(d.get("stopped_s", 0.0))
        self.alarmed = bool(d.get("alarmed", False))
        if self.drift is not None:
            self.drift.clogged = bool(d.get("clogged", False))
