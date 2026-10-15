"""Фікстури колектора (SPEC §13.0.2). Імпорти класів сервісу — лише всередині фікстур,
щоб колекція тестів працювала, поки core/ ще не змерджено."""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

T0 = datetime(2026, 10, 14, 6, 0, 0, tzinfo=UTC)
TOKEN = "t" * 43


class VirtualClock:
    """Віртуальний годинник: sleep() просуває час і віддає керування циклу."""

    def __init__(self, start: datetime = T0) -> None:
        self._now = start
        self._mono = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def advance(self, s: float) -> None:
        self._now += timedelta(seconds=s)
        self._mono += s

    async def sleep(self, s: float) -> None:
        self.advance(s)
        await asyncio.sleep(0)


class FakeOdoo:
    """Програмований стенд API-01…API-07 (/f3d/telemetry/*) на aiohttp TestServer."""

    def __init__(self) -> None:
        self.config: dict = {"sources": []}
        self.etag = "etag-1"
        self.push_status: list[int] = []  # черга кодів відповіді на push; порожньо -> 200
        self.write_enabled = False
        self.commands: list[dict] = []
        self.calls: list[tuple[str, str, object]] = []
        self.server: TestServer | None = None

    @property
    def url(self) -> str:
        assert self.server is not None
        return str(self.server.make_url("")).rstrip("/")

    def _auth_ok(self, request: web.Request) -> bool:
        return request.headers.get("Authorization") == f"Bearer {TOKEN}"

    async def _handle(self, request: web.Request) -> web.Response:
        body = await request.json() if request.can_read_body else None
        self.calls.append((request.method, request.path, body))
        if not self._auth_ok(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        path = request.path
        now = datetime.now(UTC).isoformat()
        if path.endswith("/config"):
            if request.headers.get("If-None-Match") == self.etag:
                return web.Response(status=304)
            return web.json_response({**self.config, "config_etag": self.etag, "server_time": now},
                                     headers={"ETag": self.etag})
        if path.endswith("/readings"):
            status = self.push_status.pop(0) if self.push_status else 200
            return web.json_response({"accepted": len(body.get("readings", [])) if body else 0,
                                      "server_time": now}, status=status)
        if path.endswith("/commands"):
            return web.json_response({"commands": self.commands, "write_enabled": self.write_enabled,
                                      "server_time": now})
        return web.json_response({"ok": True, "server_time": now})

    async def start(self) -> None:
        app = web.Application()
        app.router.add_route("*", "/f3d/telemetry/{tail:.*}", self._handle)
        self.server = TestServer(app)
        await self.server.start_server()

    async def stop(self) -> None:
        if self.server:
            await self.server.close()


@pytest_asyncio.fixture
async def fake_odoo():
    odoo = FakeOdoo()
    await odoo.start()
    yield odoo
    await odoo.stop()


@pytest.fixture
def vclock() -> VirtualClock:
    return VirtualClock()


@pytest.fixture
def settings(tmp_path, monkeypatch, fake_odoo):
    from collector.core.settings import Settings

    monkeypatch.setenv("F3D_ODOO_URL", fake_odoo.url)
    monkeypatch.setenv("F3D_COLLECTOR_CODE", "COL-T")
    monkeypatch.setenv("F3D_COLLECTOR_TOKEN", TOKEN)
    monkeypatch.setenv("F3D_ALLOW_HOSTS", "127.0.0.1,localhost")
    monkeypatch.setenv("F3D_BUFFER_DIR", str(tmp_path))
    monkeypatch.setenv("F3D_WRITE_ENABLED", "0")
    return Settings()


@pytest.fixture
def buffer(tmp_path):
    from collector.core.buffer import Buffer

    return Buffer(tmp_path / "buffer.sqlite", max_mb=200)


class FakeMqttClient:
    """Підміна paho.mqtt.client.Client; deliver/drop/connect_ok синхронно викликають колбеки."""

    instances: ClassVar[list] = []

    def __init__(self, *args, **kwargs) -> None:
        self.on_connect = self.on_disconnect = self.on_message = None
        self.subscribed: list[str] = []
        self.published: list[tuple[str, object]] = []
        FakeMqttClient.instances.append(self)

    def username_pw_set(self, *a, **k) -> None: ...
    def tls_set(self, *a, **k) -> None: ...
    def reconnect_delay_set(self, *a, **k) -> None: ...
    def connect_async(self, *a, **k) -> None: ...
    def loop_start(self) -> None: ...
    def loop_stop(self) -> None: ...
    def disconnect(self) -> None: ...

    def subscribe(self, topic, *a, **k):
        self.subscribed.append(topic)
        return (0, 1)

    def publish(self, topic, payload=None, *a, **k):
        self.published.append((topic, payload))

    def connect_ok(self, rc: int = 0) -> None:
        if self.on_connect:
            self.on_connect(self, None, {}, rc, None)

    def drop(self, rc: int = 7) -> None:
        if self.on_disconnect:
            self.on_disconnect(self, None, {}, rc, None)

    def deliver(self, topic: str, payload: bytes, retain: bool = False) -> None:
        msg = type("Msg", (), {"topic": topic, "payload": payload, "retain": retain, "qos": 0})()
        if self.on_message:
            self.on_message(self, None, msg)


@pytest.fixture
def fake_mqtt(monkeypatch):
    import paho.mqtt.client as mqtt

    FakeMqttClient.instances = []
    monkeypatch.setattr(mqtt, "Client", FakeMqttClient)
    return FakeMqttClient


@pytest.fixture
def mqtt_broker():
    """Маркер `broker`: F3D_TEST_MQTT=host:port або mosquitto у Docker; інакше skip (Q-16)."""
    env = os.environ.get("F3D_TEST_MQTT")
    if env:
        host, port = env.rsplit(":", 1)
        yield host, int(port)
        return
    if not shutil.which("docker"):
        pytest.skip("немає Docker і F3D_TEST_MQTT")
    cid = subprocess.run(
        ["docker", "run", "-d", "--rm", "-p", "127.0.0.1::1883", "eclipse-mosquitto:2.0.20",
         "mosquitto", "-c", "/mosquitto-no-auth.conf"], capture_output=True, text=True, check=False)
    if cid.returncode:
        pytest.skip("docker run mosquitto не вдався")
    cid_s = cid.stdout.strip()
    try:
        out = subprocess.run(["docker", "port", cid_s, "1883"], capture_output=True, text=True, check=True)
        yield "127.0.0.1", int(out.stdout.strip().splitlines()[0].rsplit(":", 1)[1])
    finally:
        subprocess.run(["docker", "stop", cid_s], capture_output=True, check=False)


@pytest_asyncio.fixture
async def modbus_server(vclock):
    """Modbus TCP сервер pymodbus 3.9.2 (units 70, 84, 86, 90, 96, zero_mode). Дані AC-78 — у тестах плагіна."""
    pytest.importorskip("pymodbus")
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
    from pymodbus.server import ModbusTcpServer

    class CountingBlock(ModbusSequentialDataBlock):
        def __init__(self, owner, *a, **k):
            super().__init__(*a, **k)
            self.owner = owner

        def getValues(self, address, count=1):
            self.owner.requests += 1
            return super().getValues(address, count)

        def setValues(self, address, values):
            vals = values if isinstance(values, list) else [values]
            if self.owner.fail_n > 0:
                self.owner.fail_n -= 1
                raise ValueError("0x04")
            for i, v in enumerate(vals):
                self.owner.writes.append((vclock.now(), 3, address + i, v))
            super().setValues(address, values)

    class Handle:
        requests = 0
        writes: ClassVar[list] = []
        fail_n = 0
        host = "127.0.0.1"
        port = 0

        def fail_writes(self, n: int) -> None:
            self.fail_n = n

    h = Handle()
    h.writes = []

    def ctx():
        return ModbusSlaveContext(
            di=CountingBlock(h, 0, [0] * 100), co=CountingBlock(h, 0, [0] * 100),
            hr=CountingBlock(h, 0, [0] * 5000), ir=CountingBlock(h, 0, [0] * 5000), zero_mode=True)

    h.slaves = {u: ctx() for u in (70, 84, 86, 90, 96)}
    context = ModbusServerContext(slaves=h.slaves, single=False)
    server = ModbusTcpServer(context, address=("127.0.0.1", 0))
    task = asyncio.create_task(server.serve_forever())
    await asyncio.sleep(0.1)
    h.port = server.server.sockets[0].getsockname()[1] if getattr(server, "server", None) else 0
    yield h
    await server.shutdown()
    task.cancel()


@pytest.fixture
def bacnet_device():
    """bacpypes3 пристрій device 140 (AC-97, X-05). Каркас: наповнює воркер bacnet_ip."""
    pytest.importorskip("bacpypes3")
    pytest.skip("фікстура bacnet_device реалізується воркером плагіна bacnet_ip")


@pytest_asyncio.fixture
async def http_push_client(settings, vclock):
    """TestClient над HttpPushServer(...).app; remote = 127.0.0.1."""
    from collector.core.http_push import HttpPushServer

    server = HttpPushServer(settings=settings, clock=vclock)
    client = TestClient(TestServer(server.app))
    await client.start_server()
    yield client
    await client.close()
