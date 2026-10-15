"""Фікстури стенда телеметрії (SPEC §13.2): ``tests/stand/stand.sh up``; прогін ``.venv/bin/pytest -q -m stand tests/stand``.
Якщо стенд не піднято — тести пропускаються з причиною."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import odoo_rpc  # noqa: E402
from helpers import STAND_DIR, METRICS_URL, SIM_TOKEN, SIM_URL, CollectorProc, Metrics, Sim  # noqa: E402,F401


def pytest_collection_modifyitems(items):
    for it in items:
        if "/stand/" in str(it.fspath):
            it.add_marker(pytest.mark.stand)
            if not it.get_closest_marker("timeout"):
                it.add_marker(pytest.mark.timeout(1800))       # стендові ТК довші за 60 с з pyproject


@pytest.fixture(scope="session")
def sim() -> Sim:
    s = Sim(SIM_URL, SIM_TOKEN)
    try:
        st, d = s.get("/health")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"стенд не піднято (tests/stand/stand.sh up): iot_sim недоступний: {e}", allow_module_level=False)
    if st != 200:
        pytest.skip("стенд не піднято: iot_sim /health != 200")
    return s


@pytest.fixture(scope="session")
def odoo(sim):
    try:
        return odoo_rpc.Odoo()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"стенд не піднято: Odoo недоступна: {e}")


@pytest.fixture
def metrics(sim) -> Metrics:
    """Метрики колектора; функціональна фікстура з очікуванням до 120 с (колектор може перезапускатись між тестами)."""
    m = Metrics(METRICS_URL)
    last: Exception | None = None
    for _ in range(40):
        try:
            m.health()
            return m
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3)
    pytest.skip(f"стенд не піднято: колектор недоступний: {last}")


@pytest.fixture(scope="session")
def col(odoo) -> CollectorProc:
    return CollectorProc(odoo)


@pytest.fixture
def token(odoo, col) -> str:
    """Чинний токен колектора (з файла стенда); перечитується щоразу — `collector-restart` видає новий токен."""
    p = STAND_DIR / "token"
    return p.read_text().strip() if p.exists() else odoo.new_token()


@pytest.fixture
def fresh_sim(sim):
    """reset емулятора перед і після ТК (SPEC §13.2: reset {"keep_time": true}); factor повертається до 1."""
    sim.post("/resume")
    sim.post("/mode", {"mode": "scenario"})
    sim.reset()
    sim.post("/time", {"factor": 1})
    yield sim
    sim.post("/resume")
    sim.post("/time", {"factor": 1})
    sim.reset()
