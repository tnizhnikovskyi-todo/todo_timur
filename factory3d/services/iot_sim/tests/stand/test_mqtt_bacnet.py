"""ТК-04 (MQTT-телематика), ТК-03 і ТК-08 (BACnet: вентиляція/котельня, пожежна панель), ТБ-04 (BACnet). AC-08/15/38/40/56/61/64/66."""

import asyncio
import json
import time

import paho.mqtt.client as mqtt
import pytest
from bacpypes3.apdu import (
    DeviceCommunicationControlRequest,
    ErrorRejectAbortNack,
    ReinitializeDeviceRequest,
)
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.settings import settings as bp_settings

from .conftest import docker
from .helpers import NOON

ALL = {99, *range(101, 126), 130, 131, 132, 133, 140, 200}


# ------------------------------------------------------------------ MQTT
def _mosq_ip():
    out = docker(
        "inspect",
        "iot_sim-mosquitto-1",
        "-f",
        "{{range $k,$v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}",
    )
    return next(i.split("=")[1] for i in out.split() if i.split("=")[0].endswith("f3d_sim"))


def _collect(seconds, user="sim", password="simpass"):
    got = []
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.username_pw_set(user, password)
    c.on_message = lambda cl, ud, m: got.append((m.topic, m.payload, m.retain))
    c.on_connect = lambda cl, ud, fl, rc, pr=None: cl.subscribe("f3d/mobile/#", qos=1)
    c.connect(_mosq_ip(), 1883)
    c.loop_start()
    time.sleep(seconds)
    c.loop_stop()
    c.disconnect()
    return got


def test_tk04_mqtt_telematics(api):
    api.post("/time", {"set": NOON, "factor": 10})
    api.scenario("shift")
    r = api.post("/scenario/battery_low/start", {"params": {"device": "FL-2", "level_pct": 18}})
    assert r.status_code == 201, r.text
    got = _collect(45)  # ТК-04: 3 хв → скорочено до 45 с реального при factor=10
    codes = {t.split("/")[2] for t, _, _ in got if t.endswith("/telemetry")}
    assert len(codes) >= 8, codes  # AC-40
    for t, p, _ in got:
        json.loads(p)  # JSON валідний
    st = [(t, json.loads(p), ret) for t, p, ret in got if t.endswith("/status") and "_all" not in t]
    assert st and all(ret for _, _, ret in st) and all(b["online"] for _, b, _ in st)
    states = [json.loads(p)["state"] for t, p, _ in got if t.endswith("/FL-2/telemetry")]
    assert {"to_charge", "charging"} & set(states), set(states)  # AC-08 (рух у зарядну)
    api.post("/device/FL-3/fault", {"reason": "comm"})
    got2 = _collect(8)
    last = [json.loads(p) for t, p, _ in got2 if t == "f3d/mobile/FL-3/status"]
    assert last and last[-1]["online"] is False
    assert _collect(2, user="sim", password="bad") == []  # ТБ: лише аутентифіковані


# ------------------------------------------------------------------ BACnet
def _gateway(host):
    out = docker("network", "inspect", "iot_sim_f3d_sim", "-f", "{{(index .IPAM.Config 0).Gateway}}")
    return out


@pytest.fixture
async def bac(host, api):
    bp_settings.route_aware = True
    gw = _gateway(host)
    client = NormalApplication(
        DeviceObject(
            objectIdentifier=("device", 4000),
            objectName="client",
            vendorIdentifier=999,
            maxApduLengthAccepted=1476,
            segmentationSupported="segmentedBoth",
        ),
        IPv4Address(f"{gw}/16:47810"),
    )
    await asyncio.sleep(0.3)

    class B:
        c = client
        h = host

        async def who_is(self, lo=None, hi=None):
            ias = await client.who_is(lo, hi, address=Address(f"2:*@{host}:47808"), timeout=3)
            return {ia.iAmDeviceIdentifier[1]: ia for ia in ias}

        def dev(self, inst):
            return Address(f"2:{inst}@{host}:47808")

        async def rp(self, inst, objid, prop="present-value"):
            return await client.read_property(self.dev(inst), objid, prop)

    yield B()
    client.close()
    bp_settings.route_aware = False


async def test_tk03_ventilation_boiler(bac, api):
    api.post("/time", {"set": NOON, "factor": 1})
    found = await bac.who_is()
    assert ALL - {99} <= set(found), ALL - set(found)  # AC-38 (99 — опційно)
    assert isinstance(await bac.rp(105, "analog-input,4"), float)
    # RPM 25 RV ≤ 2 с — через ReadProperty по 25 пристроях
    t0 = time.time()
    await asyncio.gather(*[bac.rp(i, "analog-input,1") for i in range(101, 126)])
    assert time.time() - t0 < 2.5
    # write AO:1 dev 105 = 80 (пріоритет 8): утримується (hold)
    await bac.c.write_property(bac.dev(105), "analog-output,1", "present-value", 80.0, priority=8)
    assert api.sig("ventilation/units/RV-05/heating_valve") == pytest.approx(80.0)
    # write MSV:1 = 7 (ST)
    await bac.c.write_property(bac.dev(105), "multi-state-value,1", "present-value", 7, priority=9)
    await asyncio.sleep(3)
    assert api.sig("ventilation/units/RV-05/mode") == 7
    assert await bac.rp(105, "analog-input,3") == pytest.approx(0.0, abs=0.5)
    assert str(await bac.rp(105, "binary-input,1")) == "inactive"
    # COV на AI:4 dev 105
    api.put("/signals/ventilation/units/RV-05/filter_dp_pa", {"value": 120.0, "hold_s": 120})
    await asyncio.sleep(2)
    async with bac.c.change_of_value(bac.dev(105), ObjectIdentifier("analog-input,4"), 7, False, 60) as scm:
        await asyncio.wait_for(scm.get(), 5)
        while not scm.queue.empty():
            scm.queue.get_nowait()
        api.put("/signals/ventilation/units/RV-05/filter_dp_pa", {"value": 285.0, "hold_s": 120})
        pv = await asyncio.wait_for(scm.get(), 8)
        assert pv is not None
    assert await bac.rp(105, "analog-input,4") == pytest.approx(285.0, abs=1)


async def test_tk08_fire_panel(bac, api):
    api.post("/time", {"set": NOON, "factor": 1})
    assert str(await bac.rp(200, "life-safety-zone,14")) == "quiet"
    r = api.post("/scenario/fire_drill/start", {"params": {"zone": "FA-CNC"}})
    assert r.status_code == 201, r.text
    await asyncio.sleep(4)
    assert str(await bac.rp(200, "life-safety-zone,14")) == "test-alarm"  # AC-15
    assert str(await bac.rp(200, "life-safety-point,21405")) == "test-alarm"
    assert str(await bac.rp(200, "binary-value,10")) == "active"
    # ТБ-04: запис у LSZ/BV/PIV/MSV відхилено, ReinitializeDevice/DCC відхилені
    for objid, value in (
        ("life-safety-zone,14", "alarm"),
        ("binary-value,10", "inactive"),
        ("positive-integer-value,1", 5),
        ("multi-state-value,1", 2),
    ):
        with pytest.raises(ErrorRejectAbortNack) as ei:
            await bac.c.write_property(bac.dev(200), objid, "present-value", value, priority=8)
        assert "write-access-denied" in str(ei.value)
    for req in (
        ReinitializeDeviceRequest(reinitializedStateOfDevice="coldstart", destination=bac.dev(200)),
        DeviceCommunicationControlRequest(enableDisable="disable", destination=bac.dev(200)),
    ):
        with pytest.raises(ErrorRejectAbortNack):
            await bac.c.request(req)
    assert str(await bac.rp(200, "life-safety-zone,14")) == "test-alarm"
    # forms: filter_clogged FA-FAC value=92 → PIV:21607
    api.post("/scenario/fire_drill/stop")
    api.post("/time", {"factor": 60})  # рампа забруднення (ramp_min) — на прискореному часі
    r = api.post("/scenario/filter_clogged/start", {"params": {"device": "FA-FAC", "value": 92}})
    assert r.status_code == 201, r.text
    for _ in range(40):
        piv = await bac.rp(200, "positive-integer-value,21607")
        if piv >= 90:
            break
        await asyncio.sleep(1)
    assert piv >= 90, piv  # AC-61: було 82
    api.post("/time", {"factor": 1})
    # FA-CUT fault sensor → clear → loop
    assert api.post("/device/FA-CUT/fault", {"reason": "sensor"}).status_code == 200
    await asyncio.sleep(3)
    assert str(await bac.rp(200, "life-safety-zone,12")) == "fault"
    assert api.post("/device/FA-CUT/clear").status_code == 200
    assert api.post("/device/FA-CUT/fault", {"reason": "loop"}).status_code == 200
    assert api.post("/device/FA-CUT/fault", {"reason": "spindle"}).status_code in (422, 200)
    assert api.post("/device/FA-CUT/clear").status_code == 200
    assert api.post("/device/PV-ROOF/fault", {"reason": "sensor"}).status_code == 422
    # object-list dev 200: лише LSZ/LSP/PIV/BV/MSV/device (AC-61), 302 LSP (AC-66)
    # object-list цілком: клієнт має оголосити сегментацію (bacpypes3 для клієнтського Application сам не виставляє)
    bac.c.asap.device_object = bac.c.device_object
    ol = await bac.rp(200, "device,200", "object-list")
    types = {str(o[0]) for o in ol}
    assert types <= {
        "device",
        "life-safety-zone",
        "life-safety-point",
        "binary-value",
        "multi-state-value",
        "positive-integer-value",
    }, types
    assert sum(1 for o in ol if str(o[0]) == "life-safety-point") == 302
    for inst, name in ((19001, "1.MCP.01"), (29113, "2.SND.13"), (29201, "2.FLM.01")):
        assert await bac.rp(200, f"life-safety-point,{inst}", "object-name") == name
    ev = api.get("/events", params={"kind": "fire"}).json()["items"]
    assert ev
