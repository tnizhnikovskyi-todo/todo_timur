"""P-05 Schneider PM5560 (SPEC §8.7.1): unit 1–8 (вводи/фідери), 11–59 (споживачі).

Адреси — PDU = номер документа − 1; F32/INT64 — старше слово першим. Значення — з сигналів каталогу
цього unit (``p_now``/``q``/``cos φ``/струми/енергія), решта величин виводиться з них.
Регістр 2018 (Breaker state, лише unit 1–8) — ПРИПУЩЕННЯ §8.7.1.
"""
from __future__ import annotations

import math

from iot_sim.protocols.modbus_maps import (
    Ctx,
    ModbusError,
    UnitMap,
    f32_words,
    str_words,
    to_float,
    words_of,
)

FEEDERS = {3: "QF-1", 4: "QF-2", 5: "QF-3", 6: "QF-4", 7: "QF-C1", 8: "QF-C2"}
CONSUMERS = ["SAW-1", "SAW-2", "SAW-3", "SLIDE-1", "VSAW-1", "NEST-1", "EDGE-1", "EDGE-2", "EDGE-3", "CNC-3", "CNC-1", "CNC-2", "BORE-1", "CNC-4", "DOWEL-1", "SORT-1", "SAND-1", "AUTOSPRAY-1", "UV-1", "HINGE-1", "GLUE-1", "PRESS-1", "SPRAY-1", "DRY-1", "ASMLINE-1", "ASM-1", "ASM-2", "ASM-3", "ASM-4", "ASM-5", "ASM-6", "PACK-1", "PACK-2", "BOX-1", "PACKLINE-1", "GANTRY-1", "COMPRESSOR", "DUST-1", "BOILER", "CHARGING", "OFFICE", "LP-1", "LP-2", "LP-3", "RV-ALL", "AHU-1", "EF-ELEC", "EF-CMP", "EF-CHG"]
NAMES: dict[int, str] = {1: "Q1", 2: "Q2", **FEEDERS,
                         **{11 + i: c for i, c in enumerate(CONSUMERS)}}
UNITS = sorted(NAMES)
SEMAPHORE = 5679


def _ct(unit: int) -> int:
    return 1600 if unit in (1, 2) else 630 if unit < 11 else 100


def build(ctx: Ctx) -> None:
    for unit in UNITS:
        _build_unit(ctx, ctx.unit(unit, "PM5560"), unit)


def _build_unit(ctx: Ctx, um: UnitMap, unit: int) -> None:
    def f(addr: int) -> float:
        return ctx.sig_num(unit, addr)

    def pf() -> float:
        v = f(3083)
        return v if v else (1.0 if f(3059) == 0 else 0.9)

    def p() -> float:
        return f(3059)

    def q() -> float:
        if ctx.sig_at(unit, 3067):
            return f(3067)
        return p() * math.tan(math.acos(min(1.0, abs(pf()))))

    def s() -> float:
        return f(3075) if ctx.sig_at(unit, 3075) else math.hypot(p(), q())

    def iavg() -> float:
        return f(3009) if ctx.sig_at(unit, 3009) else s() * 1000 / (math.sqrt(3) * 400)

    def ph(addr: int):  # фазний струм
        return lambda _i=0: f(addr) if ctx.sig_at(unit, addr) else iavg()

    def f32(addr: int, fn, n: int = 1) -> None:
        um.add_hr(addr, lambda: [w for i in range(n) for w in f32_words(fn())], 2 * n,
                  None, f"f32@{addr}")

    um.add_const(29, str_words(f"PM-{NAMES[unit]}", 20), "name")
    um.add_const(49, str_words("PM5560", 20), "model")
    um.add_const(69, str_words("Schneider Electric", 20), "manufacturer")
    um.add_const(129, words_of(2026000000 + unit, 2), "serial")
    um.add_const(1636, [2, 7, 4], "firmware")
    um.add_const(2013, [3], "phases")
    um.add_const(2014, [4], "wires")
    um.add_const(2015, [11], "power_system")
    um.add_const(2016, [50], "nominal_freq")
    um.add_const(2024, f32_words(400.0) + [400], "vt")
    um.add_const(2028, [_ct(unit), 5], "ct")
    if unit <= 8:
        sig = ctx.sig_at(unit, 2017)
        um.add_hr(2017, lambda: [int(to_float(sig.value)) if sig else 1], 1, None, "breaker")
    f32(2999, ph(2999))
    f32(3001, ph(3001))
    f32(3003, ph(3003))
    f32(3005, lambda: 0.02 * iavg())
    f32(3009, iavg)
    f32(3019, lambda: 400.0, 3)
    f32(3025, lambda: 400.0)
    f32(3027, lambda: 230.0, 3)
    f32(3035, lambda: 230.0)
    f32(3053, lambda: p() / 3, 3)
    f32(3059, p)
    f32(3061, lambda: q() / 3, 3)
    f32(3067, q)
    f32(3069, lambda: s() / 3, 3)
    f32(3075, s)
    f32(3077, pf, 3)
    f32(3083, pf)
    f32(3109, lambda: 50.0)

    def wh(addr: int) -> int:
        return round(f(addr) * 1000)

    def i64(addr: int, fn) -> None:
        um.add_hr(addr, lambda: words_of(fn(), 4, signed=True), 4, None, f"i64@{addr}")

    i64(3203, lambda: wh(3203))
    i64(3207, lambda: wh(3207))
    i64(3211, lambda: wh(3203) + wh(3207))
    i64(3219, lambda: 0)
    f32(2699, lambda: f(3203))
    f32(2703, lambda: f(3207))

    sem_get, sem_set = ctx.flag_store(unit, SEMAPHORE)

    def on_sem(_off: int, v: int) -> None:
        if v == 2020 and not ctx.write_accept:  # Reset All Energies
            raise ModbusError(4)
        sem_set(v)
        ctx.command(unit, f"Command Semaphore = {v}")
        if v == 2020:
            ctx.world.post("meter", {"unit": unit, "cmd": "reset_energy"})

    um.add_hr(SEMAPHORE, lambda: [sem_get()], 1, on_sem, "semaphore")
