"""AC-83: імена метрик §8.9, /health, degraded."""
from __future__ import annotations

from aiohttp.test_utils import TestClient, TestServer

from collector.core.metrics import Metrics, MetricsServer

NAMES = ["collector_up", "collector_config_etag_info", "collector_readings_total", "collector_readings_rejected_total", "collector_push_total", "collector_push_latency_seconds", "collector_buffer_rows", "collector_buffer_dropped_total", "collector_source_up", "collector_poll_seconds", "collector_poll_errors_total", "collector_poll_overrun_total", "collector_mqtt_messages_total", "collector_mqtt_missing_path_total", "collector_http_push_requests_total", "collector_bacnet_cov_active", "collector_bacnet_events_total", "collector_bacnet_events_ignored_total", "collector_bacnet_ro_blocked_total", "collector_modbus_pulse_reset_failed_total", "collector_commands_total", "collector_clock_skew_seconds", "collector_push_rejected_total", "collector_allowlist_denied_total"]


def test_metric_names(vclock):
    text = Metrics(vclock).render().decode()
    for name in NAMES:
        assert name in text, name


def test_health_degraded(vclock):
    m = Metrics(vclock)
    assert m.health(3) == {"status": "ok", "odoo": "ok", "buffer_rows": 3, "sources": {"online": 0, "error": 0}}
    m.odoo_failed()
    vclock.advance(299)
    assert m.health()["status"] == "ok" and m.health()["odoo"] == "unreachable"
    vclock.advance(2)
    assert m.health()["status"] == "degraded"
    m.odoo_ok()
    assert m.health()["status"] == "ok"
    m.set_source("S", "modbus_tcp", "error")
    vclock.advance(601)
    assert m.health()["status"] == "degraded" and m.health()["sources"] == {"online": 0, "error": 1}
    m.set_source("S", "modbus_tcp", "online")
    assert m.health()["status"] == "ok"


async def test_http_endpoints(vclock):
    m = Metrics(vclock)
    srv = MetricsServer(m, 0, rows=lambda: 7)
    async with TestClient(TestServer(srv.app)) as c:
        r = await c.get("/health")
        body = await r.json()
        assert r.status == 200 and set(body) == {"status", "odoo", "buffer_rows", "sources"} and body["buffer_rows"] == 7
        r = await c.get("/metrics")
        assert r.status == 200 and "collector_up" in await r.text()
