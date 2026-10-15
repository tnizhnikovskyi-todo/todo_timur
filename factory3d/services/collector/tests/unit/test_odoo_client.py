"""AC-73: клієнт Odoo і Pusher."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from conftest import T0, TOKEN

from collector.core.metrics import Metrics
from collector.core.odoo_client import OdooClient, Pusher, StatusReporter
from collector.core.types import Health, Reading


class StubRegistry:
    def __init__(self, etag="etag-1"):
        self.etag = etag
        self.refreshed = 0
        self.errors: dict = {}
        self.plugins: dict = {}
        self.sources: dict = {}
        self.write_enabled = True

    async def refresh(self):
        self.refreshed += 1
        return True


@pytest_asyncio.fixture
async def client(fake_odoo, vclock):
    metrics = Metrics(vclock)
    c = OdooClient(fake_odoo.url, TOKEN, collector="COL-T", clock=vclock, metrics=metrics)
    c.test_metrics = metrics  # type: ignore[attr-defined]
    yield c
    await c.close()


@pytest.fixture
def pusher(client, buffer, vclock):
    return Pusher(
        client,
        buffer,
        push_max=100,
        push_interval_s=5,
        registry=StubRegistry(),
        metrics=client.test_metrics,
        clock=vclock,
    )


async def _fill(buffer, n=3):
    await buffer.put_many([Reading(f"equipment/A/c{i}", T0, value=float(i)) for i in range(n)])


def _pushes(fake_odoo):
    return [c for c in fake_odoo.calls if c[1].endswith("/push")]


async def test_push_200_ack(fake_odoo, pusher, buffer):
    await _fill(buffer)
    assert await pusher.push_once() == "ok"
    assert await buffer.count() == 0
    body = _pushes(fake_odoo)[0][2]
    assert body["collector"] == "COL-T" and len(body["readings"]) == 3
    assert body["readings"][0]["ts"] == "2026-10-14T06:00:00Z"
    assert pusher.client.test_metrics.registry.get_sample_value("collector_push_total", {"status": "ok"}) == 1


async def test_push_423_keep_pause(fake_odoo, pusher, buffer):
    seen = []

    async def cb(v):
        seen.append(v)

    pusher.on_read_enabled = cb
    await _fill(buffer)
    fake_odoo.push_status = [423]
    assert await pusher.push_once() == "locked"
    assert await buffer.count() == 3
    assert pusher.read_enabled is False and seen == [False]


async def test_push_429_retry_after(fake_odoo, pusher, buffer, vclock):
    await _fill(buffer)
    fake_odoo.push_status = [429]
    fake_odoo.push_headers = {"Retry-After": "10"}
    assert await pusher.push_once() == "retry"
    assert await buffer.count() == 3
    vclock.advance(9)
    assert await pusher.push_once() == "wait"
    vclock.advance(1.5)
    assert await pusher.push_once() == "ok"
    assert len(_pushes(fake_odoo)) == 2


async def test_push_400_drop(fake_odoo, pusher, buffer, caplog):
    await _fill(buffer)
    fake_odoo.push_status = [400]
    with caplog.at_level(logging.ERROR):
        assert await pusher.push_once() == "rejected"
    assert await buffer.count() == 0
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert pusher.client.test_metrics.registry.get_sample_value("collector_push_rejected_total") == 1


async def test_push_503_backoff(fake_odoo, pusher, buffer, vclock):
    await _fill(buffer)
    fake_odoo.push_status = [503] * 9
    for expected in (1, 2, 4):
        assert await pusher.push_once() == "retry"
        assert await buffer.count() == 3
        assert pusher.retry_at - vclock.monotonic() == pytest.approx(expected)
        vclock.advance(expected)
    assert len(_pushes(fake_odoo)) == 9  # 3 спроби клієнта на кожен цикл


async def test_push_401_kept(fake_odoo, client, buffer, vclock):
    bad = OdooClient(fake_odoo.url, "x" * 40, collector="COL-T", clock=vclock)
    p = Pusher(bad, buffer, clock=vclock)
    await _fill(buffer)
    assert await p.push_once() == "retry"
    assert await buffer.count() == 3
    await bad.close()


async def test_config_etag_refresh(fake_odoo, pusher, buffer):
    await _fill(buffer)
    fake_odoo.push_extra = {
        "config_etag": "etag-NEW",
        "rejected": [{"i": 0, "code": "a", "reason": "unknown_code"}, {"i": 1, "code": "b", "reason": "unknown_code"}],
    }
    assert await pusher.push_once() == "ok"
    assert pusher.registry.refreshed == 1


async def test_config_304_and_etag_header(fake_odoo, client):
    data = await client.config(None)
    assert data is not None and data["config_etag"] == "etag-1"
    assert await client.config("etag-1") is None
    assert (await client.config("other")) is not None


async def test_clock_skew_warning(fake_odoo, pusher, buffer, vclock, caplog):
    vclock.now = lambda: datetime.now(UTC)  # type: ignore[method-assign]
    fake_odoo.time_offset_s = 45
    await _fill(buffer)
    with caplog.at_level(logging.WARNING):
        await pusher.push_once()
    assert "clock skew" in caplog.text
    skew = pusher.client.test_metrics.registry.get_sample_value("collector_clock_skew_seconds")
    assert skew == pytest.approx(45, abs=2)


async def test_status_payload(fake_odoo, client, buffer, vclock):
    class P:
        type = "fake"
        version = "0.1.0"
        push_mode = True

        def health(self):
            return Health(state="online", stats={"messages": 3})

    reg = StubRegistry()
    reg.plugins = {"S": P()}
    reg.sources = {"S": object(), "E": object()}
    reg.errors = {"E": Health(state="error", error="plugin x not installed")}
    sr = StatusReporter(client, reg, buffer, None, clock=vclock)
    assert await sr.send_once() is not None
    body = next(c for c in fake_odoo.calls if c[1].endswith("/status"))[2]
    assert body["collector"] == "COL-T"
    assert {s["code"]: s["state"] for s in body["sources"]} == {"S": "online", "E": "error"}
    assert body["plugins"] == [{"type": "fake", "version": "0.1.0", "sources": 1}]
    assert body["buffer"]["rows"] == 0
