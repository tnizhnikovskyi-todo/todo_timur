"""Фікстури плагіна sics: фейковий сервер, PluginContext-заглушка."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    import collector  # noqa: F401
except ImportError:  # ядро колектора не встановлено — беремо з монорепо
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "collector"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_sics_server import FakeSicsServer  # noqa: E402

from collector.core.errors import AllowlistDenied  # noqa: E402
from collector.core.types import SignalCfg, SourceCfg  # noqa: E402
from collector.plugins.base import PluginContext  # noqa: E402

DEFAULT_FRAMES = [("S", 21380.0, "kg")]


def make_signal(field, scale=None, offset=None, write=None, code=None, address=None):
    addr = {"cmd": "SI", "field": field} if address is None else address
    if scale is not None:
        addr["scale"] = scale
    if offset is not None:
        addr["offset"] = offset
    if write:
        addr["write"] = {"cmd": write}
    return SignalCfg(
        code=code or f"yard/scale/TRUCK-SCALE/{field}" + (f"_{write}" if write else ""),
        kind="gauge",
        unit="",
        period_s=1,
        scale=1.0,
        write_enabled=bool(write),
        states=None,
        decimals=0,
        address=addr,
        source_code="SICS-TRUCK-SCALE",
    )


def make_source(port, signals=(), **params):
    p = {"host": "127.0.0.1", "port": port, "mode": "stream", "timeout_s": 1, "reset_on_connect": True}
    p.update(params)
    return SourceCfg(
        code="SICS-TRUCK-SCALE", type="sics", read_enabled=True, write_enabled=True, params=p, signals=tuple(signals)
    )


def make_ctx(write_enabled=True, deny=False):
    def allowlist(host):
        if deny:
            raise AllowlistDenied(host)

    return PluginContext(
        settings=SimpleNamespace(write_enabled=write_enabled),
        secrets=lambda name: "",
        allowlist=allowlist,
        emit=lambda r: None,
        emit_event=lambda e: None,
        metrics=SimpleNamespace(),
        log=logging.getLogger("collector.plugin.sics.test"),
    )


@pytest.fixture
async def fake_sics():
    """Фабрика серверів на вільних портах; зупиняються після тесту."""
    servers: list[FakeSicsServer] = []

    async def factory(weights=None, **kw):
        server = await FakeSicsServer(weights or DEFAULT_FRAMES, **kw).start()
        servers.append(server)
        return server

    yield factory
    for server in servers:
        await server.stop()


@pytest.fixture
def ctx():
    return make_ctx()
