"""P-08/P-09 BACnet/IP: роутер + мережа 2, об'єкти RV/AHU/EF/BOILER, панель FACP-1 тільки читання
(SPEC §8.10–§8.11, A-04, AC-09, AC-15, ТБ-04). Клієнт bacpypes3 на 127.0.0.1 зі своїм портом."""

import asyncio

import pytest
from bacpypes3.apdu import ErrorRejectAbortNack
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.settings import settings as bp_settings
from iot_sim.protocols.bacnet_server import BacnetServer

from tests.protocols.conftest import free_port

ALL = {99, *range(101, 126), 130, 131, 132, 133, 140, 200}


@pytest.fixture
async def bacnet(world):
    bp_settings.route_aware = True  # адреса «2:*@ip:port» — Who-Is у віртуальну мережу через роутер
    port = free_port()
    srv = BacnetServer(world, address=f"127.0.0.1/8:{port}")
    await srv.start()
    cport = free_port()
    client = NormalApplication(
        DeviceObject(
            objectIdentifier=("device", 4000),
            objectName="client",
            vendorIdentifier=999,
            maxApduLengthAccepted=1476,
            segmentationSupported="segmentedBoth",
        ),
        IPv4Address(f"127.0.0.1/8:{cport}"),
    )
    await asyncio.sleep(0.2)
    srv.client = client
    yield srv
    client.close()
    await srv.stop()
    bp_settings.route_aware = False


async def who_is(srv, low=None, high=None):
    """Who-Is крізь роутер: unicast на роутер з DNET 2 (broadcast у віртуальній мережі)."""
    ias = await srv.client.who_is(low, high, address=Address(f"2:*@127.0.0.1:{srv.port}"), timeout=1.5)
    return {ia.iAmDeviceIdentifier[1]: ia for ia in ias}


async def dev(srv, inst):
    return Address(f"2:{inst}@127.0.0.1:{srv.port}")  # станція у vnet 2 через роутер


async def rp(srv, inst, objid, prop="present-value"):
    return await srv.client.read_property(await dev(srv, inst), objid, prop)


async def test_who_is_all_and_range(bacnet):
    found = await who_is(bacnet)
    assert set(found) >= ALL - {99}
    assert {i for i in found if i < 126 and i > 100} == set(range(101, 126))
    rv = await who_is(bacnet, 101, 125)
    assert set(rv) == set(range(101, 126))


async def test_device_object_properties(bacnet):
    found = await who_is(bacnet, 105, 105)
    assert set(found) == {105}
    addr = await dev(bacnet, 105)
    c = bacnet.client
    assert await c.read_property(addr, "device,105", "vendor-name") == "Hoval"
    assert await c.read_property(addr, "device,105", "protocol-revision") == 19
    assert await c.read_property(addr, "device,105", "max-apdu-length-accepted") == 1476
    assert await c.read_property(addr, "device,105", "firmware-revision") == "sim-0.1"
    for inst, vendor in ((130, "VTS"), (131, "VENTS/Systemair"), (140, "Kalvis (emulated)"), (200, "Siemens")):
        a = await dev(bacnet, inst)
        assert await c.read_property(a, f"device,{inst}", "vendor-name") == vendor


async def test_rv05_values_follow_world(bacnet, world):
    world.force("ventilation/units/RV-05/filter_dp_pa", 285.0, hold_s=600)
    world.force("ventilation/units/RV-05/supply_c", 19.5, hold_s=600)
    world.force("ventilation/units/RV-05/filter_extract_dp_pa", 228.0, hold_s=600)
    bacnet.sync()
    assert await rp(bacnet, 105, "analog-input,4") == pytest.approx(285.0)
    assert await rp(bacnet, 105, "analog-input,1") == pytest.approx(19.5)
    assert str(await rp(bacnet, 105, "binary-input,3")) == "active"  # 285 > 250
    assert await rp(bacnet, 105, "analog-input,5") == pytest.approx(0.8 * 285.0, abs=0.5)
    name = await rp(bacnet, 105, "analog-input,4", "object-name")
    assert name == "RV-05_FreshAirFilterDp"
    # AC-09: фільтр повернувся в норму -> AI:4 = 120, BI:3 = 0 після тіка
    world.force("ventilation/units/RV-05/filter_dp_pa", 120.0, hold_s=600)
    world.advance(2)
    assert await rp(bacnet, 105, "analog-input,4") == pytest.approx(120.0)
    assert str(await rp(bacnet, 105, "binary-input,3")) == "inactive"


async def test_units_and_descriptions(bacnet):
    assert str(await rp(bacnet, 101, "analog-input,3", "units")) == "cubic-meters-per-hour"
    assert str(await rp(bacnet, 101, "analog-input,1", "units")) == "degrees-celsius"
    assert str(await rp(bacnet, 101, "analog-input,4", "units")) == "pascals"
    assert await rp(bacnet, 101, "analog-input,1", "cov-increment") == pytest.approx(0.2)
    assert await rp(bacnet, 101, "analog-input,3", "cov-increment") == pytest.approx(50)
    assert "припливу" in await rp(bacnet, 101, "analog-input,1", "description")


async def test_ahu_and_fans_objects(bacnet, world):
    assert await rp(bacnet, 130, "analog-input,9", "object-name") == "AHU-1_RoomPressure"
    assert await rp(bacnet, 130, "binary-input,6", "object-name") == "AHU-1_BoothExtractInterlock"
    assert await rp(bacnet, 131, "analog-value,1", "object-name") == "EF-ELEC_ThermostatSetpoint"
    assert await rp(bacnet, 131, "analog-value,1") == pytest.approx(28.0)
    assert await rp(bacnet, 133, "binary-input,7", "object-name") == "EF-CHG_ChargingActive"
    world.set_flag("charging_active", 1)
    bacnet.sync()
    assert str(await rp(bacnet, 133, "binary-input,7")) == "active"


async def test_boiler_objects(bacnet, world):
    world.force("equipment/BOILER/supply_c", 77.4, hold_s=600)
    world.force("equipment/BOILER/silo_fill", 15.0, hold_s=600)
    world.force("equipment/BOILER/state", 2, hold_s=600)
    bacnet.sync()
    assert await rp(bacnet, 140, "analog-input,1") == pytest.approx(77.4, abs=0.01)
    assert str(await rp(bacnet, 140, "binary-input,5")) == "active"  # silo < 20
    assert str(await rp(bacnet, 140, "binary-input,1")) == "active"
    assert str(await rp(bacnet, 140, "binary-input,2")) == "inactive"
    assert await rp(bacnet, 140, "analog-input,4") == pytest.approx(160.0)
    assert await rp(bacnet, 140, "multi-state-value,1") == 2
    assert await rp(bacnet, 140, "analog-value,1") == pytest.approx(80.0)


async def test_write_ao_priority_and_hold(bacnet, world):
    addr = await dev(bacnet, 101)
    c = bacnet.client
    await c.write_property(addr, "analog-output,1", "present-value", 42.0, priority=8)
    sig = world.signals["ventilation/units/RV-01/heating_valve"]
    assert sig.value == pytest.approx(42.0) and sig.held(world.now())
    assert world.events.since(0, kind="command")[0]
    with pytest.raises(ErrorRejectAbortNack):
        await c.write_property(addr, "analog-output,1", "present-value", 10.0, priority=3)
    with pytest.raises(ErrorRejectAbortNack):  # RO: AI
        await c.write_property(addr, "analog-input,1", "present-value", 1.0)


async def test_write_enable_and_setpoint(bacnet, world):
    addr = await dev(bacnet, 103)
    c = bacnet.client
    await c.write_property(addr, "binary-value,1", "present-value", "inactive", priority=10)
    assert world.flag("bacnet.RV-03.enable") == 0
    assert await rp(bacnet, 103, "analog-input,3") == pytest.approx(0.0)  # одразу, без тіка
    assert str(await rp(bacnet, 103, "binary-input,1")) == "inactive"
    await c.write_property(addr, "analog-value,1", "present-value", 19.5, priority=16)
    assert world.signals["ventilation/units/RV-03/setpoint_day_c"].value == pytest.approx(19.5)
    await c.write_property(addr, "multi-state-value,1", "present-value", 4, priority=9)
    assert world.signals["ventilation/units/RV-03/mode"].value == 4
    assert world.drain("hvac")


async def test_facp_lsz_states_and_layout(bacnet, world):
    addr = await dev(bacnet, 200)
    c = bacnet.client
    assert await c.read_property(addr, "life-safety-zone,0", "object-name") == "FACP-1_Panel"
    assert await c.read_property(addr, "life-safety-zone,14", "object-name") == "FA-CNC"
    assert await c.read_property(addr, "life-safety-zone,35", "object-name") == "FA-OFFICE"
    assert str(await c.read_property(addr, "life-safety-zone,14", "present-value")) == "quiet"
    world.force("fire/groups/FA-CNC/state", "test-alarm", hold_s=600)
    world.force("fire/totals/state", 9, hold_s=600)
    world.set_flag("fire.trigger", "2.CNC.05")
    bacnet.sync()
    assert str(await c.read_property(addr, "life-safety-zone,14", "present-value")) == "test-alarm"
    assert str(await c.read_property(addr, "life-safety-zone,0", "present-value")) == "test-alarm"
    assert str(await c.read_property(addr, "life-safety-point,21405", "present-value")) == "test-alarm"
    assert str(await c.read_property(addr, "life-safety-point,21404", "present-value")) == "quiet"
    assert await c.read_property(addr, "life-safety-point,21405", "object-name") == "2.CNC.05"
    assert await c.read_property(addr, "life-safety-point,10101", "object-name") == "1.RCV-1.01"


async def test_facp_piv_contamination_and_counters(bacnet, world):
    addr = await dev(bacnet, 200)
    c = bacnet.client
    world.force("fire/groups/FA-FAC/dust", 82.0, hold_s=600)
    world.force("fire/totals/alarms", 2, hold_s=600)
    world.force("fire/totals/sounders_active", 1, hold_s=600)
    world.force("fire/loops/2/state", 1, hold_s=600)
    bacnet.sync()
    assert await c.read_property(addr, "positive-integer-value,21607", "present-value") == 82
    v = await c.read_property(addr, "positive-integer-value,21405", "present-value")
    assert 5 <= v <= 30
    assert await c.read_property(addr, "positive-integer-value,1", "present-value") == 2
    assert str(await c.read_property(addr, "binary-value,10", "present-value")) == "active"
    assert str(await c.read_property(addr, "binary-value,2", "present-value")) == "active"
    assert str(await c.read_property(addr, "binary-value,1", "present-value")) == "inactive"
    assert await c.read_property(addr, "multi-state-value,1", "object-name") == "FACP-1_SystemState"


async def test_facp_is_read_only(bacnet):
    """ТБ-04: WriteProperty -> write-access-denied; ReinitializeDevice/DCC -> service-request-denied."""
    addr = await dev(bacnet, 200)
    c = bacnet.client
    for objid, value in (
        ("life-safety-zone,14", "alarm"),
        ("binary-value,10", "inactive"),
        ("positive-integer-value,1", 5),
        ("multi-state-value,1", 2),
    ):
        with pytest.raises(ErrorRejectAbortNack) as ei:
            await c.write_property(addr, objid, "present-value", value, priority=8)
        assert "write-access-denied" in str(ei.value)
    from bacpypes3.apdu import (
        DeviceCommunicationControlRequest,
        ReinitializeDeviceRequest,
    )

    for req in (
        ReinitializeDeviceRequest(reinitializedStateOfDevice="coldstart", destination=addr),
        DeviceCommunicationControlRequest(enableDisable="disable", destination=addr),
    ):
        with pytest.raises(ErrorRejectAbortNack) as ei:
            await c.request(req)
        assert "service-request-denied" in str(ei.value)


async def test_cov_notification_on_ai_change(bacnet, world):
    """SubscribeCOV на AI: початкова нотифікація, далі — при зміні більшій за cov-increment (0,2)."""
    addr = await dev(bacnet, 102)
    world.force("ventilation/units/RV-02/supply_c", 19.0, hold_s=600)
    bacnet.sync()
    oid = ObjectIdentifier("analog-input,1")
    async with bacnet.client.change_of_value(addr, oid, 7, False, 60) as scm:
        first = await asyncio.wait_for(scm.get(), 3)  # початкова нотифікація
        assert str(first.propertyIdentifier) == "present-value"
        while not scm.queue.empty():
            scm.queue.get_nowait()
        world.force("ventilation/units/RV-02/supply_c", 25.0, hold_s=600)
        world.advance(1)  # тік -> sync -> COV
        got = []
        for _ in range(3):
            pv = await asyncio.wait_for(scm.get(), 3)
            got.append(pv)
            if str(pv.propertyIdentifier) == "present-value":
                break
        assert any(str(g.propertyIdentifier) == "present-value" for g in got)


async def test_facp_302_lsp_objects_and_names(bacnet):
    """AC-66: 302 LSP (222 + 36 ручних + 41 оповіщувач + 3 полум'я); PIV лише для 222 сповіщувачів."""
    c = bacnet.client
    addr = await dev(bacnet, 200)
    n = await c.read_property(addr, "device,200", "object-list", array_index=0)
    ol = [await c.read_property(addr, "device,200", "object-list", array_index=i) for i in range(1, n + 1)]
    assert sum(1 for o in ol if str(o[0]) == "life-safety-point") == 302
    assert sum(1 for o in ol if str(o[0]) == "positive-integer-value") == 222 + 3
    for inst, name in ((19001, "1.MCP.01"), (29113, "2.SND.13"), (29201, "2.FLM.01"), (49009, "4.MCP.09")):
        assert await c.read_property(addr, f"life-safety-point,{inst}", "object-name") == name
        assert str(await c.read_property(addr, f"life-safety-point,{inst}", "present-value")) == "quiet"


async def test_object_list_full_read_segmented(bacnet):
    """ТК-08/AC-61: object-list dev 200 цілком (сегментована відповідь); клієнт має оголосити сегментацію
    (``client.asap.device_object`` — у bacpypes3 для клієнтського Application не виставляється сам)."""
    c = bacnet.client
    c.asap.device_object = c.device_object
    ol = await rp(bacnet, 200, "device,200", "object-list")
    assert sum(1 for o in ol if str(o[0]) == "life-safety-point") == 302
    assert len(await rp(bacnet, 105, "device,105", "object-list")) > 10
