"""Фікстури плагіна energy_ctl (каркас W2-0). Власник: C."""

import sys
from pathlib import Path

try:
    import collector  # noqa: F401
except ImportError:  # ядро колектора не встановлено — беремо з монорепо
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "collector"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
