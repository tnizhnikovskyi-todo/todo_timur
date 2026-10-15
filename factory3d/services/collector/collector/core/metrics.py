"""Метрики Prometheus і HTTP :9108 (/metrics, /health), SPEC §8.9."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from aiohttp import web
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from collector.util.timeutil import Clock, SystemClock

log = logging.getLogger("collector.metrics")

ODOO_DEGRADED_S = 300.0
SOURCE_DEGRADED_S = 600.0


class Metrics:
    def __init__(self, clock: Clock | None = None, registry: CollectorRegistry | None = None) -> None:
        self.clock: Clock = clock or SystemClock()
        self.registry = registry or CollectorRegistry()
        r = self.registry
        self.up = Gauge("collector_up", "Колектор працює", registry=r)
        self.config_etag_info = Gauge("collector_config_etag_info", "Поточний etag конфігурації", ["etag"], registry=r)
        self.readings = Counter("collector_readings", "Показання в буфері", ["source"], registry=r)
        self.readings_rejected = Counter("collector_readings_rejected", "Відхилені показання", ["reason"], registry=r)
        self.push = Counter("collector_push", "Пакети API-02", ["status"], registry=r)
        self.push_rejected = Counter("collector_push_rejected", "Пакети, відкинуті з 4xx", registry=r)
        self.push_latency = Histogram("collector_push_latency_seconds", "Тривалість push", registry=r)
        self.buffer_rows = Gauge("collector_buffer_rows", "Рядків у буфері", registry=r)
        self.buffer_dropped = Counter("collector_buffer_dropped", "Викинуті лімітом буфера", registry=r)
        self.source_up = Gauge("collector_source_up", "Джерело онлайн", ["source", "type"], registry=r)
        self.poll_seconds = Histogram("collector_poll_seconds", "Тривалість poll", ["source"], registry=r)
        self.poll_errors = Counter("collector_poll_errors", "Помилки poll", ["source"], registry=r)
        self.poll_overrun = Counter("collector_poll_overrun", "poll довший за період", ["source"], registry=r)
        self.mqtt_messages = Counter("collector_mqtt_messages", "MQTT-повідомлення", ["source"], registry=r)
        self.mqtt_missing_path = Counter("collector_mqtt_missing_path", "Відсутній jsonpath", ["source"], registry=r)
        self.http_push_requests = Counter(
            "collector_http_push_requests", "Запити http_push", ["route", "status"], registry=r
        )
        self.bacnet_cov_active = Gauge("collector_bacnet_cov_active", "Активні COV-підписки", ["source"], registry=r)
        self.bacnet_events = Counter("collector_bacnet_events", "BACnet-події", ["source"], registry=r)
        self.bacnet_events_ignored = Counter(
            "collector_bacnet_events_ignored", "Проігноровані BACnet-події", ["reason"], registry=r
        )
        self.bacnet_ro_blocked = Counter(
            "collector_bacnet_ro_blocked", "Заблоковані сервіси read_only", ["source", "service"], registry=r
        )
        self.modbus_pulse_reset_failed = Counter(
            "collector_modbus_pulse_reset_failed", "Невдале скидання імпульсу", ["source"], registry=r
        )
        self.commands = Counter("collector_commands", "Команди за станом", ["state"], registry=r)
        self.clock_skew = Gauge("collector_clock_skew_seconds", "Розходження годинників з Odoo", registry=r)
        self.allowlist_denied = Counter("collector_allowlist_denied", "Відмови allow-list", registry=r)
        # плагін sics (factory3d_yard §8.8): лише оголошення, лічильники збільшує плагін через getattr
        sics_labels = ["type", "source"]
        self.collector_sics_frames_total = Counter("collector_sics_frames", "Кадри SICS", sics_labels, registry=r)
        self.collector_sics_reconnects_total = Counter(
            "collector_sics_reconnects", "Перепідключення SICS", sics_labels, registry=r
        )
        self.collector_sics_errors_total = Counter(
            "collector_sics_errors", "Помилки SICS", [*sics_labels, "kind"], registry=r
        )
        # стан для /health
        self._odoo_fail_since: float | None = None
        self._source_error_since: dict[str, float] = {}
        self._source_state: dict[str, str] = {}

    # --- Odoo/джерела (для /health) ---
    def odoo_ok(self) -> None:
        self._odoo_fail_since = None

    def odoo_failed(self) -> None:
        if self._odoo_fail_since is None:
            self._odoo_fail_since = self.clock.monotonic()

    def set_source(self, source: str, type_: str, state: str) -> None:
        self.source_up.labels(source, type_).set(1 if state == "online" else 0)
        self._source_state[source] = state
        if state == "error":
            self._source_error_since.setdefault(source, self.clock.monotonic())
        else:
            self._source_error_since.pop(source, None)

    def forget_source(self, source: str) -> None:
        self._source_state.pop(source, None)
        self._source_error_since.pop(source, None)

    def health(self, buffer_rows: int = 0) -> dict[str, Any]:
        now = self.clock.monotonic()
        since = self._odoo_fail_since
        odoo_down = since is not None
        degraded = since is not None and now - since > ODOO_DEGRADED_S
        degraded = degraded or any(now - t > SOURCE_DEGRADED_S for t in self._source_error_since.values())
        states = list(self._source_state.values())
        return {
            "status": "degraded" if degraded else "ok",
            "odoo": "unreachable" if odoo_down else "ok",
            "buffer_rows": buffer_rows,
            "sources": {"online": states.count("online"), "error": states.count("error")},
        }

    def render(self) -> bytes:
        return generate_latest(self.registry)


class MetricsServer:
    """aiohttp-сервер `/metrics` і `/health`."""

    def __init__(
        self, metrics: Metrics, port: int = 9108, rows: Callable[[], int] | None = None, host: str = "0.0.0.0"
    ) -> None:
        self.metrics = metrics
        self.port = port
        self.host = host
        self.rows = rows or (lambda: 0)
        self._runner: web.AppRunner | None = None
        self.app = web.Application()
        self.app.router.add_get("/metrics", self._metrics)
        self.app.router.add_get("/health", self._health)

    async def _metrics(self, request: web.Request) -> web.Response:
        return web.Response(body=self.metrics.render(), content_type="text/plain", charset="utf-8")

    async def _health(self, request: web.Request) -> web.Response:
        return web.json_response(self.metrics.health(self.rows()))

    async def start(self) -> int:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        server = site._server
        sockets = getattr(server, "sockets", None) or []
        if sockets:
            self.port = int(sockets[0].getsockname()[1])
        return self.port

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
