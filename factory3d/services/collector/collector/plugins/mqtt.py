"""Плагін `mqtt` (SPEC §8.6, R-21): підписка paho у власному потоці, черга -> корутина-споживач."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Sequence
from typing import Any, ClassVar

import paho.mqtt.client as mqtt

from collector.core.errors import ConnectError, NotSupported, WriteError
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins._common import ctx_clock, linear, load_schema, parse_ts, validate_source
from collector.plugins.base import PluginContext, SourcePlugin
from collector.util import jsonpath

WARN_EVERY_S = 60.0
_OFFLINE_WORDS = {"offline", "false", "0", "down"}
_ABSENT: Any = object()  # маркер «немає значення» (jsonpath.MISSING як default кидає KeyError)
_ONLINE_WORDS = {"online", "true", "1", "up"}


def topic_matches(sub: str, topic: str) -> bool:
    """MQTT-фільтр `sub` (з `+`/`#`) відповідає імені топіка `topic`."""
    sl, tl = sub.split("/"), topic.split("/")
    for i, part in enumerate(sl):
        if part == "#":
            return i == len(sl) - 1
        if i >= len(tl):
            return False
        if part != "+" and part != tl[i]:
            return False
    return len(sl) == len(tl)


def _rc(reason_code: Any) -> int:
    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0 if value in (None, "Success") else 1


def _fmt_num(value: float) -> str:
    return str(int(value)) if float(value) == int(value) else repr(float(value))


class MqttPlugin(SourcePlugin):
    type: ClassVar[str] = "mqtt"
    push_mode: ClassVar[bool] = True
    address_schema: ClassVar[dict] = load_schema("address.mqtt")
    params_schema: ClassVar[dict] = load_schema("params.mqtt")

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        super().__init__(source, ctx)
        self.clock = ctx_clock(ctx)
        p = source.params
        self.host: str = p.get("host", "")
        self.port: int = int(p.get("port", 1883))
        self.topics: list[str] = list(p.get("topics", []))
        self.qos: int = int(p.get("qos", 1))
        self.status_topic: str | None = p.get("status_topic")
        self.status_path: str = p.get("status_online_path", "$.online")
        self.client: Any = None
        self.queue: asyncio.Queue = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._state = "offline"
        self._error: str | None = None
        self._offline_devices: set[str] = set()
        self._warned: dict[str, float] = {}
        self.stats = {"messages": 0, "readings": 0}
        self._index: dict[str, list[SignalCfg]] = {}
        for sg in source.signals:
            topic = (sg.address or {}).get("topic")
            if topic:
                self._index.setdefault(topic, []).append(sg)

    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        return validate_source(source, cls.address_schema, cls.params_schema, params_check=cls._check_params)

    @staticmethod
    def _check_params(params: dict) -> list[str]:
        errs = []
        for t in params.get("topics", []) if isinstance(params.get("topics"), list) else []:
            levels = str(t).split("/")
            if any("#" in lv and lv != "#" for lv in levels) or "#" in levels[:-1]:
                errs.append(f"topics: «{t}» — `#` лише останнім рівнем")
            if any("+" in lv and lv != "+" for lv in levels):
                errs.append(f"topics: «{t}» — `+` має бути цілим рівнем")
        return errs

    # --- з'єднання ---
    async def connect(self) -> None:
        self.ctx.allowlist(self.host)
        p = self.source.params
        self._loop = asyncio.get_running_loop()
        client_id = f"{p.get('client_id', 'f3d')}-{getattr(self.ctx.settings, 'collector_code', 'col')}"
        c = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, protocol=mqtt.MQTTv311, clean_session=False
        )
        if p.get("username"):
            password = None
            if p.get("password_ref"):
                try:
                    password = self.ctx.secrets(p["password_ref"])
                except KeyError:
                    raise ConnectError(f"secret {p['password_ref']} is not set") from None
            c.username_pw_set(p["username"], password)
        if p.get("tls"):
            c.tls_set()
        c.reconnect_delay_set(1, 60)
        c.on_connect = self._on_connect
        c.on_disconnect = self._on_disconnect
        c.on_message = self._on_message
        self.client = c
        try:
            c.connect_async(self.host, self.port, int(p.get("keepalive_s", 30)))
            c.loop_start()
        except (OSError, ValueError) as e:
            raise ConnectError(f"mqtt {self.host}:{self.port}: {e}") from e

    async def subscribe(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._consumer())

    async def disconnect(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self.client is not None:
            with contextlib.suppress(Exception):
                self.client.loop_stop()
                self.client.disconnect()
            self.client = None
        self._state = "offline"

    # --- колбеки paho (потік paho) ---
    def _filters(self) -> list[tuple[str, int]]:
        subs = [(t, self.qos) for t in self.topics]
        if self.status_topic:
            flt = self.status_topic.replace("{device}", "+")
            if flt not in self.topics:
                subs.append((flt, self.qos))
        return subs

    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
        rc = _rc(reason_code)
        if rc != 0:
            self._state, self._error = "error", f"mqtt connect refused: {reason_code}"
            return
        self._state, self._error = "online", None
        client.subscribe(self._filters())

    def _on_disconnect(self, client: Any, userdata: Any, *args: Any) -> None:
        self._state = "offline"
        self._error = "mqtt broker disconnected"

    def _on_message(self, client: Any, userdata: Any, msg: Any) -> None:
        if self._loop is None:
            return
        item = (str(msg.topic), bytes(msg.payload), bool(msg.retain))
        with contextlib.suppress(RuntimeError):  # цикл закрито
            self._loop.call_soon_threadsafe(self.queue.put_nowait, item)

    # --- споживач ---
    async def _consumer(self) -> None:
        while True:
            topic, payload, retain = await self.queue.get()
            try:
                self.handle(topic, payload, retain)
            except Exception:
                self.ctx.log.exception("mqtt message on %s failed", topic)

    def _warn_once(self, key: str, msg: str, *args: Any) -> None:
        now = self.clock.monotonic()
        if now - self._warned.get(key, -WARN_EVERY_S) >= WARN_EVERY_S:
            self._warned[key] = now
            self.ctx.log.warning(msg, *args)

    def handle(self, topic: str, payload: bytes, retain: bool) -> None:
        """Опрацювати одне повідомлення (синхронно; викликає споживач)."""
        self.stats["messages"] += 1
        self.ctx.metrics.mqtt_messages.labels(self.source.code).inc()
        received = self.clock.now()
        try:
            obj: Any = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            obj = _ABSENT
        if self.status_topic and topic_matches(self.status_topic.replace("{device}", "+"), topic):
            self._handle_status(topic, payload, obj)
        for sg in self._index.get(topic, []):
            if obj is _ABSENT:
                self._warn_once(f"badjson:{topic}", "mqtt %s: payload is not JSON", topic)
                self._emit(Reading(code=sg.code, ts=received, value=None, text=None, q="bad"))
                continue
            self._signal(sg, obj, received, retain)

    def _handle_status(self, topic: str, payload: bytes, obj: Any) -> None:
        assert self.status_topic
        sl, tl = self.status_topic.split("/"), topic.split("/")
        device = next((tl[i] for i, lv in enumerate(sl) if lv == "{device}" and i < len(tl)), None)
        if device is None:
            return
        online: Any
        if obj is _ABSENT:
            word = payload.decode("utf-8", "replace").strip().lower()
            online = False if word in _OFFLINE_WORDS else True if word in _ONLINE_WORDS else None
        else:
            online = jsonpath.get(self.status_path, obj, None)
            if isinstance(online, str):
                online = (
                    False if online.lower() in _OFFLINE_WORDS else True if online.lower() in _ONLINE_WORDS else None
                )
        if online is False:
            self._offline_devices.add(device)
        elif online is True:
            self._offline_devices.discard(device)

    def _signal(self, sg: SignalCfg, obj: Any, received: Any, retain: bool) -> None:
        a = sg.address
        val = jsonpath.get(a["path"], obj, _ABSENT)
        if val is _ABSENT:
            self.ctx.metrics.mqtt_missing_path.labels(self.source.code).inc()
            return
        if val is None:
            return
        ts = received
        if a.get("ts_path") and not retain:
            raw_ts = jsonpath.get(a["ts_path"], obj, None)
            if raw_ts is not None:
                try:
                    ts = parse_ts(raw_ts)
                except (ValueError, OverflowError, OSError):
                    self._warn_once(f"ts:{sg.code}", "mqtt %s: bad ts %r", sg.code, raw_ts)
        q = "uncertain" if retain else "good"
        if sg.kind in ("gauge", "counter"):
            if isinstance(val, (bool, int | float)):
                num = float(val)
            elif isinstance(val, str):
                try:
                    num = float(val)
                except ValueError:
                    self._warn_once(f"nan:{sg.code}", "mqtt %s: not a number %r", sg.code, val)
                    return
            else:
                return
            self._emit(Reading(code=sg.code, ts=ts, value=linear(num, a), q=q))
            return
        key = ("true" if val else "false") if isinstance(val, bool) else str(val)
        text = str((a.get("map") or {}).get(key, key))[:64]
        self._emit(Reading(code=sg.code, ts=ts, text=text, q=q))

    def _emit(self, r: Reading) -> None:
        self.stats["readings"] += 1
        self.ctx.emit(r)

    # --- запис ---
    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        raise NotSupported("poll")

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        w = (signal.address or {}).get("write")
        if not w:
            raise NotSupported("write")
        if self.client is None or self._state != "online":
            raise WriteError("mqtt broker is not connected")
        body = str(w["template"])
        body = body.replace("{text}", json.dumps(text or "", ensure_ascii=False)[1:-1])
        body = body.replace("{value}", _fmt_num(value) if value is not None else "null")
        try:
            info = self.client.publish(w["topic"], body, qos=1)
        except (OSError, ValueError) as e:
            raise WriteError(f"publish failed: {e}") from e
        rc = getattr(info, "rc", 0)
        if rc not in (0, None):
            raise WriteError(f"publish failed: rc={rc}")
        return f"published {w['topic']}"

    # --- стан ---
    def health(self) -> Health:
        stats = {**self.stats, "offline_devices": sorted(self._offline_devices)}
        return Health(state=self._state, error=self._error, stats=stats)
