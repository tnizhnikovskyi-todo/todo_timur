"""P-07 Advantech ADAM-6015 RTD-1 (SPEC §8.9.6, R-20): unit 96, 7 RTD PT100 (−50…+150 °C).

RTD0–2 -> ``energy/transformers/T1/temp_c`` (максимум з трьох обмоток), RTD3–5 -> T2; RTD6 — резерв
(burnout ``fc1 pdu126`` = 1). ``raw = round(65535·(t+50)/200)``; float (``pdu30+2i``) — °C, молодше слово першим.
Розкид обмоток (ПРИПУЩЕННЯ): перша = максимум, наступні на 0,4 °C і 0,8 °C нижче.
"""
from __future__ import annotations

from iot_sim.protocols.modbus_maps import Ctx, f32_words, to_float

UNIT = 96
SIGNALS = ("energy/transformers/T1/temp_c", "energy/transformers/T2/temp_c")
SPREAD = (0.0, 0.4, 0.8)


def raw_of(t: float) -> int:
    return max(0, min(65535, round(65535 * (t + 50) / 200)))


def build(ctx: Ctx) -> None:
    um = ctx.unit(UNIT, "ADAM-6015")
    for ch in range(6):
        code, off = SIGNALS[ch // 3], SPREAD[ch % 3]

        def temp(c=code, o=off) -> float:
            return to_float(ctx.val(c)) - o

        um.add_hr(ch, lambda t=temp: [raw_of(t())], 1, None, f"RTD{ch}")
        um.add_hr(30 + 2 * ch, lambda t=temp: f32_words(t(), little=True), 2, None, f"RTD{ch}_c")
        um.add_bit("c", 120 + ch, lambda: False, None, f"burnout{ch}")
    um.add_const(6, [0], "RTD6")
    um.add_hr(42, lambda: f32_words(-50.0, little=True), 2, None, "RTD6_c")
    um.add_bit("c", 126, lambda: True, None, "burnout6")
    um.add_const(200, [0x0020] * 7, "type_codes")
    um.add_const(210, [0x6015, 0], "module_name")
