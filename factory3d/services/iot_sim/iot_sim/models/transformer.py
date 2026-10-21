"""Трансформатор T1/T2 (R-04): ``S = √(P²+Q²)`` секції, ``temp_c = 38 + 60·S/1000 + 0,3·r``.

Трансформатор Tk живить ввід Qk, тож його потужність дорівнює потужності вводу ``energy/cells/Qk/p_now``: з урахуванням
СЕС, КГУ і BESS своєї секції (R-13), від'ємна — при віддачі в мережу, нуль — в острові (R-22). Раніше брали лише
навантаження секції; це давало два різні числа для одного регістра PM5560 u1/u2 (див. ``Ctx.sig_at``).
"""

from __future__ import annotations

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model
from iot_sim.models.meter import PF_TRANSFORMER, apparent, get


@register_model("transformer")
class Transformer(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        self.section = 2 if self.device.code.endswith("2") else 1

    def update(self, p_kw: float) -> None:
        """Записує вторинні величини за активною потужністю трансформатора (знак — напрямок потоку)."""
        _q, s, i = apparent(p_kw, PF_TRANSFORMER)
        self.set("p_kw", p_kw)
        self.set("s_kva", s)
        self.set("i_a", i)
        self.set("cos_phi", PF_TRANSFORMER)
        self.set("temp_c", 38.0 + 60.0 * s / 1000.0 + 0.3 * self.r("temp_c"))

    def tick(self, dt_s: float) -> None:
        # Q1/Q2 рахуються раніше (фаза aggregate, порядок за кодом пристрою: «Q» < «T»)
        self.update(float(get(self.world, f"energy/cells/Q{self.section}/p_now", 0.0) or 0.0))
