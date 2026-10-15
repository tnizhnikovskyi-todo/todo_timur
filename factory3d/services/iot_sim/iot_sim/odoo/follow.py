"""Режим ``follow_odoo`` (SPEC §8.9.7, A-08, A-12): XML-RPC лише читання.

``OdooReadOnly`` має лише ``search_read/read/search_count/fields_get`` (будь-який інший виклик у коді
неможливий). ``FollowOdoo`` раз на ``SIM_ODOO_FOLLOW_S`` (10 с) читає «швидкі» дані (``mrp.workorder``,
``mrp.workcenter``), раз на ``SIM_ODOO_FOLLOW_SLOW_S`` (60 с) — «повільні» (пакети-фури, переміщення,
працівники, календарі, закриті заявки ТО) і записує їх у ``World``:

* ``world.workcenters[code] = {"state": "WORKING|READY|ERROR|STANDBY", "blocked": bool,
  "job": {...}|None, "qty_produced": float}``; ``world.jobs`` — список завдань
  ``{"id": "WO00013", "wo_id", "workcenter", "state" (Odoo), "isa_state", "name", "production",
  "qty_produced", "qty_production", "duration", "duration_expected", "date_start"}`` (X-38);
* ``world.trucks`` — ``{"code", "description", "plate", "dock", "type", "scheduled", "batch",
  "state", "progress"}`` (X-15, X-49); ``world.people`` — працівники з ``barcode``; ``world.shift`` —
  календар зміни; ``world.maintenance_closed`` — коди пристроїв із закритою заявкою ТО.

Помилка читання довше ``SIM_ODOO_STALE_S`` -> ``world.odoo_stale = True`` (режим не змінюється,
стан завдань заморожено); після відновлення — повна синхронізація і подія ``info``.
Фактор у цьому режимі завжди 1 (A-12) — це контролює ``control_api``.
"""
from __future__ import annotations

import asyncio
import logging
import time
import xmlrpc.client
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from datetime import time as dtime
from typing import Any

from iot_sim.core.world import World

log = logging.getLogger("iot_sim.follow")

ISA_STATE = {"ready": "AllowedToStart", "progress": "Running", "done": "Ended/Completed",
             "pending": "NotAllowedToStart", "cancel": "Ended/Cancelled"}


class OdooReadOnly:
    """XML-RPC клієнт лише для читання. Усі виклики — у потоці (``asyncio.to_thread``)."""

    ALLOWED = ("search_read", "read", "search_count", "fields_get")

    def __init__(self, url: str, db: str, user: str, apikey: str, *, guard: Any = None,
                 timeout: float = 10.0) -> None:
        self.url, self.db, self.user, self.apikey = url.rstrip("/"), db, user, apikey
        self.guard, self.timeout = guard, timeout
        self._uid: int | None = None

    @property
    def configured(self) -> bool:
        return bool(self.url and self.db and self.user and self.apikey)

    def _proxy(self, path: str) -> xmlrpc.client.ServerProxy:
        if self.guard is not None:
            self.guard.check_url(self.url)
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/{path}", allow_none=True)

    def _call(self, model: str, method: str, args: list[Any], kwargs: dict[str, Any]) -> Any:
        if method not in self.ALLOWED:
            raise PermissionError(f"метод {method} заборонено (лише читання)")
        if self._uid is None:
            uid = self._proxy("common").authenticate(self.db, self.user, self.apikey, {})
            if not uid:
                raise PermissionError("Odoo відхилила облікові дані SIM_ODOO_USER")
            self._uid = int(uid)  # type: ignore[arg-type]
        return self._proxy("object").execute_kw(self.db, self._uid, self.apikey, model, method, args, kwargs)

    async def search_read(self, model: str, domain: list[Any], fields: list[str], **kw: Any) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._call, model, "search_read", [domain], {"fields": fields, **kw})

    async def read(self, model: str, ids: list[int], fields: list[str]) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._call, model, "read", [ids], {"fields": fields})

    async def search_count(self, model: str, domain: list[Any]) -> int:
        return await asyncio.to_thread(self._call, model, "search_count", [domain], {})

    async def fields_get(self, model: str, attributes: list[str] | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._call, model, "fields_get", [], {"attributes": attributes or ["type"]})


def _m2o_id(v: Any) -> int | None:
    return v[0] if isinstance(v, (list, tuple)) and v else None


def _hm(h: float) -> dtime:
    return dtime(min(int(h), 23), round((h - int(h)) * 60) % 60)


class FollowOdoo:
    def __init__(self, world: World, odoo: Any, *, follow_s: float = 10.0, slow_s: float = 60.0,
                 stale_s: float = 120.0, mono: Callable[[], float] = time.monotonic,
                 level0_sync: bool = True) -> None:
        self.world, self.odoo = world, odoo
        self.follow_s, self.slow_s, self.stale_s = follow_s, slow_s, stale_s
        self._mono = mono
        self.level0_sync = level0_sync
        self.last_ok: datetime | None = None
        self._last_ok_mono: float | None = None
        self._last_fast = self._last_slow = -1e12
        self._last_maint: str | None = None
        self._plate_field: bool | None = None
        self._level0_done = False
        self._task: asyncio.Task[Any] | None = None
        self.errors = 0
        self._started_mono = mono()

    # --- стан ---------------------------------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(getattr(self.odoo, "configured", True))

    @property
    def active(self) -> bool:
        return self.world.mode == "follow_odoo" and self.configured

    def status(self) -> dict[str, Any]:
        return {"configured": self.configured,
                "last_ok": self.last_ok.isoformat() if self.last_ok else None,
                "stale": self.world.odoo_stale}

    def kick(self) -> None:
        """Повна синхронізація при найближчому циклі (перехід у follow_odoo, відновлення)."""
        self._last_fast = self._last_slow = -1e12

    # --- швидкі запити (10 с) --------------------------------------------------------------
    async def poll_fast(self) -> None:
        since = (self.world.now().astimezone(UTC) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        wcs = await self.odoo.search_read("mrp.workcenter", [], ["id", "code", "working_state"])
        wos = await self.odoo.search_read(
            "mrp.workorder",
            ["&", ("state", "in", ["ready", "progress", "done"]), "|", ("state", "!=", "done"),
             ("date_finished", ">=", since)],
            ["id", "name", "state", "workcenter_id", "production_id", "qty_produced", "qty_production",
             "duration", "duration_expected", "date_start", "working_state"])
        code_by_id = {w["id"]: w.get("code") for w in wcs}
        blocked = {w["code"] for w in wcs if w.get("working_state") == "blocked" and w.get("code")}
        jobs: list[dict[str, Any]] = []
        for wo in wos:
            code = code_by_id.get(_m2o_id(wo.get("workcenter_id")))
            if not code:
                continue
            if wo.get("working_state") == "blocked":
                blocked.add(code)
            jobs.append({
                "id": f"WO{wo['id']:05d}", "wo_id": wo["id"], "workcenter": code, "name": wo.get("name"),
                "state": wo["state"], "isa_state": ISA_STATE.get(wo["state"], "NotAllowedToStart"),
                "production": (wo.get("production_id") or [None, ""])[1],
                "qty_produced": wo.get("qty_produced") or 0.0, "qty_production": wo.get("qty_production") or 0.0,
                "duration": wo.get("duration") or 0.0, "duration_expected": wo.get("duration_expected") or 0.0,
                "date_start": wo.get("date_start") or None})
        centers: dict[str, dict[str, Any]] = {}
        for code in sorted(c for c in code_by_id.values() if c):
            mine = [j for j in jobs if j["workcenter"] == code]
            running = next((j for j in mine if j["state"] == "progress"), None)
            ready = next((j for j in mine if j["state"] == "ready"), None)
            is_blocked = code in blocked
            state = "ERROR" if is_blocked else ("WORKING" if running else ("READY" if ready else "STANDBY"))
            centers[code] = {"state": state, "blocked": is_blocked, "job": running or ready,
                             "qty_produced": (running or {}).get("qty_produced", 0.0)}
        self.world.jobs = jobs
        self.world.workcenters = centers

    # --- повільні запити (60 с) -------------------------------------------------------------
    async def poll_slow(self) -> None:
        o, w = self.odoo, self.world
        if self._plate_field is None:
            try:
                self._plate_field = "f3d_plate" in await o.fields_get("stock.picking.batch")
            except Exception:  # noqa: BLE001 - поле необов'язкове
                self._plate_field = False
        bf = ["name", "dock_id", "scheduled_date", "state", "picking_ids", "f3d_code", "f3d_truck"]
        batches = await o.search_read(
            "stock.picking.batch", [("dock_id", "!=", False), ("state", "in", ["draft", "in_progress"])],
            bf + (["f3d_plate"] if self._plate_field else []))
        dock_ids = sorted({d for b in batches if (d := _m2o_id(b.get("dock_id")))})
        docks = {d["id"]: d.get("f3d_code") for d in
                 (await o.read("stock.location", dock_ids, ["f3d_code"]) if dock_ids else [])}
        pick_ids = sorted({i for b in batches for i in b.get("picking_ids", [])})
        pickings = await o.search_read("stock.picking", [("id", "in", pick_ids)],
                                       ["name", "state", "picking_type_code"]) if pick_ids else []
        moves = await o.search_read("stock.move", [("picking_id", "in", pick_ids)],
                                    ["picking_id", "quantity", "product_uom_qty"]) if pick_ids else []
        ptype = {p["id"]: p.get("picking_type_code") for p in pickings}
        qty: dict[int, list[float]] = {}
        for m in moves:
            pid = _m2o_id(m.get("picking_id"))
            acc = qty.setdefault(pid, [0.0, 0.0])  # type: ignore[arg-type]
            acc[0] += float(m.get("quantity") or 0)
            acc[1] += float(m.get("product_uom_qty") or 0)
        trucks = []
        for b in batches:
            ids = b.get("picking_ids", [])
            done = sum(qty.get(i, [0, 0])[0] for i in ids)
            plan = sum(qty.get(i, [0, 0])[1] for i in ids)
            kinds = {ptype.get(i) for i in ids}
            trucks.append({
                "code": b.get("f3d_code") or None, "description": b.get("f3d_truck") or None,
                "plate": (b.get("f3d_plate") or None) if self._plate_field else None,
                "dock": docks.get(_m2o_id(b.get("dock_id"))), "batch": b["name"],
                "type": "incoming" if "incoming" in kinds else "outgoing",
                "scheduled": (b.get("scheduled_date") or "").replace(" ", "T") + "Z" if b.get("scheduled_date") else None,
                "state": b["state"], "progress": round(min(done / plan, 1.0), 3) if plan else 0.0})
        w.trucks = trucks
        emps = await o.search_read("hr.employee", [("barcode", "!=", False)],
                                   ["name", "barcode", "resource_calendar_id", "job_title"])
        w.people = [{"name": e["name"], "barcode": e["barcode"], "job": e.get("job_title") or None,
                     "shift": (e.get("resource_calendar_id") or [None, None])[1]} for e in emps]
        cal_ids = sorted({c for e in emps if (c := _m2o_id(e.get("resource_calendar_id")))})
        if cal_ids:
            att = await o.search_read("resource.calendar.attendance", [("calendar_id", "in", cal_ids)],
                                      ["dayofweek", "hour_from", "hour_to"])
            self._apply_shift(att)
        await self._poll_maintenance()
        if self.level0_sync and not self._level0_done:
            self._level0_done = True
            await self._sync_level0()

    def _apply_shift(self, att: list[dict[str, Any]]) -> None:
        if not att:
            return
        by_day: dict[int, list[tuple[float, float]]] = {}
        for a in att:
            by_day.setdefault(int(a["dayofweek"]), []).append((float(a["hour_from"]), float(a["hour_to"])))
        days = sorted(by_day)
        ref = sorted(by_day[days[0]])
        cal = self.world.shift
        cal.workdays = tuple(days)
        cal.start, cal.end = _hm(ref[0][0]), _hm(ref[-1][1])
        if len(ref) > 1:
            cal.lunch_from, cal.lunch_to = _hm(ref[0][1]), _hm(ref[1][0])

    async def _poll_maintenance(self) -> None:
        o, w = self.odoo, self.world
        domain: list[Any] = [("stage_id.done", "=", True)]
        if self._last_maint:
            domain.append(("write_date", ">=", self._last_maint))
        self._last_maint = self.world.now().astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        reqs = await o.search_read("maintenance.request", domain, ["equipment_id"])
        eq_ids = sorted({e for r in reqs if (e := _m2o_id(r.get("equipment_id")))})
        if eq_ids:
            for e in await o.read("maintenance.equipment", eq_ids, ["f3d_code"]):
                if e.get("f3d_code"):
                    w.maintenance_closed.add(e["f3d_code"])
        try:  # заявки рівня 0 (x_f3d_signal.x_request_id); модель може бути відсутня
            sigs = await o.search_read("x_f3d_signal", [("x_request_id", "!=", False)],
                                       ["x_code", "x_request_id"])
            rids = [s["x_request_id"][0] for s in sigs if s.get("x_request_id")]
            done = {r["id"] for r in await o.search_read(
                "maintenance.request", [("id", "in", rids), ("stage_id.done", "=", True)], ["id"])} if rids else set()
            for s in sigs:
                sig = w.signals.get(s.get("x_code") or "")
                if sig is not None and _m2o_id(s["x_request_id"]) in done:
                    w.maintenance_closed.add(sig.device)
        except Exception as exc:  # noqa: BLE001
            log.debug("level0 requests unavailable: %s", exc)

    async def _sync_level0(self) -> None:
        try:
            rows = await self.odoo.search_read("x_f3d_signal", [], ["x_code", "x_value"])
        except Exception as exc:  # noqa: BLE001
            log.info("level0 sync skipped: %s", exc)
            return
        n = 0
        for r in rows:
            sig = self.world.signals.get(r.get("x_code") or "")
            if sig is not None and r.get("x_value") not in (None, False, ""):
                try:
                    sig.value = float(r["x_value"])
                    n += 1
                except (TypeError, ValueError):
                    continue
        log.info("level0 start values applied: %d", n)

    # --- цикл ---------------------------------------------------------------------------
    async def step(self) -> None:
        """Один крок планувальника опитування (викликається щосекунди)."""
        if not self.active:
            return
        now = self._mono()
        try:
            due_fast = now - self._last_fast >= self.follow_s
            due_slow = now - self._last_slow >= self.slow_s
            if due_fast:
                await self.poll_fast()
                self._last_fast = now
            if due_slow:
                await self.poll_slow()
                self._last_slow = now
            if due_fast or due_slow:
                self._ok(now)
        except Exception as exc:  # noqa: BLE001 - будь-яка помилка Odoo -> лічильник stale
            self.errors += 1
            log.warning("follow_odoo read failed: %s", exc, extra={"proto": "odoo"})
            ref = self._last_ok_mono if self._last_ok_mono is not None else self._started_mono
            if now - ref > self.stale_s and not self.world.odoo_stale:
                self.world.odoo_stale = True
                self.world.events.emit("error", "Odoo недоступна: дані follow_odoo застаріли",
                                       payload={"stale_s": self.stale_s})
            if self.world.odoo_stale:
                self.kick()  # після відновлення — повна синхронізація

    def _ok(self, now: float) -> None:
        self._last_ok_mono = now
        self.last_ok = self.world.now()
        if self.world.odoo_stale:
            self.world.odoo_stale = False
            self.world.events.emit("info", "Зв'язок з Odoo відновлено, виконано повну синхронізацію")

    async def _loop(self) -> None:
        while True:
            await self.step()
            await asyncio.sleep(1.0)

    async def start(self) -> None:
        self._started_mono = self._mono()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
