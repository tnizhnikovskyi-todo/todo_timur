"""AC-81, AC-97, AC-101 (bacnet): плагін bacnet_ip проти тестового пристрою bacpypes3 (device 140)."""
from __future__ import annotations

import asyncio
import dataclasses
import hashlib

import pytest

from collector.core.errors import ConnectError, NotSupported, PollError, WriteError
from collector.plugins._common import canonical_json
from collector.plugins.bacnet_ip import RO_SERVICES, BacnetIpPlugin, normalize_object, service_name
from collector.util.timeutil import to_iso_z

from . import mk_signal, mk_source

pytestmark = pytest.mark.filterwarnings("ignore")


def _a(obj, inst, **kw):
    return {"object": obj, "instance": inst, "mode": "poll", **kw}


def _sig(code, address, kind="gauge", period_s=30, states=None, **kw):
    sg = mk_signal(code, kind=kind, address=address, period_s=period_s, **kw)
    return dataclasses.replace(sg, states=states) if states else sg


async def _plug(dev, make_ctx, signals, clock=None, **params):
    box = make_ctx(clock=clock)
    src = mk_source("BAC-T-140", "bacnet_ip", signals,
                    params={"host": "127.0.0.1", "port": dev.port, "device": 140, "timeout_s": 1, **params})
    p = BacnetIpPlugin(src, box.ctx)
    await p.connect()
    return p, box


async def _until(cond, timeout=1.5):
    end = asyncio.get_running_loop().time() + timeout
    while not cond() and asyncio.get_running_loop().time() < end:
        await asyncio.sleep(0.02)
    return cond()


def _basic():
    return [
        _sig("equipment/B/supply_c", _a("AI", 1)),
        _sig("equipment/B/ai3", _a("analog-input", 3)),
        _sig("equipment/B/mode", _a("MSV", 1), kind="state", states=["standby", "K1", "K1+K2", "fault"]),
        _sig("equipment/B/run", _a("BI", 1), kind="state"),
        _sig("fire/groups/FA-CUT/state", _a("LSZ", 12), kind="state"),
        _sig("equipment/B/piv", _a("PIV", 1)),
    ]


async def test_rpm_poll_values(bacnet_device, make_ctx):
    p, box = await _plug(bacnet_device, make_ctx, _basic())
    assert box.allowed == ["127.0.0.1"]
    out = {r.code.rsplit("/", 1)[1]: r for r in await p.poll(_basic())}
    assert out["supply_c"].value == pytest.approx(77.4, abs=1e-3)
    assert out["ai3"].value == pytest.approx(61.1, abs=1e-3)
    assert out["mode"].text == "K1"
    assert out["run"].text == "on"
    assert out["state"].text == "quiet"
    assert out["piv"].value == 17.0 and all(r.q == "good" for r in out.values())
    assert bacnet_device.services.count("read-property-multiple") == 1
    assert p.health().state == "online"
    await p.disconnect()


async def test_piv_value(bacnet_device, make_ctx):
    sg = _sig("equipment/B/piv", {"object": "PIV", "instance": 3})
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    (r,) = await p.poll([sg])
    assert r.value == 17.0 and r.q == "good"
    await p.disconnect()


async def test_address_scale_offset(bacnet_device, make_ctx):
    sg = _sig("equipment/B/t", _a("AI", 3, scale=0.1, offset=-5), scale=7.0)
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    bacnet_device.set_pv("AI:3", 611)
    (r,) = await p.poll([sg])
    assert r.value == pytest.approx(56.1, abs=1e-3)  # signal.scale (7.0) застосовує ядро, не плагін
    await p.disconnect()


async def test_status_flags_quality(bacnet_device, make_ctx):
    sg = _sig("equipment/B/supply_c", _a("AI", 1))
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    bacnet_device.set_flags("AI:1", fault=True)
    assert (await p.poll([sg]))[0].q == "uncertain"
    bacnet_device.set_flags("AI:1", in_alarm=True)
    assert (await p.poll([sg]))[0].q == "uncertain"
    bacnet_device.set_flags("AI:1", out_of_service=True)
    assert (await p.poll([sg]))[0].q == "bad"
    bacnet_device.set_flags("AI:1")
    assert (await p.poll([sg]))[0].q == "good"
    await p.disconnect()


async def test_reliability_and_missing_object(bacnet_device, make_ctx):
    a = _sig("equipment/B/a", _a("AI", 1, check_reliability=True))
    gone = _sig("equipment/B/gone", _a("AI", 99))
    p, _ = await _plug(bacnet_device, make_ctx, [a, gone])
    ra, rg = await p.poll([a, gone])
    assert ra.q == "good" and rg.q == "bad" and rg.value is None
    await p.disconnect()


async def test_rpm_falls_back_to_read_property(bacnet_device, make_ctx):
    bacnet_device.reject_rpm = True
    sigs = _basic()[:2]
    p, _ = await _plug(bacnet_device, make_ctx, sigs)
    out = await p.poll(sigs)
    assert out[0].value == pytest.approx(77.4, abs=1e-3)
    assert bacnet_device.count("read-property") >= 2
    await p.disconnect()


async def test_rpm_false_uses_read_property(bacnet_device, make_ctx):
    sig = _sig("equipment/B/supply_c", _a("AI", 1))
    p, _ = await _plug(bacnet_device, make_ctx, [sig], rpm=False)
    assert (await p.poll([sig]))[0].value == pytest.approx(77.4, abs=1e-3)
    assert bacnet_device.count("read-property-multiple") == 0 and bacnet_device.count("read-property") >= 1
    await p.disconnect()


async def test_rpm_max_chunks(bacnet_device, make_ctx):
    sigs = [_sig("equipment/B/a", _a("AI", 1)), _sig("equipment/B/b", _a("AI", 2))]
    p, _ = await _plug(bacnet_device, make_ctx, sigs, rpm_max=2)  # 4 пари (pv + status-flags) -> 2 запити
    await p.poll(sigs)
    assert bacnet_device.count("read-property-multiple") == 2
    await p.disconnect()


async def test_cov_notification(bacnet_device, make_ctx):
    sg = _sig("equipment/B/supply_c", {"object": "AI", "instance": 1, "mode": "cov"})
    p, box = await _plug(bacnet_device, make_ctx, [sg])
    assert await _until(lambda: "subscribe-cov" in bacnet_device.services)
    assert await _until(lambda: p._cov_active == {sg.code})
    assert box.metrics.bacnet_cov_active.labels("BAC-T-140")._value.get() == 1
    box.readings.clear()
    bacnet_device.set_pv("AI:1", 78.0)
    assert await _until(lambda: any(r.value == pytest.approx(78.0) for r in box.readings), 1.0)
    assert p.health().stats["cov_notifications"] >= 1
    await p.disconnect()
    assert box.metrics.bacnet_cov_active.labels("BAC-T-140")._value.get() == 0


async def test_cov_rejected_fallback_poll(bacnet_device, make_ctx):
    bacnet_device.reject_cov = True
    sg = _sig("equipment/B/supply_c", {"object": "AI", "instance": 1, "mode": "cov"})
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    assert await _until(lambda: sg.code in p._cov_failed)
    (r,) = await p.poll([sg])  # опитується з period_s
    assert r.value == pytest.approx(77.4, abs=1e-3)
    await p.disconnect()


async def test_cov_control_read_emits(bacnet_device, make_ctx, vclock):
    sg = _sig("equipment/B/supply_c", {"object": "AI", "instance": 1, "mode": "cov"}, period_s=30)
    p, box = await _plug(bacnet_device, make_ctx, [sg])
    assert await _until(lambda: p._cov_active == {sg.code} and box.readings)  # початкове COV-сповіщення
    assert bacnet_device.count("read-property-multiple") == 0
    for _ in range(9):  # 9 x 30 c = 270 c < cov_check_s = 300 c: планувальник кличе poll, запитів немає
        vclock.advance(30)
        assert await p.poll([sg]) == []
    assert bacnet_device.count("read-property-multiple") == 0
    vclock.advance(30)  # 300 c
    out = await p.poll([sg])
    assert len(out) == 1 and out[0].ts == vclock.now() and out[0].value == pytest.approx(77.4, abs=1e-3)
    assert bacnet_device.count("read-property-multiple") == 1
    vclock.advance(30)
    assert await p.poll([sg]) == []
    assert p.cov_check_s(30) == 300 and p.cov_check_s(60) == 600
    await p.disconnect()


async def test_write_priority(bacnet_device, make_ctx):
    sg = _sig("equipment/B/valve", _a("AO", 1, read_priority_array=True), write=True)
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    assert await p.write(sg, 80.0, None) == "written 80.0 @prio 8"
    assert bacnet_device.get_pv("AO:1") == 80.0
    assert bacnet_device.priority("AO:1", 8).real == 80.0
    (r,) = await p.poll([sg])
    assert r.value == 80.0 and "analog-output,1" in p._pa_cache
    assert await p.write(sg, None, "null") == "written null @prio 8"
    assert bacnet_device.get_pv("AO:1") == 0.0
    await p.disconnect()


async def test_write_ro_object_error(bacnet_device, make_ctx):
    sg = _sig("equipment/B/supply_c", _a("AI", 1), write=True)
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    with pytest.raises(WriteError, match="write-access-denied"):
        await p.write(sg, 5.0, None)
    await p.disconnect()


async def test_whois_not_found(bacnet_device, make_ctx):
    box = make_ctx()
    src = mk_source("BAC-X", "bacnet_ip", [], params={"host": "127.0.0.1", "port": bacnet_device.port,
                                                    "device": 999, "timeout_s": 1})
    with pytest.raises(ConnectError, match=r"Who-Is: device 999 not found"):
        await BacnetIpPlugin(src, box.ctx).connect()


async def test_msv_write_reverse_map(bacnet_device, make_ctx):
    mp = {"1": "standby", "2": "K1", "3": "K1+K2", "4": "fault"}
    sg = _sig("equipment/B/mode", _a("MSV", 1, map=mp), kind="state", write=True)
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    assert await p.write(sg, 1.0, "K1") == "written 2 @prio 8"  # value команди ігнорується
    assert bacnet_device.get_pv("MSV:1") == 2
    (r,) = await p.poll([sg])
    assert r.text == "K1"
    with pytest.raises(WriteError, match="boost"):
        await p.write(sg, None, "boost")
    await p.disconnect()


async def test_msv_write_states_1_based(bacnet_device, make_ctx):
    sg = _sig("equipment/B/mode", _a("MSV", 1), kind="state", write=True,
              states=["standby", "K1", "K1+K2", "fault"])
    p, _ = await _plug(bacnet_device, make_ctx, [sg])
    assert await p.write(sg, None, "K1+K2") == "written 3 @prio 8"
    assert bacnet_device.get_pv("MSV:1") == 3
    before = bacnet_device.count("write-property")
    with pytest.raises(WriteError):
        await p.write(sg, None, "boost")
    assert bacnet_device.count("write-property") == before  # без відправки
    await p.disconnect()


# --- read_only (D-07, X-05) ---
def _ro_sigs():
    return [_sig("equipment/B/supply_c", {"object": "AI", "instance": 1}),  # mode не задано -> умовч. cov
            _sig("equipment/B/mode", {"object": "MSV", "instance": 1}, kind="state", states=["a", "b", "c", "d"]),
            _sig("fire/groups/FA-CUT/state", {"object": "LSZ", "instance": 12}, kind="state")]


async def test_read_only_no_packet(bacnet_device, make_ctx):
    sigs = _ro_sigs()
    p, _box = await _plug(bacnet_device, make_ctx, sigs, read_only=True)
    for _ in range(3):
        assert len(await p.poll(sigs)) == 3
    with pytest.raises(NotSupported, match="read-only device"):
        await p.write(sigs[0], 1.0, None)
    assert bacnet_device.count("write-property") == 0
    assert not p._cov_tasks and p._cov_active == set()
    forbidden = {"subscribe-cov", "write-property", "acknowledge-alarm", "life-safety-operation",
                 "device-communication-control", "reinitialize-device"}
    assert set(bacnet_device.services) <= {"who-is", "read-property-multiple"}
    assert not forbidden & set(bacnet_device.services)
    await p.disconnect()


async def test_read_only_services_whitelist(bacnet_device, make_ctx):
    sigs = _ro_sigs()
    p, box = await _plug(bacnet_device, make_ctx, sigs, read_only=True)
    n = len(bacnet_device.services)
    with pytest.raises(NotSupported, match="read-only device: subscribe-cov"):
        await p.bapp._request(p, "SubscribeCOV", p.addr, "analog-input,1", 1, False, 60)
    assert box.metrics.bacnet_ro_blocked.labels("BAC-T-140", "subscribe-cov")._value.get() == 1
    for svc in ("write-property", "WritePropertyMultiple", "AcknowledgeAlarm", "LifeSafetyOperation",
                "DeviceCommunicationControl", "ReinitializeDevice", "AtomicWriteFile", "CreateObject"):
        with pytest.raises(NotSupported, match="read-only device"):
            await p.bapp._request(p, svc)
    assert len(bacnet_device.services) == n  # жодного пакета
    assert p.health().stats["ro_blocked"] == 9
    assert RO_SERVICES == {"who-is", "read-property", "read-property-multiple"}
    await p.disconnect()


# --- події (X-05) ---
def _ev_src(**params):
    return mk_source("BAC-T-140", "bacnet_ip", _ro_sigs(), params={"read_only": True, **params})


async def test_event_relay_life_safety(bacnet_device, make_ctx, vclock):
    sigs = _ro_sigs()
    p, box = await _plug(bacnet_device, make_ctx, sigs, read_only=True)
    await p.poll(sigs)  # LSZ:12 = quiet
    n = len(bacnet_device.services)
    msg = "Тест: сповіщувач 2.CNC.05, Присадка"
    await bacnet_device.send_event(p.bapp.local_port, message=msg)
    assert await _until(lambda: len(box.events) == 1)
    ev = box.events[0]
    payload = {"device": 140, "object": "LSZ", "instance": 12, "event_type": "change-of-life-safety",
               "from_state": "quiet", "to_state": "test-alarm", "mode": "on", "message_text": msg,
               "notification_class": 1, "priority": 1, "ack_required": False, "ts": to_iso_z(vclock.now())}
    assert ev.route == "bacnet_event" and ev.remote == "BAC-T-140" and ev.headers == {} and ev.payload == payload
    assert ev.ts == vclock.now()
    assert ev.event_id == hashlib.sha256(("bacnet_event\nBAC-T-140\n" + canonical_json(payload)).encode()).hexdigest()
    assert len(bacnet_device.services) == n  # відповідних пакетів до пристрою немає
    assert box.metrics.bacnet_events.labels("BAC-T-140")._value.get() == 1
    await p.disconnect()


async def test_event_out_of_range(bacnet_device, make_ctx):
    p, box = await _plug(bacnet_device, make_ctx, _ro_sigs(), read_only=True)
    long_msg = "x" * 600
    await bacnet_device.send_event(p.bapp.local_port, obj=("analog-input", 1), event_type="out-of-range",
                                   from_state="normal", to_state="high-limit", message=long_msg)
    assert await _until(lambda: len(box.events) == 1)
    pl = box.events[0].payload
    assert pl["object"] == "AI" and pl["event_type"] == "out-of-range"
    assert pl["from_state"] == "normal" and pl["to_state"] == "high-limit" and "mode" not in pl
    assert len(pl["message_text"]) == 500
    await p.disconnect()


async def test_event_ignored_unknown_or_disabled(bacnet_device, make_ctx):
    p, box = await _plug(bacnet_device, make_ctx, _ro_sigs(), read_only=True)
    await bacnet_device.send_event(p.bapp.local_port, device=999)
    assert await _until(
        lambda: box.metrics.bacnet_events_ignored.labels("unknown_device")._value.get() == 1)
    assert box.events == []
    await p.disconnect()
    p2, box2 = await _plug(bacnet_device, make_ctx, _ro_sigs(), read_only=True, events=False)
    await bacnet_device.send_event(p2.bapp.local_port)
    assert await _until(lambda: box2.metrics.bacnet_events_ignored.labels("disabled")._value.get() == 1)
    assert box2.events == []
    await p2.disconnect()


# --- розбір адрес/валідація (без мережі) ---
def test_normalize_and_service_names():
    assert normalize_object("AI") == "analog-input" and normalize_object("PIV") == "positive-integer-value"
    assert normalize_object("life-safety-zone") == "life-safety-zone"
    assert service_name("SubscribeCOV") == "subscribe-cov" and service_name("who_is") == "who-is"
    assert service_name("WritePropertyMultiple") == "write-property-multiple"
    assert service_name("ReadPropertyMultiple") == "read-property-multiple"


def test_effective_mode(make_ctx):
    box = make_ctx()
    sigs = [_sig("equipment/B/a", {"object": "AI", "instance": 1}), _sig("equipment/B/b", {"object": "AV", "instance": 1}),
            _sig("equipment/B/c", {"object": "PIV", "instance": 1}), _sig("equipment/B/d", {"object": "MSV", "instance": 1}),
            _sig("equipment/B/e", {"object": "AI", "instance": 2, "mode": "poll"})]
    p = BacnetIpPlugin(mk_source("B", "bacnet_ip", sigs, params={"host": "h", "device": 1}), box.ctx)
    assert [s.mode for s in p._specs.values()] == ["cov", "poll", "poll", "cov", "poll"]
    ro = BacnetIpPlugin(mk_source("B", "bacnet_ip", sigs, params={"host": "h", "device": 1, "read_only": True}), box.ctx)
    assert {s.mode for s in ro._specs.values()} == {"poll"} and ro.events is True
    assert BacnetIpPlugin(mk_source("B", "bacnet_ip", sigs, params={"host": "h", "device": 1}), box.ctx).events is False


def test_validate():
    ok = mk_source("B", "bacnet_ip", [mk_signal("equipment/a/b", address={"object": "AI", "instance": 1, "device": 140})],
                   params={"host": "iot-sim", "port": 47808, "device": 140, "network": 2, "read_only": True})
    assert BacnetIpPlugin.validate(ok) == []
    bad = mk_source("B", "bacnet_ip", [
        mk_signal("equipment/a/b", address={"object": "XX", "instance": 1}),
        mk_signal("equipment/a/c", address={"object": "AI", "instance": 9999999}),
        mk_signal("equipment/a/d", address={"object": "AI", "instance": 1, "device": 5}, write=True),
    ], params={"host": "h", "device": 140, "read_only": True, "rpm_max": 500})
    text = "\n".join(BacnetIpPlugin.validate(bad))
    assert "object" in text and "instance" in text and "params.device" in text and "rpm_max" in text
    assert "read_only" in text


async def test_poll_not_connected(make_ctx):
    p = BacnetIpPlugin(mk_source("B", "bacnet_ip", [], params={"host": "h", "device": 1}), make_ctx().ctx)
    with pytest.raises(PollError):
        await p.poll([])
