"""Аспірація DUST-1 (ADAM-6017/6050) і загальний дрейф забивання фільтра (R-09, R-20).

``airflow_m3h`` — R-01; ``filter_dp_kpa`` — дрейф ``v ← v + rate·(1 + 0,5·r)·dt_min``; ``state`` — DI0 вентилятора
(1 = працює). Дрейф скидається до ``nominal`` після закриття заявки ТО (``World.maintenance_closed`` містить код
пристрою або сигналу), після ``clear`` і коли сценарій S-04 (``filter_clogged``) знято.
"""

from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model, noise_step


class Drift:
    """R-09 для одного сигналу пристрою (``key`` — короткий ключ у ``Device.signals``)."""

    def __init__(self, model: Model, key: str) -> None:
        self.model = model
        self.key = key
        self.clogged = False

    def reset(self) -> None:
        s = self.model.sig(self.key)
        s.force(s.params["nominal"], self.model.world.now())

    def step(self, active: bool = True) -> None:
        m, s = self.model, self.model.sig(self.key)
        closed = m.world.maintenance_closed
        hit = False
        for tag in (m.device.code, s.code):
            if tag in closed:
                closed.discard(tag)
                hit = True
        flags = m.world.flags.get("filter_clogged")
        present = isinstance(flags, dict) and m.device.code in flags
        released = self.clogged and not present
        self.clogged = present
        if hit or released:
            self.reset()
        elif active and s.params.get("rate"):
            m.set(self.key, float(s.value) + s.params["rate"] * (1 + 0.5 * m.r(self.key)) * m.dt_min)


@register_model("dust")
class Dust(Model):
    def attach(self) -> None:
        self.drift = Drift(self, "filter_dp_kpa")

    def on_clear(self) -> None:
        self.drift.reset()

    def tick(self, dt_s: float) -> None:
        running = self.device.fault is None
        for key in ("airflow_m3h", "p_now"):
            s = self.sig(key)
            nominal = float(s.params.get("nominal") or 0.0) if running else 0.0
            self.set(key, noise_step(float(s.value), nominal, s.params.get("noise") or 0.0, self.r(key), self.dt_min))
        self.drift.step(running)
        self.set("state", 1 if running else 0)  # DUST-1 — критична лінія (R-22): працює і в острові

    def get_state(self) -> dict[str, Any]:
        return {"clogged": self.drift.clogged}

    def set_state(self, d: dict[str, Any]) -> None:
        self.drift.clogged = bool(d.get("clogged", False))
