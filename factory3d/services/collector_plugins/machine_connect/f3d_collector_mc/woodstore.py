"""Адаптер `woodstore` (§8.5, P-03, R-23): статус, події, стоси, завдання порталу, команди CMD-02."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
from typing import TYPE_CHECKING, Any

from collector.core.errors import PollError, WriteError
from collector.core.types import SignalCfg

from .events import canonical_json, state_dir
from .generic import GenericAdapter

if TYPE_CHECKING:
    from .rest_vendor import RestVendorPlugin

ROUTE = "mc_woodstore"
STATUS_PATH = "/api/v1/status"
EVENTS_CHUNK = 200
JOBS_CHUNK = 200
STACKS_CHUNK = 50
STACKS_RESEND_S = 15 * 60


def _chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _sha(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


class WoodStoreAdapter(GenericAdapter):
    def __init__(self, plugin: RestVendorPlugin) -> None:
        super().__init__(plugin)
        p = plugin.source.params
        self.events_period = float(p.get("events_period_s", 2))
        self.stacks_period = float(p.get("stacks_period_s", 30))
        self.jobs_period = float(p.get("jobs_period_s", 10))
        self.state_path = state_dir(plugin.ctx) / f"woodstore_{plugin.source.code}.json"
        self.cursor: dict[str, Any] = {}
        self._status_hash: str | None = None
        self._stacks_sent_at: float | None = None
        self._jobs_mem: dict[str, tuple] = {}
        self._tasks: list[asyncio.Task] = []

    # --- курсори ---
    def _load_state(self) -> None:
        try:
            self.cursor = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.cursor = {}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cursor, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.state_path)

    # --- життєвий цикл ---
    async def start(self) -> None:
        self._load_state()
        code = self.plugin.source.code
        for name, step, period in (
            ("events", self.events_step, self.events_period),
            ("stacks", self.stacks_step, self.stacks_period),
            ("jobs", self.jobs_step, self.jobs_period),
        ):
            self._tasks.append(asyncio.create_task(self._loop(name, step, period), name=f"woodstore-{name}-{code}"))

    async def stop(self) -> None:
        tasks, self._tasks = self._tasks, []
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _loop(self, name: str, step: Any, period: float) -> None:
        while True:
            try:
                await step()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - фонова задача не падає
                self.plugin.ctx.log.warning("woodstore %s_loop: %s", name, exc)
            await self.plugin.clock.sleep(period)

    def _emit(self, payload: dict) -> None:
        payload = {**payload, "source": self.plugin.source.code}
        self.plugin.emit_event(ROUTE, payload)

    async def _get_list(self, path: str, params: dict | None) -> Any:
        from .rest_vendor import NetError

        try:
            resp = await self.plugin.request("GET", path, params=params)
        except NetError as exc:
            raise PollError(str(exc)) from exc
        return resp

    # --- статус (після GET /status у poll) ---
    async def on_response(self, method: str, path: str, query: dict, body: Any) -> None:
        if method != "GET" or path != STATUS_PATH or not isinstance(body, dict):
            return
        digest = _sha({k: body.get(k) for k in ("state", "current_job", "aisles", "alarms")})
        if digest != self._status_hash:
            self._status_hash = digest
            self._emit({"kind": "status", "status": body})

    # --- events_loop ---
    async def events_step(self) -> None:
        cursor = self.cursor.get("last_event_id")
        resp = await self._get_list("/api/v1/events", {"since": cursor} if cursor is not None else None)
        if resp.status in (404, 410) or (resp.status == 400 and cursor is not None):
            self.cursor.pop("last_event_id", None)
            self._save_state()
            return
        if resp.status >= 400:
            raise PollError(f"HTTP {resp.status} /api/v1/events")
        items = resp.json() or []
        for chunk in _chunks(items, EVENTS_CHUNK):
            self._emit({"kind": "events", "items": chunk})
            self.cursor["last_event_id"] = chunk[-1].get("id")
            self._save_state()

    # --- stacks_loop ---
    async def stacks_step(self) -> None:
        resp = await self._get_list("/api/v1/stacks", None)
        if resp.status >= 400:
            raise PollError(f"HTTP {resp.status} /api/v1/stacks")
        items = resp.json() or []
        digest = _sha([{k: v for k, v in it.items() if k != "updated"} for it in items])
        now = self.plugin.clock.monotonic()
        stale = self._stacks_sent_at is None or now - self._stacks_sent_at >= STACKS_RESEND_S
        if digest == self.cursor.get("stacks_hash") and not stale:
            return
        for chunk in _chunks(items, STACKS_CHUNK):
            self._emit({"kind": "stacks", "hash": digest, "items": chunk})
        self._stacks_sent_at = now
        self.cursor["stacks_hash"] = digest
        self._save_state()

    # --- jobs_loop ---
    async def jobs_step(self) -> None:
        since = self.cursor.get("jobs_since")
        resp = await self._get_list("/api/v1/jobs", {"since": since} if since else None)
        if resp.status >= 400:
            raise PollError(f"HTTP {resp.status} /api/v1/jobs")
        items = resp.json() or []
        changed = []
        for it in items:
            key = (it.get("state"), it.get("done"))
            if self._jobs_mem.get(it.get("id")) != key:
                self._jobs_mem[it.get("id")] = key
                changed.append(it)
        for chunk in _chunks(changed, JOBS_CHUNK):
            self._emit({"kind": "jobs", "items": chunk})
        stamps = [str(it[k]) for it in items for k in ("created", "started", "finished") if it.get(k)]
        if stamps:
            self.cursor["jobs_since"] = max(stamps)
            self._save_state()

    # --- команди CMD-02 (R-23 п. 5) ---
    async def command(self, signal: SignalCfg, payload: dict) -> dict:
        op = payload["op"]
        if op == "feed":
            body = {
                "type": "feed",
                "source": payload["stack"],
                "target": payload["target"],
                "sheets": payload["sheets"],
                "product": payload["product"],
                "lot": None,
                "priority": payload["priority"],
                "external_ref": payload["ref"],
            }
            resp = await self.plugin.request("POST", "/api/v1/jobs", json_body=body)
            self._check(resp, 201)
            data = resp.json() or {}
            return {"id": data.get("id"), "state": data.get("state")}
        if op == "cancel":
            resp = await self.plugin.request("DELETE", f"/api/v1/jobs/{payload['id']}")
            self._check(resp, 200)
            data = resp.json() if resp.body else {}
            return {"id": (data or {}).get("id", payload["id"]), "state": (data or {}).get("state", "cancelled")}
        body = {"qty": payload["qty"], "product": payload["product"], "lot": payload["lot"], "reason": "odoo_inventory"}
        resp = await self.plugin.request("PATCH", f"/api/v1/stacks/{payload['stack']}", json_body=body)
        self._check(resp, 200)
        return {"id": payload["stack"], "qty": payload["qty"]}

    @staticmethod
    def _check(resp: Any, ok: int) -> None:
        if resp.status == 409:
            message = ""
            with contextlib.suppress(ValueError):
                data = resp.json() or {}
                message = str(data.get("message") or data.get("error") or "")
            raise WriteError(f"CONFLICT: {message}")
        if resp.status >= 400:
            raise WriteError(f"HTTP {resp.status}")
