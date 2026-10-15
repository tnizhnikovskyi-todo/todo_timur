"""Фікстури пакета f3d_collector_mc (SPEC §13.0.2): ua_server, woodstore_app, cutopt_app, fake_odoo_export, ctx."""

from __future__ import annotations

import asyncio
import heapq
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer
from collector.core.errors import AllowlistDenied
from collector.core.metrics import Metrics
from collector.core.types import SignalCfg, SourceCfg
from collector.plugins.base import PluginContext

sys.path.insert(0, str(Path(__file__).parent))  # `fakes.*`

from fakes.cutopt_app import FakeCutOpt  # noqa: E402
from fakes.opcua_server import FakeMachines  # noqa: E402
from fakes.woodstore_app import FakeWoodStore  # noqa: E402

T0 = datetime(2026, 10, 12, 6, 0, 0, tzinfo=UTC)
INST_URI = "http://todo.ltd/f3d/iot_sim/instances/"


class TimerClock:
    """Віртуальний годинник з таймерами: `sleep()` чекає, поки тест не викличе `tick()`; `sleeps` — журнал."""

    def __init__(self, start: datetime = T0) -> None:
        self._now = start
        self._mono = 0.0
        self._timers: list[tuple[float, int, asyncio.Future]] = []
        self._n = 0
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    async def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        fut = asyncio.get_running_loop().create_future()
        self._n += 1
        heapq.heappush(self._timers, (self._mono + s, self._n, fut))
        await fut

    async def tick(self, s: float) -> None:
        """Просуває час на `s` секунд, послідовно будячи таймери, що настали."""
        target = self._mono + s
        while self._timers and self._timers[0][0] <= target:
            due, _, fut = heapq.heappop(self._timers)
            self._set(due)
            if not fut.done():
                fut.set_result(None)
            for _ in range(5):
                await asyncio.sleep(0)
        self._set(target)
        await asyncio.sleep(0)

    def _set(self, mono: float) -> None:
        self._now += timedelta(seconds=mono - self._mono)
        self._mono = mono


async def until(cond, timeout: float = 5.0, clock: TimerClock | None = None, step: float = 0.0) -> None:
    """Чекає `cond()` реальний час; з `clock` додатково просуває віртуальний годинник на `step` с."""
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if cond():
            return
        if clock is not None and step:
            await clock.tick(step)
        await asyncio.sleep(0.02)
    raise AssertionError("умова не виконалась за відведений час")


@pytest.fixture
def vclock() -> TimerClock:
    return TimerClock()


@pytest.fixture
def ctx(tmp_path, vclock):
    settings = SimpleNamespace(
        write_enabled=False,
        odoo_url="http://127.0.0.1:1",
        odoo_ca="",
        collector_token="t" * 43,
        mc_state_dir=tmp_path,
    )
    secrets = {"F3D_OPCUA_PASSWORD": "pw", "F3D_WOODSTORE_KEY": "ws-key", "F3D_CUTOPT_KEY": "co-key"}

    def allowlist(host: str) -> None:
        if host not in ("127.0.0.1", "localhost"):
            raise AllowlistDenied(host)

    emitted: list = []
    events: list = []
    c = PluginContext(
        settings=settings,
        secrets=lambda name: secrets[name],
        allowlist=allowlist,
        emit=emitted.append,
        emit_event=events.append,
        metrics=Metrics(vclock),
        log=logging.getLogger("collector.plugin.test"),
    )
    c.emitted = emitted  # type: ignore[attr-defined]
    c.events = events  # type: ignore[attr-defined]
    c.clock = vclock  # type: ignore[attr-defined]
    return c


@pytest_asyncio.fixture
async def ua_server(vclock):
    srv = FakeMachines(now=vclock.now)
    await srv.start()
    yield srv
    await srv.stop()


@pytest_asyncio.fixture
async def woodstore_app():
    app = FakeWoodStore()
    await app.start()
    yield app
    await app.stop()


@pytest_asyncio.fixture
async def cutopt_app():
    app = FakeCutOpt()
    await app.start()
    yield app
    await app.stop()


class FakeOdooExport:
    """GET /f3d/machine/cutmap/<id>/export: Bearer колектора; програмовані відповіді (200 / 410 / 403)."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.status = 200
        self.body: dict = {
            "map": "КР/00012",
            "external_ref": "WH/MO/00233",
            "machine": "SAW-1",
            "material": "DSP16-ANT",
            "sheet": "2800x2070x16",
            "priority": 5,
            "parts": 2,
            "parts_csv": "PartId;Description;Material;Length;Width;Quantity;Grain;"
            "EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program\r\n"
            "P001;Боковина;DSP16-ANT;720;560;2;1;EB2-ANT;;EB2-ANT;;\r\n"
            "P002;Полиця;DSP16-ANT;560;300;1;0;;;;;\r\n",
        }
        self.calls: list[tuple[str, dict, str | None]] = []
        self.server: TestServer | None = None

    @property
    def url(self) -> str:
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.port}"

    async def _export(self, request: web.Request) -> web.Response:
        auth = request.headers.get("Authorization")
        self.calls.append((request.path, dict(request.query), auth))
        if auth != f"Bearer {self.token}":
            return web.json_response({"error": {"code": "unauthorized"}}, status=401)
        if self.status != 200:
            return web.json_response({"error": {"code": "x"}}, status=self.status)
        return web.json_response(self.body)

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/f3d/machine/cutmap/{id}/export", self._export)
        self.server = TestServer(app)
        await self.server.start_server()

    async def stop(self) -> None:
        if self.server is not None:
            await self.server.close()


@pytest_asyncio.fixture
async def fake_odoo_export(ctx):
    srv = FakeOdooExport(ctx.settings.collector_token)
    await srv.start()
    ctx.settings.odoo_url = srv.url
    yield srv
    await srv.stop()


# --- конфігурація джерел за Додатками C.1 / C.2 ---
def _sig(code: str, source_code: str, kind: str, address: dict, period_s: int = 1) -> SignalCfg:
    return SignalCfg(
        code=code,
        kind=kind,
        unit="",
        period_s=period_s,
        scale=1.0,
        write_enabled=False,
        states=None,
        decimals=2,
        address=address,
        source_code=source_code,
    )


def opcua_signals(machine: str, source_code: str, *, events: bool = False) -> list[SignalCfg]:
    base = f"ns=2;s={machine}"
    out = [
        _sig(
            f"workcenters/{machine}/state",
            source_code,
            "state",
            {
                "nodeid": f"{base}.State.Machine.Overview.CurrentState",
                "map": {"0": "OFFLINE", "1": "STANDBY", "2": "READY", "3": "WORKING", "4": "ERROR"},
            },
        ),
        _sig(
            f"workcenters/{machine}/mode",
            source_code,
            "state",
            {
                "nodeid": f"{base}.State.Machine.Overview.CurrentMode",
                "map": {
                    "0": "OTHER",
                    "1": "AUTOMATIC",
                    "2": "SEMIAUTOMATIC",
                    "3": "MANUAL",
                    "4": "SETUP",
                    "5": "SLEEP",
                },
            },
        ),
        _sig(
            f"workcenters/{machine}/alarm",
            source_code,
            "state",
            {"nodeid": f"{base}.State.Machine.Flags.Alarm", "map": {"0": "off", "1": "on"}},
        ),
        _sig(
            f"workcenters/{machine}/pieces_out",
            source_code,
            "counter",
            {"nodeid": f"{base}.State.Machine.Values.RelativePiecesOut"},
        ),
        _sig(
            f"workcenters/{machine}/job",
            source_code,
            "state",
            {"nodeid": f"{base}.JobManagement.JobOrderControl.JobOrderList", "job_select": "running_or_first"},
        ),
        _sig(
            f"workcenters/{machine}/job_cmd",
            source_code,
            "state",
            {"nodeid": f"{base}.JobManagement.JobOrderControl", "io": "write", "call": "job"},
        ),
    ]
    if events:
        out.append(
            _sig(f"workcenters/{machine}/event", source_code, "event", {"nodeid": f"{base}.Events", "events": True})
        )
    return out


def opcua_source(
    ua_server: FakeMachines, machine: str = "SAW-T", code: str | None = None, events: bool = False, **params
) -> SourceCfg:
    code = code or f"UA-{machine}"
    p = {
        "endpoint": ua_server.endpoint,
        "security_mode": "None",
        "ns_uri": INST_URI,
        "publishing_interval_ms": 50,
        "timeout_s": 2,
    }
    p.update(params)
    return SourceCfg(
        code=code,
        type="opcua",
        read_enabled=True,
        write_enabled=False,
        params=p,
        signals=tuple(opcua_signals(machine, code, events=events)),
    )


def gantry_signals(code: str) -> list[SignalCfg]:
    st = {"method": "GET", "path": "/api/v1/status"}
    return [
        _sig("equipment/GANTRY-1/state", code, "state", {**st, "json_path": "$.state"}, 5),
        _sig("equipment/GANTRY-1/cycles_today", code, "counter", {**st, "json_path": "$.cycles_today"}, 5),
        _sig("equipment/GANTRY-1/vacuum_kpa", code, "gauge", {**st, "json_path": "$.vacuum_kpa"}, 5),
        _sig(
            "equipment/GANTRY-1/job",
            code,
            "state",
            {
                "method": "GET",
                "path": "/api/v1/jobs",
                "query": {"state": "active"},
                "json_path": "$[0].id",
                "default": "-",
            },
            5,
        ),
        _sig(
            "equipment/GANTRY-1/cmd",
            code,
            "state",
            {"method": "POST", "path": "/api/v1/jobs", "cmd": "gantry", "io": "write"},
        ),
    ]


def cutopt_signals(code: str) -> list[SignalCfg]:
    return [
        _sig(
            "equipment/CUTOPT/cmd",
            code,
            "state",
            {"method": "POST", "path": "/jobs", "json_path": "$.job_id", "cmd": "cutopt", "io": "write"},
        )
    ]


def rest_source(base_url: str, vendor: str, code: str, **params) -> SourceCfg:
    key_ref = {"woodstore": "F3D_WOODSTORE_KEY", "cutopt": "F3D_CUTOPT_KEY"}.get(vendor, "F3D_WOODSTORE_KEY")
    p = {"base_url": base_url, "auth": "api_key", "key_ref": key_ref, "vendor": vendor, "timeout_s": 5}
    p.update(params)
    signals = gantry_signals(code) if vendor == "woodstore" else cutopt_signals(code) if vendor == "cutopt" else []
    return SourceCfg(
        code=code, type="rest_vendor", read_enabled=True, write_enabled=False, params=p, signals=tuple(signals)
    )


@pytest.fixture
def pool():
    from f3d_collector_mc.ua_session import SessionPool

    return SessionPool()


@pytest_asyncio.fixture
async def opcua_plugin(ctx, ua_server, vclock, pool):
    """Підключений і підписаний плагін `UA-SAW-T` (без подій)."""
    from f3d_collector_mc.opcua import OpcUaPlugin

    plugin = OpcUaPlugin(opcua_source(ua_server), ctx, clock=vclock, pool=pool)
    await plugin.connect()
    await plugin.subscribe()
    yield plugin
    await plugin.disconnect()


@pytest_asyncio.fixture
async def make_opcua(ctx, ua_server, vclock, pool):
    """Фабрика плагінів `opcua` (усі відключаються після тесту)."""
    from f3d_collector_mc.opcua import OpcUaPlugin

    made: list[OpcUaPlugin] = []

    def factory(machine: str = "SAW-T", code: str | None = None, **kw) -> OpcUaPlugin:
        events = kw.pop("events", False)
        plugin = OpcUaPlugin(opcua_source(ua_server, machine, code, events, **kw), ctx, clock=vclock, pool=pool)
        made.append(plugin)
        return plugin

    yield factory
    for plugin in made:
        await plugin.disconnect()


@pytest.fixture
def rest_plugin(ctx, vclock):
    """Фабрика `rest_plugin(app, vendor)` -> RestVendorPlugin (не підключений)."""
    from f3d_collector_mc.rest_vendor import RestVendorPlugin

    def factory(app, vendor: str, code: str | None = None, **params) -> RestVendorPlugin:
        code = code or {"woodstore": "REST-WOODSTORE-T", "cutopt": "REST-CUTOPT-T"}.get(vendor, "REST-T")
        return RestVendorPlugin(rest_source(app.url, vendor, code, **params), ctx, clock=vclock)

    return factory


@pytest.fixture(autouse=True)
def _reset_default_pool():
    yield
    from f3d_collector_mc.ua_session import DEFAULT_POOL

    DEFAULT_POOL._map.clear()
