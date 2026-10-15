"""aiohttp-застосунок API-20…27 (woodStore портала STORETEQ) у пам'яті — для тестів адаптера `woodstore`."""

from __future__ import annotations

import json
from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestServer

API_KEY = "ws-key"
ROWS = "ABC"


def _ts(n: int) -> str:
    return f"2026-10-12T06:{n // 60 % 60:02d}:{n % 60:02d}Z"


class FakeWoodStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, Any]] = []
        self.conflict_next = False
        self.fail_status: int | None = None
        self.status: dict[str, Any] = {
            "state": "moving",
            "position": {"x": 36.2, "y": 27.5, "z": 4.8},
            "vacuum_kpa": -71.9,
            "cycles_today": 373,
            "cycles_total": 184210,
            "hours": 11240.5,
            "current_job": "wj-1",
            "aisles": [{"no": n, "gate_open": False} for n in range(1, 10)],
            "alarms": [],
            "ts": "2026-10-12T06:00:00Z",
        }
        self.stacks = [
            {
                "id": f"PLT-{n:02d}{row}",
                "row": n,
                "col": i + 1,
                "product": "DSP16-SON" if n % 2 else None,
                "lot": None,
                "qty": 30 if n % 2 else 0,
                "max": 60,
                "reserved": 0,
                "locked": False,
                "updated": _ts(0),
            }
            for n in range(1, 10)
            for i, row in enumerate(ROWS)
        ]
        self.jobs: dict[str, dict] = {
            "wj-1": self._job("wj-1", "active", created=_ts(1), started=_ts(2)),
        }
        self.events: list[dict] = []
        self._seq = 0
        self.server: TestServer | None = None

    # --- помічники тестів ---
    @staticmethod
    def _job(job_id: str, state: str, done: int = 0, **kw: Any) -> dict:
        base = {
            "id": job_id,
            "type": "feed",
            "source": "PLT-03C",
            "target": "SAW-1",
            "sheets": 12,
            "done": done,
            "product": "DSP16-SON",
            "lot": None,
            "priority": 5,
            "external_ref": "WH/MO/00231",
            "state": state,
            "created": None,
            "started": None,
            "finished": None,
        }
        base.update(kw)
        return base

    def set_status(self, **kw: Any) -> None:
        self.status.update(kw)

    def add_events(self, n: int) -> None:
        for _ in range(n):
            self._seq += 1
            self.events.append({"id": self._seq, "ts": _ts(self._seq), "type": "sheet_placed", "job": "wj-1"})

    def set_job(self, job_id: str, state: str, done: int = 0, **kw: Any) -> None:
        self.jobs[job_id] = self._job(job_id, state, done, **kw)

    @property
    def url(self) -> str:
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.port}"

    def calls_of(self, method: str, path: str) -> list[tuple[str, str, dict, Any]]:
        return [c for c in self.calls if c[0] == method and c[1] == path]

    # --- HTTP ---
    @web.middleware
    async def _mw(self, request: web.Request, handler):
        body = None
        if request.can_read_body and request.content_type == "application/json":
            body = await request.json()
        self.calls.append((request.method, request.path, dict(request.query), body))
        if request.headers.get("X-Api-Key") != API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        if self.fail_status:
            return web.json_response({"error": "boom"}, status=self.fail_status)
        request["json"] = body
        return await handler(request)

    async def _status(self, request: web.Request) -> web.Response:
        return web.json_response(self.status)

    async def _stacks(self, request: web.Request) -> web.Response:
        return web.json_response(self.stacks)

    async def _stack_patch(self, request: web.Request) -> web.Response:
        sid = request.match_info["id"]
        for st in self.stacks:
            if st["id"] == sid:
                body = request["json"]
                st.update({k: body[k] for k in ("qty", "product", "lot") if k in body})
                return web.json_response(st)
        return web.json_response({"error": "not found"}, status=404)

    async def _jobs(self, request: web.Request) -> web.Response:
        items = list(self.jobs.values())
        state = request.query.get("state")
        if state:
            items = [j for j in items if j["state"] == state]
        since = request.query.get("since")
        if since:
            items = [j for j in items if max(str(j[k]) for k in ("created", "started", "finished") if j[k]) > since]
        return web.json_response(items)

    async def _job_create(self, request: web.Request) -> web.Response:
        if self.conflict_next:
            self.conflict_next = False
            return web.json_response({"error": "not enough sheets"}, status=409)
        body = request["json"]
        job_id = f"wj-{len(self.jobs) + 1:05d}"
        job = self._job(job_id, "queued", created=_ts(100 + len(self.jobs)))
        job.update({k: body.get(k) for k in ("type", "source", "target", "sheets", "product", "lot", "priority")})
        job["external_ref"] = body.get("external_ref")
        self.jobs[job_id] = job
        return web.json_response(job, status=201)

    async def _job_get(self, request: web.Request) -> web.Response:
        job = self.jobs.get(request.match_info["id"])
        return web.json_response(job) if job else web.json_response({"error": "not found"}, status=404)

    async def _job_delete(self, request: web.Request) -> web.Response:
        job = self.jobs.get(request.match_info["id"])
        if not job:
            return web.json_response({"error": "not found"}, status=404)
        job["state"] = "cancelled"
        return web.json_response({"id": job["id"], "state": "cancelled"})

    async def _events(self, request: web.Request) -> web.Response:
        since = request.query.get("since")
        if since is not None:
            try:
                n = int(since)
            except ValueError:
                return web.json_response({"error": "bad cursor"}, status=400)
            if n > self._seq:
                return web.json_response({"error": "unknown cursor"}, status=410)
            return web.json_response([e for e in self.events if e["id"] > n])
        return web.json_response(self.events)

    def app(self) -> web.Application:
        app = web.Application(middlewares=[self._mw])
        app.router.add_get("/api/v1/status", self._status)
        app.router.add_get("/api/v1/stacks", self._stacks)
        app.router.add_patch("/api/v1/stacks/{id}", self._stack_patch)
        app.router.add_get("/api/v1/jobs", self._jobs)
        app.router.add_post("/api/v1/jobs", self._job_create)
        app.router.add_get("/api/v1/jobs/{id}", self._job_get)
        app.router.add_delete("/api/v1/jobs/{id}", self._job_delete)
        app.router.add_get("/api/v1/events", self._events)
        return app

    async def start(self) -> None:
        self.server = TestServer(self.app())
        await self.server.start_server()

    async def stop(self) -> None:
        if self.server is not None:
            await self.server.close()
            self.server = None


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
