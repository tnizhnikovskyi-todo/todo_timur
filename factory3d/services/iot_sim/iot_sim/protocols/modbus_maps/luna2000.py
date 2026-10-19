"""P-07 Huawei LUNA2000 BESS (SPEC §8.9.2): unit 69; діапазони регістрів не перекриваються (X-51)."""

from __future__ import annotations

from typing import Any

from iot_sim.protocols.modbus_maps import Ctx, to_int, words_of

UNIT = 69


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "LUNA2000")
    kw = "infra/totals/bess_kw"

    def p_w() -> int:
        return to_int(ctx.num(kw) * 1000)

    um.add_hr(37000, lambda: [to_int(ctx.val("infra/bess/state", 2)) & 0xFFFF], 1, None, "status")
    um.add_hr(37001, lambda: words_of(p_w(), 2, signed=True), 2, None, "power")
    um.add_const(37003, [7600], "bus_voltage")
    um.add_hr(37004, lambda: [to_int(ctx.num("infra/totals/bess_soc") * 10)], 1, None, "soc")
    um.add_const(37006, [4], "working_mode")
    um.add_hr(37014, lambda: words_of(to_int(ctx.num("infra/bess/kwh_charge_total") * 100), 2), 2, None, "total_charge")
    um.add_hr(
        37016, lambda: words_of(to_int(ctx.num("infra/bess/kwh_discharge_total") * 100), 2), 2, None, "total_discharge"
    )

    def day(key: str, sign: int) -> Any:  # ПРИПУЩЕННЯ: добовий лічильник = поточний total − total на 00:00
        def get() -> list[int]:
            tot = ctx.num(f"infra/bess/kwh_{key}_total")
            d = ctx.world.now().date().isoformat()
            mark = ctx.world.flag(f"modbus.u{UNIT}.day_{key}")
            if not mark or mark.get("d") != d:
                mark = {"d": d, "v": tot}
                ctx.world.set_flag(f"modbus.u{UNIT}.day_{key}", mark)
            return words_of(to_int(max(0.0, tot - mark["v"]) * 100), 2)

        return get

    um.add_hr(37018, day("charge", 1), 2, None, "day_charge")
    um.add_hr(37020, day("discharge", -1), 2, None, "day_discharge")
    um.add_hr(
        37022, lambda: [to_int(10 * (25 + 0.05 * abs(ctx.num(kw) * 1000 / 1000))) & 0xFFFF], 1, None, "battery_temp"
    )
    um.add_const(37046, words_of(387_000, 2), "rated_capacity")
    um.add_const(37050, [990], "soh")
