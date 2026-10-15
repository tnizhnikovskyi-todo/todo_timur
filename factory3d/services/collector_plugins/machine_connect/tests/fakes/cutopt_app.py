"""aiohttp-застосунок API-30…34 (оптимізатор розкрою) у пам'яті — для тестів адаптера `cutopt`."""

from __future__ import annotations

from typing import Any

from aiohttp import web
from aiohttp.test_utils import TestServer

API_KEY = "co-key"


class FakeCutOpt:
    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.uploads: list[dict] = []
        self.calls: list[tuple[str, str, dict, Any]] = []
        self.reject_next = False
        self.server: TestServer | None = None

    @property
    def url(self) -> str:
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.port}"

    def advance(self, job_id: str, state: str, plan: dict | None = None, mpr: dict | None = None) -> None:
        job = self.jobs[job_id]
        job["state"] = state
        if plan is not None:
            job["plan"] = plan
        if mpr is not None:
            job["mpr"] = mpr

    @web.middleware
    async def _mw(self, request: web.Request, handler):
        body = None
        if request.can_read_body and request.content_type == "application/json":
            body = await request.json()
        self.calls.append((request.method, request.path, dict(request.query), body))
        if request.headers.get("X-Api-Key") != API_KEY:
            return web.json_response({"error": "unauthorized"}, status=401)
        request["json"] = body
        return await handler(request)

    async def _create(self, request: web.Request) -> web.Response:
        if self.reject_next:
            self.reject_next = False
            return web.json_response({"detail": ["parts: empty list"]}, status=422)
        upload: dict[str, Any] = {}
        reader = await request.multipart()
        async for part in reader:
            data = await part.read(decode=False)
            if part.name == "parts":
                upload["parts"] = bytes(data)
                upload["parts_filename"] = part.filename
                upload["parts_content_type"] = part.headers.get("Content-Type")
            else:
                upload[part.name] = bytes(data).decode("utf-8")
        self.uploads.append(upload)
        job_id = f"cj-{len(self.jobs) + 1}"
        self.jobs[job_id] = {
            "job_id": job_id,
            "state": "optimizing",
            "external_ref": upload.get("external_ref"),
            "machine": upload.get("machine"),
            "material": upload.get("material"),
            "parts": 48,
            "plan": None,
            "mpr": {},
            "error": None,
        }
        return web.json_response({"job_id": job_id, "state": "optimizing", "eta_s": 5}, status=202)

    def _job_or_404(self, request: web.Request) -> dict | None:
        return self.jobs.get(request.match_info["id"])

    async def _get(self, request: web.Request) -> web.Response:
        job = self._job_or_404(request)
        if not job:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({k: v for k, v in job.items() if k != "mpr"})

    async def _plan(self, request: web.Request) -> web.Response:
        job = self._job_or_404(request)
        if not job or not job.get("plan"):
            return web.json_response({"error": "not found"}, status=404)
        plan = job["plan"]
        return web.json_response({"sheets": [], "total_sheets": plan["sheets"], "waste_pct": plan["waste_pct"]})

    async def _release(self, request: web.Request) -> web.Response:
        job = self._job_or_404(request)
        if not job:
            return web.json_response({"error": "not found"}, status=404)
        job["state"] = "released"
        return web.json_response({"job_id": job["job_id"], "state": "released", "job_order_id": job["job_id"]})

    async def _mpr(self, request: web.Request) -> web.Response:
        job = self._job_or_404(request)
        part = request.query.get("part", "")
        if not job or part not in job["mpr"]:
            return web.Response(status=404, text="no mpr")
        return web.Response(text=job["mpr"][part], content_type="text/plain")

    def app(self) -> web.Application:
        app = web.Application(middlewares=[self._mw])
        app.router.add_post("/jobs", self._create)
        app.router.add_get("/jobs/{id}", self._get)
        app.router.add_get("/jobs/{id}/plan", self._plan)
        app.router.add_post("/jobs/{id}/release", self._release)
        app.router.add_get("/jobs/{id}/mpr", self._mpr)
        return app

    async def start(self) -> None:
        self.server = TestServer(self.app())
        await self.server.start_server()

    async def stop(self) -> None:
        if self.server is not None:
            await self.server.close()
            self.server = None
