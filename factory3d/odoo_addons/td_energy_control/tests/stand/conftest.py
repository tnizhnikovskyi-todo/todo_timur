"""Стенд td_energy_control (SPEC 13.2): повторно використовує фікстури стенда `td_energy` (Odoo XML-RPC, /sim/v1).

Додаткові змінні: F3D_STAND_USER_PASSWORD (пароль `en1`, `en2`, `chief`, `viewer`; за замовчуванням = пароль admin).
Передумови E-11: емулятор + збирач із плагином `td_collector_energy`; `hooks._td_enable_stand(env)`; збирач
`F3D_WRITE_ENABLED=true`, `F3D_COMMANDS_POLL_S=2`; емулятор `SIM_WRITE_ACCEPT=1`. Без `F3D_ODOO_URL` — пропуск.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

W1_STAND = Path(__file__).resolve().parents[3] / "td_energy" / "tests" / "stand"
sys.path.insert(0, str(W1_STAND))
_spec = importlib.util.spec_from_file_location("td_energy_stand_conftest", W1_STAND / "conftest.py")
_w1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_w1)

odoo, sim, stand_ready = _w1.odoo, _w1.sim, _w1.stand_ready
need_collector = _w1.need_collector
pytest_configure = _w1.pytest_configure
pytest_collection_modifyitems = _w1.pytest_collection_modifyitems


@pytest.fixture(scope="session")
def control_ready(odoo, stand_ready):
    """Прапори керування стенда увімкнено (`_td_enable_stand`) і рушій на зв'язку."""
    for flag in ("write_enabled", "automation_enabled", "remote_switching_enabled"):
        assert odoo.get_param("td.energy_control." + flag) == "True", "виконайте hooks._td_enable_stand(env)"
    return True
