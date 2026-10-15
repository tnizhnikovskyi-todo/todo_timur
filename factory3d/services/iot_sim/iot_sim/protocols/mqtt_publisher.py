"""P-06: MQTT-телематика рухомої техніки (SPEC §8.8).

Дані беруться з ``World`` (сигнали ``equipment/<code>/{battery,hours,state,x,y}`` і необов'язкові
листи ``battery_v/speed_kmh/heading_deg/zone/task/load_kg/operator/odometer_km/charging``; решту
можна передати у ``world.flags["mobile"][code]``). Події ``charge_start/charge_end/low_battery/fault/
task_start/task_end`` виводяться зі змін стану. Періоди — у реальному часі (``clock``), не частіше 1 с.

ПРИПУЩЕННЯ: одне з'єднання з брокером; LWT ``{"online": false}`` — на ``<prefix>/mobile/_all/status``,
при штатній зупинці ``status`` кожного коду публікується з ``online=false`` явно.
Брокер недоступний: буфер 10 хв (``BUFFER_S``), старіше — втрата з лічильником ``dropped``.
"""
from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote, urlsplit

from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer

log = logging.getLogger("iot_sim.mqtt")

MOBILE_CODES = ("FL-1", "FL-2", "FL-3", "FL-4", "FL-5", "FL-C1", "FL-C2", "TUGGER-1")
BUFFER_S = 600.0
PERIOD_IDLE_S = 5.0
PERIOD_MOVING_S = 1.0
HEARTBEAT_S = 60.0
LOW_BATTERY_PCT = 20.0
FW = "1.4.2"
MODELS = {"FL-1": "Jungheinrich EFG 216", "FL-2": "Jungheinrich EFG 216", "FL-3": "Linde E20",
          "FL-4": "Linde E20", "FL-5": "Linde E25", "FL-C1": "Linde E16 C", "FL-C2": "Linde E16 C",
          "TUGGER-1": "Linde P50"}
OPTIONAL = {"battery_v": "battery_v", "speed_kmh": "speed_kmh", "heading_deg": "heading_deg",
            "zone": "zone", "task": "task", "load_kg": "load_kg", "operator": "operator",
            "odometer_km": "odometer_km", "charging": "charging"}


def parse_mqtt_url(url: str) -> dict[str, Any]:
    u = urlsplit(url)
    return {"host": u.hostname or "localhost", "port": u.port or (8883 if u.scheme == "mqtts" else 1883),
            "user": unquote(u.username) if u.username else None,
            "password": unquote(u.password) if u.password else None, "tls": u.scheme == "mqtts"}


def _make_client() -> Any:
    import paho.mqtt.client as mqtt
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="iot_sim")  # type: ignore[attr-defined]


class MqttPublisher(ProtocolServer):
    name = "mqtt"

    def __init__(self, world: World, *, url: str = "mqtt://localhost:1883", prefix: str = "f3d",
                 client_factory: Callable[[], Any] = _make_client,
                 clock: Callable[[], float] = time.monotonic, guard: Any = None) -> None:
        self.world, self.prefix, self.url = world, prefix.strip("/"), url
        self.conn = parse_mqtt_url(url)
        self.client = client_factory()
        self._clock = clock
        self.guard = guard
        self.connected = False
        self.dropped = 0
        self.published = 0
        self._buffer: deque[tuple[float, str, str, int, bool]] = deque()
        self._last_tel: dict[str, float] = {}
        self._last_state: dict[str, str] = {}
        self._last_online: dict[str, bool] = {}
        self._last_task: dict[str, Any] = {}
        self._low: dict[str, bool] = {}
        self._last_hb = -HEARTBEAT_S
        self._started = False
        self.codes = [c for c in MOBILE_CODES if c in world.devices]

    # --- життєвий цикл ----------------------------------------------------------------
    def topic(self, code: str, leaf: str) -> str:
        return f"{self.prefix}/mobile/{code}/{leaf}"

    async def start(self) -> None:
        c = self.client
        if self.conn["user"]:
            c.username_pw_set(self.conn["user"], self.conn["password"])
        c.will_set(self.topic("_all", "status"), json.dumps({"online": False}), qos=1, retain=True)
        c.on_connect = self._on_connect
        c.on_disconnect = self._on_disconnect
        if self.guard is not None:
            self.guard.check(self.conn["host"])
        c.reconnect_delay_set(min_delay=1, max_delay=30)
        c.connect_async(self.conn["host"], self.conn["port"], keepalive=30)
        c.loop_start()
        self._started = True
        self.world.on_tick(self._on_tick)

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        if self.connected:
            for code in self.codes:
                self._publish(self.topic(code, "status"), self._status(code, online=False), 1, True)
        try:
            self.client.disconnect()
        finally:
            self.client.loop_stop()
        self.connected = False

    def health(self) -> dict[str, Any]:
        return {"proto": self.name, "up": self._started, "connected": self.connected,
                "buffered": len(self._buffer), "dropped": self.dropped, "published": self.published}

    # --- paho-колбеки (потік paho) ------------------------------------------------------
    def _on_connect(self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any=None) -> None:
        if getattr(reason_code, "is_failure", False) or (isinstance(reason_code, int) and reason_code):
            log.warning("mqtt connect refused: %s", reason_code, extra={"proto": "mqtt"})
            return
        self.connected = True
        log.info("mqtt connected", extra={"proto": "mqtt"})
        for code in self.codes:  # retain-статус відновлюється при reconnect
            self._send(self.topic(code, "status"), self._status(code, online=True), 1, True)
        self._flush()

    def _on_disconnect(self, client: Any, userdata: Any, *args: Any) -> None:
        self.connected = False
        log.warning("mqtt disconnected", extra={"proto": "mqtt"})

    # --- публікація ---------------------------------------------------------------------
    def _publish(self, topic: str, payload: str, qos: int, retain: bool) -> None:
        if self.connected and not self._buffer:
            self._send(topic, payload, qos, retain)
            return
        now = self._clock()
        self._buffer.append((now, topic, payload, qos, retain))
        while self._buffer and now - self._buffer[0][0] > BUFFER_S:
            self._buffer.popleft()
            self.dropped += 1

    def _send(self, topic: str, payload: str, qos: int, retain: bool) -> None:
        self.client.publish(topic, payload, qos=qos, retain=retain)
        self.published += 1

    def _flush(self) -> None:
        now = self._clock()
        while self._buffer:
            ts, topic, payload, qos, retain = self._buffer.popleft()
            if now - ts > BUFFER_S:
                self.dropped += 1
                continue
            self._send(topic, payload, qos, retain)

    # --- дані ---------------------------------------------------------------------------
    def _sig(self, code: str, leaf: str) -> Any:
        s = self.world.devices[code].signals.get(leaf)
        return None if s is None else s.value

    def _status(self, code: str, online: bool) -> str:
        return json.dumps({"code": code, "online": online, "ts": self.world.now().isoformat(),
                           "fw": FW, "model": MODELS.get(code, ""), "gateway": "sim"},
                          ensure_ascii=False)

    def telemetry(self, code: str) -> dict[str, Any]:
        dev = self.world.devices[code]
        extra = (self.world.flags.get("mobile") or {}).get(code, {})
        state = str(self._sig(code, "state") or "idle")
        mstate = getattr(getattr(dev, "model", None), "mstate", None)
        if state == "busy" and mstate == "to_charge":  # сигнал віддає to_charge як busy (§8.8.1)
            state = mstate
        if dev.fault and dev.fault != "comm":
            state = "fault"
        elif dev.fault == "comm":
            state = "offline"
        d: dict[str, Any] = {
            "ts": self.world.now().isoformat(), "code": code, "state": state,
            "battery_pct": round(float(self._sig(code, "battery") or 0.0), 1),
            "hours": round(float(self._sig(code, "hours") or 0.0), 1),
            "x": round(float(self._sig(code, "x") or 0.0), 1),
            "y": round(float(self._sig(code, "y") or 0.0), 1)}
        for key, leaf in OPTIONAL.items():
            v = self._sig(code, leaf)
            if v is None:
                v = extra.get(key)
            if v is not None:
                d[key] = round(v, 1) if isinstance(v, float) else v
        if "charging" not in d:
            d["charging"] = state == "charging"
        d.setdefault("speed_kmh", 0.0)
        d["faults"] = [dev.fault] if dev.fault else []
        return d

    def _event(self, code: str, typ: str, detail: dict[str, Any] | None = None) -> None:
        self._publish(self.topic(code, "event"),
                      json.dumps({"ts": self.world.now().isoformat(), "code": code, "type": typ,
                                  "detail": detail or {}}, ensure_ascii=False), 1, False)

    def _on_tick(self, world: World) -> None:
        self.tick()

    def tick(self) -> None:
        now = self._clock()
        online = []
        for code in self.codes:
            tel = self.telemetry(code)
            if tel["state"] != "offline":
                online.append(code)
            prev = self._last_state.get(code)
            changed = prev is not None and prev != tel["state"]
            if changed:
                self._derive_events(code, prev, tel)  # type: ignore[arg-type]
            self._last_state[code] = tel["state"]
            is_on = tel["state"] != "offline"
            if self._last_online.get(code, True) != is_on:  # §8.8.1: status — «при з'єднанні/зміні» (AC-40)
                self._publish(self.topic(code, "status"), self._status(code, online=is_on), 1, True)
            self._last_online[code] = is_on
            moving = tel.get("speed_kmh", 0.0) > 0
            period = PERIOD_MOVING_S if moving else PERIOD_IDLE_S
            if changed or code not in self._last_tel or now - self._last_tel[code] >= period:
                self._last_tel[code] = now
                self._publish(self.topic(code, "telemetry"), json.dumps(tel, ensure_ascii=False), 1, False)
            self._task_events(code, tel)
            low = tel["battery_pct"] < LOW_BATTERY_PCT
            if low and not self._low.get(code):
                self._event(code, "low_battery", {"battery_pct": tel["battery_pct"]})
            self._low[code] = low
        if now - self._last_hb >= HEARTBEAT_S:
            self._last_hb = now
            self._publish(f"{self.prefix}/mobile/_all/heartbeat",
                          json.dumps({"ts": self.world.now().isoformat(), "online": online}), 0, False)

    def _derive_events(self, code: str, prev: str, tel: dict[str, Any]) -> None:
        new = tel["state"]
        if new == "charging":
            self._event(code, "charge_start", {"battery_pct": tel["battery_pct"]})
        elif prev == "charging":
            self._event(code, "charge_end", {"battery_pct": tel["battery_pct"]})
        if new == "fault":
            self._event(code, "fault", {"faults": tel["faults"]})

    def _task_events(self, code: str, tel: dict[str, Any]) -> None:
        task = tel.get("task")
        prev = self._last_task.get(code)
        if task != prev:
            if prev:
                self._event(code, "task_end", {"task": prev})
            if task:
                self._event(code, "task_start", {"task": task})
        self._last_task[code] = task
