"""Мінімальний сервер OPC UA для тестів плагіна `opcua` (SPEC §13.0.2): Machines/<C> з State/Machine/Overview,
Flags, Values, JobManagement, Events. Простори: 0 UA, 1 urn:test, 2 other, 3 Woodworking, 4 ISA95, 5 instances."""

from __future__ import annotations

import socket
from collections.abc import Callable
from datetime import UTC, datetime

from asyncua import Server, ua
from asyncua.common.structures104 import new_struct, new_struct_field
from asyncua.server.user_managers import UserManager
from asyncua.server.users import User, UserRole

NS_URIS = [
    "urn:test",  # 1 (URI застосунку сервера)
    "http://example.org/other/",  # 2
    "http://opcfoundation.org/UA/Woodworking/",  # 3
    "http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/",  # 4
    "http://todo.ltd/f3d/iot_sim/instances/",  # 5
]
INST = 5
WW = 3
ISA = 4
METHODS = ("Store", "StoreAndStart", "Start", "Stop", "Pause", "Resume", "Cancel", "Abort", "Clear")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Users(UserManager):
    def get_user(self, iserver, username=None, password=None, certificate=None):
        if username is None or (username == "collector" and password == "pw"):
            return User(role=UserRole.User)
        return None


def _state_text(text: str) -> ua.LocalizedText:
    return ua.LocalizedText(text, "en")


class FakeMachines:
    def __init__(
        self,
        port: int | None = None,
        machines: tuple[str, ...] = ("SAW-T", "SAW-T2"),
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._now = now or (lambda: datetime.now(UTC))
        self.port = port or free_port()
        self.machines = machines
        self.endpoint = f"opc.tcp://127.0.0.1:{self.port}/f3d/"
        self.calls: list[tuple[str, tuple]] = []
        self.ret_status = 0
        self.server: Server | None = None
        self._nodes: dict[str, object] = {}
        # значення переживають stop()/start()
        self.values: dict[str, object] = {}
        self.jobs: dict[str, list[tuple[str, str]]] = {m: [] for m in machines}

    # --- життєвий цикл ---
    async def start(self) -> None:
        srv = Server(user_manager=_Users())
        await srv.init()
        srv.set_endpoint(self.endpoint)
        srv.set_server_name("fake machines")
        await srv.set_application_uri("urn:test")
        for uri in NS_URIS[1:]:
            await srv.register_namespace(uri)
        self.server = srv
        self._nodes = {}
        await self._build(srv)
        await srv.start()

    async def stop(self) -> None:
        if self.server is not None:
            srv, self.server = self.server, None
            await srv.stop()

    # --- побудова адресного простору ---
    async def _build(self, srv: Server) -> None:
        sdt = [
            (
                "ISA95StateDataType",
                [("StateText", ua.VariantType.LocalizedText, False), ("StateNumber", ua.VariantType.UInt32, False)],
            ),
            (
                "ISA95ParameterDataType",
                [("ID", ua.VariantType.String, False), ("Value", ua.VariantType.Variant, False)],
            ),
        ]
        types: dict[str, ua.NodeId] = {}
        for name, fields in sdt:
            node, _ = await new_struct(srv, ISA, name, [new_struct_field(n, t, a) for n, t, a in fields])
            types[name] = node.nodeid
        node, _ = await new_struct(
            srv,
            ISA,
            "ISA95JobOrderDataType",
            [
                new_struct_field("JobOrderID", ua.VariantType.String),
                new_struct_field("Description", ua.VariantType.LocalizedText, array=True),
                new_struct_field("WorkMasterID", ua.VariantType.String, array=True),
                new_struct_field("Priority", ua.VariantType.Int16),
                new_struct_field("JobOrderParameters", types["ISA95ParameterDataType"], array=True),
            ],
        )
        types["ISA95JobOrderDataType"] = node.nodeid
        node, _ = await new_struct(
            srv,
            ISA,
            "ISA95JobOrderAndStateDataType",
            [
                new_struct_field("JobOrder", types["ISA95JobOrderDataType"]),
                new_struct_field("State", types["ISA95StateDataType"], array=True),
            ],
        )
        types["ISA95JobOrderAndStateDataType"] = node.nodeid
        await srv.load_data_type_definitions()
        self.types = types

        props = [
            ("MessageId", ua.VariantType.String),
            ("MessageName", ua.VariantType.String),
            ("EventCategory", ua.VariantType.Int32),
            ("PathParts", ua.VariantType.String),
            ("Group", ua.VariantType.String),
            ("LocalizedMessages", ua.VariantType.LocalizedText),
            ("Arguments", ua.VariantType.String),
        ]
        self.ev_base = await srv.create_custom_event_type(WW, "WwBaseEventType", ua.ObjectIds.BaseEventType, props)
        self.ev_alarm = await srv.create_custom_event_type(
            WW, "WwAlarmConditionType", ua.ObjectIds.AlarmConditionType, props
        )

        objects = srv.nodes.objects
        machines = await objects.add_object(ua.NodeId("Machines", INST), ua.QualifiedName("Machines", INST))
        for code in self.machines:
            await self._build_machine(srv, machines, code)

    def _nid(self, name: str) -> ua.NodeId:
        return ua.NodeId(name, INST)

    async def _build_machine(self, srv: Server, parent, code: str) -> None:
        obj = await parent.add_object(self._nid(code), ua.QualifiedName(code, INST))

        async def var(name: str, value, vtype) -> None:
            key = f"{code}.{name}"
            init = self.values.get(key, value)
            node = await obj.add_variable(self._nid(key), ua.QualifiedName(name.rsplit(".", 1)[-1], INST), init, vtype)
            await node.set_writable()
            await node.write_value(ua.DataValue(ua.Variant(init, vtype), SourceTimestamp=self._now()))
            self._nodes[key] = node

        await var("State.Machine.Overview.CurrentState", 3, ua.VariantType.Int32)
        await var("State.Machine.Overview.CurrentMode", 1, ua.VariantType.Int32)
        await var("State.Machine.Flags.Alarm", False, ua.VariantType.Boolean)
        await var("State.Machine.Values.RelativePiecesOut", 0, ua.VariantType.UInt64)
        key = f"{code}.JobManagement.JobOrderControl.JobOrderList"
        jl = await obj.add_variable(
            self._nid(key),
            ua.QualifiedName("JobOrderList", INST),
            ua.Variant([], ua.VariantType.ExtensionObject),
            datatype=self.types["ISA95JobOrderAndStateDataType"],
        )
        await jl.set_writable()
        self._nodes[key] = jl
        if self.jobs[code]:
            await self._write_jobs(code)
        ev = await obj.add_object(self._nid(f"{code}.Events"), ua.QualifiedName("Events", INST))
        await ev.set_event_notifier([ua.EventNotifier.SubscribeToEvents])
        self._nodes[f"{code}.Events"] = ev
        joc = await obj.add_object(
            self._nid(f"{code}.JobManagement.JobOrderControl"), ua.QualifiedName("JobOrderControl", INST)
        )
        job_arg = ua.Argument()
        job_arg.Name = "JobOrder"
        job_arg.DataType = self.types["ISA95JobOrderDataType"]
        job_arg.ValueRank = -1
        str_arg = ua.Argument()
        str_arg.Name = "JobOrderID"
        str_arg.DataType = ua.NodeId(ua.ObjectIds.String)
        str_arg.ValueRank = -1
        cmt_arg = ua.Argument()
        cmt_arg.Name = "Comment"
        cmt_arg.DataType = ua.NodeId(ua.ObjectIds.LocalizedText)
        cmt_arg.ValueRank = 1
        cmt_arg.ArrayDimensions = [0]
        out_arg = ua.Argument()
        out_arg.Name = "ReturnStatus"
        out_arg.DataType = ua.NodeId(ua.ObjectIds.UInt64)
        out_arg.ValueRank = -1
        for m in METHODS:
            inputs = [job_arg] if m in ("Store", "StoreAndStart") else [str_arg, cmt_arg]
            await joc.add_method(
                self._nid(f"{code}.JobManagement.JobOrderControl.{m}"),
                ua.QualifiedName(m, ISA),
                self._make_handler(m),
                inputs,
                [out_arg],
            )

    def _make_handler(self, method: str):
        async def handler(parent, *args):
            self.calls.append((method, tuple(a.Value if isinstance(a, ua.Variant) else a for a in args)))
            return [ua.Variant(self.ret_status, ua.VariantType.UInt64)]

        return handler

    # --- помічники тестів ---
    def _node(self, name: str, code: str):
        return self._nodes[f"{code}.{name}"]

    async def set(self, var: str, value, machine: str = "SAW-T") -> None:
        """var: `CurrentState`, `CurrentMode`, `Alarm`, `RelativePiecesOut` (або повний хвіст шляху)."""
        paths = {
            "CurrentState": ("State.Machine.Overview.CurrentState", ua.VariantType.Int32),
            "CurrentMode": ("State.Machine.Overview.CurrentMode", ua.VariantType.Int32),
            "Alarm": ("State.Machine.Flags.Alarm", ua.VariantType.Boolean),
            "RelativePiecesOut": ("State.Machine.Values.RelativePiecesOut", ua.VariantType.UInt64),
        }
        name, vtype = paths[var]
        self.values[f"{machine}.{name}"] = value
        await self._node(name, machine).write_value(ua.DataValue(ua.Variant(value, vtype), SourceTimestamp=self._now()))

    async def set_jobs(self, items: list[tuple[str, str]], machine: str = "SAW-T") -> None:
        self.jobs[machine] = list(items)
        await self._write_jobs(machine)

    async def _write_jobs(self, machine: str) -> None:
        out = []
        for job_id, state_text in self.jobs[machine]:
            order = ua.ISA95JobOrderDataType(JobOrderID=job_id)
            state = ua.ISA95StateDataType(StateText=_state_text(state_text), StateNumber=1)
            out.append(ua.ISA95JobOrderAndStateDataType(JobOrder=order, State=[state]))
        await self._node("JobManagement.JobOrderControl.JobOrderList", machine).write_value(
            ua.DataValue(ua.Variant(out, ua.VariantType.ExtensionObject), SourceTimestamp=self._now())
        )

    async def fire_event(
        self,
        kind: str,
        message_id: str,
        category: int,
        text_uk: str,
        text_en: str,
        active: bool = True,
        machine: str = "SAW-T",
        severity: int = 1000,
    ) -> None:
        etype = self.ev_alarm if kind == "alarm" else self.ev_base
        gen = await self.server.get_event_generator(etype, self._node("Events", machine).nodeid)
        ev = gen.event
        ev.SourceName = machine
        ev.Severity = severity
        ev.MessageId = message_id
        ev.MessageName = "SpindleOverload" if message_id == "E0421" else message_id
        ev.EventCategory = category
        ev.PathParts = [machine, "Spindle", "Z"]
        ev.Group = "Drive"
        ev.LocalizedMessages = [ua.LocalizedText(text_uk, "uk"), ua.LocalizedText(text_en, "en")]
        ev.Arguments = []
        if kind == "alarm":
            ev.ActiveState = ua.LocalizedText("Active" if active else "Inactive")
            setattr(ev, "ActiveState/Id", active)
            ev.data_types["ActiveState/Id"] = ua.VariantType.Boolean
            ev.AckedState = ua.LocalizedText("Unacknowledged")
            setattr(ev, "AckedState/Id", False)
            ev.data_types["AckedState/Id"] = ua.VariantType.Boolean
        await gen.trigger(message=text_uk)
