"""Стенд моста td_genset_factory3d (ТК-G14, ТК-G15; W1_SPEC B.13): pytest -m stand; XML-RPC до Odoo.

Клієнт Odoo беремо зі стенда td_energy (``helpers.py``). Змінні: F3D_ODOO_URL, F3D_ODOO_DB, F3D_ODOO_USER,
F3D_ODOO_PASSWORD. Прапорці: F3D_STAND_TD_GENSET=1 (у БД td_genset + fake_relay профілю D700 + міст + td_energy),
F3D_STAND_DESTRUCTIVE=1 (дозволити видалення й повторне встановлення моста: ТК-G15).
Без F3D_ODOO_URL усі стендові тести пропускаються.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "td_energy" / "tests" / "stand"))
from helpers import Odoo, env  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "stand: стендові тести (Odoo + fake_relay td_genset)")


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="F3D_ODOO_URL не задано: стенд не піднято")
    for item in items:
        if "/tests/stand/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.stand)
            if not os.environ.get("F3D_ODOO_URL"):
                item.add_marker(skip)


def flag(name: str) -> bool:
    return os.environ.get(name) == "1"


need_genset = pytest.mark.skipif(
    not flag("F3D_STAND_TD_GENSET"), reason="немає td_genset + fake_relay + міст (F3D_STAND_TD_GENSET=1)"
)
need_destructive = pytest.mark.skipif(
    not flag("F3D_STAND_DESTRUCTIVE"), reason="видаляє й ставить міст заново (F3D_STAND_DESTRUCTIVE=1)"
)


@pytest.fixture(scope="session")
def odoo() -> Odoo:
    return Odoo(env("F3D_ODOO_URL"), env("F3D_ODOO_DB"), env("F3D_ODOO_USER", "admin"), env("F3D_ODOO_PASSWORD"))
