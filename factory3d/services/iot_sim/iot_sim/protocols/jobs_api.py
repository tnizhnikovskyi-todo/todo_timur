"""P-04 ``/jobs`` — файловий обмін картами розкрою (SPEC §8.6, API-30…API-34).

Оптимізатор — жадібне гільйотинне розкладання FFDH (детерміноване). Стан ``optimizing`` триває
``eta_s`` sim-секунд (рахується від ``world.clock.epoch()``), далі ``planned``. ``release`` (API-33)
ставить у World команди: ``world.post("opc_joborders", {machine, job_order_id, ...})`` для OPC UA
``JobOrderList`` і ``world.post("woodstore_jobs", {type: "feed", target, sheets, product, ...})``
для порталу (лише для target ∈ SAW-*/NEST-1). Стани ``running/done`` не ведуться (ПРИПУЩЕННЯ).
"""
from __future__ import annotations

import csv
import io
import math
import re
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer
from iot_sim.protocols.woodstore_api import (
    TARGETS,
    ApiError,
    UvicornRunner,
    api_key_dep,
    install_errors,
)

CSV_COLUMNS = ("PartId", "Description", "Material", "Length", "Width", "Quantity", "Grain",
               "EdgeTop", "EdgeBottom", "EdgeLeft", "EdgeRight", "Program")
MAX_LEN, MAX_WID = 2800, 2070
ETA_S = 5


class CsvError(Exception):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        self.errors = errors


def parse_parts(text: str) -> list[dict[str, Any]]:
    """CSV §8.6.1 (роздільник ``;``) -> список деталей; помилки -> ``CsvError``."""
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";"))
    errors: list[dict[str, Any]] = []
    parts: list[dict[str, Any]] = []
    for i, r in enumerate(rows, start=2):  # рядок 1 — заголовок
        try:
            length, width, qty = int(r["Length"]), int(r["Width"]), int(r["Quantity"])
        except (KeyError, TypeError, ValueError):
            errors.append({"row": i, "error": "Length/Width/Quantity must be integers"})
            continue
        err = None
        if length > MAX_LEN:
            err = f"Length > {MAX_LEN}"
        elif width > MAX_WID:
            err = f"Width > {MAX_WID}"
        elif length < 1 or width < 1:
            err = "Length/Width must be positive"
        elif qty < 1:
            err = "Quantity < 1"
        if err:
            errors.append({"row": i, "error": err})
            continue
        parts.append({"id": r.get("PartId") or f"P{i - 1:03d}", "description": r.get("Description"),
                      "length": length, "width": width, "quantity": qty,
                      "program": r.get("Program") or None})
    if not rows:
        errors.append({"row": 1, "error": "no data rows"})
    if errors:
        raise CsvError(errors)
    return parts


def parse_json_parts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buf = io.StringIO()
    wr = csv.writer(buf, delimiter=";")
    wr.writerow(CSV_COLUMNS)
    for p in items:
        wr.writerow([p.get(c, p.get(c.lower(), "")) for c in CSV_COLUMNS])
    return parse_parts(buf.getvalue())


def optimize(parts: list[dict[str, Any]], sheet_w: int, sheet_h: int, product: str) -> dict[str, Any]:
    """FFDH: деталі за спаданням ``Width`` (висота полиці), полиці по довжині листа."""
    items = []
    for p in parts:
        for _ in range(p["quantity"]):
            items.append({"id": p["id"], "w": p["length"], "h": p["width"]})
    items.sort(key=lambda t: (-t["h"], -t["w"], t["id"]))
    sheets: list[dict[str, Any]] = []  # {"shelves": [{"y","h","x"}], "parts": []}
    for it in items:
        for sh in sheets:
            placed = False
            for shelf in sh["shelves"]:
                if it["h"] <= shelf["h"] and shelf["x"] + it["w"] <= sheet_w:
                    sh["parts"].append({**it, "x": shelf["x"], "y": shelf["y"], "rot": 0})
                    shelf["x"] += it["w"]
                    placed = True
                    break
            if placed:
                break
            top = sum(s["h"] for s in sh["shelves"])
            if top + it["h"] <= sheet_h:
                sh["shelves"].append({"y": top, "h": it["h"], "x": it["w"]})
                sh["parts"].append({**it, "x": 0, "y": top, "rot": 0})
                placed = True
                break
        else:
            placed = False
        if not placed:
            sheets.append({"shelves": [{"y": 0, "h": it["h"], "x": it["w"]}],
                           "parts": [{**it, "x": 0, "y": 0, "rot": 0}]})
    out_sheets, cut_mm, used_total = [], 0, 0
    for no, sh in enumerate(sheets, start=1):
        area = sum(p["w"] * p["h"] for p in sh["parts"])
        used_total += area
        cuts = []
        for shelf in sh["shelves"]:
            cuts.append({"dir": "y", "pos": shelf["y"] + shelf["h"], "from": 0, "to": sheet_w})
            cut_mm += sheet_w
        for p in sh["parts"]:
            cuts.append({"dir": "x", "pos": p["x"] + p["w"], "from": p["y"], "to": p["y"] + p["h"]})
            cut_mm += p["h"]
        out_sheets.append({
            "no": no, "product": product,
            "parts": [{"id": p["id"], "x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"],
                       "rot": p["rot"]} for p in sh["parts"]],
            "waste_pct": round(100 * (1 - area / (sheet_w * sheet_h)), 1), "cuts": cuts})
    total = len(out_sheets)
    waste = round(100 * (1 - used_total / (total * sheet_w * sheet_h)), 1) if total else 0.0
    return {"sheets": out_sheets, "total_sheets": total, "waste_pct": waste,
            "cut_length_m": round(cut_mm / 1000, 1), "est_min": math.ceil(total * 3 + cut_mm / 20000)}


def mpr_text(job: dict[str, Any], part: dict[str, Any]) -> str:
    """Мінімальний валідний MPR woodWOP (ПРИПУЩЕННЯ: лише заголовок і контур)."""
    length, width = part["length"], part["width"]
    return "\r\n".join([
        "[H", 'VERSION="4.0 Alpha"', 'OP="1"', 'WW="9.0.82"', "",
        "[001", f"LA={length}", f"BR={width}", "DI=16", "",
        "<100 \\WerkStck\\", f'LA="{length}"', f'BR="{width}"', 'DI="16"', "",
        '<101 \\Kommentar\\', f'KM="{job["external_ref"] or job["job_id"]} {part["id"]}"', "",
        "!"]) + "\r\n"


class JobStore:
    def __init__(self, world: World) -> None:
        self.world = world
        self.jobs: dict[str, dict[str, Any]] = {}
        self._seq = 76

    def create(self, parts: list[dict[str, Any]], material: str, sheet: str,
               external_ref: str | None, machine: str | None) -> dict[str, Any]:
        m = re.fullmatch(r"(\d+)x(\d+)(?:x\d+)?", sheet or "2800x2070x16")
        if not m:
            raise ApiError(422, "VALIDATION", "sheet must look like 2800x2070x16")
        sw, sh = int(m.group(1)), int(m.group(2))
        self._seq += 1
        now = self.world.now().isoformat()
        plan = optimize(parts, sw, sh, material)
        job = {"job_id": f"cj-{self._seq:05d}", "state": "optimizing",
               "external_ref": external_ref, "machine": machine, "material": material,
               "parts": sum(p["quantity"] for p in parts), "plan": None, "created": now,
               "updated": now, "error": None, "_plan": plan, "_parts": parts,
               "_ready": self.world.clock.epoch() + ETA_S}
        self.jobs[job["job_id"]] = job
        return job

    def get(self, jid: str) -> dict[str, Any]:
        job = self.jobs.get(jid)
        if job is None:
            raise ApiError(404, "NOT_FOUND", f"job {jid}")
        if job["state"] == "optimizing" and self.world.clock.epoch() >= job["_ready"]:
            p = job["_plan"]
            job["plan"] = {k: p[k] for k in ("total_sheets", "waste_pct", "cut_length_m", "est_min")}
            job["plan"]["sheets"] = job["plan"].pop("total_sheets")
            job["state"] = "planned"
            job["updated"] = self.world.now().isoformat()
        return job

    @staticmethod
    def public(job: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in job.items() if not k.startswith("_")}


def create_app(store: JobStore, apikey: str) -> FastAPI:
    app = FastAPI(title="iot_sim /jobs")
    install_errors(app)
    dep = [Depends(api_key_dep(apikey))]

    @app.post("/jobs", dependencies=dep, status_code=202)
    async def submit(request: Request):
        ctype = request.headers.get("content-type", "")
        try:
            if ctype.startswith("application/json"):
                body = await request.json()
                parts = parse_json_parts(body.get("parts") or [])
            else:
                form = await request.form()
                body = dict(form)
                raw = form.get("parts")
                text = (await raw.read()).decode("utf-8") if hasattr(raw, "read") else str(raw or "")
                parts = parse_parts(text)
        except CsvError as e:
            return JSONResponse({"detail": e.errors}, 422)
        if not body.get("material"):
            raise ApiError(422, "VALIDATION", "material is required")
        job = store.create(parts, str(body["material"]), str(body.get("sheet") or "2800x2070x16"),
                           body.get("external_ref"), body.get("machine"))
        return {"job_id": job["job_id"], "state": "optimizing", "eta_s": ETA_S}

    @app.get("/jobs/{jid}", dependencies=dep)
    def get_job(jid: str) -> dict:
        return store.public(store.get(jid))

    @app.get("/jobs/{jid}/plan", dependencies=dep)
    def get_plan(jid: str) -> dict:
        job = store.get(jid)
        if job["state"] == "optimizing":
            raise ApiError(409, "CONFLICT", "plan is not ready")
        p = job["_plan"]
        return {"sheets": p["sheets"], "total_sheets": p["total_sheets"], "waste_pct": p["waste_pct"]}

    @app.post("/jobs/{jid}/release", dependencies=dep)
    async def release(jid: str, request: Request) -> dict:
        job = store.get(jid)
        if job["state"] != "planned":
            raise ApiError(409, "CONFLICT", f"job is {job['state']}, expected planned")
        try:
            body = await request.json()
        except ValueError:
            body = {}
        machine = body.get("machine") or job["machine"]
        if not machine or machine not in store.world.devices:
            raise ApiError(422, "VALIDATION", "known machine is required")
        prio = int(body.get("priority", 5))
        job["machine"], job["state"] = machine, "released"
        job["updated"] = store.world.now().isoformat()
        w = store.world
        w.post("opc_joborders", {"machine": machine, "job_order_id": jid, "priority": prio,
                                 "external_ref": job["external_ref"]})
        if machine in TARGETS:
            w.post("woodstore_jobs", {"type": "feed", "target": machine, "priority": prio,
                                      "sheets": job["_plan"]["total_sheets"],
                                      "product": job["material"],
                                      "external_ref": job["external_ref"]})
        return {"job_id": jid, "state": "released", "job_order_id": jid}

    @app.get("/jobs/{jid}/mpr", dependencies=dep)
    def get_mpr(jid: str, part: str | None = None) -> PlainTextResponse:
        job = store.get(jid)
        machine = job["machine"] or ""
        if not machine.startswith(("CNC", "NEST")):
            raise ApiError(404, "NOT_FOUND", "MPR only for CNC/NEST")
        parts = job["_parts"]
        p = next((x for x in parts if part in (None, x["id"])), None)
        if p is None:
            raise ApiError(404, "NOT_FOUND", f"part {part}")
        return PlainTextResponse(mpr_text(job, p))

    return app


class JobsApi(ProtocolServer):
    name = "jobs"

    def __init__(self, world: World, *, port: int = 8083, host: str = "0.0.0.0",
                 apikey: str = "") -> None:
        self.world, self.port = world, port
        self.store = JobStore(world)
        self.app = create_app(self.store, apikey)
        self._runner = UvicornRunner(self.app, host, port)

    async def start(self) -> None:
        await self._runner.start()

    async def stop(self) -> None:
        await self._runner.stop()

    def health(self) -> dict:
        return {"proto": self.name, "up": self._runner.up, "port": self.port,
                "jobs": len(self.store.jobs)}


__all__ = ["JobStore", "JobsApi", "create_app", "optimize", "parse_parts"]
