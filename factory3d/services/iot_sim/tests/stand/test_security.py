"""ТБ-01 (ізоляція compose), ТБ-05 (хеші каталогу), ТБ-07 (allow-list вихідних з'єднань)."""
import csv
import hashlib
import io
import json
import subprocess
import time

import httpx

from .conftest import ROOT, docker

ODOO_CSV = ROOT.parents[1] / "odoo_addons" / "td_iot_sim" / "data" / "td_sim_signal.csv"
COMPOSE = ["docker", "compose", "-f", "docker-compose.sim.yml"]


def _cfg(profile):
    r = subprocess.run([*COMPOSE, "--profile", profile, "config", "--format", "json"], cwd=ROOT, check=True,
                       capture_output=True, text=True, env={**__import__("os").environ, "TD_GENSET_PATH": "/x"})
    return json.loads(r.stdout)


def test_tb01_compose_isolation():
    demo = _cfg("demo")
    assert demo["networks"]["f3d_sim"]["internal"] is True
    for name, svc in demo["services"].items():
        assert not svc.get("ports"), f"{name}: ports опубліковано в profile demo"
    dev = _cfg("dev")["services"]
    pub = {(p["host_ip"], int(p["published"])) for p in dev["iot_sim"]["ports"]}
    assert pub == {("127.0.0.1", 8090), ("127.0.0.1", 4840)}
    assert not dev["mosquitto"].get("ports")
    sim = dev["iot_sim"]
    assert sim["cap_drop"] == ["ALL"] and sim["read_only"] is True and sim["user"] == "10001:10001"
    # docker ps / inspect запущеного стенду: порти 502/47808/… на хост не опубліковані
    ports = docker("ps", "--format", "{{.Names}} {{.Ports}}")
    line = next(ln for ln in ports.splitlines() if ln.startswith("iot_sim-iot_sim-1"))
    for bad in ("502", "47808", "50000", "8081", "8082", "4001", "1883"):
        assert f":{bad}->" not in line, line
    hc = json.loads(docker("inspect", "iot_sim-iot_sim-1"))[0]["HostConfig"]
    assert hc["CapDrop"] == ["ALL"] and hc["ReadonlyRootfs"] is True and not hc["Privileged"]
    net = json.loads(docker("network", "inspect", "iot_sim_f3d_sim"))[0]
    assert net["Internal"] is True
    mos = json.loads(docker("inspect", "iot_sim-mosquitto-1"))[0]["NetworkSettings"]["Ports"]
    assert not any(mos.get(k) for k in mos)


def _pairs(text):
    return {(r["code"], r["address"]) for r in csv.DictReader(io.StringIO(text))}


def test_tb05_catalog_sets_equal(api):
    svc = (ROOT / "catalog" / "signals.csv").read_text(encoding="utf-8")
    odoo = ODOO_CSV.read_text(encoding="utf-8")
    rest = api.get("/catalog/signals.csv").text
    a, b, c = _pairs(svc), _pairs(odoo), _pairs(rest)
    assert len(a) == 1205
    assert a == b == c
    assert hashlib.sha256(svc.encode()).hexdigest() == hashlib.sha256(rest.encode()).hexdigest()
    # множина сигналів з GET /sim/v1/signals ⊂ каталог (без protocol=none)
    items = api.get("/signals", params={"limit": 2000}).json()["items"]
    codes = {r["code"] for r in csv.DictReader(io.StringIO(svc)) if r["protocol"] != "none"}
    assert {i["code"] for i in items} <= codes and len(items) >= 1000
    st = api.get("/status").json()
    assert st["catalog_hash"].startswith("sha256:")


def test_tb07_outbound_allowlist(api, token):
    """SIM_LPR_PUSH_URL на хост поза списком → з'єднання не встановлюється, метрика iot_sim_outbound_denied_total."""
    off = ROOT / "tests" / "stand" / "_out.override.yml"
    off.write_text("services:\n  iot_sim:\n    environment:\n      SIM_LPR_PUSH_URL: http://203.0.113.9:9/lpr\n")
    base = [*COMPOSE, "--profile", "dev"]
    try:
        subprocess.run([*base, "-f", str(off), "up", "-d", "--force-recreate", "iot_sim"], cwd=ROOT, check=True,
                       capture_output=True)
        for _ in range(60):
            try:
                if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        time.sleep(3)
        h = {"Authorization": "Bearer " + token}
        httpx.post("http://127.0.0.1:8090/sim/v1/time", json={"set": "2026-10-14T06:25:00+03:00", "factor": 3}, headers=h)
        r = httpx.post("http://127.0.0.1:8090/sim/v1/scenario/truck_arrival/start",
                       json={"params": {"booking": "BATCH/IN/00001"}}, headers=h)
        assert r.status_code == 201, r.text

        def denied():
            m = httpx.get("http://127.0.0.1:8090/sim/v1/metrics").text
            return next((float(ln.split()[-1]) for ln in m.splitlines()
                         if ln.startswith("iot_sim_outbound_denied_total")), 0.0)

        end = time.time() + 60
        while time.time() < end and denied() < 1:
            time.sleep(2)
        assert denied() >= 1, "метрика outbound_denied не зросла"
        log = docker("logs", "iot_sim-iot_sim-1", check=False)
        assert "outbound denied" in log
    finally:
        off.unlink()
        subprocess.run([*base, "up", "-d", "--force-recreate", "iot_sim"], cwd=ROOT, check=True, capture_output=True)
        for _ in range(60):
            try:
                if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)
