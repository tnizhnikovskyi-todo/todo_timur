"""AC-73: обрив сервера -> q=bad, offline, переп'єднання з бекофом і відновленням підписок."""

from __future__ import annotations

import asyncio

from conftest import until

CODE = "workcenters/SAW-T/state"


def last(ctx, code: str = CODE):
    found = [r for r in ctx.emitted if r.code == code]
    return found[-1] if found else None


async def test_server_down_bad_quality(ctx, ua_server, opcua_plugin, vclock):
    await until(lambda: last(ctx))
    await ua_server.stop()
    await until(lambda: last(ctx).q == "bad", timeout=10, clock=vclock, step=5)
    reading = last(ctx)
    assert reading.text == "bad" and reading.value is None
    assert opcua_plugin.health().state == "offline"
    # лічильники при обриві — пропуск, а не bad-показання
    assert all(r.code != "workcenters/SAW-T/pieces_out" or r.q == "good" for r in ctx.emitted)


async def test_reconnect_resubscribe(ctx, ua_server, opcua_plugin, vclock):
    await until(lambda: last(ctx))
    await ua_server.stop()
    await until(lambda: last(ctx).q == "bad", timeout=10, clock=vclock, step=5)
    await ua_server.start()
    await until(lambda: opcua_plugin.health().state == "online", timeout=20, clock=vclock, step=5)
    await until(lambda: last(ctx).q == "good")
    await ua_server.set("CurrentState", 2)
    await until(lambda: last(ctx).text == "READY", timeout=3)
    assert (
        ctx.metrics.registry.get_sample_value("collector_mc_opcua_reconnects_total", {"endpoint": ua_server.endpoint})
        == 1
    )


async def test_backoff_sequence(ctx, ua_server, opcua_plugin, vclock):
    await until(lambda: last(ctx))
    await ua_server.stop()
    await asyncio.sleep(2)  # клієнт asyncua помічає обрив (його власний нагляд, реальний час)
    vclock.sleeps.clear()
    await vclock.tick(5)  # наш нагляд (5 с) бачить обрив і починає переп'єднання
    await until(lambda: opcua_plugin.health().state == "offline")

    def backoffs() -> list[float]:
        return [s for s in vclock.sleeps if s != 5.0]

    # сервер лежить: бекоф 1, 2, 4, … 60 с (нагляд — 5 с, його тут не рахуємо)
    for k in range(8):
        await until(lambda k=k: len(backoffs()) > k, timeout=10)
        await vclock.tick(61)
    assert backoffs()[:8] == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]


async def test_secure_connect_failure_names_server_certificate(make_opcua, monkeypatch):
    """Стенд ТБ-07: при SignAndEncrypt і чужому сертифікаті asyncua дає лише TimeoutError — у помилці джерела має бути
    підказка про закріплений сертифікат сервера (без секретів)."""
    import pytest
    from collector.core.errors import ConnectError
    from f3d_collector_mc import ua_session

    async def no_security(self, client):
        return None

    async def boom(self, *a, **kw):
        raise TimeoutError("")

    monkeypatch.setattr(ua_session.Session, "_configure_security", no_security)
    monkeypatch.setattr(ua_session.Client, "connect", boom)
    plugin = make_opcua("SAW-T", security_mode="SignAndEncrypt", security_policy="Basic256Sha256")
    with pytest.raises(ConnectError, match="server certificate"):
        await plugin.connect()
    plain = make_opcua("SAW-T2", security_mode="None")
    with pytest.raises(ConnectError) as ei:
        await plain.connect()
    assert "server certificate" not in str(ei.value)
