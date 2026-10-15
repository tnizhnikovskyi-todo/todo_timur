"""AC-82: allow-list."""
from __future__ import annotations

import asyncio
import socket

import pytest

from collector.core.allowlist import Allowlist
from collector.core.errors import AllowlistDenied
from collector.core.metrics import Metrics


def test_allowlist_blocks_connect(monkeypatch):
    calls = []
    monkeypatch.setattr(asyncio, "open_connection", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: calls.append(a))
    metrics = Metrics()
    al = Allowlist(["iot-sim", "10.0.3.0/24"], "http://odoo19:8069", metrics)
    with pytest.raises(AllowlistDenied):
        al("10.0.0.9")
    assert calls == []
    assert metrics.registry.get_sample_value("collector_allowlist_denied_total") == 1
    al("10.0.3.21")
    al("iot-sim")


def test_cidr_allowed():
    al = Allowlist(["10.0.3.0/24", "192.168.1.5"])
    for ok in ("10.0.3.1", "10.0.3.254", "192.168.1.5"):
        assert al.is_allowed(ok)
    for bad in ("10.0.4.1", "192.168.1.6", ""):
        assert not al.is_allowed(bad)


def test_odoo_host_auto():
    al = Allowlist([], "http://odoo19:8069")
    al("odoo19")
    with pytest.raises(AllowlistDenied):
        al("other-host-9")


def test_hostname_resolved_to_allowed_ip(monkeypatch):
    monkeypatch.setattr("collector.core.allowlist._resolve", lambda h: {"10.0.3.7"} if h == "plc.local" else set())
    al = Allowlist(["10.0.3.0/24"])
    al("plc.local")
