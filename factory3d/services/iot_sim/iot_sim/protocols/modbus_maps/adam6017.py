"""P-07 Advantech ADAM-6017 AI-1 (SPEC §8.9.6, R-20): unit 90, 8 AI 4–20 мА.

``raw = round(65535·(mA−4)/16)``, ``mA = 4 + 16·(eng−lo)/(hi−lo)``; float-регістри (``pdu30+2i``) — мА
IEEE754, молодше слово першим. AI4–AI7 — резерв: raw 0, burnout ``fc1 pdu124+4`` = 1.
"""
from __future__ import annotations

from iot_sim.protocols.modbus_maps import Ctx, f32_words, to_float

UNIT = 90
# (сигнал, lo, hi) для AI0…AI3
CHANNELS = (
    ("equipment/DUST-1/airflow_m3h", 0.0, 32000.0),
    ("equipment/DUST-1/filter_dp_kpa", 0.0, 4.0),
    ("equipment/SPRINKLERS/pressure_bar", 0.0, 16.0),
    ("equipment/AIR-RING/pressure_bar", 0.0, 16.0),
)


def milliamps(value: float, lo: float, hi: float) -> float:
    frac = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    return 4.0 + 16.0 * frac


def raw_of(value: float, lo: float, hi: float) -> int:
    return max(0, min(65535, round(65535 * (milliamps(value, lo, hi) - 4) / 16)))


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "ADAM-6017")
    for i, (code, lo, hi) in enumerate(CHANNELS):
        um.add_hr(i, lambda c=code, a=lo, b=hi: [raw_of(to_float(ctx.val(c)), a, b)], 1, None,
                  f"AI{i}")
        um.add_hr(30 + 2 * i, lambda c=code, a=lo, b=hi: f32_words(
            milliamps(to_float(ctx.val(c)), a, b), little=True), 2, None, f"AI{i}_ma")
        um.add_bit("c", 120 + i, lambda: False, None, f"burnout{i}")
    for i in range(4, 8):
        um.add_const(i, [0], f"AI{i}")
        um.add_hr(30 + 2 * i, lambda: f32_words(4.0, little=True), 2, None, f"AI{i}_ma")
        um.add_bit("c", 120 + i, lambda: True, None, f"burnout{i}")
    um.add_const(200, [0x0107] * 8, "type_codes")
    um.add_const(210, [0x6017, 0], "module_name")
