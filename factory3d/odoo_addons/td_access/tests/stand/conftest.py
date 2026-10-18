"""Стенд td_access (SPEC §13.2): pytest -m stand; XML-RPC до Odoo, /sim/v1 емулятора.

Змінні: F3D_ODOO_URL, F3D_ODOO_DB, F3D_ODOO_USER, F3D_ODOO_PASSWORD, SIM_API_URL, SIM_API_TOKEN (секрети — лише в
середовищі, не в репозиторії). Додатково: F3D_SIM_BIOSTAR_URL (адреса емулятора для Odoo, за замовчуванням
https://127.0.0.1:8443), SIM_BIOSTAR_PASS (пароль BioStar емулятора), SIM_BIOSTAR_HTTP (HTTP-порт для перевірок
журналу, за замовчуванням http://127.0.0.1:8081), F3D_STAND_DAY (день sim-сценаріїв ТК-03/04, YYYY-MM-DD).
Без F3D_ODOO_URL усі стендові тести пропускаються.
"""
from __future__ import annotations

import os

import httpx
import pytest

from helpers import Odoo, Sim, day_before, env
from seed import seed_employees

BIOSTAR_PASS = os.environ.get("SIM_BIOSTAR_PASS", "")


def pytest_configure(config):
    config.addinivalue_line("markers", "stand: стендові тести (Odoo + емулятор iot_sim)")


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="F3D_ODOO_URL не задано: стенд не піднято")
    for item in items:
        if "/tests/stand/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.stand)
            if not os.environ.get("F3D_ODOO_URL"):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def odoo() -> Odoo:
    return Odoo(env("F3D_ODOO_URL"), env("F3D_ODOO_DB"), env("F3D_ODOO_USER", "admin"),
                env("F3D_ODOO_PASSWORD"))


@pytest.fixture(scope="session")
def sim() -> Sim:
    return Sim(env("SIM_API_URL", "http://127.0.0.1:8090"), env("SIM_API_TOKEN"))


@pytest.fixture(scope="session")
def bs_http():
    """HTTP-вхід BioStar емулятора (A-07, лише тести) з сесією адміністратора."""
    c = httpx.Client(base_url=os.environ.get("SIM_BIOSTAR_HTTP", "http://127.0.0.1:8081"), timeout=15, verify=False)
    r = c.post("/api/login", json={"User": {"login_id": "admin", "password": env("SIM_BIOSTAR_PASS")}})
    r.raise_for_status()
    c.headers["bs-session-id"] = r.headers["bs-session-id"]
    return c


@pytest.fixture(scope="session")
def day() -> str:
    """День sim-сценаріїв: учора (події «сьогодні» після реального «зараз» Odoo відкидає future_tolerance)."""
    return os.environ.get("F3D_STAND_DAY") or day_before(1)


@pytest.fixture(scope="session")
def server_id(odoo, sim):
    """Підготовка стенду: 35 працівників, URL емулятора, пароль, read_enabled=True, write_enabled=False."""
    seed_employees(odoo)
    sid = odoo.server()["id"]
    odoo.k("td.access.server", "write", [sid], {"url": os.environ.get("F3D_SIM_BIOSTAR_URL", "https://127.0.0.1:8443"),
                                                  "verify_ssl": False})
    assert odoo.get_param("td.base.environment") == "test"
    odoo.param("biostar_password", env("SIM_BIOSTAR_PASS"))
    odoo.param("read_enabled", "True")
    odoo.param("write_enabled", "False")
    return sid


@pytest.fixture(scope="session")
def people_loaded(odoo, sim, server_id):
    """Чекає, поки емулятор підхопить 35 працівників з Odoo (follow, ≤ 70 с): 36 користувачів у BioStar."""
    from helpers import wait_for

    def total():
        msg = odoo.k("td.access.server", "action_test_connection", [server_id])["params"]["message"]
        return int(msg.split("користувачів ")[1].split(",")[0])
    assert wait_for(lambda: total() >= 36, 150, 5), "емулятор не підхопив працівників з Odoo"
    sim.post("/mode", {"mode": "scenario"})
    return True
