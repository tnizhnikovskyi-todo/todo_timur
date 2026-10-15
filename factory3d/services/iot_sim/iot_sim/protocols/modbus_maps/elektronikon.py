"""P-07 Atlas Copco Elektronikon Mk5 (SPEC §8.9.3, ПРИПУЩЕННЯ): unit 70; PDU = номер − 1."""
from __future__ import annotations

import math

from iot_sim.protocols.modbus_maps import Ctx, ModbusError, to_int, words_of

UNIT = 70
C = "equipment/COMPRESSOR"


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "Elektronikon")

    def load() -> float:
        return ctx.num(f"{C}/load")

    def state() -> int:
        return to_int(ctx.val(f"{C}/state", 0))

    um.add_hr(3000, lambda: [state() & 0xFFFF], 1, None, "status")
    um.add_hr(3001, lambda: [to_int(ctx.num(f"{C}/pressure_bar") / 0.001)], 1, None, "pressure")
    um.add_hr(3002, lambda: [to_int(ctx.num(f"{C}/temp_c") / 0.1)], 1, None, "temp")
    um.add_const(3003, [30], "dew_point")
    um.add_const(3004, [240], "ambient")
    um.add_hr(3009, lambda: [to_int(load())], 1, None, "load")
    um.add_hr(3010, lambda: [to_int(1200 + 36 * load())], 1, None, "speed")
    um.add_hr(3011, lambda: [to_int(10 * 37 * load() / 100 * 1000 / (math.sqrt(3) * 400 * 0.95))],
              1, None, "current")
    um.add_hr(3019, lambda: words_of(to_int(ctx.num(f"{C}/hours")), 2), 2, None, "hours")
    um.add_hr(3021, lambda: words_of(to_int(0.65 * ctx.num(f"{C}/hours")), 2), 2, None, "loaded")
    um.add_hr(3023, lambda: words_of(to_int(ctx.world.flag("modbus.u70.cycles", 0)), 2), 2,
              None, "cycles")
    um.add_hr(3029, lambda: [to_int(max(0.0, 18000 - ctx.num(f"{C}/hours")))], 1, None, "service")
    um.add_hr(3039, lambda: [11 if state() == 3 else 0], 1, None, "shutdown_code")

    def setpoint_set(_off: int, v: int) -> None:
        if not ctx.write_accept:
            raise ModbusError(4)
        ctx.world.set_flag("modbus.u70.setpoint", v)
        ctx.command(UNIT, f"Setpoint pressure = {v / 1000:g} bar")

    um.add_hr(3099, lambda: [to_int(ctx.world.flag("modbus.u70.setpoint", 7000))], 1,
              setpoint_set, "setpoint")
