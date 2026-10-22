"""Аспірація DUST-1 (ADAM-6017/6050) і загальний дрейф забивання фільтра (R-09, R-20).

``airflow_m3h`` — R-01; ``filter_dp_kpa`` — R-09; ``state`` — DI0 вентилятора (1 = працює).

R-09 (обмежений дрейф): у нормі перепад росте від ``nominal`` повільно й зі згасанням,
``v ← v + rate·(1 + 0,5·r)·dt_min·(стеля − v)/(стеля − nominal)``, де ``стеля = nominal + 0,75·(поріг − nominal)``
(120 → 217,5 Па при порозі 250; 1,0 → 1,6 кПа при порозі 1,8) — тож без сценарію поріг не досягається ніколи.
Швидкість ``rate`` з каталогу — початкова (при чистому фільтрі). Фільтр «замінюється» (скидання до ``nominal``), коли
перепад добирається до 90…98 % смуги ``nominal…стеля`` (частка детермінована від коду пристрою, щоб установки не
скидалися одночасно) — пилоподібний графік замість монотонного росту. Також скидання: закриття заявки ТО
(``World.maintenance_closed`` містить код пристрою або сигналу), ``clear`` і зняття сценарію S-04 (``filter_clogged``).
Поки сценарій S-04 активний, стелі немає: R-09 росте лінійно ``v ← v + rate·(1 + 0,5·r)·dt_min`` (навмисне забивання).
Значення, виставлене ззовні понад стелю (``force``), не змінюється: без сценарію воно не росте і не скидається.
"""

from __future__ import annotations

from typing import Any

from iot_sim.core.rng import det
from iot_sim.models import register_model
from iot_sim.models.base import Model, noise_step

BAND_FRAC = 0.75  # стеля норми: частка відстані від nominal до порога
CHANGE_FRAC_MIN = 0.90  # заміна фільтра при досягненні 90…98 % смуги nominal…стеля
CHANGE_FRAC_SPAN = 0.08


class Drift:
    """R-09 для одного сигналу пристрою (``key`` — короткий ключ у ``Device.signals``)."""

    def __init__(self, model: Model, key: str) -> None:
        self.model = model
        self.key = key
        self.clogged = False

    def reset(self) -> None:
        s = self.model.sig(self.key)
        s.force(s.params["nominal"], self.model.world.now())

    def band(self) -> tuple[float, float, float] | None:
        """``(nominal, стеля, рівень заміни фільтра)``; ``None`` — смуга не визначена (немає порога)."""
        p = self.model.sig(self.key).params
        nominal, thr = p.get("nominal"), p.get("threshold")
        if nominal is None or thr is None or float(thr) <= float(nominal):
            return None
        nominal = float(nominal)
        ceiling = nominal + BAND_FRAC * (float(thr) - nominal)
        frac = CHANGE_FRAC_MIN + CHANGE_FRAC_SPAN * (det(self.model.device.code) % 1000) / 1000.0
        return nominal, ceiling, nominal + frac * (ceiling - nominal)

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
            return
        rate = s.params.get("rate")
        if not (active and rate):
            return
        v = float(s.value)
        grow = float(rate) * (1 + 0.5 * m.r(self.key)) * m.dt_min
        band = None if present else self.band()
        if band is None:  # сценарій S-04 (або немає порога): лінійно, без стелі
            m.set(self.key, v + grow)
            return
        nominal, ceiling, change_at = band
        if change_at <= v <= ceiling:  # кінцевий перепад: планова заміна фільтра
            self.reset()
        elif v < ceiling:
            m.set(self.key, min(ceiling, v + grow * (ceiling - v) / (ceiling - nominal)))


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
