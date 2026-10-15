"""P-07 Socomec ATyS p 1600 (SPEC §8.9.4): unit 71, Annexe III; адреси вже PDU."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from iot_sim.protocols.modbus_maps import Ctx, ModbusError, to_int, words_of

UNIT = 71
A = "infra/ats"
MODES = (0x0000, 0x0001, 0x0010, 0x0020, 0x0040)
LAST_TRANSFER = int(datetime(2026, 10, 5, 18, 42, tzinfo=ZoneInfo("Europe/Kyiv")).timestamp())


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "ATyS p")

    def sig(leaf: str, default: int = 0) -> Any:
        return lambda: [to_int(ctx.val(f"{A}/{leaf}", default)) & 0xFFFF]

    um.add_hr(20480, lambda: words_of(to_int(ctx.world.clock.epoch()), 2), 2, None, "datetime")
    um.add_hr(20482, sig("mode", 0x20), 1, None, "mode")
    um.add_hr(20483, sig("position", 2), 1, None, "position")
    um.add_hr(20484, sig("gen_start", 0), 1, None, "gen_start")
    um.add_const(20485, [1], "priority")
    um.add_hr(20486, sig("src1_state", 2), 1, None, "src1_state")
    um.add_hr(20487, sig("src2_state", 0), 1, None, "src2_state")

    def src1() -> int:
        return to_int(ctx.val(f"{A}/src1_state", 2))

    def src2() -> int:
        return to_int(ctx.val(f"{A}/src2_state", 0))

    for i in range(3):  # ПРИПУЩЕННЯ: додаткові регістри емулятора
        um.add_hr(20490 + i, lambda: [400 if src1() > 0 else 0], 1, None, "s1_v")
        um.add_hr(20500 + i, lambda: [400 if src2() > 0 else 0], 1, None, "s2_v")
    um.add_hr(20493, lambda: [500 if src1() > 0 else 0], 1, None, "s1_f")
    um.add_hr(20503, lambda: [500 if src2() > 0 else 0], 1, None, "s2_f")
    um.add_hr(20510, lambda: words_of(to_int(ctx.world.flag("modbus.u71.transfers", 17)), 2), 2,
              None, "transfer_counter")
    um.add_const(20512, words_of(LAST_TRANSFER, 2), "last_transfer")
    um.add_const(57635, [71], "slave_address")

    def set_mode(_off: int, v: int) -> None:
        if not ctx.write_accept:
            raise ModbusError(4)  # SIM_WRITE_ACCEPT=0 -> 0x04
        if v not in MODES:
            raise ModbusError(3)
        ctx.world.force(f"{A}/mode", v)
        ctx.world.post("ats", {"cmd": "set_mode", "value": v})
        ctx.command(UNIT, f"Set Operating Mode = {v:#06x}", {"mode": v})

    um.add_hr(21761, sig("mode", 0x20), 1, set_mode, "set_mode")
