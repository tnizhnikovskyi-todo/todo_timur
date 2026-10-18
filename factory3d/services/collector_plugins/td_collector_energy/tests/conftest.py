"""Фікстури плагіна energy_ctl: ядро збирача — з монорепо, якщо не встановлене. Власник: C."""

import sys
from pathlib import Path

import pytest

try:
    import collector  # noqa: F401
except ImportError:  # ядро колектора не встановлено — беремо з монорепо
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "collector"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def _single_instance():
    """Сам клас-сторож «єдиного екземпляра» не повинен текти між тестами."""
    from td_collector_energy.plugin import EnergyCtlPlugin

    EnergyCtlPlugin._active = None
    yield
    EnergyCtlPlugin._active = None
