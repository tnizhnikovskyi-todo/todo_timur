import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from iot_sim.protocols.control_api import create_app

    return TestClient(create_app())
