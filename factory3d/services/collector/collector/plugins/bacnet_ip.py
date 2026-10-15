"""Плагін `bacnet_ip` (SPEC §8.8, R-23, FR-29): ReadPropertyMultiple, COV, запис, події, режим read_only."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import socket
import zlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from bacpypes3.apdu import ErrorRejectAbortNack  # type: ignore[import-untyped]
from bacpypes3.app import Application  # type: ignore[import-untyped]
from bacpypes3.basetypes import ErrorType  # type: ignore[import-untyped]
from bacpypes3.local.device import DeviceObject  # type: ignore[import-untyped]
from bacpypes3.local.networkport import NetworkPortObject  # type: ignore[import-untyped]
from bacpypes3.pdu import Address  # type: ignore[import-untyped]
from bacpypes3.primitivedata import Null, ObjectIdentifier  # type: ignore[import-untyped]

from collector.core.errors import ConnectError, NotSupported, PollError, WriteError
from collector.core.types import Health, PushEvent, Reading, SignalCfg, SourceCfg
from collector.plugins._common import Ewma, canonical_json, ctx_clock, linear, load_schema, validate_source
from collector.plugins.base import PluginContext, SourcePlugin
from collector.util.timeutil import to_iso_z

log = logging.getLogger("collector.plugin.bacnet_ip")

RO_SERVICES = frozenset({"who-is", "read-property", "read-property-multiple"})
MAX_MESSAGE = 500
ADDR_CACHE = "bacnet_addr.json"

LONG = {
    "AI": "analog-input",
    "AO": "analog-output",
    "AV": "analog-value",
    "BI": "binary-input",
    "BO": "binary-output",
    "BV": "binary-value",
    "MSI": "multi-state-input",
    "MSV": "multi-state-value",
    "LSZ": "life-safety-zone",
    "LSP": "life-safety-point",
    "PIV": "positive-integer-value",
}
SHORT = {v: k for k, v in LONG.items()}
_COV_DEFAULT = {
    "analog-input",
    "binary-input",
    "multi-state-input",
    "multi-state-value",
    "life-safety-zone",
    "life-safety-point",
}
_PA_TYPES = {"analog-output", "analog-value", "binary-output", "binary-value"}
_BINARY = {"binary-input", "binary-output", "binary-value"}
_MULTI = {"multi-state-input", "multi-state-value"}
_TEXT_TYPES = _BINARY | _MULTI | {"life-safety-zone", "life-safety-point"}


def normalize_object(name: str) -> str:
    """`AI`/`analog-input` -> `analog-input`."""
    return LONG.get(name, name)


def service_name(name: str) -> str:
    """`SubscribeCOV` / `subscribe_cov` -> `subscribe-cov`."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", name.strip().replace("_", "-").replace(" ", "-"))
    return s.lower()


def _num(v: Any) -> float | None:
    if isinstance(v, ErrorType) or v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_error(v: Any) -> bool:
    return isinstance(v, ErrorType | ErrorRejectAbortNack)


# ---------------------------------------------------------------------------
# Застосунок bacpypes3 (один на процес)
# ---------------------------------------------------------------------------
class _F3DApplication(Application):
    """bacpypes3-застосунок колектора + прийом `UnconfirmedEventNotification`."""

    owner: BacnetApp

    async def do_UnconfirmedEventNotificationRequest(self, apdu: Any) -> None:
        self.owner.on_event(apdu)


class BacnetApp:
    """Локальний device «F3D Collector»; спільний для всіх джерел `bacnet_ip` (refcount)."""

    _instance: ClassVar[BacnetApp | None] = None

    def __init__(self, settings: Any) -> None:
        bind = getattr(settings, "bacnet_bind", "0.0.0.0:47808")
        dev_id = int(getattr(settings, "bacnet_device_id", 3999))
        device = DeviceObject(objectIdentifier=("device", dev_id), objectName="F3D Collector", vendorIdentifier=999)
        port = NetworkPortObject(
            bind,
            objectIdentifier=("network-port", 1),
            objectName="NetworkPort-1",
            networkNumber=0,
            networkNumberQuality="unknown",
        )
        self.app: _F3DApplication = _F3DApplication.from_object_list([device, port])  # type: ignore[assignment]
        self.app.owner = self
        self.plugins: list[BacnetIpPlugin] = []
        self.refs = 0
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def acquire(cls, settings: Any) -> BacnetApp:
        inst = cls._instance
        if inst is not None and inst.loop is not asyncio.get_running_loop():
            inst = cls._instance = None  # застарілий застосунок з іншого (закритого) циклу
        if inst is None:
            inst = cls._instance = cls(settings)
            await inst._wait_ready()
        inst.refs += 1
        return inst

    async def _wait_ready(self, timeout_s: float = 5.0) -> None:
        """bacpypes3 створює UDP-ендпоінт у фоновому завданні — чекаємо, доки з'явиться транспорт."""
        end = asyncio.get_running_loop().time() + timeout_s
        while not self.local_port:
            if asyncio.get_running_loop().time() > end:
                raise ConnectError("bacnet: local UDP endpoint was not created")
            await asyncio.sleep(0.01)

    async def release(self) -> None:
        self.refs -= 1
        if self.refs <= 0:
            if BacnetApp._instance is self:
                BacnetApp._instance = None
            with contextlib.suppress(Exception):
                self.app.close()

    @property
    def local_port(self) -> int:
        for link in self.app.link_layers.values():
            transport = getattr(link.server, "local_transport", None)
            if transport is not None:
                return int(transport.get_extra_info("sockname")[1])
        return 0

    # --- вихідні запити з білим списком для read_only (D-07, X-05) ---
    async def _request(self, plugin: BacnetIpPlugin, service: str, *args: Any, **kwargs: Any) -> Any:
        svc = service_name(service)
        if plugin.read_only and svc not in RO_SERVICES:
            plugin.stats["ro_blocked"] += 1
            plugin.ctx.metrics.bacnet_ro_blocked.labels(plugin.source.code, svc).inc()
            raise NotSupported(f"read-only device: {svc}")
        timeout = plugin.timeout_s
        if svc == "who-is":
            fut = self.app.who_is(*args, timeout=timeout, **kwargs)
            return await asyncio.wait_for(fut, timeout + 1)
        if svc == "subscribe-cov":
            scm = self.app.change_of_value(*args, **kwargs)
            await asyncio.wait_for(scm.__aenter__(), timeout)
            return scm
        fn = {
            "read-property": self.app.read_property,
            "read-property-multiple": self.app.read_property_multiple,
            "write-property": self.app.write_property,
        }.get(svc)
        if fn is None:
            raise NotSupported(f"unsupported service: {svc}")
        return await asyncio.wait_for(fn(*args, **kwargs), timeout)

    # --- вхідні події ---
    def on_event(self, apdu: Any) -> None:
        try:
            device = int(apdu.initiatingDeviceIdentifier[1])
        except (TypeError, ValueError, IndexError):
            return
        targets = [p for p in self.plugins if p.device == device]
        if not targets:
            metric = next(iter(self.plugins), None)
            if metric is not None:
                metric.ctx.metrics.bacnet_events_ignored.labels("unknown_device").inc()
            return
        for p in targets:
            p.handle_event(apdu)


# ---------------------------------------------------------------------------
# Плагін
# ---------------------------------------------------------------------------
@dataclass
class _Spec:
    sg: SignalCfg
    objtype: str
    instance: int
    prop: str
    index: int | None
    mode: str

    @property
    def objid(self) -> str:
        return f"{self.objtype},{self.instance}"

    @property
    def prop_ref(self) -> str:
        return self.prop if self.index is None else f"{self.prop}[{self.index}]"


class BacnetIpPlugin(SourcePlugin):
    type: ClassVar[str] = "bacnet_ip"
    address_schema: ClassVar[dict] = load_schema("address.bacnet_ip")
    params_schema: ClassVar[dict] = load_schema("params.bacnet_ip")

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        super().__init__(source, ctx)
        p = source.params
        self.clock = ctx_clock(ctx)
        self.host: str = p.get("host", "")
        self.port: int = int(p.get("port", 47808))
        self.device: int = int(p.get("device", -1))
        self.timeout_s: float = float(p.get("timeout_s", 5))
        self.rpm: bool = bool(p.get("rpm", True))
        self.rpm_max: int = int(p.get("rpm_max", 50))
        self.cov_lifetime_s: int = int(p.get("cov_lifetime_s", 300))
        self.read_only: bool = bool(p.get("read_only", False))
        self.events: bool = bool(p.get("events", self.read_only))
        self.bapp: BacnetApp | None = None
        self.addr: Address | None = None
        self.stats = {"polls": 0, "cov_notifications": 0, "events": 0, "ro_blocked": 0, "errors": 0}
        self.latency = Ewma()
        self._specs: dict[str, _Spec] = {}
        self._cov_tasks: dict[str, asyncio.Task] = {}
        self._cov_active: set[str] = set()
        self._cov_failed: set[str] = set()
        self._last_read: dict[str, float] = {}
        self._state_cache: dict[tuple[str, int], str] = {}  # останній to_state/present-value LSZ/LSP
        self._pa_cache: dict[str, Any] = {}
        self._rpm_ok = self.rpm
        self._last_ok: float | None = None
        self._last_error: str | None = None
        for sg in source.signals:
            if sg.address:
                self._specs[sg.code] = self._spec(sg)

    # --- адреса сигналу ---
    def _spec(self, sg: SignalCfg) -> _Spec:
        a = sg.address
        objtype = normalize_object(str(a["object"]))
        prop = str(a.get("property", "present-value"))
        default = "cov" if objtype in _COV_DEFAULT else "poll"
        mode = str(a.get("mode", default))
        if self.read_only or prop != "present-value" or a.get("states") or objtype == "device":
            mode = "poll"
        return _Spec(sg, objtype, int(a["instance"]), prop, a.get("index"), mode)

    # --- валідація ---
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        errs = validate_source(source, cls.address_schema, cls.params_schema, cls._check_address)
        if source.params.get("read_only") is True:
            if source.write_enabled:
                errs.append("write_enabled: заборонено для джерела з params.read_only")
            errs += [
                f"{s.code}: write_enabled заборонено для джерела з params.read_only"
                for s in source.signals
                if s.write_enabled
            ]
        return errs

    @staticmethod
    def _check_address(a: dict, params: dict) -> list[str]:
        errs = []
        if "device" in a and "device" in params and a["device"] != params["device"]:
            errs.append("device: має дорівнювати params.device")
        for st in a.get("states", []) or []:
            if normalize_object(str(st.get("object"))) not in set(LONG.values()) | {"device"}:
                errs.append(f"states.object: недопустиме значення «{st.get('object')}»")
        return errs

    # --- з'єднання ---
    async def _resolve_host(self) -> str:
        loop = asyncio.get_running_loop()
        try:
            infos = await loop.getaddrinfo(self.host, None, family=socket.AF_INET, type=socket.SOCK_DGRAM)
        except OSError as e:
            raise ConnectError(f"cannot resolve {self.host}: {e}") from e
        return str(infos[0][4][0])

    def _cache_file(self) -> Path | None:
        d = getattr(self.ctx.settings, "buffer_dir", None)
        return Path(d) / ADDR_CACHE if d else None

    def _cache_store(self, addr: Address) -> None:
        f = self._cache_file()
        if f is None:
            return
        with contextlib.suppress(OSError, ValueError):
            data = json.loads(f.read_text()) if f.exists() else {}
            data[f"{self.host}:{self.port}/{self.device}"] = str(addr)
            f.write_text(json.dumps(data))

    def _cache_load(self) -> Address | None:
        f = self._cache_file()
        if f is None or not f.exists():
            return None
        with contextlib.suppress(OSError, ValueError):
            text = json.loads(f.read_text()).get(f"{self.host}:{self.port}/{self.device}")
            if text:
                return Address(text)
        return None

    async def connect(self) -> None:
        self.ctx.allowlist(self.host)
        self._cov_failed.clear()
        self.bapp = await BacnetApp.acquire(self.ctx.settings)
        if self not in self.bapp.plugins:
            self.bapp.plugins.append(self)
        try:
            await self._locate()
        except BaseException:
            await self.disconnect()
            raise
        if self.read_only and any(
            s.sg.address.get("mode") == "cov" or s.objtype in _COV_DEFAULT for s in self._specs.values()
        ):
            self.ctx.log.info("bacnet %s: read_only — COV-сигнали опитуються як poll", self.source.code)
        self._start_cov()

    async def _locate(self) -> None:
        assert self.bapp is not None
        configured = self.source.params.get("address")
        if configured:
            self.addr = Address(configured)
            return
        target = Address(f"{await self._resolve_host()}:{self.port}")
        try:
            iams = await self.bapp._request(self, "who-is", self.device, self.device, target)
        except (TimeoutError, ErrorRejectAbortNack, OSError):
            iams = []
        if iams:
            self.addr = iams[0].pduSource
            self._cache_store(self.addr)
            return
        cached = self._cache_load()
        if cached is not None:
            self.ctx.log.warning("Who-Is: device %s not answered, using cached address %s", self.device, cached)
            self.addr = cached
            return
        raise ConnectError(f"Who-Is: device {self.device} not found")

    async def disconnect(self) -> None:
        for t in self._cov_tasks.values():
            t.cancel()
        if self._cov_tasks:
            await asyncio.gather(*self._cov_tasks.values(), return_exceptions=True)
        self._cov_tasks.clear()
        self._cov_active.clear()
        self._gauge()
        if self.bapp is not None:
            if self in self.bapp.plugins:
                self.bapp.plugins.remove(self)
            bapp, self.bapp = self.bapp, None
            await bapp.release()

    def _gauge(self) -> None:
        self.ctx.metrics.bacnet_cov_active.labels(self.source.code).set(len(self._cov_active))

    # --- читання ---
    def _cov_signals(self) -> list[_Spec]:
        return [s for s in self._specs.values() if s.mode == "cov" and s.sg.code not in self._cov_failed]

    @staticmethod
    def cov_check_s(period_s: float) -> float:
        return max(period_s * 10, 300)

    def _want_read(self, spec: _Spec) -> bool:
        """COV-сигнал з активною підпискою читається лише контрольно раз на cov_check_s."""
        code = spec.sg.code
        if spec.mode != "cov" or code in self._cov_failed or code not in self._cov_active:
            return True
        last = self._last_read.get(code)
        return last is None or self.clock.monotonic() - last >= self.cov_check_s(spec.sg.period_s)

    def _pairs(self, spec: _Spec) -> list[tuple[str, str]]:
        sg, a = spec.sg, spec.sg.address
        pairs = [(spec.objid, spec.prop_ref)]
        if spec.prop == "present-value" and spec.objtype != "device":
            pairs.append((spec.objid, "status-flags"))
            if a.get("check_reliability"):
                pairs.append((spec.objid, "reliability"))
            if a.get("read_priority_array") and spec.objtype in _PA_TYPES:
                pairs.append((spec.objid, "priority-array"))
        for st in a.get("states") or []:
            pairs.append((f"{normalize_object(str(st['object']))},{int(st['instance'])}", "present-value"))
        _ = sg
        return pairs

    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        started = self.clock.monotonic()
        self.stats["polls"] += 1
        try:
            return await self._poll(signals)
        except PollError as e:
            self.stats["errors"] += 1
            self._last_error = str(e)
            raise
        finally:
            self.latency.add((self.clock.monotonic() - started) * 1000)

    async def _poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        if self.bapp is None or self.addr is None:
            raise PollError("not connected")
        specs = [self._specs[s.code] for s in signals if s.code in self._specs]
        specs = [s for s in specs if self._want_read(s)]
        if not specs:
            return []
        pairs: list[tuple[str, str]] = []
        for s in specs:
            for pr in self._pairs(s):
                if pr not in pairs:
                    pairs.append(pr)
        data = await self._read_pairs(pairs)
        ts = self.clock.now()
        now = self.clock.monotonic()
        out = []
        for s in specs:
            self._last_read[s.sg.code] = now
            out.append(self._reading(s, data, ts))
        self._last_ok = now
        self._last_error = None
        return out

    async def _read_pairs(self, pairs: list[tuple[str, str]]) -> dict[tuple[str, str], Any]:
        assert self.bapp is not None
        data: dict[tuple[str, str], Any] = {}
        for i in range(0, len(pairs), self.rpm_max):
            chunk = pairs[i : i + self.rpm_max]
            if self._rpm_ok:
                try:
                    data.update(await self._rpm(chunk))
                    continue
                except ErrorRejectAbortNack as e:
                    if "unrecognized" not in str(e.reason).lower():
                        raise PollError(f"ReadPropertyMultiple: {e}") from e
                    self.ctx.log.info("bacnet %s: RPM unsupported, switching to ReadProperty", self.source.code)
                    self._rpm_ok = False
            data.update(await self._read_each(chunk))
        return data

    async def _rpm(self, chunk: list[tuple[str, str]]) -> dict[tuple[str, str], Any]:
        assert self.bapp is not None
        grouped: dict[str, list[str]] = {}
        for obj, prop in chunk:
            grouped.setdefault(obj, []).append(prop)
        params: list[Any] = []
        for obj, props in grouped.items():
            params += [obj, props]
        try:
            res = await self.bapp._request(self, "read-property-multiple", self.addr, params)
        except TimeoutError:
            raise PollError(f"ReadPropertyMultiple timeout ({self.timeout_s} s)") from None
        out: dict[tuple[str, str], Any] = {}
        for (otype, inst), prop, idx, value in res:
            key = f"{otype},{inst}"
            name = str(prop) if idx is None else f"{prop}[{idx}]"
            out[(key, name)] = value
        return out

    async def _read_each(self, chunk: list[tuple[str, str]]) -> dict[tuple[str, str], Any]:
        assert self.bapp is not None
        out: dict[tuple[str, str], Any] = {}
        for obj, prop in chunk:
            try:
                out[(obj, prop)] = await self.bapp._request(self, "read-property", self.addr, obj, prop)
            except TimeoutError:
                raise PollError(f"ReadProperty timeout ({self.timeout_s} s)") from None
            except ErrorRejectAbortNack as e:
                out[(obj, prop)] = e
        return out

    # --- інтерпретація значень ---
    @staticmethod
    def _flags(value: Any) -> tuple[bool, bool]:
        """(fault_or_alarm, out_of_service)."""
        if value is None or _is_error(value):
            return False, False
        try:
            return bool(value["fault"]) or bool(value["in-alarm"]), bool(value["out-of-service"])
        except (KeyError, TypeError, IndexError, ValueError):
            return False, False

    def _reading(self, s: _Spec, data: dict, ts: Any) -> Reading:
        sg = s.sg
        a = sg.address
        raw = data.get((s.objid, s.prop_ref))
        if raw is None or _is_error(raw):
            return Reading(code=sg.code, ts=ts, q="bad")
        q = "good"
        if s.prop == "present-value":
            fault, oos = self._flags(data.get((s.objid, "status-flags")))
            if oos:
                q = "bad"
            elif fault:
                q = "uncertain"
            rel = data.get((s.objid, "reliability"))
            if (
                a.get("check_reliability")
                and rel is not None
                and not _is_error(rel)
                and str(rel) != "no-fault-detected"
            ):
                q = "bad"
            pa = data.get((s.objid, "priority-array"))
            if pa is not None and not _is_error(pa):
                self._pa_cache[s.objid] = pa
        if a.get("states"):
            return self._composite(s, data, ts, q)
        return self._make(s, raw, ts, q)

    def _make(self, s: _Spec, raw: Any, ts: Any, q: str) -> Reading:
        sg, a = s.sg, s.sg.address
        if sg.kind in ("gauge", "counter"):
            num = _num(raw)
            if num is None:
                return Reading(code=sg.code, ts=ts, q="bad")
            return Reading(code=sg.code, ts=ts, value=linear(num, a), q=q)
        text, tq = self._text(s, raw)
        if s.objtype in ("life-safety-zone", "life-safety-point"):
            self._state_cache[(s.objtype, s.instance)] = str(raw)
        return Reading(code=sg.code, ts=ts, text=text, q=q if tq == "good" else tq)

    @staticmethod
    def _text(s: _Spec, raw: Any) -> tuple[str, str]:
        sg, a = s.sg, s.sg.address
        amap: dict = a.get("map") or {}
        num = _num(raw)
        idx = None if num is None else int(num)
        if s.objtype in _MULTI and idx is not None:
            if str(idx) in amap:
                return str(amap[str(idx)]), "good"
            states = sg.states or []
            if 1 <= idx <= len(states):
                return str(states[idx - 1]), "good"
            return str(idx), "uncertain"
        if s.objtype in _BINARY and idx is not None:
            amap = amap or {"0": "off", "1": "on"}
            if str(idx) in amap:
                return str(amap[str(idx)]), "good"
            return str(idx), "uncertain"
        name = str(raw)
        if name in amap:
            return str(amap[name]), "good"
        if idx is not None and str(idx) in amap:
            return str(amap[str(idx)]), "good"
        return name, "good"

    def _composite(self, s: _Spec, data: dict, ts: Any, q: str) -> Reading:
        sg = s.sg
        for st in sg.address["states"]:
            key = (f"{normalize_object(str(st['object']))},{int(st['instance'])}", "present-value")
            val = data.get(key)
            if val is None or _is_error(val):
                continue
            eq = st["eq"]
            if str(val) == str(eq) or (
                _num(val) is not None and isinstance(eq, int | float) and _num(val) == float(eq)
            ):
                return Reading(code=sg.code, ts=ts, text=str(st["text"]), q=q)
        return Reading(code=sg.code, ts=ts, q="uncertain")

    # --- COV ---
    def _start_cov(self) -> None:
        for s in self._cov_signals():
            if s.sg.code not in self._cov_tasks:
                self._cov_tasks[s.sg.code] = asyncio.create_task(self._cov_loop(s))

    async def _cov_loop(self, s: _Spec) -> None:
        code = s.sg.code
        assert self.bapp is not None
        pid = zlib.crc32(code.encode()) % (1 << 22) or 1
        try:
            scm = await self.bapp._request(
                self, "subscribe-cov", self.addr, ObjectIdentifier(s.objid), pid, False, self.cov_lifetime_s
            )
        except (ErrorRejectAbortNack, TimeoutError, NotSupported, OSError, ValueError) as e:
            self._cov_fallback(code, f"SubscribeCOV rejected: {e}")
            return
        scm.create_refresh_task = lambda: None  # поновлення робимо самі, на 2/3 lifetime
        if scm.refresh_subscription_handle is not None:
            scm.refresh_subscription_handle.cancel()
        self._cov_active.add(code)
        self._gauge()
        pv: Any = None
        flags: Any = None
        renew_s = self.cov_lifetime_s * 2 / 3
        try:
            while True:
                try:
                    prop, value = await asyncio.wait_for(scm.get_value(), renew_s)
                except TimeoutError:
                    await asyncio.wait_for(scm.refresh_subscription(), self.timeout_s)
                    if scm.refresh_subscription_handle is not None:
                        scm.refresh_subscription_handle.cancel()
                    continue
                items = [(prop, value)]
                while not scm.queue.empty():
                    items.append(await scm.get_value())
                for prop, value in items:
                    if str(prop) == "present-value":
                        pv = value
                    elif str(prop) == "status-flags":
                        flags = value
                if pv is None:
                    continue
                self.stats["cov_notifications"] += 1
                self._last_ok = self.clock.monotonic()
                data = {(s.objid, s.prop_ref): pv, (s.objid, "status-flags"): flags}
                rd = self._reading(s, data, self.clock.now())
                self._last_read[code] = self.clock.monotonic()
                self.ctx.emit(rd)
        except (ErrorRejectAbortNack, TimeoutError, OSError) as e:
            self._cov_fallback(code, f"COV renewal failed: {e}")
        finally:
            self._cov_active.discard(code)
            self._gauge()
            with contextlib.suppress(BaseException):
                if not self.read_only:
                    await asyncio.wait_for(scm.__aexit__(None, None, None), 1.0)

    def _cov_fallback(self, code: str, why: str) -> None:
        self._cov_failed.add(code)
        self.ctx.log.warning("bacnet %s: %s — сигнал %s опитується з period_s", self.source.code, why, code)

    # --- події ---
    def handle_event(self, apdu: Any) -> None:
        """`UnconfirmedEventNotification` -> `bacnet_event` (SPEC §8.8)."""
        if not self.events or not self.source.read_enabled:
            self.ctx.metrics.bacnet_events_ignored.labels("disabled").inc()
            return
        try:
            payload = self._event_payload(apdu)
        except Exception:
            self.ctx.log.exception("bacnet event decode failed")
            return
        ts = self.clock.now()
        payload["ts"] = to_iso_z(ts)
        event_id = hashlib.sha256(f"bacnet_event\n{self.source.code}\n{canonical_json(payload)}".encode()).hexdigest()
        self.stats["events"] += 1
        self.ctx.metrics.bacnet_events.labels(self.source.code).inc()
        self.ctx.emit_event(
            PushEvent(
                event_id=event_id, route="bacnet_event", ts=ts, remote=self.source.code, headers={}, payload=payload
            )
        )

    def _event_payload(self, apdu: Any) -> dict[str, Any]:
        otype = str(apdu.eventObjectIdentifier[0])
        inst = int(apdu.eventObjectIdentifier[1])
        event_type = str(apdu.eventType)
        payload: dict[str, Any] = {
            "device": int(apdu.initiatingDeviceIdentifier[1]),
            "object": SHORT.get(otype, otype),
            "instance": inst,
            "event_type": event_type,
        }
        key = (otype, inst)
        if event_type == "change-of-life-safety":
            params = apdu.eventValues.changeOfLifeSafety
            to_state = str(params.newState)
            payload["from_state"] = self._state_cache.get(key) or str(apdu.fromState)
            payload["to_state"] = to_state
            payload["mode"] = str(params.newMode)
            self._state_cache[key] = to_state
        else:
            if getattr(apdu, "fromState", None) is not None:
                payload["from_state"] = str(apdu.fromState)
            payload["to_state"] = str(apdu.toState)
        msg = getattr(apdu, "messageText", None)
        payload["message_text"] = str(msg)[:MAX_MESSAGE] if msg is not None else ""
        payload["notification_class"] = int(apdu.notificationClass)
        payload["priority"] = int(apdu.priority)
        payload["ack_required"] = bool(apdu.ackRequired)
        return payload

    # --- запис ---
    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        if self.read_only:
            raise NotSupported("read-only device")
        if self.bapp is None or self.addr is None:
            raise WriteError("not connected")
        s = self._specs.get(signal.code) or self._spec(signal)
        a = signal.address
        prio = int(a.get("priority") or 8)
        pv: Any
        shown: str
        if text == "null" or (value is None and not text):
            pv, shown = Null(()), "null"
        elif text:
            n = self._state_number(s, text)
            pv = ("active" if n else "inactive") if s.objtype in _BINARY else n
            shown = str(n)
        else:
            assert value is not None
            if s.objtype in _MULTI or s.objtype == "positive-integer-value":
                pv = int(value)
                shown = str(pv)
            elif s.objtype in _BINARY:
                pv, shown = ("active" if value else "inactive"), str(int(bool(value)))
            else:
                pv, shown = float(value), str(float(value))
        try:
            await self.bapp._request(self, "write-property", self.addr, s.objid, s.prop_ref, pv, priority=prio)
        except TimeoutError:
            raise WriteError(f"WriteProperty timeout ({self.timeout_s} s)") from None
        except ErrorRejectAbortNack as e:
            raise WriteError(f"WriteProperty rejected: {e}") from e
        return f"written {shown} @prio {prio}"

    @staticmethod
    def _state_number(s: _Spec, text: str) -> int:
        amap: dict = s.sg.address.get("map") or {}
        for k, v in amap.items():
            if str(v) == text:
                return int(k)
        if not amap:
            if s.objtype in _MULTI and s.sg.states and text in s.sg.states:
                return s.sg.states.index(text) + 1
            if s.objtype in _BINARY and text in ("inactive", "active"):
                return 0 if text == "inactive" else 1
        raise WriteError(f"text «{text}» немає в map/states")

    # --- стан ---
    def health(self) -> Health:
        periods = [s.period_s for s in self.source.signals] or [10]
        window = 2 * max(periods)
        stats = {**self.stats, "latency_ms": self.latency.value}
        now = self.clock.monotonic()
        if self._last_error is not None and (self._last_ok is None or now - self._last_ok > window):
            return Health(state="offline", error=self._last_error, stats=stats)
        return Health(state="online", stats=stats)
