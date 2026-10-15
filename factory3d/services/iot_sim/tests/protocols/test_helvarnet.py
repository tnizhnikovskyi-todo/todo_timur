"""P-08 HelvarNet (SPEC §8.10.4): кадри, версії, склад груп (AC-65), C:110, команди + push, часткові кадри."""
import asyncio
import inspect

import pytest
from iot_sim.protocols.helvarnet_server import HelvarServer

from tests.protocols.conftest import free_port


class Client:
    def __init__(self, reader, writer):
        self.r, self.w = reader, writer
        self.buf = ""

    async def frame(self, timeout=2.0) -> str:
        """Наступний повний кадр (до `#` або `$`)."""
        while True:
            m = [i for i, ch in enumerate(self.buf) if ch in "#$"]
            if m:
                out, self.buf = self.buf[: m[0] + 1], self.buf[m[0] + 1:]
                return out
            data = await asyncio.wait_for(self.r.read(4096), timeout)
            assert data, "з'єднання закрито"
            self.buf += data.decode()

    async def ask(self, msg: str) -> str:
        self.w.write(msg.encode())
        await self.w.drain()
        while True:
            f = await self.frame()
            # unsolicited push C:13 від моделі освітлення не є відповіддю на запит
            if not (f.startswith(">") and ",C:13," in f and ",C:13," not in msg):
                return f

    async def close(self):
        self.w.close()


async def connect(srv) -> Client:
    r, w = await asyncio.open_connection("127.0.0.1", srv.tcp_port)
    await asyncio.sleep(0.05)
    return Client(r, w)


@pytest.fixture
async def helvar(world):
    srv = HelvarServer(world, tcp_port=free_port(), udp_port=free_port(), host="127.0.0.1")
    await srv.start()
    srv.c = await connect(srv)
    yield srv
    await srv.c.close()
    await srv.stop()


def addrs(frame: str) -> list[str]:
    return frame.rsplit("=", 1)[1][:-1].split(",")


async def test_basic_queries_and_reply_format(helvar):
    c = helvar.c
    assert await c.ask(">V:2,C:101#") == "?V:2,C:101=1#"
    assert await c.ask(">V:2,C:102,@1#") == "?V:2,C:102,@1=1,2,3#"
    assert await c.ask(">V:2,C:107#") == "?V:2,C:107=F3D#"
    assert await c.ask(">V:2,C:190#") == "?V:2,C:190=5.4.0#"
    assert await c.ask(">V:2,C:191#") == "?V:2,C:191=2#"
    assert (await c.ask(">V:2,C:165#")).endswith(",32,40#")
    assert await c.ask(">V:2,C:105,G:12#") == "?V:2,C:105,G:12=Розкрій#"
    epoch = int((await c.ask(">V:2,C:185#")).split("=")[1][:-1])
    assert epoch == int(helvar.world.now().timestamp())


async def test_response_in_request_version(helvar):
    assert await helvar.c.ask(">V:1,C:101#") == "?V:1,C:101=1#"
    helvar.version = 1  # SIM_HELVAR_VERSION=1: V:2 -> 18, V:1 обробляється
    assert await helvar.c.ask(">V:2,C:101#") == "!V:2,C:101=18#"
    assert await helvar.c.ask(">V:1,C:101#") == "?V:1,C:101=1#"


async def test_ac65_group_composition(helvar):
    c = helvar.c
    cut = addrs(await c.ask(">V:2,C:164,G:12#"))
    assert cut == [f"@1.2.1.{i}" for i in range(1, 28)]
    eb = addrs(await c.ask(">V:2,C:164,G:13#"))
    assert eb[0] == "@1.2.1.28" and eb[-1] == "@1.2.1.54"
    cnc = addrs(await c.ask(">V:2,C:164,G:14#"))
    assert cnc[0] == "@1.2.2.1" and cnc[-1] == "@1.2.2.27"  # 27 > 64 − 54 -> нова лінія
    assert addrs(await c.ask(">V:2,C:164,G:15#"))[0] == "@1.2.2.28"
    rcv1 = addrs(await c.ask(">V:2,C:164,G:1#"))
    assert rcv1 == ["@1.1.1.1", "@1.1.1.2", "@1.1.1.3", "@1.1.1.4"]
    assert addrs(await c.ask(">V:2,C:164,G:11#"))[-1] == "@1.1.1.50"  # LT-PKS 49–50
    out1 = addrs(await c.ask(">V:2,C:164,G:26#"))  # LT-OUT-1
    assert out1[0] == "@1.3.1.59" and out1[-1] == "@1.3.1.62"
    assert addrs(await c.ask(">V:2,C:164,G:27#"))[0] == "@1.3.2.1"  # 4 > 64 − 62
    assert addrs(await c.ask(">V:2,C:164,G:32#"))[-1] == "@1.3.2.24"  # LT-OUT-7


async def test_partial_frames_for_big_group(helvar):
    c = helvar.c
    c.w.write(b">V:2,C:164,G:16#")  # LT-FAC: 91 світильник
    await c.w.drain()
    first, second = await c.frame(), await c.frame()
    assert first.startswith("?V:2,C:164,G:16=@1.2.3.1") and first.endswith("$")
    assert len(first.rsplit("=", 1)[1][:-1].split(",")) == 64
    assert second.startswith("?V:2,C:164,G:16=@1.2.4.1") and second.endswith("#")
    assert second.rsplit("=", 1)[1][:-1].split(",")[-1] == "@1.2.4.27"


async def test_total_320_devices(helvar):
    total = sum(len(g.devices) for g in helvar.layout.groups)
    assert total == 320 and len(helvar.layout.groups) == 32


async def test_query_level_power_and_state(helvar, world):
    world.force("lighting/groups/LT-CUT/level", 60, hold_s=600)
    c = helvar.c
    assert await c.ask(">V:2,C:152,@1.2.1.5#") == "?V:2,C:152,@1.2.1.5=60#"
    assert await c.ask(">V:2,C:161,G:12#") == f"?V:2,C:161,G:12={round(27 * 126 * 60 / 100)}#"
    assert await c.ask(">V:2,C:160,@1.2.1.5#") == f"?V:2,C:160,@1.2.1.5={round(126 * 60 / 100)}#"
    assert await c.ask(">V:2,C:110,@1.2.1.5#") == "?V:2,C:110,@1.2.1.5=0#"
    assert await c.ask(">V:2,C:104,@1.2.1.5#") == "?V:2,C:104,@1.2.1.5=1537#"
    assert await c.ask(">V:2,C:112,@1.2.1.5#") == "?V:2,C:112,@1.2.1.5=0#"


async def test_c110_fault_and_blackout(helvar, world):
    c = helvar.c
    world.set_flag("lighting_scene", {"LT-CUT": {"scene": None, "level": None, "fault_device": "@1.2.1.5"}})
    assert await c.ask(">V:2,C:110,@1.2.1.5#") == "?V:2,C:110,@1.2.1.5=2#"
    assert await c.ask(">V:2,C:112,@1.2.1.5#") == "?V:2,C:112,@1.2.1.5=1#"
    assert await c.ask(">V:2,C:110,@1.2.1.6#") == "?V:2,C:110,@1.2.1.6=0#"
    world.clear_flag("lighting_scene")
    world.set_flag("blackout", {"phase": "outage"})
    assert await c.ask(">V:2,C:110,@1.2.1.1#") == "?V:2,C:110,@1.2.1.1=0#"   # звичайні — без бітів
    assert await c.ask(">V:2,C:152,@1.2.1.1#") == "?V:2,C:152,@1.2.1.1=0#"   # рівень 0
    em = helvar.layout.emergency[0]
    assert await c.ask(f">V:2,C:110,{em}#") == f"?V:2,C:110,{em}=1024#"  # 0x400


async def test_errors(helvar):
    c = helvar.c
    assert await c.ask(">V:2,C:110,@1.2.1.99#") == "!V:2,C:110,@1.2.1.99=11#"
    assert await c.ask(">V:2,C:161,G:99#") == "!V:2,C:161,G:99=1#"
    assert await c.ask(">V:2,C:152,@1.9.1.1#") == "!V:2,C:152,@1.9.1.1=10#"
    assert await c.ask(">V:2,C:152,@2.1.1.1#") == "!V:2,C:152,@2.1.1.1=9#"
    assert await c.ask(">V:2,C:152,@1.1.9.1#") == "!V:2,C:152,@1.1.9.1=4#"
    assert await c.ask(">V:2,C:999#") == "!V:2,C:999=15#"
    assert await c.ask(">V:2,C:13,G:99,L:60,F:1,A:1#") == "!V:2,C:13,G:99,L:60,F:1,A:1=1#"
    assert await c.ask(">V:2,C:11,G:12,B:9,S:3,A:1#") == "!V:2,C:11,G:12,B:9,S:3,A:1=7#"
    assert await c.ask(">V:2,C:11,G:12,B:1,S:17,A:1#") == "!V:2,C:11,G:12,B:1,S:17,A:1=8#"
    assert await c.ask(">V:2,C:152#") == "!V:2,C:152=17#"


async def test_direct_level_pushes_to_all_clients_and_acks(helvar, world):
    other = await connect(helvar)
    c = helvar.c
    c.w.write(b">V:2,C:13,G:12,L:60,F:100#")
    await c.w.drain()
    assert await other.frame() == ">V:2,C:13,G:12,L:60,F:100#"
    assert await c.frame() == ">V:2,C:13,G:12,L:60,F:100#"  # push й відправнику
    sig = world.signals["lighting/groups/LT-CUT/level"]
    assert sig.value == 60 and sig.held(world.now())
    assert world.drain("lighting")[0]["target"] == "LT-CUT"
    assert world.events.since(0, kind="command")[0]
    # з підтвердженням: push усім + !…=0# відправнику
    c.w.write(b">V:2,C:13,G:19,L:50,F:200,A:1#")
    await c.w.drain()
    frames = {await c.frame(), await c.frame()}
    assert frames == {">V:2,C:13,G:19,L:50,F:200#", "!V:2,C:13,G:19,L:50,F:200,A:1=0#"}
    assert await other.frame() == ">V:2,C:13,G:19,L:50,F:200#"
    await other.close()


async def test_recall_scene_and_device_commands(helvar, world):
    c = helvar.c
    c.w.write(b">V:2,C:11,G:12,B:1,S:3,F:500,A:1#")
    await c.w.drain()
    frames = {await c.frame(), await c.frame()}
    assert ">V:2,C:11,G:12,B:1,S:3,F:500#" in frames and "!V:2,C:11,G:12,B:1,S:3,F:500,A:1=0#" in frames
    assert world.signals["lighting/groups/LT-CUT/level"].value == 50  # S3 = 50 %
    assert await c.ask(">V:2,C:152,@1.2.1.5#") == "?V:2,C:152,@1.2.1.5=50#"
    c.w.write(b">V:2,C:14,@1.2.1.5,L:20,F:10#")
    await c.w.drain()
    assert await c.frame() == ">V:2,C:14,@1.2.1.5,L:20,F:10#"
    assert await c.ask(">V:2,C:152,@1.2.1.5#") == "?V:2,C:152,@1.2.1.5=20#"
    assert await c.ask(">V:2,C:152,@1.2.1.6#") == "?V:2,C:152,@1.2.1.6=50#"
    c.w.write(b">V:2,C:15,G:12,P:-20,F:10#")  # пропорція: 50 · 0,8 = 40
    await c.w.drain()
    await c.frame()
    assert world.signals["lighting/groups/LT-CUT/level"].value == 40
    assert await c.ask(">V:2,C:152,@1.2.1.5#") == "?V:2,C:152,@1.2.1.5=40#"  # перевизначення скинуто


async def test_push_on_world_level_change(helvar, world):
    world.force("lighting/groups/LT-HW/level", 35, hold_s=600)
    world.advance(1)
    g = helvar.layout.by_code["LT-HW"].g
    want = f">V:2,C:13,G:{g},L:35,F:100#"
    frames = []
    for _ in range(len(helvar.layout.groups) + 1):  # модель може змінити й інші групи
        frames.append(await helvar.c.frame())
        if want in frames:
            break
    assert want in frames


async def test_emergency_function_test(helvar, world):
    c = helvar.c
    assert await c.ask(">V:2,C:171,G:40#") == "?V:2,C:171,G:40=0#"
    c.w.write(b">V:2,C:19,G:40,A:1#")
    await c.w.drain()
    frames = {await c.frame(), await c.frame()}
    assert "!V:2,C:19,G:40,A:1=0#" in frames
    assert await c.ask(">V:2,C:171,G:40#") == "?V:2,C:171,G:40=2#"
    world.advance(61)
    assert await c.ask(">V:2,C:171,G:40#") == "?V:2,C:171,G:40=1#"
    assert (await c.ask(">V:2,C:19,G:12,A:1#")).endswith("=1#")  # лише EMERGENCY
    assert addrs(await c.ask(">V:2,C:164,G:40#")) == helvar.layout.emergency


async def test_udp_query(helvar):
    loop = asyncio.get_running_loop()
    fut = loop.create_future()

    class P(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            fut.set_result(data.decode())

    transport, _ = await loop.create_datagram_endpoint(P, remote_addr=("127.0.0.1", helvar.udp_port))
    transport.sendto(b">V:2,C:101#")
    assert await asyncio.wait_for(fut, 2) == "?V:2,C:101=1#"
    transport.close()


async def test_two_frames_in_one_segment(helvar):
    c = helvar.c
    c.w.write(b">V:2,C:101#>V:2,C:107#")
    await c.w.drain()
    assert await c.frame() == "?V:2,C:101=1#"
    assert await c.frame() == "?V:2,C:107=F3D#"


def test_default_ports_are_standard():
    params = inspect.signature(HelvarServer).parameters
    assert params["tcp_port"].default == 50000 and params["udp_port"].default == 50001
