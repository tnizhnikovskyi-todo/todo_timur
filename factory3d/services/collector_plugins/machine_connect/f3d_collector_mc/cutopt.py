"""Адаптер `cutopt` (§8.6, P-04, R-24): команди CMD-03 до оптимізатора розкрою."""

from __future__ import annotations

import json
import math
import ssl
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import aiohttp
from collector.core.errors import WriteError
from collector.core.types import Reading, SignalCfg

from .generic import GenericAdapter

if TYPE_CHECKING:
    from .rest_vendor import RestVendorPlugin

ROUTE = "mc_cutopt"
MAX_MPR_BYTES = 200 * 1024
ODOO_TIMEOUT_S = 15


class CutOptAdapter(GenericAdapter):
    def __init__(self, plugin: RestVendorPlugin) -> None:
        super().__init__(plugin)
        self._maps: dict[str, str] = {}

    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        return []

    def _odoo_session(self) -> aiohttp.ClientSession:
        """Окрема сесія для читання API-01 Odoo (A-14): Bearer колектора, TLS-перевірка як у ядра."""
        settings = self.plugin.ctx.settings
        ca = getattr(settings, "odoo_ca", "") or ""
        connector = aiohttp.TCPConnector(ssl=ssl.create_default_context(cafile=ca)) if ca else None
        return aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {settings.collector_token}"},
            timeout=aiohttp.ClientTimeout(total=ODOO_TIMEOUT_S),
            connector=connector,
        )

    def _emit(self, payload: dict) -> None:
        self.plugin.emit_event(ROUTE, {**payload, "source": self.plugin.source.code})

    async def _request(self, method: str, path: str, **kw: Any) -> Any:
        from .rest_vendor import NetError

        try:
            return await self.plugin.request(method, path, **kw)
        except NetError as exc:
            raise WriteError(f"network error: {exc}") from exc

    @staticmethod
    def _fail(resp: Any) -> None:
        if resp.status >= 400:
            raise WriteError(f"HTTP {resp.status}")

    async def command(self, signal: SignalCfg, payload: dict) -> dict:
        op = payload["op"]
        return await getattr(self, f"_op_{op}")(payload)

    # --- upload ---
    async def _export(self, map_id: int, token: str) -> dict:
        settings = self.plugin.ctx.settings
        url = f"{settings.odoo_url.rstrip('/')}/f3d/machine/cutmap/{map_id}/export"  # токен — лише в заголовку (DEC-20)
        try:
            async with self._odoo_session() as sess, sess.get(url, headers={"X-F3D-Token": token}) as r:
                status = r.status
                body = await r.read()
        except (aiohttp.ClientError, TimeoutError, OSError) as exc:
            raise WriteError(f"export unavailable: {type(exc).__name__}") from exc
        if status != 200:
            raise WriteError(f"export {status}")
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError as exc:
            raise WriteError("export bad json") from exc
        return data  # type: ignore[no-any-return]

    async def _op_upload(self, p: dict) -> dict:
        exp = await self._export(p["map"], p["token"])
        form = aiohttp.FormData()
        form.add_field(
            "parts", exp["parts_csv"].encode("utf-8"), filename="parts.csv", content_type="text/csv; charset=utf-8"
        )
        for key in ("material", "sheet", "external_ref", "machine"):
            form.add_field(key, str(exp.get(key, "")))
        resp = await self._request("POST", "/jobs", data=form)
        if resp.status == 422:
            detail = (resp.json() or {}).get("detail") or ["unprocessable"]
            first = detail[0] if isinstance(detail, list) and detail else detail
            if isinstance(first, dict):
                first = first.get("msg") or first
            raise WriteError(f"422: {first}"[:200])
        self._fail(resp)
        job = resp.json() or {}
        job_id = job.get("job_id")
        self._maps[job_id] = exp.get("map", "")
        self._emit({"kind": "job", "map": exp.get("map"), "job": job})
        return {"job_id": job_id, "state": job.get("state"), "eta_s": job.get("eta_s")}

    # --- status ---
    async def _op_status(self, p: dict) -> dict:
        job_id = p["job"]
        resp = await self._request("GET", f"/jobs/{job_id}")
        self._fail(resp)
        job = resp.json() or {}
        map_name = self._maps.get(job_id)
        self._emit({"kind": "job", "map": map_name, "job": job})
        plan = job.get("plan")
        if job.get("state") == "planned":
            pr = await self._request("GET", f"/jobs/{job_id}/plan")
            self._fail(pr)
            plan_body = pr.json() or {}
            self._emit({"kind": "plan", "map": map_name, "job_id": job_id, "plan": plan_body})
            plan = plan or {"sheets": plan_body.get("total_sheets"), "waste_pct": plan_body.get("waste_pct")}
        plan = plan or {}
        return {
            "job_id": job_id,
            "state": job.get("state"),
            "sheets": plan.get("sheets"),
            "waste_pct": plan.get("waste_pct"),
        }

    # --- release ---
    async def _op_release(self, p: dict) -> dict:
        job_id = p["job"]
        resp = await self._request(
            "POST", f"/jobs/{job_id}/release", json_body={"machine": p["machine"], "priority": p["priority"]}
        )
        self._fail(resp)
        job = resp.json() or {}
        self._emit({"kind": "job", "map": self._maps.get(job_id), "job": job})
        return {"job_id": job.get("job_id", job_id), "state": job.get("state"), "job_order_id": job.get("job_order_id")}

    # --- mpr ---
    async def _op_mpr(self, p: dict) -> dict:
        job_id, part = p["job"], p["part"]
        resp = await self._request("GET", f"/jobs/{job_id}/mpr", params={"part": part})
        if resp.status == 404:
            return {"part": part, "size_kb": None}
        self._fail(resp)
        if len(resp.body) > MAX_MPR_BYTES:
            raise WriteError("mpr too large")
        self._emit({"kind": "mpr", "map": self._maps.get(job_id), "job_id": job_id, "part": part, "text": resp.text})
        return {"part": part, "size_kb": max(1, math.ceil(len(resp.body) / 1024))}
