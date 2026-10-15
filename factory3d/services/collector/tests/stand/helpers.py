"""Спільні засоби стенда телеметрії (SPEC §13.2–§13.4). Змінні: F3D_STAND_ODOO_URL/DB/LOGIN/PASSWORD (XML-RPC до Odoo),
F3D_STAND_SIM_URL, SIM_API_TOKEN, F3D_STAND_COLLECTOR_METRICS, F3D_STAND_DIR (логи/стан процесного стенда).
Якщо стенд не піднято — усі тести пропускаються з причиною (а не падають).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import odoo_rpc  # noqa: E402


HERE = Path(__file__).resolve().parent
COLLECTOR_DIR = HERE.parents[1]
STAND_DIR = Path(os.environ.get("F3D_STAND_DIR", "/tmp/f3dstand"))
SIM_URL = os.environ.get("F3D_STAND_SIM_URL", "http://127.0.0.1:8090/sim/v1")
SIM_TOKEN = os.environ.get("SIM_API_TOKEN", "stand-token-0123456789abcdef0123456789")
METRICS_URL = os.environ.get("F3D_STAND_COLLECTOR_METRICS", "http://127.0.0.1:9108")
ODOO_URL = odoo_rpc.URL


def http(method: str, url: str, body=None, headers=None, raw: bytes | None = None, timeout: float = 15.0):
    """(status, text, headers) без винятків на 4xx/5xx."""
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    hd = dict(headers or {})
    if body is not None and "Content-Type" not in hd:
        hd["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=hd)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


def wait(fn, timeout: float = 30, step: float = 0.5):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return None


class Sim:
    """Пульт емулятора (iot_sim §7.2)."""

    def __init__(self, base: str, token: str):
        self.base, self.token = base, token

    def req(self, method, path, body=None, auth=True):
        return http(method, self.base + path, body, {"Authorization": "Bearer " + self.token} if auth else {})

    def get(self, path):
        st, txt, _ = self.req("GET", path)
        return st, (json.loads(txt) if txt.startswith(("{", "[")) else txt)

    def post(self, path, body=None):
        st, txt, _ = self.req("POST", path, body or {})
        return st, (json.loads(txt) if txt.startswith(("{", "[")) else txt)

    def put(self, path, body=None):
        st, txt, _ = self.req("PUT", path, body or {})
        return st, (json.loads(txt) if txt.startswith(("{", "[")) else txt)

    def sig(self, code):
        st, d = self.get("/signals/" + code)
        assert st == 200, (code, d)
        return d

    def value(self, code):
        return self.sig(code)["value"]

    def scenario(self, name, **params):
        st, d = self.post(f"/scenario/{name}/start", {"params": params})
        assert st == 201, d
        return d

    def stop(self, name):
        return self.post(f"/scenario/{name}/stop")

    def reset(self, keep_time=True):
        return self.post("/reset", {"keep_time": keep_time})


class Metrics:
    def __init__(self, base: str):
        self.base = base

    def text(self) -> str:
        return http("GET", self.base + "/metrics")[1]

    def get(self, name: str, **labels) -> float | None:
        """Значення метрики; labels — підрядки ``key="value"``. None — метрики/мітки немає."""
        total, found = 0.0, False
        for line in self.text().splitlines():
            if not line.startswith(name) or line.startswith("#"):
                continue
            head, _, val = line.rpartition(" ")
            if head[len(name) : len(name) + 1] not in ("{", ""):
                continue
            if all(f'{k}="{v}"' in head for k, v in labels.items()):
                total += float(val)
                found = True
        return total if found else None

    def health(self) -> dict:
        return json.loads(http("GET", self.base + "/health")[1])


class CollectorProc:
    """Керування процесом колектора (еквівалент docker compose у процесному стенді)."""

    def __init__(self, odoo, extra_env: dict | None = None):
        self.odoo = odoo

    @staticmethod
    def sh(*args: str, env: dict | None = None, timeout: int = 180) -> str:
        e = {**os.environ, **(env or {})}
        r = subprocess.run(
            [str(HERE / "stand.sh"), *args], capture_output=True, text=True, env=e, timeout=timeout, check=False
        )
        return (r.stdout + r.stderr).strip()

    def restart(self, env: dict | None = None):
        out = self.sh("collector-restart", env=env)
        assert wait(lambda: self._up(), 60), out
        return out

    @staticmethod
    def _up() -> bool:
        try:
            return http("GET", METRICS_URL + "/health", timeout=3)[0] == 200
        except Exception:  # noqa: BLE001
            return False

    def log(self) -> str:
        p = STAND_DIR / "collector.log"
        return p.read_text(errors="replace") if p.exists() else ""

    def cli(self, *args: str) -> str:
        return self.sh("cli", *args, timeout=120)


def parse_title_number(text: str) -> float | None:
    m = re.search(r"(\d+[.,]?\d*)", text or "")
    return float(m.group(1).replace(",", ".")) if m else None
