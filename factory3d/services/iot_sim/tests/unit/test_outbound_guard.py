import socket
from types import SimpleNamespace

import pytest

from iot_sim.core.outbound import OutboundDenied, OutboundGuard


@pytest.fixture
def fake_conn(monkeypatch):
    calls = []
    monkeypatch.setattr(socket, "create_connection", lambda addr, *a, **k: calls.append(addr) or "sock")
    return calls


def test_denied_host(fake_conn):
    denied = []
    g = OutboundGuard("mosquitto", on_denied=denied.append)
    g.install()
    g.install()  # повторно — без подвійної обгортки
    try:
        with pytest.raises(OutboundDenied):
            socket.create_connection(("10.0.0.1", 80))
        assert fake_conn == []  # жодного TCP-з'єднання
        assert g.denied_total == 1 and denied == ["10.0.0.1"]
        assert socket.create_connection(("mosquitto", 1883)) == "sock"
        assert fake_conn == [("mosquitto", 1883)]
    finally:
        g.uninstall()
    g.uninstall()
    assert socket.create_connection(("10.0.0.1", 80)) == "sock"


def test_allow_rules():
    g = OutboundGuard(" Odoo19 , *.corp.local, 10.1.0.0/16, 127.0.0.1 ,")
    assert g.is_allowed("odoo19") and g.is_allowed("ODOO19")
    assert g.is_allowed("a.corp.local") and not g.is_allowed("corp.local.evil.com")
    assert g.is_allowed("10.1.2.3") and not g.is_allowed("10.2.0.1")
    assert g.is_allowed("[127.0.0.1]") and not g.is_allowed("") and not g.is_allowed("not-an-ip")
    assert OutboundGuard(["x"]).is_allowed("x")


def test_check_url_and_httpx_hook():
    import asyncio

    g = OutboundGuard("127.0.0.1")
    g.check_url("http://127.0.0.1:8090/sim/v1/lpr-sink")
    with pytest.raises(OutboundDenied) as ei:
        g.check_url("http://10.0.0.1/")
    assert ei.value.host == "10.0.0.1" and g.denied_total == 1
    asyncio.run(g.httpx_hook(SimpleNamespace(url=SimpleNamespace(host="127.0.0.1"))))
    with pytest.raises(OutboundDenied):
        asyncio.run(g.httpx_hook(SimpleNamespace(url=SimpleNamespace(host="evil"))))


def test_denied_emits_error_event(world):
    g = OutboundGuard("mosquitto",
                      on_denied=lambda h: world.events.emit("error", f"outbound denied: {h}"))
    with pytest.raises(OutboundDenied):
        g.check("10.0.0.1")
    assert world.events.last("error").message == "outbound denied: 10.0.0.1"
