"""Стенд factory3d_energy (SPEC §13.2–13.4): pytest -m stand; XML-RPC до Odoo, /sim/v1 емулятора, колектор telemetry.

Змінні: F3D_ODOO_URL, F3D_ODOO_DB, F3D_ODOO_USER, F3D_ODOO_PASSWORD, SIM_API_URL, SIM_API_TOKEN (секрети — лише в
середовищі). Прапорці середовища: F3D_STAND_COLLECTOR=1 (колектор запущено і шле дані), F3D_STAND_DEMO=1 (база — копія
демо 14.10: МО 00231, BOM лінії A, ККД-дані), F3D_STAND_LONG=1 (дозволити сценарії > 30 хв: ТК-02, ТК-10),
F3D_STAND_TD_GENSET=1 (є td_genset/factory3d_genset), F3D_STAND_VIEWER=1 (є factory3d_viewer).
Без F3D_ODOO_URL усі стендові тести пропускаються.
"""

from __future__ import annotations

import os

import pytest

from helpers import Odoo, Sim, env


def pytest_configure(config):
    config.addinivalue_line("markers", "stand: стендові тести (Odoo + емулятор iot_sim + колектор)")


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="F3D_ODOO_URL не задано: стенд не піднято")
    for item in items:
        if "/tests/stand/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.stand)
            if not os.environ.get("F3D_ODOO_URL"):
                item.add_marker(skip)


def flag(name: str) -> bool:
    return os.environ.get(name) == "1"


need_collector = pytest.mark.skipif(
    not flag("F3D_STAND_COLLECTOR"), reason="колектор telemetry не запущено (F3D_STAND_COLLECTOR=1)"
)
need_demo = pytest.mark.skipif(not flag("F3D_STAND_DEMO"), reason="немає копії демо-бази 14.10 (F3D_STAND_DEMO=1)")
need_long = pytest.mark.skipif(not flag("F3D_STAND_LONG"), reason="сценарій > 30 хв: F3D_STAND_LONG=1")
need_genset = pytest.mark.skipif(not flag("F3D_STAND_TD_GENSET"), reason="немає td_genset/factory3d_genset")
need_viewer = pytest.mark.skipif(not flag("F3D_STAND_VIEWER"), reason="немає factory3d_viewer (AC-63/65 — MAN)")


@pytest.fixture(scope="session")
def odoo() -> Odoo:
    return Odoo(env("F3D_ODOO_URL"), env("F3D_ODOO_DB"), env("F3D_ODOO_USER", "admin"), env("F3D_ODOO_PASSWORD"))


@pytest.fixture(scope="session")
def sim() -> Sim:
    return Sim(env("SIM_API_URL", "http://127.0.0.1:8090"), env("SIM_API_TOKEN"))


@pytest.fixture(scope="session")
def stand_ready(odoo):
    """Підготовка: середовище test, read_enabled=True, write_enabled=False (SPEC §3)."""
    assert odoo.get_param("factory3d.base.environment") == "test"
    odoo.param("read_enabled", "True")
    odoo.param("write_enabled", "False")
    return True
