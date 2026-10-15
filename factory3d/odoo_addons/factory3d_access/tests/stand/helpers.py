"""Клієнти стенду: XML-RPC до Odoo і REST керування емулятора (/sim/v1)."""
from __future__ import annotations

import os
import ssl
import time
import xmlrpc.client
from datetime import UTC, datetime, timedelta

import httpx


def env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        raise RuntimeError(f"змінна середовища {name} не задана (див. DEPLOY_TEST.md)")
    return val


class Odoo:
    """Тонка обгортка над ``xmlrpc/2``; ``k`` = ``execute_kw``."""

    def __init__(self, url: str, db: str, user: str, password: str):
        self.url, self.db, self.user, self.password = url.rstrip("/"), db, user, password
        ctx = ssl.create_default_context()
        self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True, context=ctx)
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True, context=ctx)
        self.uid = self.common.authenticate(db, user, password, {})
        if not self.uid:
            raise RuntimeError("Odoo: автентифікація не вдалась")

    def as_user(self, login: str, password: str) -> Odoo:
        return Odoo(self.url, self.db, login, password)

    def k(self, model: str, method: str, *args, **kw):
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, list(args), kw)

    def param(self, key: str, value: str | None):
        full = f"factory3d.access.{key}"
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

    def server(self) -> dict:
        rows = self.k("f3d.access.server", "search_read", [], ["name", "url", "state", "error_count", "last_error",
                      "users_total", "devices_total", "next_try_at", "last_poll_new", "last_poll_rows",
                      "last_event_ts"], limit=1, order="id")
        return rows[0]

    def poll(self, server_id: int, times: int = 1):
        """«Опитати зараз»; повертає останнє повідомлення нотифікації."""
        res = None
        for _ in range(times):
            for attempt in range(12):       # одночасно з кроном «опитування подій» (lock) — повторити
                try:
                    res = self.k("f3d.access.server", "action_poll_now", [server_id])
                    break
                except xmlrpc.client.Fault as fault:
                    if "вже виконується" not in str(fault) or attempt == 11:
                        raise
                    time.sleep(3)
        return res

    def poll_until_quiet(self, server_id: int, *, max_rounds: int = 12) -> int:
        """Опитує, поки сторінки не закінчаться (last_poll_more=False) і нових подій немає; повертає суму нових."""
        total = 0
        for _ in range(max_rounds):
            self.poll(server_id)
            row = self.k("f3d.access.server", "read", [server_id], ["last_poll_new", "last_poll_more"])[0]
            total += row["last_poll_new"]
            if not row["last_poll_more"] and not row["last_poll_new"]:
                break
        return total


class Sim:
    """REST керування емулятора з Bearer-токеном."""

    def __init__(self, url: str, token: str):
        self.http = httpx.Client(base_url=url.rstrip("/"), headers={"Authorization": f"Bearer {token}"}, timeout=15)

    def get(self, path: str):
        r = self.http.get("/sim/v1" + path)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict | None = None):
        r = self.http.post("/sim/v1" + path, json=body or {})
        r.raise_for_status()
        return r.json()

    def set_time(self, local_iso: str, factor: float = 10):
        return self.post("/time", {"set": local_iso, "factor": factor})

    def access_event(self, device: str, user: str, code: int = 4102, tna_key: str = "", **extra):
        params = {"device": device, "user": user, "code": code, "tna_key": tna_key, **extra}
        return self.post("/scenario/access_event/start", {"params": params})

    def scenario(self, name: str, params: dict | None = None):
        return self.post(f"/scenario/{name}/start", {"params": params or {}})


def kyiv_iso(day: str, hhmm: str) -> str:
    """'2026-10-14', '06:30' -> '2026-10-14T06:30:00+03:00' (до 25.10.2026 діє літній час, DEC-4)."""
    return f"{day}T{hhmm}:00+03:00"


def utc_now() -> datetime:
    return datetime.now(UTC)


def wait_for(cond, timeout: float = 60, step: float = 1.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        val = cond()
        if val:
            return val
        time.sleep(step)
    return cond()


def day_before(days: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
