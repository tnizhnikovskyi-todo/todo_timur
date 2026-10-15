"""Стенд (SPEC §13.2): клієнти pymodbus/asyncua/bacpypes3/paho/httpx проти docker compose (профіль dev).

Підняти: ``tests/stand/up.sh``; прогін: ``.venv/bin/pytest -m stand tests/stand``.
Хост: ``STAND_HOST`` або IP контейнера ``iot_sim-iot_sim-1`` у мережі f3d_sim (порти §8.1.3 не публікуються на хост — ТБ-01).
Токен: ``SIM_API_TOKEN`` з ``.env``.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
CONTAINER = os.environ.get("STAND_CONTAINER", "iot_sim-iot_sim-1")


def pytest_collection_modifyitems(items):
    for it in items:
        if "/stand/" in str(it.fspath):
            it.add_marker(pytest.mark.stand)


def _env_token() -> str:
    if os.environ.get("SIM_API_TOKEN"):
        return os.environ["SIM_API_TOKEN"]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("SIM_API_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("SIM_API_TOKEN не знайдено")


def _env_get(key: str) -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def docker(*args: str, check: bool = True) -> str:
    r = subprocess.run(["docker", *args], check=False, capture_output=True, text=True, timeout=120)
    if check and r.returncode:
        raise RuntimeError(r.stderr[-500:])
    return r.stdout.strip()


def container_ip() -> str:
    if os.environ.get("STAND_HOST"):
        return os.environ["STAND_HOST"]
    out = ""
    for _ in range(30):      # після recreate мережа підключається не одразу
        out = docker("inspect", CONTAINER, "-f",
                     "{{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}", check=False)
        for item in out.split():
            name, _, ip = item.partition("=")
            if name.endswith("f3d_sim") and ip:
                return ip
        time.sleep(1)
    raise RuntimeError(f"немає IP у мережі f3d_sim: {out}")


def fresh_service() -> None:
    """Перестворити iot_sim зі СВІЖИМ станом (том зі знімком видаляється: інакше mode/лічильники переживають рестарт)."""
    base = ["docker", "compose", "-f", "docker-compose.sim.yml", "--profile", "dev"]
    subprocess.run([*base, "rm", "-sf", "iot_sim"], cwd=ROOT, check=False, capture_output=True)
    subprocess.run(["docker", "volume", "rm", "-f", "iot_sim_iot_sim_state"], check=False, capture_output=True)
    subprocess.run([*base, "up", "-d", "iot_sim"], cwd=ROOT, check=True, capture_output=True)
    for _ in range(60):
        try:
            if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                return
        except Exception:  # noqa: BLE001, S110
            pass
        time.sleep(1)
    raise RuntimeError("iot_sim не піднявся")


@pytest.fixture
def host() -> str:  # IP контейнера змінюється після recreate (ТК-13, ТК-17, ТБ-07) — обчислюється щоразу
    return container_ip()


@pytest.fixture(scope="session")
def token() -> str:
    return _env_token()


@pytest.fixture(scope="session")
def env_get():
    return _env_get


@pytest.fixture(scope="session")
def api_url() -> str:
    return os.environ.get("STAND_API", "http://127.0.0.1:8090/sim/v1")


@pytest.fixture(scope="session", autouse=True)
def _health(api_url):
    for _ in range(60):
        try:
            if httpx.get(api_url + "/health", timeout=3).json().get("status") == "ok":
                return
        except Exception:  # noqa: BLE001, S110
            pass
        time.sleep(1)
    pytest.fail("GET /health != ok: стенд не піднято (tests/stand/up.sh)")


class Api:
    """Синхронний клієнт REST керування."""

    def __init__(self, base: str, token: str):
        self.base, self.token = base, token
        self.c = httpx.Client(timeout=15)

    def req(self, method, path, *, auth=True, token=None, **kw):
        h = {}
        if auth:
            h["Authorization"] = "Bearer " + (token if token is not None else self.token)
        return self.c.request(method, self.base + path, headers=h, **kw)

    def get(self, path, **kw):
        return self.req("GET", path, **kw)

    def post(self, path, json=None, **kw):
        return self.req("POST", path, json=json, **kw)

    def put(self, path, json=None, **kw):
        return self.req("PUT", path, json=json, **kw)

    def sig(self, code):
        return self.get("/signals/" + code).json()["value"]

    def signals(self, prefix):
        return {i["code"]: i for i in self.get("/signals", params={"prefix": prefix, "limit": 2000}).json()["items"]}

    def scenario(self, name, **params):
        r = self.post(f"/scenario/{name}/start", {"params": params})
        assert r.status_code == 201, r.text
        return r.json()

    def wait(self, fn, timeout=30, step=0.5):
        end = time.time() + timeout
        while time.time() < end:
            v = fn()
            if v:
                return v
            time.sleep(step)
        return None


@pytest.fixture(scope="session")
def _api(api_url, token):
    return Api(api_url, token)


@pytest.fixture
def api(_api):
    """REST-клієнт; після кожного ТК — POST /reset (SPEC §13.2), час повертається до factor=1."""
    assert _api.post("/resume").status_code == 200
    _api.post("/mode", {"mode": "scenario"})
    _api.post("/reset")
    _api.post("/time", {"factor": 1})
    yield _api
    _api.post("/resume")
    _api.post("/time", {"factor": 1})
    _api.post("/reset")
