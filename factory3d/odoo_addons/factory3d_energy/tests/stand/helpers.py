"""Клієнти стенду factory3d_energy: XML-RPC до Odoo і REST керування емулятора (/sim/v1)."""

from __future__ import annotations

import os
import time
import xmlrpc.client

import httpx


def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"змінна середовища {name} не задана (див. DEPLOY_TEST.md)")
    return val


class OdooFault(Exception):
    """Помилка Odoo (усічена до останнього рядка)."""


class Odoo:
    """Тонка обгортка над ``xmlrpc/2``; ``k`` = ``execute_kw``."""

    def __init__(self, url: str, db: str, user: str, password: str):
        self.url, self.db, self.user, self.password = url.rstrip("/"), db, user, password
        self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        self.uid = self.common.authenticate(db, user, password, {})
        if not self.uid:
            raise RuntimeError(f"Odoo: автентифікація {user} не вдалась")

    def as_user(self, login: str, password: str) -> Odoo:
        return Odoo(self.url, self.db, login, password)

    def k(self, model: str, method: str, *args, **kw):
        try:
            return self.models.execute_kw(self.db, self.uid, self.password, model, method, list(args), kw)
        except xmlrpc.client.Fault as fault:  # без багаторядкового трейсбека Odoo у виводі pytest
            lines = [ln for ln in str(fault.faultString).strip().splitlines() if ln.strip()]
            raise OdooFault(f"{model}.{method}: {lines[-1] if lines else fault.faultCode}") from None

    def param(self, key: str, value: str | None, prefix: str = "factory3d.energy."):
        full = prefix + key
        ids = self.k("ir.config_parameter", "search", [("key", "=", full)])
        if value is None:
            if ids:
                self.k("ir.config_parameter", "unlink", ids)
        elif ids:
            self.k("ir.config_parameter", "write", ids, {"value": value})
        else:
            self.k("ir.config_parameter", "create", {"key": full, "value": value})

    def get_param(self, full_key: str) -> str | None:
        return self.k("ir.config_parameter", "get_param", full_key) or None

    def signal(self, code: str) -> dict:
        rows = self.k(
            "f3d.signal",
            "search_read",
            [("code", "=", code)],
            ["last_value", "last_ts", "last_quality", "status"],
            limit=1,
        )
        return rows[0] if rows else {}

    def energy_source_ids(self) -> list[int]:
        """Джерела, створені модулем energy (без EN-DERIVED): 68."""
        ids = [
            r["res_id"]
            for r in self.k(
                "ir.model.data",
                "search_read",
                [("module", "=", "factory3d_energy"), ("model", "=", "f3d.source")],
                ["res_id"],
            )
        ]
        return self.k("f3d.source", "search", [("id", "in", ids), ("code", "!=", "EN-DERIVED")])

    def ref_id(self, xmlid: str) -> int:
        mod, name = xmlid.split(".", 1)
        return self.k("ir.model.data", "search_read", [("module", "=", mod), ("name", "=", name)], ["res_id"], limit=1)[
            0
        ]["res_id"]


class Sim:
    """REST керування емулятора з Bearer-токеном."""

    def __init__(self, url: str, token: str):
        self.http = httpx.Client(base_url=url.rstrip("/"), headers={"Authorization": f"Bearer {token}"}, timeout=15)

    def get(self, path: str, **params):
        r = self.http.get("/sim/v1" + path, params=params or None)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None):
        r = self.http.post("/sim/v1" + path, json=body or {})
        r.raise_for_status()
        return r.json()

    def put(self, path: str, body: dict):
        r = self.http.put("/sim/v1" + path, json=body)
        r.raise_for_status()
        return r.json()

    def value(self, code: str) -> float:
        return float(self.get("/signals/" + code)["value"])

    def scenario(self, name: str, params: dict | None = None):
        return self.post(f"/scenario/{name}/start", {"params": params or {}})


def wait_for(cond, timeout: float = 60, step: float = 1.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        val = cond()
        if val:
            return val
        time.sleep(step)
    return cond()


def shell_json(script: str, marker: str, db: str | None = None, timeout: int = 600, **env_extra) -> dict:
    """Запускає ``script`` у ``odoo-bin shell`` бази стенду (stdin) і повертає JSON з рядка ``<marker> {...}``.

    Потрібен ``F3D_ENV_SH`` (factory3d/tools/odoo/env.sh: ODOO_PY, ODOO_BIN, ODOO_CONF, ODOO_ADDONS_PATH)."""
    import json
    import subprocess
    from pathlib import Path

    env_sh = os.environ.get("F3D_ENV_SH")
    if not env_sh:
        raise RuntimeError("F3D_ENV_SH (factory3d/tools/odoo/env.sh) не задано: odoo shell недоступний")
    cmd = (
        f'source "{env_sh}" && "$ODOO_PY" "$ODOO_BIN" shell -c "$ODOO_CONF" --addons-path="$ODOO_ADDONS_PATH" '
        f'-d "{db or os.environ["F3D_ODOO_DB"]}" --no-http --log-level=warn < "{Path(__file__).parent / script}"'
    )
    res = subprocess.run(
        ["bash", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **{k: str(v) for k, v in env_extra.items()}},
    )
    lines = [x for x in res.stdout.splitlines() if x.startswith(marker + " ")]
    if not lines:
        raise RuntimeError(f"shell {script}: немає {marker}: {res.stdout[-300:]} {res.stderr[-300:]}")
    return json.loads(lines[-1][len(marker) + 1 :])
