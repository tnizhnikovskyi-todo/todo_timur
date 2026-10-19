"""Реєстр драйверів моделей: ім'я драйвера -> клас (SPEC §8.2.3).

Невідомий драйвер -> ``PassiveModel`` (тримає номінал). Воркери поведінки додають файл
``models/<driver>.py`` з ``@register_model("<driver>")``; ``load_all()`` підхоплює його сам.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from iot_sim.models.base import AGGREGATE, SOURCE, Model, NoiseModel, PassiveModel

MODELS: dict[str, type[Model]] = {"passive": PassiveModel, "noise": NoiseModel}
_loaded = False


def register_model(driver: str) -> Any:
    """Декоратор: ``@register_model("compressor") class Compressor(Model): ...``."""

    def deco(cls: type[Model]) -> type[Model]:
        cls.driver = driver
        MODELS[driver] = cls
        return cls

    return deco


def load_all() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for m in pkgutil.iter_modules(__path__):
        if m.name != "base":
            importlib.import_module(f"{__name__}.{m.name}")


def model_class(driver: str) -> type[Model]:
    load_all()
    return MODELS.get(driver, PassiveModel)


__all__ = [
    "AGGREGATE",
    "MODELS",
    "SOURCE",
    "Model",
    "NoiseModel",
    "PassiveModel",
    "load_all",
    "model_class",
    "register_model",
]
