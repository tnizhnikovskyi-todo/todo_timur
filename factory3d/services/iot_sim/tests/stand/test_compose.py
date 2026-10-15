"""ТК-18: compose з genset_relay за CI-02 (td_genset §8.5). Повний прогін потребує клону td_genset (TD_GENSET_PATH)."""
import os
import subprocess
from pathlib import Path

import pytest

from .conftest import ROOT


def _cfg(env):
    r = subprocess.run(["docker", "compose", "-f", "docker-compose.sim.yml", "--profile", "dev", "config", "--format",
                        "json"], cwd=ROOT, check=True, capture_output=True, text=True, env={**os.environ, **env})
    import json
    return json.loads(r.stdout)["services"]


def test_tk18_step1_compose_config_has_genset_relay():
    """Крок 1: `compose --profile dev config` валідний; genset_relay: env/мережі за td_genset §8.5."""
    svc = _cfg({"TD_GENSET_PATH": "/opt/td_genset", "RELAY_SIM_TOKEN": "t" * 32})
    r = svc["genset_relay"]
    assert r["environment"]["RELAY_PROFILE"] == "d700" and r["environment"]["RELAY_PORT"] == "8000"
    assert r["environment"]["RELAY_SIM_TOKEN"] == "t" * 32
    assert set(r["networks"]) == {"f3d_sim", "odoo_default"}
    assert svc["iot_sim"]["environment"]["SIM_GENSET_RELAY_TOKEN"] == "t" * 32     # той самий токен (X-75)


@pytest.mark.skipif(not os.environ.get("TD_GENSET_PATH") or not (Path(os.environ.get("TD_GENSET_PATH", "")) / "relay").is_dir(),
                    reason="немає TD_GENSET_PATH/relay: у td_genset (origin/claude/dreamy-ramanujan-p2wlej) немає каталогу relay/ і /sim/v1 API-F — запасний режим §8.14")
def test_tk18_steps2_5_genset_relay_up():  # pragma: no cover - потребує td_genset

    token = os.environ["RELAY_SIM_TOKEN"]
    subprocess.run(["docker", "compose", "-f", "docker-compose.sim.yml", "--profile", "dev", "up", "-d", "--build",
                    "iot_sim", "mosquitto", "genset_relay"], cwd=ROOT, check=True)
    code = ("import urllib.request;r=urllib.request.Request('http://genset_relay:8000/sim/v1/state',"
            f"headers={{'Authorization':'Bearer {token}'}});print(urllib.request.urlopen(r).read())")
    out = subprocess.run(["docker", "exec", "iot_sim-iot_sim-1", "python", "-c", code],
                         check=True, capture_output=True, text=True).stdout
    assert "D700" in out

