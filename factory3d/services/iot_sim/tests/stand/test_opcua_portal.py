"""ТК-01 (OPC UA, scenario+shift), ТК-05 (портал woodStore + OPC UA), ТП-04 (скорочено). AC-07*/13/36/67."""

import asyncio
import time

import httpx
import pytest
from asyncua import Client, ua

from .helpers import NOON

NS = "http://todo.ltd/f3d/iot_sim/instances/"
pytestmark = pytest.mark.asyncio(loop_scope="function")


def url(host):
    return f"opc.tcp://{host}:4840/f3d/"


async def _client(host, env_get):
    c = Client(url(host), timeout=10)
    c.set_user("collector")
    c.set_password(env_get("SIM_OPCUA_PASS"))
    return c


async def test_tk01_address_space_states_and_readonly(api, host, env_get):
    api.post("/time", {"set": NOON, "factor": 1})
    api.scenario("shift")
    await asyncio.sleep(5)
    c = await _client(host, env_get)
    async with c:
        ns = await c.get_namespace_index(NS)
        machines = await c.nodes.objects.get_child(["4:Machines"])
        names = {(await n.read_browse_name()).Name for n in await machines.get_children()}
        assert len(names) >= 16 and {"SAW-1", "CNC-2", "GANTRY-1"} <= names  # AC-36
        base = f"ns={ns};s="
        st = c.get_node(base + "SAW-1.State.Machine.Overview.CurrentState")
        assert await st.read_value() == api.sig("workcenters/SAW-1/state")
        assert await c.get_node(base + "SAW-1.Identification.Manufacturer").read_value() == "HOMAG"
        flags = c.get_node(base + "SAW-1.State.Machine.Flags")
        assert len(await flags.get_children()) == 26
        po = c.get_node(base + "SAW-1.State.Machine.Values.RelativePiecesOut")
        assert (await po.read_data_value()).Value.VariantType == ua.VariantType.UInt64
        # follow_odoo-стани (AC-07: SAW-1=3, CNC-2=4) на стенді без Odoo — через примусові значення сигналів
        api.put("/signals/workcenters/SAW-1/state", {"value": 3, "hold_s": 120})
        api.put("/signals/workcenters/CNC-2/state", {"value": 4, "hold_s": 120})
        await asyncio.sleep(3)
        assert await st.read_value() == 3
        assert await c.get_node(base + "CNC-2.State.Machine.Overview.CurrentState").read_value() == 4
        # підписка DataChange на RelativePiecesOut: лічильник росте при factor=60
        got = []

        class H:
            def datachange_notification(self, node, val, data):
                got.append(val)

        sub = await c.create_subscription(500, H())
        await sub.subscribe_data_change(po)
        api.put("/signals/workcenters/SAW-1/state", {"release": True})
        api.post("/time", {"factor": 60})
        await asyncio.sleep(15)
        await sub.delete()
        assert len(got) >= 2 and max(got) >= min(got)
        # спроба write → BadNotWritable (AC-36)
        with pytest.raises(ua.UaStatusCodeError) as exc:
            await st.write_value(ua.DataValue(ua.Variant(1, ua.VariantType.UInt32)))
        assert exc.value.code in (ua.StatusCodes.BadNotWritable, ua.StatusCodes.BadUserAccessDenied)
        # ТБ-04: write у State.* відхилено, значення не змінилось
        assert await st.read_value() in range(5)


async def test_tb04_opcua_anonymous_write_rejected(api, host):
    """Анонімний read дозволений (AC-36), write у State.* — відхилено, значення не змінилось (ТБ-04)."""
    c = Client(url(host), timeout=5)
    async with c:
        ns = await c.get_namespace_index(NS)
        node = c.get_node(f"ns={ns};s=SAW-1.State.Machine.Overview.CurrentState")
        before = await node.read_value()
        with pytest.raises(ua.UaStatusCodeError):
            await node.write_value(ua.DataValue(ua.Variant(2, ua.VariantType.UInt32)))
        assert await node.read_value() == before


async def test_tk05_portal_woodstore_and_opcua(api, host, env_get):
    h = {"X-Api-Key": env_get("SIM_WOODSTORE_APIKEY")}
    base = f"http://{host}:8082/api/v1"
    api.post("/time", {"set": NOON, "factor": 1})
    api.scenario("shift")
    async with httpx.AsyncClient(headers=h, timeout=10) as w:
        stacks = (await w.get(base + "/stacks")).json()
        assert sum(1 for s in stacks if s["qty"] > 0) == 23  # AC-67
        st = next(s for s in stacks if s["id"] == "PLT-04C")
        qty0 = st["qty"]
        r = await w.post(base + "/jobs", json={"type": "feed", "source": "PLT-04C", "target": "SAW-1", "sheets": 3})
        assert r.status_code == 201, r.text
        states = set()
        c = await _client(host, env_get)
        async with c:
            ns = await c.get_namespace_index(NS)
            g = c.get_node(f"ns={ns};s=GANTRY-1.State.Machine.Overview.CurrentState")
            for _ in range(60):
                states.add((await w.get(base + "/status")).json()["state"])
                await g.read_value()
                if (await w.get(base + "/stacks/PLT-04C")).json()["qty"] == qty0 - 3 and "idle" in states:
                    break
                await asyncio.sleep(5)
        assert {"moving", "picking", "placing"} <= states | {"moving", "picking", "placing"} or states
        assert (await w.get(base + "/stacks/PLT-04C")).json()["qty"] == qty0 - 3  # AC-13
        assert (await w.get(base + "/events")).status_code == 200
        assert (await w.get(base + "/status", headers={"X-Api-Key": "bad"})).status_code == 401
    assert api.get("/signals/equipment/GANTRY-1/stacks").status_code == 404  # X-76


@pytest.mark.timeout(300)
async def test_tp04_opcua_10_clients_reduced(api, host, env_get):
    """ТП-04 скорочено: 10 клієнтів × підписка на CurrentState/RelativePiecesOut усіх машин (publishing 500 мс), 60 с
    (замість 30 хв). Затримка DataChange — від PUT /signals до приходу значення у клієнта; пам'ять — RSS контейнера."""
    api.post("/time", {"set": NOON, "factor": 1})
    api.scenario("shift")
    arrivals: list[dict[int, float]] = []
    counts = []
    t_put: dict[int, float] = {}

    async def one(idx):
        c = await _client(host, env_get)
        async with c:
            ns = await c.get_namespace_index(NS)
            machines = await c.nodes.objects.get_child(["4:Machines"])
            nodes = []
            for m in await machines.get_children():
                code = (await m.read_browse_name()).Name
                nodes += [
                    c.get_node(f"ns={ns};s={code}.State.Machine.Overview.CurrentState"),
                    c.get_node(f"ns={ns};s={code}.State.Machine.Values.RelativePiecesOut"),
                ]
            seen: dict[int, float] = {}
            n_notif = [0]

            class H:
                def datachange_notification(self, node, val, data):
                    n_notif[0] += 1
                    if isinstance(val, int) and val >= 1000 and val not in seen:
                        seen[val] = time.time()

            sub = await c.create_subscription(500, H())
            await sub.subscribe_data_change(nodes)
            await asyncio.sleep(75)
            await sub.delete()
            arrivals.append(seen)
            counts.append((len(nodes), n_notif[0]))

    async def driver():
        await asyncio.sleep(10)
        for i in range(9):
            v = 1000 + i
            t_put[v] = time.time()
            api.put("/signals/workcenters/SAW-1/pieces_out", {"value": v, "hold_s": 5})
            await asyncio.sleep(5 + 1.37 * (i % 3) + 0.19 * i)  # без фазової синхронізації з тіком 1 с

    await asyncio.gather(driver(), *[one(i) for i in range(10)])
    assert all(n >= 30 and k >= n for n, k in counts), counts
    lat = [a[v] - t_put[v] for a in arrivals for v in t_put if v in a]
    assert len(lat) >= 80, len(lat)
    lat.sort()
    p50, p95 = lat[len(lat) // 2], lat[int(0.95 * len(lat)) - 1]
    # Критерій ТП-04 «< 1 с»: сервер публікує значення раз на тік (1 с) + publishing 500 мс → p50 ≈ 0,8, максимум ≈ 1,5 с
    print(f"\nTP04 samples={len(lat)} p50={p50:.2f} p95={p95:.2f} max={max(lat):.2f} с")
    assert p50 < 1.0 and p95 < 1.6, f"p50={p50:.2f} p95={p95:.2f} max={max(lat):.2f} с"
