"""P-07 Huawei SUN2000-115KTL-M2 (SPEC §8.9.1): unit 61–68 = PV-INV-1…8; адреса вже PDU, слова ``big``.

Із каталогу: ``p_kw`` (32080), ``status`` (32089), ``kwh_today`` (32114), ``kwh_total`` (32106);
решта регістрів виводиться з активної потужності.
"""

from __future__ import annotations

import math
from datetime import datetime, time
from typing import Any

from iot_sim.protocols.modbus_maps import (
    Ctx,
    ModbusError,
    UnitMap,
    str_words,
    to_float,
    to_int,
    words_of,
)

UNITS = range(61, 69)
RATED_KW = 115.0
PMAX_KW = 125.0
DAY_START, DAY_END = time(6, 30), time(18, 30)  # ПРИПУЩЕННЯ: схід/захід для регістрів 32091/32093


def build(ctx: Ctx) -> None:
    for unit in UNITS:
        _build_unit(ctx, ctx.unit(unit, "SUN2000"), unit)


def _epoch(ctx: Ctx, t: time) -> int:
    now = ctx.world.now()
    return int(datetime.combine(now.date(), t, tzinfo=now.tzinfo).timestamp())


def _build_unit(ctx: Ctx, um: UnitMap, unit: int) -> None:
    k = unit - 60
    base = f"infra/pv/PV-INV-{k}"

    def p() -> float:
        return ctx.num(f"{base}/p_kw")

    def i32(v: float, gain: int) -> list[int]:
        return words_of(to_int(v * gain), 2, signed=True)

    um.add_const(30000, str_words("SUN2000-115KTL-M2", 15), "model")
    um.add_const(30015, str_words(f"HV2240000000{k:02d}", 10), "sn")
    um.add_const(30073, words_of(int(RATED_KW * 1000), 2), "pn")
    um.add_const(30075, words_of(int(PMAX_KW * 1000), 2), "pmax")

    def pv_v(i: int) -> Any:
        return lambda: [to_int(10 * (700 + 8 * i)) if p() > 0.05 else 0]

    def pv_i(i: int) -> Any:  # 10 стрінгів: I = P_dc / (V·10)
        return lambda: [to_int(100 * (p() / 0.986 * 1000 / ((700 + 8 * i) * 10))) if p() > 0.05 else 0]

    for i in range(10):
        um.add_hr(32016 + 2 * i, pv_v(i), 1, None, f"pv{i + 1}_v")
        um.add_hr(32017 + 2 * i, pv_i(i), 1, None, f"pv{i + 1}_i")
    um.add_hr(32064, lambda: i32(p() / 0.986, 1000), 2, None, "dc_power")
    for off, vv in enumerate((4000, 4000, 4000)):
        um.add_const(32066 + off, [vv], "v_line")
    for off in range(3):
        um.add_const(32069 + off, [2300], "v_phase")
    for off in range(3):
        um.add_hr(32072 + 2 * off, lambda: i32(p() * 1000 / (math.sqrt(3) * 400), 1000), 2, None, "i_phase")

    peak_key = f"modbus.u{unit}.peak"

    def peak() -> list[int]:
        today = ctx.world.now().date().isoformat()
        cur = ctx.world.flag(peak_key) or {}
        best = max(p(), cur.get("v", 0.0)) if cur.get("d") == today else p()
        ctx.world.set_flag(peak_key, {"d": today, "v": best})
        return i32(best, 1000)

    um.add_hr(32078, peak, 2, None, "peak")
    um.add_hr(32080, lambda: i32(p(), 1000), 2, None, "active_power")
    um.add_const(32082, [0, 0], "reactive")
    um.add_const(32084, [1000], "pf")
    um.add_const(32085, [5000], "freq")
    um.add_const(32086, [9840], "eff")
    um.add_hr(32087, lambda: [to_int(10 * (25 + 0.25 * 100 * p() / RATED_KW))], 1, None, "temp")
    um.add_const(32088, [3000], "insulation")

    def status() -> int:
        sig = ctx.world.signals.get(f"{base}/status")
        return to_int(sig.value) if sig else 0xA000

    um.add_hr(32089, lambda: [status() & 0xFFFF], 1, None, "status")

    def fault_code() -> int:
        s = status()
        return 2032 if s == 0x0303 else 2064 if s == 0x0300 else 0

    um.add_hr(32090, lambda: [fault_code()], 1, None, "fault_code")
    um.add_hr(32091, lambda: words_of(_epoch(ctx, DAY_START), 2), 2, None, "startup")
    um.add_hr(32093, lambda: words_of(_epoch(ctx, DAY_END), 2), 2, None, "shutdown")
    um.add_hr(32106, lambda: words_of(to_int(ctx.num(f"{base}/kwh_total") * 100), 2), 2, None, "kwh_total")
    um.add_hr(32114, lambda: words_of(to_int(ctx.num(f"{base}/kwh_today") * 100), 2), 2, None, "kwh_today")

    # RW: час системи (40000+2) і код мережевого стандарту (42000) — запис лише при write_accept
    def rw(addr: int, n: int, default: Any) -> None:
        key = f"modbus.u{unit}.{addr}"

        def get() -> list[int]:
            v = ctx.world.flag(key)
            return list(v) if v else list(default())

        def setter(off: int, w: int) -> None:
            if not ctx.write_accept:
                raise ModbusError(4)
            cur = get()
            cur[off] = w
            ctx.world.set_flag(key, cur)
            ctx.command(unit, f"write {addr}+{off} = {w}")

        um.add_hr(addr, get, n, setter, f"rw{addr}")

    rw(40000, 2, lambda: words_of(to_int(to_float(ctx.world.clock.epoch())), 2))
    rw(42000, 1, lambda: [0])
