"""P-07 TEDOM Quanto D800 NG (SPEC §8.9.5, ПРИПУЩЕННЯ): unit 72; адреси задано одразу в PDU."""
from __future__ import annotations

from iot_sim.protocols.modbus_maps import Ctx, ModbusError, to_int, words_of

UNIT = 72
H = "infra/chp"


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "TEDOM")

    def state() -> int:
        return to_int(ctx.val(f"{H}/state", 2))

    um.add_hr(40000, lambda: [state()], 1, None, "state")
    um.add_hr(40001, lambda: [to_int(ctx.num("infra/totals/chp_kw"))], 1, None, "power")
    um.add_hr(40002, lambda: [to_int(ctx.num(f"{H}/heat_kw"))], 1, None, "heat")
    um.add_hr(40003, lambda: [to_int(ctx.num(f"{H}/gas_m3h") / 0.1)], 1, None, "gas")
    um.add_const(40004, [900, 700], "water_temps")
    um.add_hr(40006, lambda: [1500 if state() == 2 else 0], 1, None, "speed")

    def setpoint_set(_off: int, v: int) -> None:
        if not ctx.write_accept:
            raise ModbusError(4)
        ctx.world.set_flag("modbus.u72.setpoint", v)
        ctx.world.set_flag("chp_run", v > 0)  # ненульове завдання навантаження запускає КГУ, 0 — зупиняє
        ctx.command(UNIT, f"Load setpoint = {v} %")

    um.add_hr(40007, lambda: [to_int(ctx.world.flag("modbus.u72.setpoint", 50))], 1,
              setpoint_set, "load_setpoint")
    um.add_hr(40010, lambda: words_of(to_int(ctx.num(f"{H}/hours")), 2), 2, None, "hours")
    um.add_const(40012, words_of(211, 2), "starts")
    um.add_hr(40014, lambda: words_of(to_int(ctx.num(f"{H}/kwh_total")), 2), 2, None, "kwh_total")
    um.add_hr(40020, lambda: [101 if state() == 3 else 0], 1, None, "alarm_code")
