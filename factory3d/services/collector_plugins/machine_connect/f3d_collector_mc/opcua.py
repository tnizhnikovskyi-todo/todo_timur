"""Плагін `opcua` (§8.3, R-22): підписки DataChange і події, poll, виклики JobOrderControl."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse

from asyncua import Node, ua
from collector.core.errors import NotSupported, WriteError
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins._common import schema_errors, validate_source
from collector.plugins.base import PluginContext, SourcePlugin
from collector.util.timeutil import SystemClock

from . import cmdtext, nodeids, ua_values
from .events import inc_metric, make_event
from .ua_session import DEFAULT_POOL, Session, SessionConfig, SessionPool

DEFAULT_APP_URI = "urn:todo.ltd:f3d:collector"
DEFAULT_WW_URI = "http://opcfoundation.org/UA/Woodworking/"
DEFAULT_ISA_URI = "http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/"
CALL_TIMEOUT_S = 10.0
BAD_WARN_EVERY_S = 60.0

_SCHEMA_DIR = Path(__file__).parent / "schemas"


def _ext(name: str) -> dict:
    return json.loads((_SCHEMA_DIR / f"{name}.ext.json").read_text(encoding="utf-8"))


_BASE_ADDRESS = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["nodeid"],
    "properties": {
        "nodeid": {"type": "string", "pattern": r"^ns=\d+;[sigb]=.{1,240}$"},
        "mode": {"enum": ["subscribe", "poll"]},
        "sampling_ms": {"type": "number", "minimum": 0, "maximum": 60000},
        "map": {
            "type": "object",
            "propertyNames": {"pattern": "^-?[0-9]+$"},
            "additionalProperties": {"type": "string", "maxLength": 64},
        },
    },
}
_BASE_PARAMS = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["endpoint"],
    "properties": {
        "endpoint": {"type": "string", "pattern": r"^opc\.tcp://"},
        "security_mode": {"enum": ["None", "Sign", "SignAndEncrypt"]},
        "security_policy": {"enum": ["None", "Basic256Sha256", "Aes128_Sha256_RsaOaep", "Aes256_Sha256_RsaPss"]},
        "username": {"type": "string"},
        "password_ref": {"type": "string"},
        "cert_ref": {"type": "string"},
        "key_ref": {"type": "string"},
        "timeout_s": {"type": "number", "exclusiveMinimum": 0, "maximum": 120},
        "publishing_interval_ms": {"type": "number", "minimum": 50, "maximum": 60000},
    },
}


class _DataHandler:
    """Обробник підписки DataChange (R-22 п. 2–4)."""

    def __init__(self, plugin: OpcUaPlugin) -> None:
        self.plugin = plugin

    def datachange_notification(self, node: Node, val: Any, data: Any) -> None:
        self.plugin.on_data(node.nodeid, data.monitored_item.Value)

    def status_change_notification(self, status: Any) -> None:
        code = getattr(status, "Status", status)
        if hasattr(code, "is_good") and not code.is_good():
            self.plugin.session.mark_bad(f"status {getattr(code, 'name', code)}")


class _EventHandler:
    """Обробник підписки на події й тривоги (EV-01)."""

    def __init__(self, plugin: OpcUaPlugin) -> None:
        self.plugin = plugin

    def event_notification(self, event: Any) -> None:
        self.plugin.on_event(event)

    def status_change_notification(self, status: Any) -> None:
        code = getattr(status, "Status", status)
        if hasattr(code, "is_good") and not code.is_good():
            self.plugin.session.mark_bad(f"status {getattr(code, 'name', code)}")


class OpcUaPlugin(SourcePlugin):
    type = "opcua"
    version = "0.1.0"
    push_mode = True
    address_schema: ClassVar[dict] = {"allOf": [_BASE_ADDRESS, _ext("address.opcua")]}
    params_schema: ClassVar[dict] = {"allOf": [_BASE_PARAMS, _ext("params.opcua")]}

    def __init__(
        self, source: SourceCfg, ctx: PluginContext, clock: Any = None, pool: SessionPool | None = None
    ) -> None:
        super().__init__(source, ctx)
        self.clock = clock or getattr(ctx, "clock", None) or SystemClock()
        self.pool = pool or DEFAULT_POOL
        p = source.params
        self.endpoint: str = p.get("endpoint", "")
        self.publishing_ms: float = float(p.get("publishing_interval_ms", 1000))
        self.heartbeat_s: float = float(p.get("heartbeat_s", 60))
        self.session: Session | None = None
        self._subs: list[Any] = []
        self._tasks: list[asyncio.Task] = []
        self._hb: asyncio.Task | None = None
        self._by_node: dict[ua.NodeId, list[SignalCfg]] = {}
        self._alarm_types: set[ua.NodeId] = set()
        self._last_good: dict[str, Reading] = {}
        self._bad: set[str] = set()
        self._items: set[str] = set()
        self._online = False
        self._subscribed = False
        self._last_notification: datetime | None = None
        self._bad_warned = -BAD_WARN_EVERY_S
        self.stats = {"items": 0, "notifications": 0, "events": 0, "reconnects": 0}

    # --- валідація ---
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        return validate_source(source, cls.address_schema, cls.params_schema, cls._check_address)

    @staticmethod
    def _check_address(addr: dict, params: dict) -> list[str]:
        errs = schema_errors(OpcUaPlugin.address_schema, addr)
        if errs:
            return errs
        out: list[str] = []
        try:
            nodeids.validate(addr["nodeid"])
        except ValueError as exc:
            out.append(str(exc))
        if addr.get("events") and addr.get("mode", "subscribe") != "subscribe":
            out.append("events: лише з mode=subscribe")
        if addr.get("io") == "write" and addr.get("events"):
            out.append("events: несумісно з io=write")
        return out

    # --- життєвий цикл ---
    @property
    def _signals(self) -> list[SignalCfg]:
        return [s for s in self.source.signals if s.address and (s.address.get("io") or "read") != "write"]

    def _ns_uri(self, signal: SignalCfg | None = None) -> str | None:
        if signal is not None and signal.address.get("ns_uri"):
            return signal.address["ns_uri"]
        return self.source.params.get("ns_uri")

    async def connect(self) -> None:
        p = self.source.params
        self.ctx.allowlist(urlparse(self.endpoint).hostname or "")
        cfg = SessionConfig(
            endpoint=self.endpoint,
            security_mode=p.get("security_mode", "None"),
            security_policy=p.get("security_policy", "None"),
            username=p.get("username") or None,
            timeout_s=float(p.get("timeout_s", 5)),
            app_uri=p.get("app_uri", DEFAULT_APP_URI),
            secrets=self.ctx.secrets,
            params=p,
        )
        self.session = self.pool.get(cfg, self.clock, self.ctx)
        await self.session.join(self)
        self._online = True

    async def disconnect(self) -> None:
        await self._stop_all()
        session, self.session = self.session, None
        self._online = False
        if session is not None:
            await session.leave(self)

    async def subscribe(self) -> None:
        await self._setup()
        self._subscribed = True
        if self._hb is None:
            self._hb = asyncio.create_task(self._heartbeat(), name=f"opcua-heartbeat-{self.source.code}")

    # --- підписки (§8.3 п. 3) ---
    async def _stop_all(self) -> None:
        for task in [*self._tasks, *([self._hb] if self._hb else [])]:
            task.cancel()
        await asyncio.gather(*self._tasks, *([self._hb] if self._hb else []), return_exceptions=True)
        self._tasks = []
        self._hb = None
        subs, self._subs = self._subs, []
        for sub in subs:
            try:
                await asyncio.wait_for(sub.delete(), 2)
            except Exception:  # noqa: BLE001, S110
                pass

    async def _drop_subs(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self._subs = []  # сесія вже закрита, підписки зникли разом із нею

    async def _setup(self) -> None:
        session = self.session
        assert session is not None and session.client is not None
        client = session.client
        ns_array = session.ns_array
        self._by_node = {}
        data_nodes: dict[float, list[Node]] = {}
        poll_nodes: list[tuple[SignalCfg, Node]] = []
        event_sources: list[Node] = []
        self._items = set()
        for sig in self._signals:
            addr = sig.address
            nid = nodeids.resolve(addr["nodeid"], self._ns_uri(sig), ns_array)
            if addr.get("events"):
                event_sources.append(client.get_node(nid))
                continue
            self._items.add(sig.code)
            self._by_node.setdefault(nid, []).append(sig)
            node = client.get_node(nid)
            if addr.get("mode", "subscribe") == "poll":
                poll_nodes.append((sig, node))
            else:
                data_nodes.setdefault(float(addr.get("sampling_ms", 0)), []).append(node)
        self.stats["items"] = len(self._items)
        for sampling, nodes in data_nodes.items():
            sub = await client.create_subscription(self.publishing_ms, _DataHandler(self))
            self._subs.append(sub)
            uniq = list({n.nodeid: n for n in nodes}.values())
            results = await sub.subscribe_data_change(uniq, sampling_interval=sampling)
            for node, res in zip(uniq, results, strict=False):
                if isinstance(res, ua.StatusCode):
                    self.ctx.log.warning("opcua %s: monitored item %s: %s", self.source.code, node.nodeid, res)
                    self._set_bad(node.nodeid)
        if event_sources:
            evtypes = await self._event_types(client, ns_array)
            for src in event_sources:
                evsub = await client.create_subscription(self.publishing_ms, _EventHandler(self))
                self._subs.append(evsub)
                await evsub.subscribe_events(src, evtypes)
        if poll_nodes:
            self._tasks.append(asyncio.create_task(self._poll_loop(poll_nodes), name=f"opcua-poll-{self.source.code}"))

    def _set_bad(self, nodeid: ua.NodeId) -> None:
        for sig in self._by_node.get(nodeid, []):
            reading = ua_values.bad_reading(sig, self.clock.now())
            self._bad.add(sig.code)
            if reading is not None:
                self.ctx.emit(reading)

    async def _event_types(self, client: Any, ns_array: list[str]) -> list[Any]:
        """WwBaseEventType і WwAlarmConditionType за browse-шляхом у просторі `ww_uri`; інакше BaseEventType."""
        ww_uri = next((s.address.get("ww_uri") for s in self._signals if s.address.get("ww_uri")), DEFAULT_WW_URI)
        self._alarm_types = set()
        try:
            idx = ns_array.index(ww_uri)
            base = await client.get_node(ua.ObjectIds.BaseEventType).get_child(f"{idx}:WwBaseEventType")
            alarm = await client.get_node(ua.ObjectIds.AlarmConditionType).get_child(f"{idx}:WwAlarmConditionType")
        except Exception as exc:  # noqa: BLE001
            self.ctx.log.warning(
                "opcua %s: Woodworking event types not found (%s), BaseEventType", self.source.code, exc
            )
            return [client.get_node(ua.ObjectIds.BaseEventType)]
        self._alarm_types = {alarm.nodeid}
        return [base, alarm]

    async def _poll_loop(self, items: list[tuple[SignalCfg, Node]]) -> None:
        period = min(float(s.period_s) for s, _ in items) or 1.0
        while True:
            try:
                assert self.session is not None and self.session.client is not None
                dvs = await self.session.client.read_attributes([n for _, n in items])
                for (_sig, node), dv in zip(items, dvs, strict=False):
                    self.on_data(node.nodeid, dv)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                self.ctx.log.warning("opcua %s: poll failed: %s", self.source.code, exc)
            await self.clock.sleep(period)

    # --- сповіщення (§8.3 п. 4) ---
    def on_data(self, nodeid: ua.NodeId, dv: Any) -> None:
        now = self.clock.now()
        for sig in self._by_node.get(nodeid, []):
            if sig.address.get("job_select") and self.session is not None and not self.session.types_ok:
                reading: Reading | None = ua_values.bad_reading(sig, now)
            else:
                reading = ua_values.to_reading(sig, dv, now)
                _ts, future = ua_values.value_ts(dv, now)
                if future:
                    self.ctx.log.warning("opcua %s: %s timestamp is in the future", self.source.code, sig.code)
            self.stats["notifications"] += 1
            self._last_notification = now
            inc_metric(self.ctx, "collector_mc_opcua_notifications_total", source=self.source.code)
            if reading is None:
                self._mark_bad(sig.code)
                continue
            if reading.q == "bad":
                self._mark_bad(sig.code)
            else:
                self._bad.discard(sig.code)
                self._last_good[sig.code] = reading
            self.ctx.emit(reading)

    def _mark_bad(self, code: str) -> None:
        self._bad.add(code)
        now = self.clock.monotonic()
        if now - self._bad_warned >= BAD_WARN_EVERY_S:
            self._bad_warned = now
            self.ctx.log.warning("opcua %s: Bad status of %s", self.source.code, code)

    def on_event(self, event: Any) -> None:
        payload = ua_values.event_payload(
            self.source.code, self.source.code.removeprefix("UA-"), event, frozenset(self._alarm_types)
        )
        self.stats["events"] += 1
        inc_metric(self.ctx, "collector_mc_opcua_events_total", source=self.source.code, kind=payload["kind"])
        self.ctx.emit_event(make_event("mc_opcua", self.source.code, payload, ts=self.clock.now()))

    async def _heartbeat(self) -> None:
        """R-22 п. 4: раз на `heartbeat_s` останні добрі значення з ts = now (лише при online-сесії)."""
        while True:
            await self.clock.sleep(self.heartbeat_s)
            if not self._online:
                continue
            now = self.clock.now()
            for code, last in list(self._last_good.items()):
                self.ctx.emit(Reading(code=code, ts=now, value=last.value, text=last.text, q="good"))

    # --- нагляд (виклики з Session) ---
    def session_down(self, reason: str) -> None:
        self._online = False
        now = self.clock.now()
        for sig in self._signals:
            if sig.address.get("events"):
                continue
            reading = ua_values.bad_reading(sig, now)
            self._bad.add(sig.code)
            if reading is not None:
                self.ctx.emit(reading)

    async def resubscribe(self) -> None:
        await self._drop_subs()
        if self._subscribed:
            await self._setup()
        self._bad.clear()
        self._online = True

    def health(self) -> Health:
        session = self.session
        stats = dict(self.stats)
        stats["reconnects"] = session.reconnects if session is not None else 0
        if self._last_notification is not None:
            stats["last_notification"] = self._last_notification.isoformat()
        if session is None or not session.connected:
            return Health(state="offline", error=session.last_error if session else None, stats=stats)
        n = len(self._items)
        if n and len(self._bad & self._items) >= n:
            return Health(state="error", error="усі вузли Bad_…", last_ok=self._last_notification, stats=stats)
        return Health(state="online", last_ok=self._last_notification, stats=stats)

    # --- команди (§8.3 п. 6, R-21, R-22 п. 6) ---
    def _job_signal(self, signal: SignalCfg) -> None:
        if (signal.address or {}).get("call") != "job":
            raise NotSupported("call")

    def _check_write_enabled(self) -> None:
        if not getattr(self.ctx.settings, "write_enabled", False):
            raise WriteError("write disabled")

    async def call(self, signal: SignalCfg, payload: dict) -> dict:
        self._job_signal(signal)
        self._check_write_enabled()
        try:
            checked = cmdtext.check_payload("job", payload)
        except ValueError as exc:
            self._count_command(signal, "job", "rejected")
            raise WriteError(f"bad_command: {exc}") from exc
        return await self._invoke(signal, checked)

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        self._job_signal(signal)
        self._check_write_enabled()
        try:
            checked = cmdtext.parse_cmd("job", text or "")
        except ValueError as exc:
            self._count_command(signal, "job", "rejected")
            raise WriteError(f"bad_command: {exc}") from exc
        data = await self._invoke(signal, checked)
        return cmdtext.result_text("job", checked, data)

    def _count_command(self, signal: SignalCfg, cmd: str, result: str) -> None:
        inc_metric(self.ctx, "collector_mc_commands_total", source=self.source.code, cmd=cmd, result=result)

    async def _invoke(self, signal: SignalCfg, p: dict) -> dict:
        session = self.session
        if session is None or not session.connected or session.client is None:
            self._count_command(signal, p["method"], "error")
            raise WriteError("not connected")
        if not session.types_ok:
            self._count_command(signal, p["method"], "error")
            raise WriteError("data types not loaded")
        try:
            status = await asyncio.wait_for(self._call_method(session, signal, p), CALL_TIMEOUT_S)
        except WriteError:
            self._count_command(signal, p["method"], "error")
            raise
        except Exception as exc:  # noqa: BLE001
            self._count_command(signal, p["method"], "error")
            raise WriteError(f"call {p['method']} failed: {type(exc).__name__}: {exc}") from exc
        if status != 0:
            self._count_command(signal, p["method"], "error")
            raise WriteError(f"ReturnStatus={status}")
        self._count_command(signal, p["method"], "ok")
        self.ctx.log.info("opcua %s: %s %s ok", self.source.code, p["method"], p["job"])
        return {"ReturnStatus": 0}

    async def _call_method(self, session: Session, signal: SignalCfg, p: dict) -> int:
        client = session.client
        assert client is not None
        addr = signal.address
        obj = client.get_node(nodeids.resolve(addr["nodeid"], self._ns_uri(signal), session.ns_array))
        isa_uri = addr.get("isa_uri", DEFAULT_ISA_URI)
        try:
            isa_idx = session.ns_array.index(isa_uri)
        except ValueError:
            raise WriteError(f"namespace {isa_uri} not found") from None
        method = await obj.get_child(f"{isa_idx}:{p['method']}")
        if p["method"] in ("Store", "StoreAndStart"):
            params = [
                ua.ISA95ParameterDataType(ID="PlannedOrderQuantity", Value=ua.Variant(float(p["qty"]))),
                ua.ISA95ParameterDataType(ID="OrderNumbers", Value=ua.Variant([p["ref"]], ua.VariantType.String)),
            ]
            order = ua.ISA95JobOrderDataType(
                JobOrderID=p["job"],
                Description=[ua.LocalizedText(f"{p['ref']} {p['job']}", "uk")],
                WorkMasterID=[],
                Priority=p["priority"],
                JobOrderParameters=params,
            )
            args: list[Any] = [order]
        else:
            args = [ua.Variant(p["job"], ua.VariantType.String), ua.Variant([], ua.VariantType.LocalizedText)]
        ret = await obj.call_method(method, *args)
        if isinstance(ret, list | tuple):
            ret = ret[0] if ret else 0
        return int(ret or 0)
