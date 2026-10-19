"""Верстат без інтерфейсу виробника: ADAM-6050 (P-02, SPEC §8.4.2), драйвер ``io_machine``.

Той самий автомат R-14 і потужність R-02, але ``state`` — біт DI «в роботі» (``CurrentState == WORKING``),
``alarm`` — біт DI «аварія» (``Error``), ``pieces_out`` — лічильник імпульсів (цикл = деталь, R-16).
"""

from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.machine import WORKING, Machine


@register_model("io_machine")
class IoMachine(Machine):
    kind = "adam"

    def flag_value(self, b: bool) -> Any:
        return int(bool(b))

    def state_value(self, cs: int) -> Any:
        return int(cs == WORKING)
