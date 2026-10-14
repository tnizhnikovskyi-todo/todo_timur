"""P-03 woodStore API v1 (SPEC §8.5): портал STORETEQ P-500, ``GET/PATCH/POST/DELETE /api/v1/*``.

Стан (стоси, завдання, події) веде цей модуль; значення вакууму/циклів беруться з сигналів
``equipment/GANTRY-1/*`` у World, якщо вони є. Тік (``world.on_tick``): активне завдання кладе
1 лист кожні ``sheet_period_s`` sim-секунд і зменшує ``qty`` стосу (R-18). Стан для моделі порталу:
``world.flags["woodstore"] = {"state", "current_job"}``. Нові завдання від ``/jobs`` (API-33)
надходять через ``world.post("woodstore_jobs", {...})`` (поля як у POST /jobs).
Режим ``follow_odoo`` (авто-``feed`` за РЦ у роботі) — НЕ реалізовано (ПРИПУЩЕННЯ).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections import deque
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer

log = logging.getLogger("iot_sim.woodstore")

TARGETS = ("SAW-1", "SAW-2", "SAW-3", "NEST-1")
JOB_TYPES = ("feed", "restack", "return", "count")
JOB_STATES = ("queued", "active", "done", "cancelled", "error")
PORTAL_STATES = ("idle", "moving", "picking", "placing", "blocked", "error")
EVENT_RING = 2000
DEMO_PRODUCTS = ("DSP16-SON", "DSP16-WHT", "DSP18-ANT", "MDF18-RAW", "HDF3-WHT", "DSP16-OAK")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


class JobIn(BaseModel):
    type: str = "feed"
    source: str | None = None
    target: str | None = None
    sheets: int = 1
    product: str | None = None
    lot: str | None = None
    priority: int = 5
    external_ref: str | None = None


class StackPatch(BaseModel):
    qty: int | None = None
    product: str | None = None
    lot: str | None = None
    reason: str | None = None


class UvicornRunner:
    """Uvicorn усередині поточного event loop (без обробників сигналів)."""

    def __init__(self, app: FastAPI, host: str, port: int) -> None:
        cfg = uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="off")
        self.server = uvicorn.Server(cfg)
        self.server.capture_signals = contextlib.nullcontext  # type: ignore[method-assign]
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        self.task = asyncio.create_task(self.server.serve())
        for _ in range(200):
            if self.server.started or self.task.done():
                break
            await asyncio.sleep(0.05)
        if not self.server.started:
            raise RuntimeError("uvicorn не стартував")

    async def stop(self) -> None:
        self.server.should_exit = True
        if self.task:
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    @property
    def up(self) -> bool:
        return bool(self.task and not self.task.done() and self.server.started)


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": {"code": "VALIDATION", "message": str(exc.errors())[:300]}},
                            422)


def api_key_dep(expected: str):
    def check(x_api_key: str | None = Header(default=None)) -> None:
        if not expected or x_api_key != expected:
            raise ApiError(401, "UNAUTHORIZED", "invalid or missing X-Api-Key")
    return check


class WoodStore:
    """Модель сховища: стоси, завдання, події."""

    def __init__(self, world: World, *, sheet_period_s: float = 60.0,
                 demo_json: str | Path | None = None) -> None:
        self.world = world
        self.sheet_period_s = sheet_period_s
        self.stacks: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.events: deque[dict[str, Any]] = deque(maxlen=EVENT_RING)
        self._ev_seq = 0
        self._job_seq = 411
        self._next_sheet_at: float | None = None
        self.cycles_total = 184210
        self.cycles_today = 0
        self._seed(demo_json)
        world.on_tick(self.on_tick)

    # --- початкові дані --------------------------------------------------------------
    def _seed(self, demo_json: str | Path | None) -> None:
        locs: dict[str, Any] = {}
        if demo_json and Path(demo_json).is_file():
            locs = {k: v for k, v in json.loads(Path(demo_json).read_text("utf-8"))
                    .get("locations", {}).items() if k.startswith("PLT-")}
        for i in range(36):
            row, col = i // 6 + 1, i % 6 + 1
            sid = f"PLT-{row:02d}{chr(64 + col)}"
            src = locs.get(sid, {})
            filled = i < 23
            product = src.get("product") or (DEMO_PRODUCTS[i % len(DEMO_PRODUCTS)] if filled else None)
            qty = int(src.get("qty", (20 + (i * 7) % 40) if filled else 0))
            self.stacks[sid] = {
                "id": sid, "row": row, "col": col, "product": product if qty else None,
                "lot": (src.get("lot") or f"{product}-2610-{100 + i}") if qty else None,
                "qty": qty, "max": int(src.get("capacity", 60)), "reserved": 0,
                "locked": False, "updated": self.world.now().isoformat()}

    # --- події і завдання -----------------------------------------------------------
    def emit(self, type_: str, message: str = "", **kw: Any) -> None:
        self._ev_seq += 1
        self.events.append({"id": self._ev_seq, "ts": self.world.now().isoformat(), "type": type_,
                            "job": kw.get("job"), "stack": kw.get("stack"),
                            "target": kw.get("target"), "message": message})

    def available(self, product: str | None, lot: str | None, source: str | None) -> list[dict]:
        out = [s for s in self.stacks.values() if s["qty"] - s["reserved"] > 0 and not s["locked"]
               and (source is None or s["id"] == source)
               and (product is None or s["product"] == product)
               and (lot is None or s["lot"] == lot)]
        return sorted(out, key=lambda s: -(s["qty"] - s["reserved"]))

    def create_job(self, body: JobIn | dict[str, Any]) -> dict[str, Any]:
        j = body if isinstance(body, JobIn) else JobIn(**body)
        if j.type not in JOB_TYPES:
            raise ApiError(422, "VALIDATION", f"type must be one of {JOB_TYPES}")
        if j.type == "feed" and j.target not in TARGETS:
            raise ApiError(422, "VALIDATION", f"target must be one of {TARGETS}")
        if j.sheets < 1:
            raise ApiError(422, "VALIDATION", "sheets must be >= 1")
        if j.source is not None and j.source not in self.stacks:
            raise ApiError(404, "NOT_FOUND", f"stack {j.source}")
        source, product = j.source, j.product
        if j.type == "feed":
            cands = self.available(product, j.lot, source)
            if not cands or sum(s["qty"] - s["reserved"] for s in cands) < j.sheets:
                raise ApiError(409, "CONFLICT", "not enough sheets in stock")
            if source is None:
                source = cands[0]["id"]
            if source:
                st = self.stacks[source]
                if st["qty"] - st["reserved"] < j.sheets:
                    raise ApiError(409, "CONFLICT", f"stack {source} holds fewer sheets")
                st["reserved"] += j.sheets
                product = product or st["product"]
        self._job_seq += 1
        job = {"id": f"wj-{self._job_seq:05d}", "type": j.type, "source": source,
               "target": j.target, "sheets": j.sheets, "done": 0, "product": product,
               "lot": j.lot or (self.stacks[source]["lot"] if source else None),
               "priority": j.priority, "external_ref": j.external_ref, "state": "queued",
               "created": self.world.now().isoformat(), "started": None, "finished": None}
        self.jobs[job["id"]] = job
        return job

    def cancel_job(self, job: dict[str, Any]) -> None:
        if job["state"] in ("queued", "active"):
            if job["source"] and job["type"] == "feed":
                st = self.stacks[job["source"]]
                st["reserved"] = max(0, st["reserved"] - (job["sheets"] - job["done"]))
            job["state"] = "cancelled"
            job["finished"] = self.world.now().isoformat()
            self.emit("job_finished", "cancelled", job=job["id"], target=job["target"])

    # --- тік --------------------------------------------------------------------------
    def active(self) -> dict[str, Any] | None:
        return next((j for j in self.jobs.values() if j["state"] == "active"), None)

    def aisles(self) -> list[dict[str, Any]]:
        gates = self.world.flag("aisles_open", []) or []
        return [{"no": n, "gate_open": n in gates} for n in range(1, 10)]

    def on_tick(self, _world: World) -> None:
        w = self.world
        for item in w.drain("woodstore_jobs"):
            with contextlib.suppress(ApiError):
                self.create_job(item)
        epoch = w.clock.epoch()
        job = self.active()
        if job is None:
            queued = sorted((j for j in self.jobs.values() if j["state"] == "queued"),
                            key=lambda j: (-j["priority"], j["id"]))
            if queued:
                job = queued[0]
                job["state"], job["started"] = "active", w.now().isoformat()
                self._next_sheet_at = epoch + self.sheet_period_s
                self.emit("job_started", job=job["id"], target=job["target"], stack=job["source"])
        if job is not None and self._next_sheet_at is not None and epoch >= self._next_sheet_at:
            if any(a["gate_open"] for a in self.aisles()):
                self._next_sheet_at = epoch + 1  # портал не заходить у відкритий прохід
            else:
                self._place_sheet(job)
                self._next_sheet_at = epoch + self.sheet_period_s
        w.set_flag("woodstore", {"state": self.portal_state(), "current_job":
                                 (self.active() or {}).get("id")})

    def _place_sheet(self, job: dict[str, Any]) -> None:
        self.cycles_total += 1
        self.cycles_today += 1
        if job["type"] == "feed" and job["source"]:
            st = self.stacks[job["source"]]
            st["qty"] = max(0, st["qty"] - 1)
            st["reserved"] = max(0, st["reserved"] - 1)
            st["updated"] = self.world.now().isoformat()
            self.emit("sheet_placed", job=job["id"], stack=st["id"], target=job["target"])
            if st["qty"] == 0:
                self.emit("stack_empty", stack=st["id"])
        job["done"] += 1
        if job["done"] >= job["sheets"]:
            job["state"], job["finished"] = "done", self.world.now().isoformat()
            self.emit("job_finished", job=job["id"], target=job["target"])

    def portal_state(self) -> str:
        dev = self.world.devices.get("GANTRY-1")
        if dev is not None and dev.fault and dev.fault != "comm":
            return "error"
        if any(a["gate_open"] for a in self.aisles()):
            return "blocked"
        return "placing" if self.active() else "idle"

    def status(self) -> dict[str, Any]:
        sig = self.world.signals
        vac = sig.get("equipment/GANTRY-1/vacuum_kpa")
        cyc = sig.get("equipment/GANTRY-1/cycles_today")
        job = self.active()
        return {"state": self.portal_state(),
                "position": {"x": 36.2, "y": 27.5, "z": 4.8},
                "vacuum_kpa": round(float(vac.value), 1) if vac is not None else -71.9,
                "cycles_today": max(self.cycles_today, int(cyc.value) if cyc is not None else 0),
                "cycles_total": self.cycles_total, "hours": 11240.5,
                "current_job": job["id"] if job else None, "aisles": self.aisles(),
                "alarms": [], "ts": self.world.now().isoformat()}


def create_app(store: WoodStore, apikey: str) -> FastAPI:
    app = FastAPI(title="woodStore API v1")
    install_errors(app)
    dep = [Depends(api_key_dep(apikey))]

    def get_stack(sid: str) -> dict[str, Any]:
        if sid not in store.stacks:
            raise ApiError(404, "NOT_FOUND", f"stack {sid}")
        return store.stacks[sid]

    def get_job(jid: str) -> dict[str, Any]:
        if jid not in store.jobs:
            raise ApiError(404, "NOT_FOUND", f"job {jid}")
        return store.jobs[jid]

    @app.get("/api/v1/status", dependencies=dep)
    def status() -> dict:
        return store.status()

    @app.get("/api/v1/stacks", dependencies=dep)
    def stacks(product: str | None = None, row: int | None = None) -> list:
        return [s for s in store.stacks.values()
                if (product is None or s["product"] == product)
                and (row is None or s["row"] == row)]

    @app.get("/api/v1/stacks/{sid}", dependencies=dep)
    def stack(sid: str) -> dict:
        return get_stack(sid)

    @app.patch("/api/v1/stacks/{sid}", dependencies=dep)
    def patch_stack(sid: str, body: StackPatch) -> dict:
        s = get_stack(sid)
        if body.qty is not None:
            if not 0 <= body.qty <= s["max"]:
                raise ApiError(422, "VALIDATION", f"qty must be 0..{s['max']}")
            s["qty"] = body.qty
        if body.product is not None:
            s["product"] = body.product
        if body.lot is not None:
            s["lot"] = body.lot
        s["updated"] = store.world.now().isoformat()
        store.emit("stack_updated", body.reason or "", stack=sid)
        return s

    @app.get("/api/v1/jobs", dependencies=dep)
    def jobs(state: str | None = None, since: str | None = None) -> list:
        if state is not None and state not in JOB_STATES:
            raise ApiError(422, "VALIDATION", f"state must be one of {JOB_STATES}")
        return [j for j in store.jobs.values()
                if (state is None or j["state"] == state)
                and (since is None or j["created"] >= since)]

    @app.post("/api/v1/jobs", dependencies=dep, status_code=201)
    def create_job(body: JobIn) -> dict:
        return store.create_job(body)

    @app.get("/api/v1/jobs/{jid}", dependencies=dep)
    def job(jid: str) -> dict:
        return get_job(jid)

    @app.delete("/api/v1/jobs/{jid}", dependencies=dep)
    def delete_job(jid: str) -> dict:
        j = get_job(jid)
        store.cancel_job(j)
        return {"id": jid, "state": j["state"]}

    @app.get("/api/v1/events", dependencies=dep)
    def events(since: int = 0) -> list:
        return [e for e in store.events if e["id"] > since]

    return app


class WoodStoreApi(ProtocolServer):
    name = "woodstore"

    def __init__(self, world: World, *, port: int = 8082, host: str = "0.0.0.0",
                 apikey: str = "", sheet_period_s: float = 60.0,
                 demo_json: str | Path | None = None) -> None:
        self.world, self.port, self.host = world, port, host
        self.store = WoodStore(world, sheet_period_s=sheet_period_s, demo_json=demo_json)
        self.app = create_app(self.store, apikey)
        self._runner = UvicornRunner(self.app, host, port)

    async def start(self) -> None:
        await self._runner.start()

    async def stop(self) -> None:
        await self._runner.stop()

    def health(self) -> dict:
        return {"proto": self.name, "up": self._runner.up, "port": self.port,
                "stacks": sum(1 for s in self.store.stacks.values() if s["qty"] > 0)}
