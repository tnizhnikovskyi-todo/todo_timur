"""ТК-13 (REST і стоп-крани), ТБ-02/03/09-частково, ТП-05, ТК-14 (час), ТК-16 (рестарт)."""
import re
import statistics
import time

import httpx
import pytest

from .conftest import docker


def test_tk13_endpoints_with_and_without_token(api):
    for path in ("/status", "/devices", "/devices/CNC-2", "/scenarios", "/runs", "/signals", "/events",
                 "/catalog/signals.csv", "/catalog/devices.json"):
        assert api.get(path).status_code == 200, path
    for path in ("/status", "/devices", "/signals"):   # ≤ 5 хибних на хвилину: далі — блокування IP (ТБ-02)
        assert api.get(path, auth=False).status_code == 401, path
    assert api.get("/health", auth=False).json()["status"] == "ok"
    assert api.get("/metrics", auth=False).status_code in (200, 401)
    assert api.get("/devices/NOPE").status_code == 404
    assert api.post("/scenario/shift/start", {"params": {}}, auth=False).status_code == 401
    time.sleep(61)  # вікно лімітера хибних токенів


def test_tk13_stop_all_resume(api):
    assert api.post("/stop-all").status_code == 200
    r = api.post("/scenario/shift/start", {"params": {}})
    assert r.status_code == 423
    assert api.post("/device/CNC-2/fault", {"reason": "generic"}).status_code == 423
    assert api.get("/status").status_code == 200      # читання працює
    assert api.post("/resume").status_code == 200
    assert api.post("/scenario/shift/start", {"params": {}}).status_code == 201


def test_tk13_put_signal_hold(api):
    code = "workcenters/SAW-1/pieces_out"
    r = api.put("/signals/" + code, {"value": 77, "hold_s": 120})
    assert r.status_code == 200 and r.json()["held_until"]
    time.sleep(2.5)
    assert api.sig(code) == 77
    assert api.put("/signals/" + code, {"release": True}).status_code == 200
    assert api.put("/signals/" + code, {"value": 1, "hold_s": 999999}).status_code == 422
    assert api.get("/signals/equipment/GANTRY-1/stacks").status_code == 404   # X-76


def test_tk13_sim_enabled_0_restart(api, token):
    """SIM_ENABLED=0: рестарт з env → 423 на запис; повернення — recreate без змінної."""
    import subprocess

    from .conftest import ROOT
    off = ROOT / "tests" / "stand" / "_off.override.yml"
    off.write_text("services:\n  iot_sim:\n    environment:\n      SIM_ENABLED: \"0\"\n")
    base = "docker compose -f docker-compose.sim.yml --profile dev"
    env = dict(__import__("os").environ)
    subprocess.run((base + f" -f {off} up -d --force-recreate iot_sim").split(), cwd=ROOT, env=env, check=True,
                   capture_output=True)
    try:
        for _ in range(40):
            try:
                if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        h = {"Authorization": "Bearer " + token}
        r = httpx.post("http://127.0.0.1:8090/sim/v1/scenario/shift/start", json={"params": {}}, headers=h)
        assert r.status_code == 423, r.text
        assert httpx.post("http://127.0.0.1:8090/sim/v1/resume", headers=h).status_code == 423
    finally:
        off.unlink()
        subprocess.run((base + " up -d --force-recreate iot_sim").split(), cwd=ROOT, env=env, check=True,
                       capture_output=True)
        for _ in range(40):
            try:
                if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)


def test_tb02_token_checks_and_429(api):
    assert api.get("/status", auth=False).status_code == 401
    assert api.get("/status", token="wrong").status_code == 401
    assert api.get("/status", token="x" * 200).status_code == 401
    codes = [api.get("/status", token=f"bad{i}").status_code for i in range(8)]
    assert 429 in codes
    # навіть правильний токен із заблокованого IP — 429; чекаємо 60 с
    assert api.get("/status").status_code == 429
    assert api.wait(lambda: api.get("/status").status_code == 200, timeout=75, step=3)


def test_tb03_injections(api):
    assert api.post("/device/..%2Fetc%2Fpasswd/fault", {"reason": "generic"}).status_code in (404, 422)
    assert api.post("/device/../etc/passwd/fault", {"reason": "generic"}).status_code in (404, 422)
    assert api.post("/device/CNC-2; DROP/fault", {"reason": "generic"}).status_code in (404, 422)
    assert api.post("/device/CNC-2/fault", {"reason": "generic", "note": "A" * 10240}).status_code in (413, 422, 200)
    api.post("/device/CNC-2/clear")
    deep: dict = {}
    cur = deep
    for _ in range(100):
        cur["a"] = {}
        cur = cur["a"]
    assert api.post("/scenario/shift/start", {"params": deep}).status_code in (400, 422)
    assert api.post("/scenario/shift; DROP/start", {"params": {}}).status_code == 404
    assert api.get("/status").status_code == 200       # сервіс живий
    log = docker("logs", "iot_sim-iot_sim-1", check=False)
    assert "Traceback" not in "\n".join(l for l in log.splitlines() if "Unhandled" in l or "ASGI" in l)


def test_tb06_no_secrets_in_logs(env_get):
    import subprocess
    r = subprocess.run(["docker", "logs", "iot_sim-iot_sim-1"], check=False, capture_output=True, text=True)
    log = r.stdout + r.stderr
    for key in ("SIM_API_TOKEN", "SIM_BIOSTAR_PASS", "SIM_WOODSTORE_APIKEY", "SIM_JOBS_APIKEY", "SIM_OPCUA_PASS"):
        val = env_get(key)
        if val:
            assert val not in log, key
    assert not re.search(r"bs-session-id[\"':= ]+[0-9a-f-]{16,}", log, re.IGNORECASE)


def test_tp05_signals_rate(api):
    lat = []
    t_end = time.time() + 20
    n = 0
    while time.time() < t_end:
        t0 = time.perf_counter()
        r = api.get("/signals", params={"limit": 2000})
        lat.append(time.perf_counter() - t0)
        assert r.status_code == 200
        n += 1
        time.sleep(max(0, 0.1 - lat[-1]))
    p95 = statistics.quantiles(lat, n=20)[18]
    cnt = r.json()["count"]
    assert cnt >= 900, cnt
    assert p95 < 0.1, f"p95={p95:.3f}"


def test_tk14_time_factor(api):
    r = api.post("/time", {"factor": 10, "set": "2026-10-12T06:30:00+03:00"})
    assert r.status_code == 200
    t0 = api.get("/status").json()["sim_now"]
    time.sleep(10)
    t1 = api.get("/status").json()["sim_now"]
    from datetime import datetime
    d = (datetime.fromisoformat(t1) - datetime.fromisoformat(t0)).total_seconds()
    assert 85 <= d <= 115, d       # 10 с реального × 10
    assert api.post("/time", {"factor": 500}).status_code == 422


@pytest.mark.timeout(240)
def test_tk16_restore_after_restart(api):
    api.post("/time", {"factor": 60, "set": "2026-10-12T10:00:00+03:00"})
    api.scenario("shift")
    api.post("/device/CNC-3/fault", {"reason": "generic"})
    time.sleep(12)
    before = api.sig("workcenters/SAW-1/pieces_out")
    # снапшот раз на SIM_SNAPSHOT_S (60 с реального); чекаємо його і перезапускаємо
    time.sleep(62)
    docker("restart", "iot_sim-iot_sim-1")
    for _ in range(60):
        try:
            if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    time.sleep(2)
    assert "restored" in docker("logs", "iot_sim-iot_sim-1", check=False)
    after = api.sig("workcenters/SAW-1/pieces_out")
    assert after >= before * 0.5          # лічильники продовжені, не скинуті в 0 (AC-48)
    assert api.get("/devices/CNC-3").json()["state"] == "fault"
