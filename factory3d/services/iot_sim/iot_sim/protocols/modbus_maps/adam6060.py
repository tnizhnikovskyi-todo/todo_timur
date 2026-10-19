"""P-11 Advantech ADAM-6060 IO-7 (SPEC §8.13.1): unit 86 — шлагбауми GATE-W / GATE-E.

6 DI (стріла, петля, фотоелемент ×2 воріт), 6 реле DO (open/close/hold ×2), лічильники на DI як у 6050.
Запис FC 05 у DO: командний сигнал каталогу (``yard/gates/<G>/cmd_*``) + ``world.post("yard",
{"kind": "gate_cmd", "gate", "cmd", "value"})`` + подія ``command``; стрілою керує модель ``yard``.
"""

from __future__ import annotations

from iot_sim.protocols.modbus_maps import Ctx
from iot_sim.protocols.modbus_maps.adam6050 import digital_module

UNIT = 86


def build(ctx: Ctx) -> None:
    digital_module(ctx, UNIT, n_di=6, n_do=6, module=0x6060, name="ADAM-6060")
