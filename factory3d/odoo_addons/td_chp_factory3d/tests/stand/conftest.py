"""Стенд моста td_chp_factory3d (ТК-B11): pytest -m stand; XML-RPC до Odoo зі стендом `iot_sim`.

Клієнт Odoo беремо зі стенда td_energy (`helpers.py`). Змінні: F3D_ODOO_URL, F3D_ODOO_DB, F3D_ODOO_USER,
F3D_ODOO_PASSWORD (користувач — головний енергетик; другий для 2/2 — F3D_ODOO_USER2/F3D_ODOO_PASSWORD2). Без
F3D_ODOO_URL усі стендові тести пропускаються.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "td_energy" / "tests" / "stand"))
from helpers import Odoo, env  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "stand: стендові тести (Odoo + iot_sim)")


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="F3D_ODOO_URL не задано: стенд не піднято")
    for item in items:
        if "/tests/stand/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.stand)
            if not os.environ.get("F3D_ODOO_URL"):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def odoo() -> Odoo:
    return Odoo(env("F3D_ODOO_URL"), env("F3D_ODOO_DB"), env("F3D_ODOO_USER", "admin"), env("F3D_ODOO_PASSWORD"))
