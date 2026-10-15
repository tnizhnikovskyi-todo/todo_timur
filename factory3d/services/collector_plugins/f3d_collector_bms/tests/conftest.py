"""Фікстури плагіна helvarnet: фейковий роутер, PluginContext-заглушка, фабрика плагінів."""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    import collector  # noqa: F401
except ImportError:  # ядро колектора не встановлено — беремо з монорепо
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "collector"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fake_helvar_router import FakeHelvarRouter  # noqa: E402

from collector.core.errors import AllowlistDenied  # noqa: E402
from collector.core.types import SignalCfg, SourceCfg  # noqa: E402
from collector.plugins.base import PluginContext  # noqa: E402
from f3d_collector_bms.connection import POOL  # noqa: E402
from f3d_collector_bms.helvarnet import HelvarNetPlugin  # noqa: E402


def make_signal(group=12, query="level", code=None, period_s=30, **addr):
    address = {"query": query, **addr}
    if group is not None:
        address["group"] = group
    return SignalCfg(
        code=code or f"lighting/groups/G{group}/{query}",
        kind="gauge",
        unit="",
        period_s=period_s,
        scale=1.0,
        write_enabled=query in ("level", "scene"),
        states=None,
        decimals=2,
        address=address,
        source_code="HN-LP-2",
    )


def make_source(port, signals=(), code="HN-LP-2", **params):
    p = {"host": "127.0.0.1", "port": port, "router": 2, "timeout_s": 1}
    p.update(params)
    return SourceCfg(
        code=code, type="helvarnet", read_enabled=True, write_enabled=True, params=p, signals=tuple(signals)
    )


def make_ctx(deny=False):
    emitted: list = []

    def allowlist(host):
        if deny:
            raise AllowlistDenied(host)

    ctx = PluginContext(
        settings=SimpleNamespace(write_enabled=True),
        secrets=lambda name: "",
        allowlist=allowlist,
        emit=emitted.append,
        emit_event=lambda e: None,
        metrics=SimpleNamespace(),
        log=logging.getLogger("collector.plugin.helvarnet.test"),
    )
    ctx.emitted = emitted  # type: ignore[attr-defined]
    return ctx


@pytest.fixture(autouse=True)
def _clean_pool():
    POOL.reset()
    yield
    POOL.reset()


@pytest.fixture
async def fake_router():
    """Фабрика фейкових роутерів на вільних портах; зупиняються після тесту."""
    servers: list[FakeHelvarRouter] = []

    async def factory(**kw):
        server = await FakeHelvarRouter(**kw).start()
        servers.append(server)
        return server

    yield factory
    for server in servers:
        await server.stop()


@pytest.fixture
async def plugin_factory():
    """Створює й підключає плагін; `disconnect` після тесту."""
    plugins: list[HelvarNetPlugin] = []

    async def factory(fake, signals=(), connect=True, deny=False, **params):
        ctx = make_ctx(deny=deny)
        plugin = HelvarNetPlugin(make_source(fake.port, signals, **params), ctx)
        plugin.verify_extra_s = 0.05
        plugins.append(plugin)
        if connect:
            await plugin.connect()
        return plugin

    yield factory
    for plugin in plugins:
        with contextlib.suppress(Exception):
            await plugin.disconnect()
