"""Лічильники PM5560 і спільні енергетичні хелпери (SPEC §8.7.2, R-03, R-13, R-22).

``meter`` (фаза ``aggregate``): фідери ``QF-*`` (unit 3–8) — сума своїх споживачів за ``energy.lines``
макета, а також інтеграл кВт·год кожного споживача (``kwh_total``/``kwh_shift``, R-03); вводи ``Q1``/``Q2``
(unit 1/2) — сума секції; ``Q2`` ще віднімає генерацію й додає заряд BESS (R-13). У острові
(``blackout``) вводи = 0, а лінії рахують лише критичних споживачів (R-22).

Хелпери модуля (``consumer_p``, ``total_load``, ``p_crit``, ``island``…) читають сигнали за повним кодом,
тому не залежать від колізій коротких ключів ``Device.signals``.

ASSUMPTION: ``kwh_total`` у сигналі — кВт·год (float); протокольний шар множить на 1000 (Вт·год, INT64).

W2 (R-59, SPEC §8.2): вікно керування контролера ГРЩ. Прапори світу (``ctl(world, name)``, значення за замовчуванням —
``CTL_DEFAULTS``; ``POST /sim/v1/reset`` очищає всі прапори → стандартні значення): ``shed_limit`` ({вузол: % ліміту},
``shed_factor``), ``extra_load_kw`` (+/− до навантаження), ``export_target_kw`` (``export_demo``), ``qs_closed``.
Споживач віддає ``consumer_p · shed_factor``; при ``qs_closed`` потужності вводів Q1 і Q2 вирівнюються; сторожовий
таймер ``shed_valid_s`` (веде вводу Q1) повертає ліміти й ``pv_limit_pct`` до 100 %.

W3 (SPEC §8.1): вводи Q1/Q2 ведуть ``kvarh_total += |q_kvar|·dt/3600`` (квар·год; старт — номінал сигналу; «Reset All
Energies» обнуляє й його) — PM5560 «Reactive Energy Delivered», регістр pdu 3219 (i64, ×0,001).
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
def get(world: Any, code: str, default: float = 0.0) -> Any:
    s = world.signals.get(code)
    return default if s is None else s.value


def put(world: Any, code: str, value: Any) -> bool:
    s = world.signals.get(code)
    return False if s is None else s.set(value, world.now())


def blackout(world: Any) -> dict[str, Any] | None:
    b = world.flags.get("blackout")
    return b if isinstance(b, dict) else None


def island(world: Any) -> bool:
    """Мережі немає: сценарій ``blackout`` у фазі ``outage`` (R-22)."""
    b = blackout(world)
    return b is not None and b.get("phase", "outage") != "restoring"


# --- прапори вікна керування контролера ГРЩ (SPEC §8.2, R-59) ------------------------------
CTL_DEFAULTS: dict[str, Any] = {
    "ctl_remote": 1, "qs_closed": False, "qs_cmd": 0, "qs_ack": 0,
    "pfc_mode": 1, "pfc_cos_target": None,
    "bess_mode": 0, "bess_setpoint_kw": 0.0, "bess_until_soc": 0.0, "bess_valid_s": 0.0, "bess_valid_left": 0.0,
    "bess_ack": 0, "bess_reserve_pct": 30.0, "bess_auto_idle": False,
    "chp_run": False, "chp_cmd": 0, "chp_ack": 0, "chp_permit": 1, "chp_start_s": 60.0, "gas_bar": 2.10,
    "air_setpoint_bar": 7.00, "pv_limit_pct": 100.0,
    "shed_valid_s": 0.0, "shed_valid_left": 0.0, "extra_load_kw": 0.0, "export_target_kw": None,
}
SHED_NODES = ("CHARGING", "RV-ALL", "DRY-1", "COMPRESSOR", "LP-1")
BESS_TEMP_MAX_C = 40.0


def ctl(world: Any, name: str) -> Any:
    """Прапор керування (``world.flags``) або значення за замовчуванням ``CTL_DEFAULTS``."""
    return world.flags.get(name, CTL_DEFAULTS[name])


def remote(world: Any) -> bool:
    """Контролер у дистанційному режимі (``ctl_remote``, за замовчуванням 1)."""
    return bool(int(ctl(world, "ctl_remote")))


def qs_closed(world: Any) -> bool:
    """QS замкнений: команда контролера (``qs_closed``) або параметр сценарію W1 ``swb.qs_closed``."""
    cfg = world.flags.get("swb")
    return bool(ctl(world, "qs_closed")) or bool(isinstance(cfg, dict) and cfg.get("qs_closed"))


def shed_factor(world: Any, code: str) -> float:
    """``limit_pct / 100`` для вузла (за замовчуванням 1): ліміт навантаження контролера (R-51)."""
    limits = world.flags.get("shed_limit")
    if isinstance(limits, dict) and code in limits:
        return max(0.0, min(100.0, float(limits[code]))) / 100.0
    return 1.0


def shed_active(world: Any) -> bool:
    limits = world.flags.get("shed_limit")
    shed = isinstance(limits, dict) and any(float(v) < 100.0 for v in limits.values())
    return shed or float(ctl(world, "pv_limit_pct")) < 100.0


def bess_temp_c(world: Any) -> float:
    """Температура шафи BESS: ``25 + 0,05·|P|`` (R-59)."""
    return 25.0 + 0.05 * abs(float(get(world, "infra/totals/bess_kw", 0.0) or 0.0))


def consumer_p(world: Any, code: str) -> float:
    return float(get(world, f"energy/consumers/{code}/p_now", 0.0) or 0.0) * shed_factor(world, code)


def base_load(world: Any) -> float:
    return sum(consumer_p(world, c) for c in ALL_CONSUMERS)


def gen_kw(world: Any) -> float:
    return float(get(world, "infra/totals/pv_now")) + float(get(world, "infra/totals/chp_kw"))


def extra_load(world: Any, base: float | None = None) -> float:
    """Додаток до навантаження: ``extra_load_kw`` (≥ −load) і підгонка ``export_demo`` (експорт = ``export_target_kw``)."""
    if island(world):
        return 0.0
    base = base_load(world) if base is None else base
    extra = float(ctl(world, "extra_load_kw") or 0.0)
    target = ctl(world, "export_target_kw")
    if target is not None and gen_kw(world) > float(target):
        extra = (gen_kw(world) - float(target)) - base
    return max(extra, -base)


def p_crit(world: Any) -> float:
    """Σ ``p_now`` критичних споживачів (R-22)."""
    return sum(consumer_p(world, c) for c in CRITICAL)


def total_load(world: Any) -> float:
    """R-13: ``load = Σ p_now`` усіх споживачів; в острові — лише критичних."""
    if island(world):
        return p_crit(world)
    base = base_load(world)
    return base + extra_load(world, base)


def section_p(world: Any, section: int) -> float:
    """Навантаження секції; додаток ``extra_load`` ділиться порівну між секціями (сума вводів = імпорт)."""
    if island(world):
        return 0.0
    own = sum(consumer_p(world, c) for line in SECTIONS[section] for c in LINE_CONSUMERS[line])
    return own + extra_load(world) / 2.0


def update_rv_all(world: Any) -> None:
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
        self.kvarh_start = float(self.val("kvarh_total", 0.0) or 0.0) if self.cell else 0.0  # номінал каталогу
        self.kvarh_acc = 0.0                  # накопичено емулятором, квар·год
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
    def _commands(self) -> None:
        """Modbus 2020 (Reset All Energies) → ``post("meter", {unit, cmd})``: обнуляє накопичені кВт·год лічильника."""
        q = self.world.inbox["meter"]
        mine = [c for c in q if c.get("unit") == self.device.unit_id and c.get("cmd") == "reset_energy"]
        if not mine:
            return
        for c in mine:
            q.remove(c)
        self.own_wh = self.export_wh = 0.0
        self.kvarh_start = self.kvarh_acc = 0.0
        for c in self.consumers:  # type: ignore[assignment]
            self.e_wh[c] = 0.0  # type: ignore[index]
            self.base_wh[c] = 0.0  # type: ignore[index]
            put(self.world, f"energy/consumers/{c}/kwh_total", 0.0)
            put(self.world, f"energy/consumers/{c}/kwh_shift", 0.0)

    def tick(self, dt_s: float) -> None:
        self._commands()
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

    def _cell_p(self) -> float:
        """Потужність вводу; при замкненому QS обидва вводи ділять навантаження порівну: ``(P1 + P2) / 2``."""
        w = self.world
        p1 = section_p(w, 1)
        p2 = 0.0 if island(w) else section_p(w, 2) - gen_kw(w) + float(get(w, "infra/totals/bess_kw"))
        if qs_closed(w) and not island(w):
            return (p1 + p2) / 2.0
        return p1 if self.device.code == "Q1" else p2

    def _watchdog(self, dt_s: float) -> None:
        """Сторожовий таймер ``shed_valid_s`` (веде лише ввід Q1): за 0 усі ліміти й ``pv_limit_pct`` → 100 %."""
        w = self.world
        if not shed_active(w):
            return
        left = float(ctl(w, "shed_valid_left")) - dt_s
        if left > 0:
            w.set_flag("shed_valid_left", left)
            return
        w.clear_flag("shed_limit")
        w.set_flag("pv_limit_pct", 100.0)
        w.set_flag("shed_valid_left", 0.0)
        w.events.emit("info", "Контролер ГРЩ: сторожовий таймер скидання — ліміти повернуто до 100 %")

    def _tick_cell(self) -> None:
        if self.device.code == "Q1":
            self._watchdog(self.dt_s)
        p = self._cell_p()
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
        self.kvarh_acc += abs(q) * self.dt_s / 3600.0
        self.set("kvarh_total", round(self.kvarh_start + self.kvarh_acc, 6))
        self.set("state", 2 if failed else 1)

    def on_fault(self, reason: str, **kw: Any) -> None:
        self.set("state", 2)

    def get_state(self) -> dict[str, Any]:
        return {"e_wh": self.e_wh, "base_wh": self.base_wh, "shift_key": self.shift_key,
                "own_wh": self.own_wh, "export_wh": self.export_wh, "pf": self.pf,
                "kvarh_start": self.kvarh_start, "kvarh_acc": self.kvarh_acc}

    def set_state(self, d: dict[str, Any]) -> None:
        self.e_wh = dict(d.get("e_wh", {}))
        self.base_wh = dict(d.get("base_wh", {}))
        self.shift_key = d.get("shift_key")
        self.own_wh = float(d.get("own_wh", 0.0))
        self.export_wh = float(d.get("export_wh", 0.0))
        self.pf = float(d.get("pf", 0.9))
        self.kvarh_start = float(d.get("kvarh_start", self.kvarh_start))
        self.kvarh_acc = float(d.get("kvarh_acc", 0.0))
