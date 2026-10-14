"""Лічильники PM5560 і спільні енергетичні хелпери (SPEC §8.7.2, R-03, R-13, R-22).

``meter`` (фаза ``aggregate``): фідери ``QF-*`` (unit 3–8) — сума своїх споживачів за ``energy.lines``
макета, а також інтеграл кВт·год кожного споживача (``kwh_total``/``kwh_shift``, R-03); вводи ``Q1``/``Q2``
(unit 1/2) — сума секції; ``Q2`` ще віднімає генерацію й додає заряд BESS (R-13). У острові
(``blackout``) вводи = 0, а лінії рахують лише критичних споживачів (R-22).

Хелпери модуля (``consumer_p``, ``total_load``, ``p_crit``, ``island``…) читають сигнали за повним кодом,
тому не залежать від колізій коротких ключів ``Device.signals``.

ASSUMPTION: ``kwh_total`` у сигналі — кВт·год (float); протокольний шар множить на 1000 (Вт·год, INT64).
"""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model, noise_step

LINE_CONSUMERS: dict[str, tuple[str, ...]] = {
    "BW-1": ("SAW-1", "SAW-2", "EDGE-1", "EDGE-2", "CNC-1", "CNC-2", "SORT-1"),
    "BW-2": ("SAW-3", "SLIDE-1", "VSAW-1", "NEST-1", "EDGE-3", "CNC-3", "BORE-1", "CNC-4",
             "DOWEL-1", "GANTRY-1"),
    "BW-3": ("SAND-1", "AUTOSPRAY-1", "UV-1", "HINGE-1", "GLUE-1", "PRESS-1", "SPRAY-1", "DRY-1"),
    "BW-4": ("ASMLINE-1", "ASM-1", "ASM-2", "ASM-3", "ASM-4", "ASM-5", "ASM-6", "PACK-1", "PACK-2",
             "BOX-1", "PACKLINE-1"),
    "C1": ("COMPRESSOR", "DUST-1", "BOILER"),
    "C2": ("CHARGING", "OFFICE", "LP-1", "LP-2", "LP-3", "RV-ALL", "AHU-1", "EF-ELEC", "EF-CMP",
           "EF-CHG"),
}
SECTIONS: dict[int, tuple[str, ...]] = {1: ("BW-3", "BW-2", "C1"), 2: ("BW-1", "BW-4", "C2")}
# R-22: ``CRITICAL`` макета (BW-1 — уся лінія, решта — окремі споживачі).
CRITICAL: frozenset[str] = frozenset(LINE_CONSUMERS["BW-1"]) | {
    "LP-1", "LP-2", "LP-3", "DUST-1", "COMPRESSOR", "BOILER", "OFFICE", "EF-ELEC", "EF-CHG"}
ALL_CONSUMERS: tuple[str, ...] = tuple(c for cs in LINE_CONSUMERS.values() for c in cs)
PF_TRANSFORMER = 0.97
V_LL = 400.0


# --- хелпери, спільні для моделей енергетики -------------------------------------------
def get(world, code: str, default: float = 0.0) -> Any:
    s = world.signals.get(code)
    return default if s is None else s.value


def put(world, code: str, value: Any) -> bool:
    s = world.signals.get(code)
    return False if s is None else s.set(value, world.now())


def blackout(world) -> dict[str, Any] | None:
    b = world.flags.get("blackout")
    return b if isinstance(b, dict) else None


def island(world) -> bool:
    """Мережі немає: сценарій ``blackout`` у фазі ``outage`` (R-22)."""
    b = blackout(world)
    return b is not None and b.get("phase", "outage") != "restoring"


def consumer_p(world, code: str) -> float:
    return float(get(world, f"energy/consumers/{code}/p_now", 0.0) or 0.0)


def p_crit(world) -> float:
    """Σ ``p_now`` критичних споживачів (R-22)."""
    return sum(consumer_p(world, c) for c in CRITICAL)


def total_load(world) -> float:
    """R-13: ``load = Σ p_now`` усіх споживачів; в острові — лише критичних."""
    if island(world):
        return p_crit(world)
    return sum(consumer_p(world, c) for c in ALL_CONSUMERS)


def section_p(world, section: int) -> float:
    if island(world):
        return 0.0
    return sum(consumer_p(world, c) for line in SECTIONS[section] for c in LINE_CONSUMERS[line])


def update_rv_all(world) -> None:
    """``RV-ALL`` = Σ потужностей вентиляторів RV-01…RV-25 (дзеркало PM5560 u55)."""
    total, seen = 0.0, False
    for code, s in world.signals.items():
        if code.startswith("ventilation/units/RV-") and code.endswith("/p_now"):
            total += float(s.value)
            seen = True
    if seen:
        put(world, "energy/consumers/RV-ALL/p_now", round(total, 3))


def apparent(p: float, pf: float) -> tuple[float, float, float]:
    """``(Q, S, I)``: ``Q = P·tan(acos PF)``, ``S = √(P²+Q²)``, ``I = S·1000/(√3·400)``."""
    q = p * math.tan(math.acos(min(max(pf, 0.01), 1.0)))
    s = math.hypot(p, q)
    return q, s, s * 1000.0 / (math.sqrt(3) * V_LL)


@register_model("meter")
class Meter(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        code = self.device.code
        self.cell = code in ("Q1", "Q2")
        self.line = ""
        for s in self.device.signals.values():
            parts = s.code.split("/")
            if parts[0] == "energy" and parts[1] == "lines":
                self.line = parts[2]
        self.e_wh: dict[str, float] = {}      # кожен споживач лінії, Вт·год
        self.base_wh: dict[str, float] = {}   # Вт·год на початок зміни
        self.shift_key: str | None = None
        self.own_wh = 0.0
        self.export_wh = 0.0
        self.pf = 0.9
        self.consumers = LINE_CONSUMERS.get(self.line, ())

    # --- зміна (R-03) ---------------------------------------------------------------
    def _shift_key(self) -> str:
        now = self.world.now()
        day = now.date() if now.time() >= self.world.shift.start else now.date() - timedelta(days=1)
        return day.isoformat()

    def _integrate_consumers(self) -> None:
        key = self._shift_key()
        for c in self.consumers:
            p = consumer_p(self.world, c)
            if c not in self.e_wh:  # старт: узгодити з початковими kwh_total / kwh_shift
                tot = float(get(self.world, f"energy/consumers/{c}/kwh_total", 0.0) or 0.0)
                self.e_wh[c] = tot * 1000.0
                shift = float(get(self.world, f"energy/consumers/{c}/kwh_shift", 0.0) or 0.0)
                self.base_wh[c] = self.e_wh[c] - shift * 1000.0
            self.e_wh[c] += p * 1000.0 * self.dt_s / 3600.0
            if self.shift_key is not None and key != self.shift_key:
                self.base_wh[c] = self.e_wh[c]
            put(self.world, f"energy/consumers/{c}/kwh_total", round(self.e_wh[c] / 1000.0, 6))
            put(self.world, f"energy/consumers/{c}/kwh_shift",
                round((self.e_wh[c] - self.base_wh[c]) / 1000.0, 6))
        self.shift_key = key

    # --- тік --------------------------------------------------------------------------
    def tick(self, dt_s: float) -> None:
        if self.cell:
            self._tick_cell()
        else:
            self._tick_feeder()

    def _currents(self, i: float) -> None:
        for ph in ("i_a", "i_b", "i_c"):
            self.set(ph, i * (1 + 0.03 * self.r(ph)))

    def _tick_feeder(self) -> None:
        self._integrate_consumers()
        isl = island(self.world)
        failed = self.device.fault is not None
        p = 0.0 if failed else sum(
            consumer_p(self.world, c) for c in self.consumers if not isl or c in CRITICAL)
        self.pf = min(0.97, max(0.8, noise_step(self.pf, 0.9, 0.02, self.r("cos_phi"), self.dt_min)))
        _, _, i = apparent(p, self.pf)
        self.own_wh += p * 1000.0 * self.dt_s / 3600.0
        self.set("p_now", p)
        self.set("i_now", i)
        self.set("cos_phi", self.pf)
        self._currents(i)
        self.set("kwh_total", round(self.own_wh / 1000.0, 6))
        self.set("state", 2 if failed else 1)

    def _tick_cell(self) -> None:
        w = self.world
        if self.device.code == "Q1":
            p = section_p(w, 1)
        elif island(w):
            p = 0.0
        else:
            gen = float(get(w, "infra/totals/pv_now")) + float(get(w, "infra/totals/chp_kw"))
            p = section_p(w, 2) - gen + float(get(w, "infra/totals/bess_kw"))
        failed = self.device.fault is not None
        if failed:
            p = 0.0
        q, _, i = apparent(p, PF_TRANSFORMER)
        wh = p * 1000.0 * self.dt_s / 3600.0
        self.own_wh += max(0.0, wh)
        self.export_wh += max(0.0, -wh)
        self.set("p_now", p)
        self.set("q_kvar", q)
        self.set("i_now", i)
        self._currents(i)
        self.set("kwh_total", round(self.own_wh / 1000.0, 6))
        self.set("kwh_export", round(self.export_wh / 1000.0, 6))
        self.set("state", 2 if failed else 1)

    def on_fault(self, reason: str, **kw: Any) -> None:
        self.set("state", 2)

    def get_state(self) -> dict[str, Any]:
        return {"e_wh": self.e_wh, "base_wh": self.base_wh, "shift_key": self.shift_key,
                "own_wh": self.own_wh, "export_wh": self.export_wh, "pf": self.pf}

    def set_state(self, d: dict[str, Any]) -> None:
        self.e_wh = dict(d.get("e_wh", {}))
        self.base_wh = dict(d.get("base_wh", {}))
        self.shift_key = d.get("shift_key")
        self.own_wh = float(d.get("own_wh", 0.0))
        self.export_wh = float(d.get("export_wh", 0.0))
        self.pf = float(d.get("pf", 0.9))
