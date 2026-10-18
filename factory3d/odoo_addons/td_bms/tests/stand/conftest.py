# ruff: noqa: E501
"""Фікстури стенда td_bms (SPEC §13.2): ``tests/stand/stand.sh up``; прогін
``/tmp/f3dvenv/collector/bin/pytest -q -m stand odoo_addons/td_bms/tests/stand``. Без стенда тести пропускаються.
Допоміжні класи (Sim, Metrics, http, wait) і XML-RPC-клієнт беруться зі стенда колектора (services/collector/tests/stand)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("F3D_STAND_ODOO_URL", "http://127.0.0.1:18070")
os.environ.setdefault("F3D_STAND_ODOO_DB", "f3d_factory3d_bms_w7")
HERE = Path(__file__).resolve().parent
COLLECTOR_STAND = HERE.parents[3] / "services" / "collector" / "tests" / "stand"
sys.path.insert(0, str(COLLECTOR_STAND))
sys.path.insert(0, str(HERE))
import odoo_rpc  # noqa: E402
from helpers import METRICS_URL, SIM_TOKEN, SIM_URL, Metrics, Sim, http, wait  # noqa: E402,F401


def pytest_collection_modifyitems(items):
    for it in items:
        if "/bms/tests/stand/" in str(it.fspath) or "td_bms/tests/stand" in str(it.fspath):
            it.add_marker(pytest.mark.stand)
            if not it.get_closest_marker("timeout"):
                it.add_marker(pytest.mark.timeout(1800))


@pytest.fixture(scope="session")
def sim() -> Sim:
    s = Sim(SIM_URL, SIM_TOKEN)
    try:
        st, _ = s.get("/health")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"стенд не піднято (tests/stand/stand.sh up): iot_sim недоступний: {e}")
    if st != 200:
        pytest.skip("стенд не піднято: iot_sim /health != 200")
    return s


@pytest.fixture(scope="session", autouse=True)
def sim_clock(sim):
    """Годинник емулятора — 10:00 за Києвом (робоча зміна), як у кроці «повернути» ТК-05."""
    import datetime as dt

    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=3))).date().isoformat()
    sim.post("/time", {"set": f"{today}T10:00:00+03:00"})
    return today


@pytest.fixture(scope="session")
def odoo(sim):
    try:
        return odoo_rpc.Odoo()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"стенд не піднято: Odoo недоступна: {e}")


@pytest.fixture
def metrics(sim) -> Metrics:
    m = Metrics(METRICS_URL)
    last = None
    for _ in range(20):
        try:
            m.health()
            return m
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3)
    pytest.skip(f"стенд не піднято: колектор недоступний: {last}")


@pytest.fixture
def fresh_sim(sim):
    sim.post("/resume")
    sim.post("/mode", {"mode": "scenario"})
    sim.reset()
    sim.post("/time", {"factor": 1})
    yield sim
    sim.post("/resume")
    sim.post("/time", {"factor": 1})
    sim.reset()


@pytest.fixture
def full_calendar(odoo):
    """Календар «Цілодобово (ТК)» на час тесту; після — порожній (календар компанії), відкриті заявки перевірок закриті."""
    from bms_lib import close_bms_requests, use_calendar

    use_calendar(odoo, "Цілодобово (ТК)")
    yield
    use_calendar(odoo, None)
    close_bms_requests(odoo)


@pytest.fixture
def no_calendar(odoo):
    from bms_lib import close_bms_requests, use_calendar

    use_calendar(odoo, "Без робочого часу (ТК)")
    yield
    use_calendar(odoo, None)
    close_bms_requests(odoo)
