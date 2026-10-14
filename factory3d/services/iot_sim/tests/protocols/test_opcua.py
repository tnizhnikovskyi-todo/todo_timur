"""P-01 OPC UA: читання, статуси, JobOrderList, методи (SPEC §8.3)."""
import pytest
from asyncua import Client, ua

from iot_sim.protocols.opcua_server import OpcUaServer

NS_INST = "http://todo.ltd/f3d/iot_sim/instances/"


@pytest.fixture
async def opc(world, port):
    srv = OpcUaServer(world, port=port, host="127.0.0.1", user="collector", password="pw")
    await srv.start()
    yield srv
    await srv.stop()


def url(srv):
    return f"opc.tcp://127.0.0.1:{srv.port}/f3d/"


async def test_machines_folder_and_namespaces(opc):
    async with Client(url(opc)) as c:
        assert await c.get_namespace_index(NS_INST) == 2
        assert await c.get_namespace_index("http://opcfoundation.org/UA/Woodworking/") == 7
        machines = await c.nodes.objects.get_child(["4:Machines"])
        names = {(await n.read_browse_name()).Name for n in await machines.get_children()}
    assert {"SAW-1", "CNC-2", "GANTRY-1"} <= names
    assert len(names) == len(opc.machines) >= 16


async def test_state_follows_world(opc, world):
    world.force("workcenters/SAW-1/state", 3, hold_s=600)
    world.force("workcenters/SAW-1/pieces_out", 7, hold_s=600)
    world.advance(2)
    await opc.refresh()
    async with Client(url(opc)) as c:
        ns = await c.get_namespace_index(NS_INST)
        st = c.get_node(f"ns={ns};s=SAW-1.State.Machine.Overview.CurrentState")
        po = c.get_node(f"ns={ns};s=SAW-1.State.Machine.Values.RelativePiecesOut")
        man = c.get_node(f"ns={ns};s=SAW-1.Identification.Manufacturer")
        assert await st.read_value() == 3
        assert await po.read_value() == 7
        assert await man.read_value() == "HOMAG"
        assert (await st.read_data_value()).StatusCode.is_good()


async def test_comm_fault_gives_bad_status(opc, world):
    world.devices["SAW-2"].fault = "comm"
    await opc.refresh()
    async with Client(url(opc)) as c:
        ns = await c.get_namespace_index(NS_INST)
        flag = c.get_node(f"ns={ns};s=SAW-2.State.Machine.Flags.MachineOn")
        with pytest.raises(ua.UaStatusCodeError) as exc:
            await flag.read_value()
        assert exc.value.code == ua.StatusCodes.BadCommunicationError
        st = c.get_node(f"ns={ns};s=SAW-2.State.Machine.Overview.CurrentState")
        assert await st.read_value() == 0


async def test_anonymous_cannot_write(opc):
    async with Client(url(opc)) as c:
        ns = await c.get_namespace_index(NS_INST)
        node = c.get_node(f"ns={ns};s=SAW-1.State.Machine.Overview.CurrentState")
        with pytest.raises(Exception):  # noqa: B017
            await node.write_value(ua.DataValue(ua.Variant(1, ua.VariantType.UInt32)))


async def test_user_login(opc):
    bad = Client(url(opc))
    bad.set_user("collector")
    bad.set_password("wrong")
    with pytest.raises(Exception):  # noqa: B017
        await bad.connect()
    good = Client(url(opc))
    good.set_user("collector")
    good.set_password("pw")
    async with good:
        assert await good.nodes.root.read_browse_name()


async def test_joborder_list_and_method(opc, world):
    world.post("opc_joborders", {"machine": "SAW-1", "job_order_id": "cj-00077"})
    await opc.refresh()
    c = Client(url(opc))
    c.set_user("collector")
    c.set_password("pw")
    async with c:
        ns = await c.get_namespace_index(NS_INST)
        lst = c.get_node(f"ns={ns};s=SAW-1.JobManagement.JobOrderControl.JobOrderList")
        assert "cj-00077" in await lst.read_value()
        ctl = c.get_node(f"ns={ns};s=SAW-1.JobManagement.JobOrderControl")
        assert await ctl.call_method(f"{ns}:Store", "WO00013", "") == 0
        await opc.refresh()
        assert "WO00013" in await lst.read_value()
    assert world.drain("opc_joborder")[0]["job_order_id"] == "WO00013"


async def test_methods_require_login(opc):
    async with Client(url(opc)) as c:
        ns = await c.get_namespace_index(NS_INST)
        ctl = c.get_node(f"ns={ns};s=SAW-1.JobManagement.JobOrderControl")
        with pytest.raises(ua.UaStatusCodeError) as exc:
            await ctl.call_method(f"{ns}:Store", "WO00099", "")
        assert exc.value.code == ua.StatusCodes.BadUserAccessDenied
    c = Client(url(opc))
    c.set_user("collector")
    c.set_password("pw")
    async with c:
        ctl = c.get_node(f"ns={ns};s=SAW-1.JobManagement.JobOrderControl")
        assert await ctl.call_method(f"{ns}:Store", "WO00099", "") == 0
