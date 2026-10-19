"""P-01 OPC UA (SPEC §8.3): один сервер, об'єкт на верстат у ``Objects/Machines``.

Спрощення відносно стандарту OPC 40550/40001 (nodeset-файли не завантажуються):
типи вузлів — ``BaseObjectType``; ``JobOrderList`` — ``String[]`` з ``JobOrderID``
(повний ``ISA95JobOrderAndStateDataType`` — ПРИПУЩЕННЯ на наступну ітерацію); події —
``BaseEventType`` з ``Message``/``Severity``/``SourceName``. Методи ``JobOrderControl.*`` приймають
``JobOrderID`` і ставлять команду ``world.post("opc_joborder", {...})``; виклик методів — лише
під ``SIM_OPCUA_USER`` (анонім -> BadUserAccessDenied).

Дані читаються лише через ``World``: ``workcenters/<C>/{state,mode,alarm,pieces_out,job}``,
``energy/consumers/<C>/p_now``, ``equipment/GANTRY-1/*``. Нові ``JobOrder`` від ``/jobs`` (API-33)
надходять через ``world.post("opc_joborders", {"machine", "job_order_id", ...})``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC
from pathlib import Path
from typing import Any

from asyncua import Server, ua, uamethod
from asyncua.crypto.permission_rules import PermissionRuleset, SimpleRoleRuleset
from asyncua.server.user_managers import UserManager
from asyncua.server.users import User, UserRole

from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer

log = logging.getLogger("iot_sim.opcua")

NS_URIS = [
    "http://todo.ltd/f3d/iot_sim/instances/",  # 2
    "http://opcfoundation.org/UA/DI/",  # 3
    "http://opcfoundation.org/UA/Machinery/",  # 4
    "http://opcfoundation.org/UA/Machinery/Jobs/",  # 5
    "http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/",  # 6
    "http://opcfoundation.org/UA/Woodworking/",  # 7
]
APP_URI = "urn:todo.ltd:f3d:iot_sim"
STATE_ENUM = {"OFFLINE": 0, "STANDBY": 1, "READY": 2, "WORKING": 3, "ERROR": 4}
GANTRY_STATE = {"idle": 2, "moving": 3, "picking": 3, "placing": 3, "blocked": 1, "error": 4}
DEVICE_CLASS = {
    "SAW": "PanelSaw",
    "NEST": "NestingMachine",
    "EDGE": "EdgeBander",
    "CNC": "CNCMachiningCenter",
    "BORE": "ThroughfeedDrilling",
    "DOWEL": "DowelInserting",
    "SORT": "SortingCell",
    "ASMLINE": "CaseClamp",
    "GANTRY": "StorageSystem",
}
# 9 обов'язкових (M) + 17 опційних, SPEC §8.3 (AC-36: 26 булевих)
FLAGS = (
    "MachineOn",
    "MachineInitialized",
    "PowerPresent",
    "Emergency",
    "Calibrated",
    "Error",
    "Alarm",
    "Warning",
    "RecipeInRun",
    "AirPresent",
    "DustChipSuction",
    "Safety",
    "Remote",
    "WorkpiecePresent",
    "Moving",
    "Hold",
    "RecipeInSetup",
    "RecipeInHold",
    "ManualActivityRequired",
    "LoadingEnabled",
    "WaitUnload",
    "WaitLoad",
    "EnergySaving",
    "ExternalEmergency",
    "MaintenanceRequired",
    "FeedRuns",
)
VALUES_U64 = (
    "AbsoluteMachineOnTime",
    "RelativeMachineOnTime",
    "AbsoluteProductionTime",
    "RelativeProductionTime",
    "AbsoluteWorkingTime",
    "RelativeWorkingTime",
    "AbsoluteErrorTime",
    "RelativeErrorTime",
    "AbsolutePiecesIn",
    "RelativePiecesIn",
    "AbsolutePiecesOut",
    "RelativePiecesOut",
    "AbsoluteRunsTotal",
    "RelativeRunsTotal",
)
JOB_METHODS = (
    "Store",
    "StoreAndStart",
    "Start",
    "Update",
    "Stop",
    "Cancel",
    "Clear",
    "Pause",
    "Resume",
    "Abort",
    "RevokeStart",
)
JOB_STATES = {
    "Store": "AllowedToStart",
    "StoreAndStart": "Running",
    "Start": "Running",
    "Resume": "Running",
    "Pause": "Interrupted",
    "Stop": "Ended",
    "Cancel": "Ended",
    "Abort": "Aborted",
    "RevokeStart": "NotAllowedToStart",
}


def _state_int(v: Any) -> int:
    if isinstance(v, str):
        return STATE_ENUM.get(v.upper(), GANTRY_STATE.get(v.lower(), 0))
    try:
        return max(0, min(4, int(v)))
    except (TypeError, ValueError):
        return 0


def _u64(v: Any) -> int:
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


class _Rules(PermissionRuleset):
    """Анонім (роль User) читає/підписується, але не викликає методи (SPEC §8.3.1)."""

    def __init__(self) -> None:
        self._base = SimpleRoleRuleset()

    def check_validity(self, user: Any, action_type: Any, body: Any) -> Any:
        call_id = ua.NodeId(ua.ObjectIds.CallRequest_Encoding_DefaultBinary)
        write_id = ua.NodeId(ua.ObjectIds.WriteRequest_Encoding_DefaultBinary)
        if action_type == write_id:  # ТБ-04: клієнтський Write заборонений усім, включно з collector
            return False
        if action_type == call_id and user.role != UserRole.Admin:
            return False
        if user.role == UserRole.Admin:
            return True
        return self._base.check_validity(user, action_type, body)


class _Users(UserManager):
    def __init__(self, user: str, password: str) -> None:
        self.user, self.password = user, password

    def get_user(self, iserver: Any, username: Any = None, password: Any = None, certificate: Any = None) -> Any:
        if username:
            if username == self.user and password == self.password:
                return User(role=UserRole.Admin, name=username)
            return None
        return User(role=UserRole.User)


class OpcUaServer(ProtocolServer):
    name = "opcua"

    def __init__(
        self,
        world: World,
        *,
        port: int = 4840,
        host: str = "0.0.0.0",
        user: str = "collector",
        password: str = "",
        cert_dir: str | Path | None = None,
    ) -> None:
        self.world = world
        self.port, self.host = port, host
        self.user, self.password = user, password
        self.cert_dir = Path(cert_dir) if cert_dir else None
        self.up = False
        self.server: Server | None = None
        self.ns = 2
        self.machines: list[str] = []
        self.joborders: dict[str, list[dict[str, Any]]] = {}
        self._nodes: dict[str, Any] = {}
        self._cache: dict[str, Any] = {}
        self._events: dict[str, Any] = {}
        self._cursor = 0
        self._wake = asyncio.Event()
        self._task: asyncio.Task[Any] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # --- життєвий цикл ----------------------------------------------------------------
    def _machine_codes(self) -> list[str]:
        out = []
        for code in sorted(self.world.devices):
            sig = self.world.signals.get(f"workcenters/{code}/state")
            if (sig is not None and sig.protocol == "P-01") or code == "GANTRY-1":
                out.append(code)
        return out

    async def start(self) -> None:
        srv = self.server = Server(user_manager=_Users(self.user, self.password))
        await srv.init()
        srv.set_endpoint(f"opc.tcp://{self.host}:{self.port}/f3d/")
        srv.set_server_name("iot_sim")
        await srv.set_application_uri(APP_URI)
        policies = [ua.SecurityPolicyType.NoSecurity]
        if self.cert_dir and (self.cert_dir / "server.der").is_file() and (self.cert_dir / "server.key").is_file():
            await srv.load_certificate(self.cert_dir / "server.der")
            await srv.load_private_key(self.cert_dir / "server.key")
            policies.append(ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt)
        srv.set_security_policy(policies, permission_ruleset=_Rules())
        for uri in NS_URIS:
            await srv.register_namespace(uri)
        self.ns = await srv.get_namespace_index(NS_URIS[0])
        self.machines = self._machine_codes()
        folder = await srv.nodes.objects.add_folder(ua.NodeId("Machines", self.ns), ua.QualifiedName("Machines", 4))
        for code in self.machines:
            await self._build_machine(folder, code)
        self._cursor = self.world.events.seq
        await srv.start()
        self.up = True
        self._loop = asyncio.get_running_loop()
        self.world.on_tick(self._on_tick)
        await self.refresh()
        self._task = asyncio.create_task(self._run())
        log.info("OPC UA up on port %s", self.port)

    async def stop(self) -> None:
        self.up = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self.server:
            await self.server.stop()
            self.server = None
        try:
            self.world._tick_cbs.remove(self._on_tick)
        except ValueError:
            pass

    def health(self) -> dict[str, Any]:
        return {"proto": self.name, "up": self.up, "port": self.port, "machines": len(self.machines)}

    def _on_tick(self, _world: World) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._wake.set)

    async def _run(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            try:
                await self.refresh()
            except Exception:
                log.exception("opcua refresh failed")

    # --- побудова адресного простору --------------------------------------------------
    async def _var(
        self, parent: Any, path: str, name: str, value: Any, vt: ua.VariantType, writable: bool = False
    ) -> Any:
        nid = ua.NodeId(f"{path}.{name}", self.ns)
        node = await parent.add_variable(nid, ua.QualifiedName(name, self.ns), ua.Variant(value, vt))
        if writable:
            await node.set_writable()
        self._nodes[f"{path}.{name}"] = (node, vt)
        return node

    async def _obj(self, parent: Any, path: str, name: str) -> Any:
        return await parent.add_object(ua.NodeId(f"{path}.{name}", self.ns), ua.QualifiedName(name, self.ns))

    async def _build_machine(self, folder: Any, code: str) -> None:
        dev = self.world.devices[code]
        ns = self.ns
        obj = await folder.add_object(ua.NodeId(code, ns), ua.QualifiedName(code, ns))
        ident = await self._obj(obj, code, "Identification")
        p = f"{code}.Identification"
        model = str(dev.params.get("model", code))
        for k, v in (
            ("Manufacturer", "HOMAG"),
            ("Model", model),
            ("ProductInstanceUri", f"urn:homag:{model}:{code}"),
            ("SerialNumber", code),
            ("DeviceClass", DEVICE_CLASS.get(code.split("-")[0], "Machine")),
            ("AssetId", code),
            ("Location", str(dev.params.get("zone", ""))),
        ):
            await self._var(ident, p, k, v, ua.VariantType.String, writable=k in ("AssetId", "Location"))
        await self._var(ident, p, "YearOfConstruction", 2024, ua.VariantType.UInt16)
        state = await self._obj(obj, code, "State")
        machine = await self._obj(state, f"{code}.State", "Machine")
        mp = f"{code}.State.Machine"
        overview = await self._obj(machine, mp, "Overview")
        await self._var(overview, f"{mp}.Overview", "CurrentState", 0, ua.VariantType.UInt32)
        await self._var(overview, f"{mp}.Overview", "CurrentMode", 1, ua.VariantType.UInt32)
        flags = await self._obj(machine, mp, "Flags")
        for f in FLAGS:
            await self._var(flags, f"{mp}.Flags", f, False, ua.VariantType.Boolean)
        values = await self._obj(machine, mp, "Values")
        for v in VALUES_U64:
            await self._var(values, f"{mp}.Values", v, 0, ua.VariantType.UInt64)
        for v in ("FeedSpeed", "ActualCycle"):
            await self._var(values, f"{mp}.Values", v, 0.0, ua.VariantType.Double)
        for v in ("AxisOverride", "SpindleOverride"):
            await self._var(values, f"{mp}.Values", v, 100, ua.VariantType.UInt32)
        events = await self._obj(obj, code, "Events")
        await events.write_attribute(ua.AttributeIds.EventNotifier, ua.DataValue(ua.Variant(1, ua.VariantType.Byte)))
        self._events[code] = events
        ms = await self._obj(obj, code, "ManufacturerSpecific")
        msp = f"{code}.ManufacturerSpecific"
        await self._var(ms, msp, "PowerActive", 0.0, ua.VariantType.Double)
        if code == "GANTRY-1":
            await self._var(ms, msp, "VacuumKpa", 0.0, ua.VariantType.Double)
            await self._var(ms, msp, "CyclesToday", 0, ua.VariantType.UInt64)
            return
        jm = await self._obj(obj, code, "JobManagement")
        joc = await self._obj(jm, f"{code}.JobManagement", "JobOrderControl")
        jp = f"{code}.JobManagement.JobOrderControl"
        await self._var(joc, jp, "JobOrderList", [""], ua.VariantType.String)
        for m in JOB_METHODS:
            await joc.add_method(
                ua.NodeId(f"{jp}.{m}", ns),
                ua.QualifiedName(m, ns),
                self._make_method(code, m),
                [ua.VariantType.String, ua.VariantType.String],
                [ua.VariantType.UInt64],
            )
        res = await self._obj(jm, f"{code}.JobManagement", "JobOrderResults")
        await self._var(
            res, f"{code}.JobManagement.JobOrderResults", "JobOrderResponseList", [""], ua.VariantType.String
        )
        self.joborders[code] = []

    def _make_method(self, code: str, method: str) -> Any:
        @uamethod
        def call(parent: Any, job_order_id: str = "", comment: str = "") -> int:
            self.world.post(
                "opc_joborder", {"machine": code, "method": method, "job_order_id": job_order_id, "comment": comment}
            )
            self._apply_command(code, method, job_order_id)
            return 0

        return call

    def _apply_command(self, code: str, method: str, job_id: str) -> None:
        if self.world.mode == "follow_odoo":  # §8.3.2: приймаємо, але веде Odoo
            self.world.events.emit("info", f"{code}: {method} ignored in follow_odoo", device=code)
            return
        lst = self.joborders.setdefault(code, [])
        item = next((j for j in lst if j["id"] == job_id), None)
        if method in ("Store", "StoreAndStart") and item is None and job_id:
            item = {"id": job_id, "state": "AllowedToStart"}
            lst.append(item)
        if item is None:
            return
        if method == "Clear":
            lst.remove(item)
        elif method in JOB_STATES:
            item["state"] = JOB_STATES[method]

    # --- оновлення значень ------------------------------------------------------------
    def _sig(self, *codes: str) -> Any:
        for c in codes:
            s = self.world.signals.get(c)
            if s is not None:
                return s
        return None

    async def _write(self, key: str, value: Any, good: bool, ts: Any) -> None:
        node, vt = self._nodes[key]
        stamp = (tuple(value) if isinstance(value, list) else value, good)
        if self._cache.get(key) == stamp:
            return
        self._cache[key] = stamp
        sc = ua.StatusCode(ua.StatusCodes.Good if good else ua.StatusCodes.BadCommunicationError)
        await node.write_value(ua.DataValue(ua.Variant(value, vt), sc, SourceTimestamp=ts))

    async def refresh(self) -> None:
        """Оновити змінні з World (кожен тік; у тестах — вручну після ``world.advance``)."""
        w = self.world
        for item in w.drain("opc_joborders"):
            m = item.get("machine")
            if m in self.joborders:
                self.joborders[m].append({"id": item["job_order_id"], "state": "AllowedToStart"})
        # SourceTimestamp — UTC з tzinfo (ST-3): naive-час asyncua кодує як UTC, а w.now() — локальний Київ (+2/+3 год)
        now = w.now().astimezone(UTC)
        for code in self.machines:
            dev = w.devices[code]
            ok = dev.fault != "comm"
            mp = f"{code}.State.Machine"
            st = self._sig(f"workcenters/{code}/state", f"equipment/{code}/state")
            cur = _state_int(st.value) if st is not None else 0
            alarm = self._sig(f"workcenters/{code}/alarm")
            alarmed = bool(alarm.value) if alarm is not None else False
            if dev.fault == "comm":
                cur = 0
            elif dev.fault:
                alarmed, cur = True, 4
            mode = self._sig(f"workcenters/{code}/mode")
            mode_v = 1 if mode is None or isinstance(mode.value, str) else _u64(mode.value)
            flags = {
                "MachineOn": cur > 0,
                "MachineInitialized": cur > 0,
                "PowerPresent": dev.fault != "power",
                "Emergency": dev.fault == "emergency",
                "Calibrated": True,
                "Error": cur == 4,
                "Alarm": alarmed,
                "Warning": bool(alarm is not None and alarm.status == "warn"),
                "RecipeInRun": cur == 3,
                "Moving": cur == 3,
                "MaintenanceRequired": False,
            }
            mf = getattr(getattr(dev, "model", None), "flags", None) or {}
            flags.update(
                {
                    "AirPresent": True,
                    "Safety": True,
                    "Remote": True,
                    "DustChipSuction": cur == 3,
                    "WorkpiecePresent": cur == 3,
                    "Hold": False,
                    "RecipeInSetup": False,
                    "RecipeInHold": False,
                    "ManualActivityRequired": False,
                    "LoadingEnabled": cur in (2, 3),
                    "WaitUnload": False,
                    "WaitLoad": cur == 2,
                    "FeedRuns": cur == 3,
                    "EnergySaving": bool(mf.get("EnergySaving", cur == 1)),
                    "ExternalEmergency": bool(mf.get("ExternalEmergency", False)),
                }
            )
            flags["Emergency"] = flags["Emergency"] or flags["ExternalEmergency"]
            await self._write(f"{mp}.Overview.CurrentState", cur, True, now)
            await self._write(f"{mp}.Overview.CurrentMode", mode_v, ok, now)
            for k, v in flags.items():
                await self._write(f"{mp}.Flags.{k}", v, ok, now)
            po = self._sig(f"workcenters/{code}/pieces_out")
            n = _u64(po.value) if po is not None else 0
            for k in ("AbsolutePiecesOut", "RelativePiecesOut"):
                await self._write(f"{mp}.Values.{k}", n, ok, now)
            cyc = self._sig(f"equipment/{code}/cycles_today")
            if cyc is not None:
                await self._write(f"{mp}.Values.RelativeRunsTotal", _u64(cyc.value), ok, now)
            pw = self._sig(f"energy/consumers/{code}/p_now")
            await self._write(
                f"{code}.ManufacturerSpecific.PowerActive", float(pw.value) if pw is not None else 0.0, ok, now
            )
            if code == "GANTRY-1":
                vac = self._sig("equipment/GANTRY-1/vacuum_kpa")
                await self._write(
                    "GANTRY-1.ManufacturerSpecific.VacuumKpa", float(vac.value) if vac is not None else 0.0, ok, now
                )
                await self._write(
                    "GANTRY-1.ManufacturerSpecific.CyclesToday", _u64(cyc.value) if cyc is not None else 0, ok, now
                )
            else:
                await self._write_joborders(code, ok, now)
        await self._emit_events()

    async def _write_joborders(self, code: str, ok: bool, now: Any) -> None:
        lst = self.joborders[code]
        jsig = self._sig(f"workcenters/{code}/job")
        cur = str(jsig.value) if jsig is not None and jsig.value not in (None, "", 0) else ""
        if cur and not any(j["id"] == cur for j in lst):
            lst.append({"id": cur, "state": "Running"})
        for j in lst:  # завдання з сигналу: зникло -> Ended/Completed (лишається до зміни)
            if jsig is not None and j["state"] == "Running" and j["id"] != cur and not j["id"].startswith("cj-"):
                j["state"] = "Ended"
        base = f"{code}.JobManagement"
        await self._write(f"{base}.JobOrderControl.JobOrderList", [j["id"] for j in lst] or [""], ok, now)
        await self._write(
            f"{base}.JobOrderResults.JobOrderResponseList",
            [j["id"] for j in lst if j["state"] == "Ended"] or [""],
            ok,
            now,
        )

    def job_orders(self, code: str) -> list[dict[str, Any]]:
        return list(self.joborders.get(code, []))

    async def _emit_events(self) -> None:
        evs, self._cursor = self.world.events.since(self._cursor)
        for ev in evs:
            holder = self._events.get(ev.device or "")
            if holder is None or self.server is None:
                continue
            g = await self.server.get_event_generator(emitting_node=holder)
            g.event.Message = ua.LocalizedText(ev.message)
            g.event.SourceName = ev.device
            g.event.Severity = {"alarm": 800, "error": 1000, "fault": 800}.get(ev.kind, 200)
            await g.trigger()
