"""Фікстури стенда machine_connect (SPEC §13.2): ``tests/stand/stand.sh build && stand.sh template``, далі
``pytest -m stand tests/stand``. Якщо стенд не піднято — тести пропускаються з причиною."""

from __future__ import annotations


import pytest

from . import odoo_rpc
from .helpers import METRICS_URL, SIM_TOKEN, SIM_URL, Metrics, Sim, stand_sh, wait  # noqa: E402


def pytest_collection_modifyitems(items):
    for it in items:
        if "/stand/" in str(it.fspath):
            it.add_marker(pytest.mark.stand)
            if not it.get_closest_marker("timeout"):
                it.add_marker(pytest.mark.timeout(3600))  # ТК довші за 60 с з pyproject


@pytest.fixture(scope="session")
def sim() -> Sim:
    s = Sim(SIM_URL, SIM_TOKEN)
    try:
        st, _ = s.get("/health")
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"стенд не піднято (tests/stand/stand.sh build/up): iot_sim недоступний: {e}")
    if st != 200:
        pytest.skip("стенд не піднято: iot_sim /health != 200")
    return s


@pytest.fixture
def metrics() -> Metrics:
    return Metrics(METRICS_URL)


def _ready(o, n: int = 35) -> bool:
    return o.count("f3d.machine", [("raw_ts", "!=", False)]) >= n


@pytest.fixture
def fresh(sim):
    """Фабрика свіжої бази й процесів: ``fresh(env=None, scenario=None, params=None)`` → Odoo-клієнт.

    SPEC §13.2: reset емулятора з `keep_time`, час емулятора = реальний, база — свіжа копія `f3d_mc_t0`; чекає, поки колектор
    прочитає всі 35 верстатів. `params` — параметри модуля (`factory3d.machine_connect.*`), що вмикаються ДО старту колектора.
    """

    def make(env: dict | None = None, scenario: tuple | None = None, params: dict | None = None, ready: bool = True):
        sim.post("/resume")
        sim.reset()
        sim.sync_time()
        out = stand_sh("fresh", "t0")
        assert "←" in out, out
        # Odoo ще не запущена: параметри вмикаємо після `serve`, але до першого опитування колектор не доходить — для
        # надійності колектор стартує вже після виставлення параметрів (serve = Odoo; collector-restart = колектор).
        out = stand_sh("odoo-start", env=env)
        assert "http" in out or "serve.sh stop" in out, "Odoo не стартувала: " + out
        o = odoo_rpc.Odoo()
        for k, v in (params or {}).items():
            o.param(k if k.startswith("factory3d.") else "factory3d.machine_connect." + k, v)
        if scenario:
            sim.scenario(scenario[0], **scenario[1])
        stand_sh("collector-restart", env=env)
        if ready:
            assert wait(lambda: _ready(o), 120, 3), "колектор не прочитав усі верстати: " + out
        return o

    yield make
    sim.post("/resume")
    sim.post("/time", {"factor": 1})
    sim.reset()
