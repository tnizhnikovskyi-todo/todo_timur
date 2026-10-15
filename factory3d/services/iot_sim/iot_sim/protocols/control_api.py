"""REST керування ``/sim/v1`` (SPEC §7.2, API-10…API-19, §8.16, §11).

``create_app(settings, world=..., runner=..., servers=..., follow=...)``. Без ``world`` працюють лише
``/health`` і ``/lpr-sink`` (каркас W0). Авторизація — ``Authorization: Bearer <SIM_API_TOKEN>`` для всього,
крім ``GET /health``, ``GET /metrics``, ``POST /lpr-sink``; 5 хибних токенів з однієї IP за хвилину -> 429
на 60 с. ``SIM_READONLY_API=1`` -> 403 на POST/PUT; ``SIM_ENABLED=0`` або ``stop-all`` -> 423 на команди.
Стан сервісу (``locked``, тік, мета збоїв) — ``app.state.ctl`` (``ControlState``).
"""
from __future__ import annotations

import hmac
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Histogram,
    generate_latest,
)
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from pydantic import BaseModel, Field

from iot_sim import __version__
from iot_sim.config import Settings
from iot_sim.core.clock import MAX_FACTOR, MIN_FACTOR
from iot_sim.core.events import CursorGone
from iot_sim.core.scenarios import ScenarioError, ScenarioParamsError, ScenarioRunner
from iot_sim.core.world import World

EXPECTED_PROTOCOLS = ("opcua", "modbus", "bacnet", "mqtt", "helvarnet", "biostar", "woodstore",
                      "jobs", "sics", "lpr")
TICK_LATE_S = 3.0
MAX_HOLD_S = 86_400
AUTH_FAILS = 5
AUTH_WINDOW_S = 60.0
FAULT_REASONS = ("generic", "spindle", "emergency", "power", "comm", "sensor")
LSZ_REASONS = ("sensor", "generic", "loop")


class ControlState:
    """Спільний стан керування: читає/міняє головний цикл (``__main__``) і ендпоїнти."""

    def __init__(self, settings: Settings | None, world: World | None, runner: ScenarioRunner | None,
                 servers: dict[str, Any], follow: Any, guard: Any, mono: Callable[[], float]) -> None:
        self.settings, self.world, self.runner = settings, world, runner
        self.servers, self.follow, self.guard, self.mono = servers, follow, guard, mono
        self.token = settings.api_token if settings else ""
        self.readonly = bool(settings and settings.readonly_api)
        self.enabled = settings.enabled if settings else True
        self.stopped = False  # стоп-кран API-17
        self.started = mono()
        self.catalog_source = settings.catalog_source if settings else "local"
        self.fault_meta: dict[str, dict[str, Any]] = {}
        self.registry = CollectorRegistry()
        self.tick_hist = Histogram("iot_sim_tick_seconds", "Тривалість тіку ядра", registry=self.registry,
                                   buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5))
        self._fails: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}

    @property
    def locked(self) -> bool:
        return (not self.enabled) or self.stopped

    def protocols(self) -> dict[str, str]:
        out = {n: "off" for n in EXPECTED_PROTOCOLS}
        for name, srv in self.servers.items():
            try:
                out[name] = "ok" if srv.health().get("up") else "down"
            except Exception:  # noqa: BLE001
                out[name] = "down"
        out["control"] = "ok"
        return out

    def tick_late(self) -> bool:
        w = self.world
        return bool(w and w.last_tick_real is not None and self.mono() - w.last_tick_real > TICK_LATE_S)


class StartBody(BaseModel):
    run_ref: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class StopBody(BaseModel):
    run_id: str | None = None


class FaultBody(BaseModel):
    reason: str | None = None
    note: str = ""


class TimeBody(BaseModel):
    factor: float | None = None
    set: str | None = None


class ModeBody(BaseModel):
    mode: Literal["scenario", "follow_odoo"]


class SignalPut(BaseModel):
    value: float | int | bool | str | None = None
    hold_s: float = 600.0
    release: bool = False


class ResetBody(BaseModel):
    keep_time: bool = True
    seed: int | None = None


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _device_state(dev: Any) -> str:
    if dev.fault:
        return "offline" if dev.fault == "comm" else "fault"
    return "passive" if dev.driver == "passive" else "ok"


def create_app(settings: Settings | None = None, *, world: World | None = None,
               runner: ScenarioRunner | None = None, servers: dict[str, Any] | None = None,
               follow: Any = None, guard: Any = None,
               mono: Callable[[], float] = time.monotonic) -> FastAPI:
    app = FastAPI(title="iot_sim control API", version=__version__)
    ctl = ControlState(settings, world, runner, servers if servers is not None else {}, follow, guard, mono)
    app.state.ctl = ctl

    def W() -> World:
        if ctl.world is None:
            raise HTTPException(503, "world is not running")
        return ctl.world

    def R() -> ScenarioRunner:
        if ctl.runner is None:
            raise HTTPException(503, "scenario runner is not running")
        return ctl.runner

    # --- авторизація ---------------------------------------------------------------------
    def check_token(request: Request) -> None:
        ip = request.client.host if request.client else "?"
        now = mono()
        if ctl._blocked_until.get(ip, 0.0) > now:
            raise HTTPException(429, "too many invalid tokens")
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        if ctl.token and hmac.compare_digest(token.encode(), ctl.token.encode()):
            return
        fails = ctl._fails[ip]
        fails.append(now)
        while fails and now - fails[0] > AUTH_WINDOW_S:
            fails.popleft()
        if len(fails) >= AUTH_FAILS:
            ctl._blocked_until[ip] = now + AUTH_WINDOW_S
            fails.clear()
        raise HTTPException(401, "invalid token")

    def read_auth(request: Request) -> None:
        check_token(request)

    def write_auth(request: Request) -> None:
        check_token(request)
        if ctl.readonly:
            raise HTTPException(403, "API is read-only (SIM_READONLY_API)")
        if ctl.locked:
            raise HTTPException(423, "emulator is locked (SIM_ENABLED=0 / stop-all)")

    def admin_auth(request: Request) -> None:  # stop-all/resume працюють і в заблокованому стані
        check_token(request)
        if ctl.readonly:
            raise HTTPException(403, "API is read-only (SIM_READONLY_API)")

    # --- API-18 health/metrics -----------------------------------------------------------
    @app.get("/sim/v1/health")
    def health() -> dict[str, Any]:
        protocols = ctl.protocols()
        down = [n for n, s in protocols.items() if s == "down"]
        stale = bool(ctl.world and ctl.world.odoo_stale)
        if ctl.locked:
            status = "locked"
        elif down or ctl.tick_late() or stale:
            status = "degraded"
        else:
            status = "ok"
        return {"status": status, "version": __version__,
                "uptime_s": round(mono() - ctl.started, 1), "protocols": protocols,
                "servers": {n: s for n, s in protocols.items() if s != "off"}}

    class _Collector:
        def collect(self) -> Any:
            w = ctl.world
            yield GaugeMetricFamily("iot_sim_up", "Сервіс працює", value=1)
            if w is not None:
                period = (ctl.settings.tick_ms if ctl.settings else 1000) / 1000  # лаг = запізнення понад період тіку
                lag = 0.0 if w.last_tick_real is None else max(0.0, mono() - w.last_tick_real - period)
                yield GaugeMetricFamily("iot_sim_tick_lag_seconds", "Відставання тіку", value=lag)
                yield GaugeMetricFamily("iot_sim_signals_total", "Сигнали", value=len(w.signals))
                yield GaugeMetricFamily("iot_sim_alarms", "Сигнали в alarm",
                                        value=sum(1 for s in w.signals.values() if s.status == "alarm"))
                g = GaugeMetricFamily("iot_sim_signal_value", "Значення сигналу", labels=["code"])
                for s in w.signals.values():
                    if s.kind in ("gauge", "counter") and s.spec.emulated and isinstance(s.value, (int, float)):
                        g.add_metric([s.code], float(s.value))
                yield g
                ev = CounterMetricFamily("iot_sim_events_total", "Події", labels=["kind"])
                for k, n in w.events.counts.items():
                    ev.add_metric([k], n)
                yield ev
                yield GaugeMetricFamily("iot_sim_runs_active", "Активні запуски",
                                        value=len(ctl.runner.active()) if ctl.runner else 0)
                last = ctl.follow.last_ok if ctl.follow is not None and ctl.follow.last_ok else None
                yield GaugeMetricFamily("iot_sim_odoo_last_ok_timestamp", "Остання успішна синхронізація Odoo",
                                        value=last.timestamp() if last else 0)
            up = GaugeMetricFamily("iot_sim_protocol_up", "Протокол слухає", labels=["proto"])
            req = CounterMetricFamily("iot_sim_protocol_requests_total", "Запити", labels=["proto"])
            for name, srv in ctl.servers.items():
                try:
                    h = srv.health()
                except Exception:  # noqa: BLE001
                    h = {}
                up.add_metric([name], 1 if h.get("up") else 0)
                if "requests" in h:
                    req.add_metric([name], h["requests"])
            yield up
            yield req
            yield CounterMetricFamily("iot_sim_outbound_denied_total", "Відмови allow-list",
                                      value=getattr(ctl.guard, "denied_total", 0))
            mq = ctl.servers.get("mqtt")
            if mq is not None:
                yield CounterMetricFamily("iot_sim_mqtt_dropped_total", "Втрачені MQTT-повідомлення",
                                          value=getattr(mq, "dropped", 0))

    ctl.registry.register(_Collector())

    @app.get("/sim/v1/metrics")
    def metrics() -> Response:
        return Response(generate_latest(ctl.registry), media_type=CONTENT_TYPE_LATEST)

    # --- LPR-приймач (без токена, §8.13.2) ------------------------------------------------
    @app.post("/sim/v1/lpr-sink")
    async def lpr_sink(request: Request) -> dict[str, Any]:
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(422, "invalid JSON") from None
        if not isinstance(body, dict):
            raise HTTPException(422, "JSON object expected")
        if ctl.world is not None:
            cam = str(body.get("sensorProviderID") or "") or None
            ctl.world.events.emit("info", f"LPR {body.get('plateText', '?')} {body.get('carState', '')}".strip(),
                                  device=cam, payload=body)
        return {"received": True}

    # --- API-10 status ---------------------------------------------------------------------
    @app.get("/sim/v1/status", dependencies=[Depends(read_auth)])
    def status() -> dict[str, Any]:
        w = W()
        s = ctl.settings
        runs = [_run_brief(r) for r in (ctl.runner.active() if ctl.runner else [])]
        return {
            "enabled": not ctl.locked, "version": __version__, "mode": w.mode, "factor": w.clock.factor,
            "sim_now": w.now().isoformat(), "real_now": datetime.now(UTC).astimezone(w.clock.tz).isoformat(),
            "uptime_s": round(mono() - ctl.started, 1), "seed": w.seed, "tick_ms": s.tick_ms if s else 1000,
            "devices": len(w.devices), "signals": len(w.signals),
            "alarms": sum(1 for x in w.signals.values() if x.status == "alarm"),
            "devices_fault": sorted(c for c, d in w.devices.items() if d.fault),
            "runs": runs, "protocols": ctl.protocols(),
            "odoo": {**(ctl.follow.status() if ctl.follow is not None else
                        {"configured": False, "last_ok": None, "stale": w.odoo_stale}),
                     "catalog_source": ctl.catalog_source},
            "catalog_hash": "sha256:" + w.registry.catalog_hash}

    def _run_brief(r: Any) -> dict[str, Any]:
        return {"id": r.id, "run_ref": r.run_ref, "scenario": r.name, "state": r.state,
                "started": _iso(r.started), "params": r.params}

    # --- API-11/12 devices -----------------------------------------------------------------
    def _device(code: str) -> dict[str, Any]:
        d = W().devices[code]
        meta = ctl.fault_meta.get(code)
        return {"code": code, "name": d.params.get("name", code), "protocol": d.protocol, "driver": d.driver,
                "unit_id": d.unit_id, "instance": d.instance, "address": d.address, "enabled": True,
                "state": _device_state(d),
                "fault": ({"reason": d.fault, "note": (meta or {}).get("note", ""),
                           "since": (meta or {}).get("since")} if d.fault else None),
                "model": d.driver, "signals": [s.code for s in d.signals.values()], "extra": {}}

    @app.get("/sim/v1/devices", dependencies=[Depends(read_auth)])
    def devices(protocol: str | None = None, state: str | None = None) -> list[dict[str, Any]]:
        out = [_device(c) for c in sorted(W().devices)]
        return [d for d in out if (protocol is None or d["protocol"] == protocol)
                and (state is None or d["state"] == state)]

    @app.get("/sim/v1/devices/{code}", dependencies=[Depends(read_auth)])
    def device(code: str) -> dict[str, Any]:
        if code not in W().devices:
            raise HTTPException(404, f"device {code} not found")
        return _device(code)

    @app.post("/sim/v1/device/{code}/fault", dependencies=[Depends(write_auth)])
    def device_fault(code: str, body: FaultBody | None = None) -> dict[str, Any]:
        w = W()
        dev = w.devices.get(code)
        if dev is None:
            raise HTTPException(404, f"device {code} not found")
        body = body or FaultBody()
        lsz = bool(dev.params.get("lsz")) or code.startswith("FA-")
        if dev.driver == "passive" and not lsz:
            raise HTTPException(422, f"device {code} is passive")
        allowed = LSZ_REASONS if lsz else FAULT_REASONS
        reason = body.reason or ("sensor" if lsz else "generic")
        if reason not in allowed:
            raise HTTPException(422, f"reason must be one of {list(allowed)}")
        if dev.fault == reason:
            return {"code": code, "state": dev.state}
        w.fault(code, reason, **({"note": body.note} if body.note else {}))
        ctl.fault_meta[code] = {"note": body.note, "since": w.now().isoformat()}
        return {"code": code, "state": _device_state(dev)}

    @app.post("/sim/v1/device/{code}/clear", dependencies=[Depends(write_auth)])
    def device_clear(code: str) -> dict[str, Any]:
        w = W()
        dev = w.devices.get(code)
        if dev is None:
            raise HTTPException(404, f"device {code} not found")
        w.clear(code)
        ctl.fault_meta.pop(code, None)
        return {"code": code, "state": _device_state(dev)}

    # --- API-13 scenarios ------------------------------------------------------------------
    def _scenario_err(exc: ScenarioError) -> HTTPException:
        if isinstance(exc, ScenarioParamsError):
            return HTTPException(422, exc.errors)
        return HTTPException(exc.status, str(exc))

    @app.get("/sim/v1/scenarios", dependencies=[Depends(read_auth)])
    def scenarios() -> list[dict[str, Any]]:
        out = []
        for item in R().list():
            sc = R().scenarios[item["name"]]
            try:
                default = sc.Params().model_dump(mode="json")  # type: ignore[call-arg]
            except Exception:  # noqa: BLE001 - є обов'язкові параметри
                default = {}
            out.append({**item, "params_default": default})
        return out

    @app.post("/sim/v1/scenario/{name}/start", status_code=201, dependencies=[Depends(write_auth)])
    async def scenario_start(name: str, body: StartBody | None = None) -> dict[str, Any]:
        body = body or StartBody()
        try:
            run = R().start(name, body.params, body.run_ref)
        except ScenarioError as exc:
            raise _scenario_err(exc) from exc
        return {"id": run.id, "scenario": run.name, "state": run.state, "started": _iso(run.started),
                "ends": _iso(run.ends)}

    @app.post("/sim/v1/scenario/{name}/stop", dependencies=[Depends(write_auth)])
    async def scenario_stop(name: str, body: StopBody | None = None) -> dict[str, Any]:
        r = R()
        if name not in r.scenarios:
            raise HTTPException(404, f"unknown scenario {name}")
        run_id = body.run_id if body else None
        try:
            if run_id:
                if r.runs.get(run_id) is not None and r.runs[run_id].name != name:
                    raise HTTPException(404, f"run {run_id} is not a {name} run")
                runs = [await r.stop(run_id)]
            else:
                runs = [await r.stop(x.id) for x in r.active() if x.name == name]  # type: ignore[attr-defined]
        except ScenarioError as exc:
            raise _scenario_err(exc) from exc
        return {"id": runs[0].id if runs else None, "state": "stopped", "runs": [x.id for x in runs]}

    def _run_full(r: Any) -> dict[str, Any]:
        n = sum(1 for e in W().events.ring if e.run_id == r.id)
        return {**_run_brief(r), "events": n, "result": r.result}

    @app.get("/sim/v1/runs", dependencies=[Depends(read_auth)])
    def runs() -> list[dict[str, Any]]:
        return [_run_full(r) for r in R().runs.values()]

    @app.get("/sim/v1/runs/{run_id}", dependencies=[Depends(read_auth)])
    def run_get(run_id: str) -> dict[str, Any]:
        r = R().runs.get(run_id)
        if r is None:
            raise HTTPException(404, f"run {run_id} not found")
        return _run_full(r)

    # --- API-14 time, API-15 mode ----------------------------------------------------------
    @app.post("/sim/v1/time", dependencies=[Depends(write_auth)])
    def set_time(body: TimeBody) -> dict[str, Any]:
        w = W()
        if body.factor is None and body.set is None:
            raise HTTPException(422, "factor and/or set required")
        if body.factor is not None and not MIN_FACTOR <= body.factor <= MAX_FACTOR:
            raise HTTPException(422, f"factor must be within [{MIN_FACTOR}; {MAX_FACTOR}]")
        target = None
        if body.set is not None:
            try:
                target = datetime.fromisoformat(body.set)
            except ValueError:
                raise HTTPException(422, "set must be ISO 8601") from None
        if body.factor is not None and w.mode == "follow_odoo" and body.factor != 1:
            raise HTTPException(409, "factor is fixed to 1 in follow_odoo mode")
        if target is not None:
            w.clock.set(target)
        if body.factor is not None:
            w.clock.set_factor(body.factor)
        return {"factor": w.clock.factor, "sim_now": w.now().isoformat()}

    @app.post("/sim/v1/mode", dependencies=[Depends(write_auth)])
    def set_mode(body: ModeBody) -> dict[str, Any]:
        w = W()
        if body.mode == "follow_odoo":
            if ctl.follow is None or not ctl.follow.configured:
                raise HTTPException(422, "Odoo is not configured")
            w.clock.set_factor(1.0)
        w.set_mode(body.mode)
        if body.mode == "follow_odoo":
            ctl.follow.kick()
        return {"mode": w.mode, "factor": w.clock.factor}

    # --- API-16 signals --------------------------------------------------------------------
    def _signal(s: Any) -> dict[str, Any]:
        return {"code": s.code, "value": s.value, "unit": s.unit, "status": s.status, "ts": _iso(s.ts),
                "device": s.device, "protocol": s.protocol, "kind": s.kind}

    @app.get("/sim/v1/signals", dependencies=[Depends(read_auth)])
    def signals(prefix: str | None = None, device: str | None = None, status: str | None = None,
                limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        rows = [s for s in W().signals.values() if s.spec.emulated
                and (prefix is None or s.code.startswith(prefix)) and (device is None or s.device == device)
                and (status is None or s.status == status)]
        return {"count": len(rows), "items": [_signal(s) for s in rows[offset:offset + max(limit, 0)]]}

    def _sig(code: str) -> Any:
        s = W().signals.get(code)
        if s is None:
            raise HTTPException(404, f"signal {code} not found")
        if not s.spec.emulated:
            m = re.match(r"(?:обчислює|власник)\s+(\S+)", s.spec.model)
            raise HTTPException(404, f"computed by {m.group(1) if m else 'owner module'}")
        return s

    @app.get("/sim/v1/signals/{code:path}", dependencies=[Depends(read_auth)])
    def signal_get(code: str) -> dict[str, Any]:
        return _signal(_sig(code))

    @app.put("/sim/v1/signals/{code:path}", dependencies=[Depends(write_auth)])
    def signal_put(code: str, body: SignalPut) -> dict[str, Any]:
        s = _sig(code)
        if body.release:
            W().release(s.code)
        else:
            if body.value is None:
                raise HTTPException(422, "value or release required")
            if not 0 < body.hold_s <= MAX_HOLD_S:
                raise HTTPException(422, f"hold_s must be within (0; {MAX_HOLD_S}]")
            s.force(body.value, W().now(), body.hold_s)
        return {"code": s.code, "value": s.value, "held_until": _iso(s.held_until)}

    # --- API-17 reset / stop-all / resume --------------------------------------------------
    @app.post("/sim/v1/reset", dependencies=[Depends(write_auth)])
    async def reset(body: ResetBody | None = None) -> dict[str, Any]:
        w, body = W(), body or ResetBody()
        await R().stop_all()
        for code, dev in w.devices.items():
            if dev.fault:
                w.clear(code)
        ctl.fault_meta.clear()
        w.reset_models()
        for sig in w.signals.values():
            sig.value, sig.held_until, sig.status = sig.spec.initial_value(), None, "ok"
            sig.ts = w.now()
        w.flags.clear()
        w.inbox.clear()
        w.maintenance_closed.clear()
        if body.seed is not None:
            w.seed = body.seed
            w._rngs.clear()
        if not body.keep_time:
            w.clock.set(datetime.now(w.clock.tz))
        return {"ok": True, "sim_now": w.now().isoformat()}

    @app.post("/sim/v1/stop-all", dependencies=[Depends(admin_auth)])
    async def stop_all() -> dict[str, Any]:
        w = W()
        await R().stop_all()
        ctl.stopped = True
        return {"ok": True, "sim_now": w.now().isoformat()}

    @app.post("/sim/v1/resume", dependencies=[Depends(admin_auth)])
    def resume() -> dict[str, Any]:
        w = W()
        if not ctl.enabled:
            raise HTTPException(423, "emulator disabled by SIM_ENABLED=0")
        ctl.stopped = False
        return {"ok": True, "sim_now": w.now().isoformat()}

    # --- API-19 events ---------------------------------------------------------------------
    @app.get("/sim/v1/events", dependencies=[Depends(read_auth)])
    def events(since: str | None = None, kind: str | None = None, device: str | None = None,
               limit: int = 500) -> JSONResponse:
        bus = W().events
        cursor = 0
        if since:
            found = next((e.seq for e in bus.ring if e.id == since), None)
            if found is None:
                return JSONResponse({"detail": "cursor is gone: re-read events from the start"}, status_code=410)
            cursor = found
        try:
            items, _ = bus.since(cursor, max(1, min(limit, 10_000)), kind, device)
        except CursorGone:
            return JSONResponse({"detail": "cursor is gone: re-read events from the start"}, status_code=410)
        return JSONResponse({"items": [e.to_dict() for e in items],
                             "next": items[-1].id if items else since})

    # --- каталог -----------------------------------------------------------------------------
    @app.get("/sim/v1/catalog/signals.csv", dependencies=[Depends(read_auth)])
    def catalog_csv() -> FileResponse:
        path = Path(ctl.settings.catalog_dir if ctl.settings else "./catalog") / "signals.csv"
        if not path.is_file():
            raise HTTPException(404, "catalog not found")
        return FileResponse(path, media_type="text/csv")

    @app.get("/sim/v1/catalog/devices.json", dependencies=[Depends(read_auth)])
    def catalog_devices() -> list[dict[str, Any]]:
        return [_device(c) for c in sorted(W().devices)]

    return app
