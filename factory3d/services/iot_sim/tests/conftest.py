import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SEED = 20261012


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from iot_sim.protocols.control_api import create_app

    return TestClient(create_app())


@pytest.fixture(scope="session")
def registry():
    from iot_sim.core.registry import Registry

    return Registry.load(ROOT / "catalog")


@pytest.fixture
def clock():
    from iot_sim.core.clock import FakeClock

    return FakeClock("2026-10-12T10:30:00")  # 12.10.2026 10:30 Київ


@pytest.fixture
def world(registry, clock):
    """SPEC §13.1: ``world(seed=20261012, clock=FakeClock(2026-10-12 10:30 Київ))``."""
    from iot_sim.core.world import World

    return World(registry, seed=SEED, clock=clock)
