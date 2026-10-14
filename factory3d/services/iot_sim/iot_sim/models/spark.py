"""Іскрогасіння GreCon SPARK-1 (R-26; SPEC §8.11.3, ADAM-6050 u85 DI0…DI3).

* DI0 (``state``) — імпульс 0,6 с, DI1 (``extinguishing``) — 2 с; ``count_today += 1``; подія WARNING
  «Іскрогасіння: іскру виявлено на магістралі аспірації над лінією A, гасіння 0,6 с».
* Сценарій S-08: ``world.post("spark", {"fault": bool, "index": i})`` -> негайна іскра; ``fault=true`` —
  DI2 (``fault``) = 1 на ``FAULT_HOLD_S`` (потім скидається) -> заявка у споживача.
* Фон: детермінований (``det``-керований) генератор із середнім 1 іскра/8 год у зміні, поки працює
  хоча б один SAW-*/NEST-1 (``current_state == WORKING``).
* Імпульс видно щонайменше один тік: значення пишуться до зменшення таймерів.
"""
from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model

DI0_S, DI1_S = 0.6, 2.0
FAULT_HOLD_S = 600.0
MEAN_PER_MIN = 1 / (8 * 60)  # 1 іскра / 8 год
LINES = ("A", "B", "C", "D")
SOURCES = ("SAW-1", "SAW-2", "SAW-3", "NEST-1")


@register_model("spark")
class Spark(Model):
    def attach(self) -> None:
        self.t_di0 = 0.0
        self.t_di1 = 0.0
        self.t_fault = 0.0
        self.count_total = 0
        self.count_today = int(self.val("count_today", 0) or 0)
        self.day: Any = None
        self.last_minute: int | None = None

    def trigger(self, fault: bool = False) -> None:
        self.t_di0, self.t_di1 = DI0_S, DI1_S
        self.count_today += 1
        self.count_total += 1
        line = LINES[self.count_total % len(LINES)]
        if fault:
            self.t_fault = FAULT_HOLD_S
        self.world.events.emit(
            "fire", f"Іскрогасіння: іскру виявлено на магістралі аспірації над лінією {line}, гасіння 0,6 с",
            device=self.device.code, payload={"line": line, "fault": fault, "level": "warn"})

    def _working(self) -> bool:
        for code in SOURCES:
            dev = self.world.devices.get(code)
            if dev is not None and getattr(dev.model, "current_state", None) == 3:
                return True
        return False

    def tick(self, dt_s: float) -> None:
        w = self.world
        now = w.now()
        if self.day != now.date():
            self.count_today = 0 if self.day is not None else self.count_today
            self.day = now.date()
        for cmd in w.drain("spark"):
            self.trigger(bool(cmd.get("fault")))
        minute = w.minute
        if minute != self.last_minute:
            self.last_minute = minute
            if w.shift.in_shift(now) and self._working() and (self.r("state") + 1) / 2 < MEAN_PER_MIN:
                self.trigger()
        self.set("state", int(self.t_di0 > 0))
        self.set("extinguishing", int(self.t_di1 > 0))
        self.set("fault", int(self.t_fault > 0 or self.device.fault not in (None, "comm")))
        self.set("water_ok", 0 if self.device.fault == "sensor" else 1)
        self.set("count_today", self.count_today)
        self.t_di0 = max(0.0, self.t_di0 - dt_s)
        self.t_di1 = max(0.0, self.t_di1 - dt_s)
        self.t_fault = max(0.0, self.t_fault - dt_s)

    def get_state(self) -> dict[str, Any]:
        return {"count_total": self.count_total, "count_today": self.count_today, "t_fault": self.t_fault}

    def set_state(self, d: dict[str, Any]) -> None:
        self.count_total = d.get("count_total", 0)
        self.count_today = d.get("count_today", 0)
        self.t_fault = d.get("t_fault", 0.0)
