"""Рухома техніка: навантажувачі FL-*, тягач TUGGER-1 (R-05, R-06, R-19; SPEC §8.8, §10).

Стани (``mstate``): idle, busy, to_charge, charging, offline (``fault comm``), fault. У сигнал ``state``
``to_charge`` віддається як ``busy`` (для переглядача, §8.8.1); повний стан — ``mstate``/``telemetry()``.

* R-05: ``charging`` -> ``v += 4·rate·dt_min`` до 95 (потім idle і далі завдання); у ``busy``/``to_charge``
  ``v -= rate·(1 + 0,3 r)·dt_min``; ``v ≤ limit`` (20) -> ``to_charge`` (їде в ``Z-CHG``), на місці — ``charging``.
* R-06: ``hours += dt/3600`` у ``busy``/``to_charge``.
* R-19: маршрут між центроїдами зон (``params["route"]``, полігони — ``catalog/zones.json`` або
  ``set_zones()``), 6 км/год, стоянка 90 с на кінцях; поза зміною — ``idle`` у ``Z-CHG``;
  ``x, y`` — лінійна інтерполяція, ``zone`` — полігон, що містить точку, ``heading`` — напрям.
* ``outbox`` — події для MQTT (``charge_start|charge_end|low_battery|fault|task_start|task_end``).
"""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model

SPEED_MS = 6.0 / 3.6
DWELL_S = 90.0
CHARGE_LIMIT_DEFAULT = 20.0
FULL = 95.0
CHARGE_ZONE = "Z-CHG"
_ZONES: dict[str, dict[str, Any]] | None = None


def set_zones(zones: list[dict[str, Any]] | None) -> None:
    """Підміна полігонів зон (API-01 ``zones[]``); ``None`` -> перечитати ``catalog/zones.json``."""
    global _ZONES
    _ZONES = None if zones is None else {z["code"]: _norm(z) for z in zones}


def _norm(z: dict[str, Any]) -> dict[str, Any]:
    poly = [tuple(p) for p in z["polygon"]]
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    return {"code": z["code"], "polygon": poly, "centroid": (cx, cy)}


def zones() -> dict[str, dict[str, Any]]:
    global _ZONES
    if _ZONES is None:
        path = Path(__file__).resolve().parents[2] / "catalog" / "zones.json"
        data = json.loads(path.read_text(encoding="utf-8"))["zones"]
        _ZONES = {z["code"]: _norm(z) for z in data}
    return _ZONES


def point_in_polygon(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def zone_at(x: float, y: float) -> str | None:
    for code, z in zones().items():
        if point_in_polygon(x, y, z["polygon"]):
            return code
    return None


@register_model("mobile")
class Mobile(Model):
    def attach(self) -> None:
        p = self.device.params
        self.route: list[str] = list(p.get("route", [CHARGE_ZONE]))
        self.home: str = p.get("home", CHARGE_ZONE)
        bat = self.sig("battery")
        self.rate = bat.params["rate"] or 0.15
        self.limit = bat.params["limit"] or CHARGE_LIMIT_DEFAULT
        self.battery = float(bat.value)
        self.mstate = "idle"
        self.prev_state = "idle"
        self.pos = self._centroid(self.route[0])
        self.heading = 0.0
        self.speed_ms = 0.0
        self.leg = 1 if len(self.route) > 1 else 0
        self.dir = 1
        self.dwell = 0.0
        self.hours = float(self.val("hours", 0.0))
        self.outbox: deque[dict[str, Any]] = deque(maxlen=1000)
        self.low_sent = False

    @staticmethod
    def _centroid(code: str) -> tuple[float, float]:
        return zones()[code]["centroid"]

    def emit(self, typ: str, **detail: Any) -> None:
        self.outbox.append({"ts": self.world.now().isoformat(), "code": self.device.code, "type": typ,
                            "detail": detail})

    def _set_state(self, st: str) -> None:
        if st != self.mstate:
            old, self.mstate = self.mstate, st
            if st == "charging":
                self.emit("charge_start", battery_pct=round(self.battery, 1))
            elif old == "charging":
                self.emit("charge_end", battery_pct=round(self.battery, 1))
            elif st == "busy" and old == "idle":
                self.emit("task_start", route=self.route)
            elif st == "idle" and old == "busy":
                self.emit("task_end", route=self.route)
            elif st == "to_charge":
                self.emit("low_battery", battery_pct=round(self.battery, 1))

    # --- рух ----------------------------------------------------------------------------
    def _go(self, target: tuple[float, float], dt: float) -> float:
        """Рух до точки; повертає невикористаний час (>0, якщо дісталися)."""
        dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
        dist = math.hypot(dx, dy)
        if dist < 1e-9:
            self.speed_ms = 0.0
            return dt
        self.heading = math.degrees(math.atan2(dy, dx)) % 360
        need = dist / SPEED_MS
        if need <= dt:
            self.pos = target
            self.speed_ms = 0.0
            return dt - need
        k = SPEED_MS * dt / dist
        self.pos = (self.pos[0] + dx * k, self.pos[1] + dy * k)
        self.speed_ms = SPEED_MS
        return 0.0

    def _route_step(self, dt: float) -> None:
        if len(self.route) < 2:
            self.speed_ms = 0.0
            return
        left = dt
        while left > 1e-9:
            if self.dwell > 0:
                used = min(self.dwell, left)
                self.dwell -= used
                left -= used
                self.speed_ms = 0.0
                continue
            target = self._centroid(self.route[self.leg])
            left = self._go(target, left)
            if math.hypot(target[0] - self.pos[0], target[1] - self.pos[1]) > 1e-9:
                break  # у русі
            self.dwell = DWELL_S
            nxt = self.leg + self.dir
            if nxt < 0 or nxt >= len(self.route):
                self.dir = -self.dir
                nxt = self.leg + self.dir
            self.leg = nxt

    # --- тік ----------------------------------------------------------------------------
    def tick(self, dt_s: float) -> None:
        w = self.world
        in_shift = w.shift.in_shift(w.now())
        fault = self.device.fault
        bl = w.flags.get("battery_low")  # S-10: сценарій battery_low задає заряд моделі (прапор «одноразовий»)
        if isinstance(bl, dict) and self.device.code in bl:
            self.battery = max(0.0, min(100.0, float(bl.pop(self.device.code))))
        if fault == "comm":
            self._set_state("offline")
            self.speed_ms = 0.0
            self._publish()
            return
        if fault:
            self._set_state("fault")
            self.speed_ms = 0.0
            self._publish()
            return
        if self.mstate in ("offline", "fault"):
            self._set_state("idle")
        # R-05
        if self.mstate == "charging":
            self.battery = min(FULL, self.battery + 4 * self.rate * self.dt_min)
            if self.battery >= FULL:
                self._set_state("idle")
        elif self.mstate in ("busy", "to_charge"):
            self.battery -= self.rate * (1 + 0.3 * self.r("battery")) * self.dt_min
            self.hours += dt_s / 3600  # R-06
        self.battery = max(0.0, min(100.0, self.battery))
        # перехід за станом заряду / зміни
        if self.mstate != "charging":
            low = self.battery <= self.limit
            if low:
                if self.mstate != "to_charge":
                    self._set_state("to_charge")
            elif self.mstate == "to_charge" or (in_shift and self.mstate == "idle"):
                self._set_state("busy")
            elif not in_shift and self.mstate == "busy":
                self._set_state("idle")
        # рух
        home = self._centroid(self.home)
        if self.mstate == "to_charge" or (self.mstate == "idle" and not in_shift):
            left = self._go(self._centroid(CHARGE_ZONE), dt_s)
            if self.mstate == "to_charge" and left > 0:
                self._set_state("charging")
        elif self.mstate == "busy":
            self._route_step(dt_s)
        elif self.mstate == "idle":
            self._go(home, dt_s)
        else:
            self.speed_ms = 0.0
        self._publish()

    def _publish(self) -> None:
        self.set("battery", self.battery)
        self.set("hours", self.hours)
        self.set("state", "busy" if self.mstate == "to_charge" else self.mstate)
        self.set("x", round(self.pos[0], 2))
        self.set("y", round(self.pos[1], 2))

    @property
    def zone(self) -> str | None:
        return zone_at(*self.pos)

    def telemetry(self) -> dict[str, Any]:
        """Схема ``telemetry`` §8.8.1 (``to_charge`` лишається повним станом)."""
        return {"ts": self.world.now().isoformat(), "code": self.device.code, "state": self.mstate,
                "battery_pct": round(self.battery, 1), "charging": self.mstate == "charging",
                "hours": round(self.hours, 1), "x": round(self.pos[0], 2), "y": round(self.pos[1], 2),
                "heading_deg": round(self.heading), "speed_kmh": round(self.speed_ms * 3.6, 1),
                "zone": self.zone, "task": f"{self.route[0]}→{self.route[-1]}" if self.mstate == "busy" else None,
                "faults": [self.device.fault] if self.device.fault else []}

    def get_state(self) -> dict[str, Any]:
        return {"mstate": self.mstate, "pos": list(self.pos), "leg": self.leg, "dir": self.dir,
                "dwell": self.dwell, "battery": self.battery, "hours": self.hours}

    def set_state(self, d: dict[str, Any]) -> None:
        self.mstate = d.get("mstate", "idle")
        self.pos = tuple(d.get("pos", self.pos))
        self.leg, self.dir, self.dwell = d.get("leg", 0), d.get("dir", 1), d.get("dwell", 0.0)
        self.battery = d.get("battery", self.battery)
        self.hours = d.get("hours", self.hours)
