"""P-11: Axis LPV push (SPEC §8.13.2; AC-18, AC-53, AC-54)."""
import asyncio
import json
from datetime import datetime

import httpx
import pytest
from iot_sim.core.outbound import OutboundDenied, OutboundGuard
from iot_sim.protocols.lpr_push import LprPusher, build_axis_payload

URL = "http://collector.test/f3d/lpr"


class Recorder:
    def __init__(self, fail_first=0, status=200):
        self.calls = []
        self.fail_first = fail_first
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if len(self.calls) <= self.fail_first:
            raise httpx.ConnectError("refused")
        return httpx.Response(self.status, json={"received": True})


def make(world, rec, **kw):
    client = httpx.AsyncClient(transport=httpx.MockTransport(rec))
    sleeps = []

    async def sleep(s):
        sleeps.append(s)

    p = LprPusher(world, url=URL, client=client, sleep=sleep, **kw)
    p.sleeps = sleeps
    return p


async def settle():
    for _ in range(20):
        await asyncio.sleep(0)


def test_build_axis_payload_example():
    ts = datetime.fromisoformat("2026-10-14T08:15:05.507+03:00")
    body = build_axis_payload({"camera": "CAM-05", "plate": "AA4512KT", "state": "new",
                               "booking": {"batch": "BATCH/OUT/00004", "dock": "DOCK-E2", "partner": "Меблі Дім (демо)"}},
                              ts, counter=2117397)
    assert body["capture_timestamp"] == body["frame_timestamp"] == "1791954905507"
    assert body["capture_ts"] == "1791954905507000000" and body["datetime"] == "20261014 081505507"
    assert body["plateText"] == "AA4512KT" and body["plateUnicode"] == "АА4512КТ"
    assert (body["plateList"], body["plateListMode"]) == ("f3d_bookings", "allow")
    assert body["plateListDescription"] == "BATCH/OUT/00004 DOCK-E2 Меблі Дім (демо)"
    assert (body["GEOtarget"], body["carMoveDirection"], body["sensorProviderID"]) == ("GATE-W", "in", "CAM-05")
    assert body["packetCounter"] == "2117397" and body["camera_info"]["ProdShortName"] == "AXIS P1488-LE"
    assert all(isinstance(body[k], str) for k in ("plateConfidence", "carState", "roiID"))


def test_no_booking_and_exit_camera():
    ts = datetime.fromisoformat("2026-10-14T08:15:05+03:00")
    body = build_axis_payload({"camera": "CAM-06", "plate": "AA1234KT", "state": "lost", "booking": None}, ts)
    assert (body["plateList"], body["plateListMode"], body["plateListDescription"]) == ("", "none", "")
    assert (body["GEOtarget"], body["carMoveDirection"], body["carState"]) == ("GATE-E", "out", "lost")


async def test_event_with_lpr_payload_is_posted_json(world):
    rec = Recorder()
    p = make(world, rec)
    await p.start()
    world.events.emit("yard", "в'їзд", device="CAM-05",
                      payload={"lpr": {"camera": "CAM-05", "plate": "AA4512KT", "state": "new", "booking": None}})
    world.events.emit("yard", "без lpr", device="CAM-05", payload={})
    await settle()
    assert len(rec.calls) == 1
    req = rec.calls[0]
    assert req.headers["content-type"] == "application/json" and "authorization" not in req.headers
    assert json.loads(req.content)["plateText"] == "AA4512KT"
    assert p.sent == 1 and p.health()["up"]
    await p.stop()


async def test_full_axis_body_passes_through(world):
    rec = Recorder()
    p = make(world, rec)
    await p.start()
    world.events.emit("yard", "x", payload={"lpr": {"plateText": "ZZ", "carState": "new"}})
    await settle()
    assert json.loads(rec.calls[0].content) == {"plateText": "ZZ", "carState": "new"}
    await p.stop()


async def test_retries_2_5_10_then_error_event(world):
    rec = Recorder(fail_first=99)
    p = make(world, rec)
    ok = await p.deliver({"plateText": "AA1", "sensorProviderID": "CAM-05"})
    assert ok is False and len(rec.calls) == 4 and p.sleeps == [2.0, 5.0, 10.0]
    err = world.events.last("error")
    assert err is not None and err.device == "CAM-05" and "AA1" in err.message and p.failed == 1


async def test_retry_succeeds_on_second_attempt(world):
    rec = Recorder(fail_first=1)
    p = make(world, rec)
    assert await p.deliver({"plateText": "AA1"}) is True
    assert len(rec.calls) == 2 and p.sleeps == [2.0] and world.events.last("error") is None


async def test_http_error_status_is_retried(world):
    rec = Recorder(status=503)
    p = make(world, rec)
    assert await p.deliver({"plateText": "AA1"}) is False and len(rec.calls) == 4


async def test_outbound_guard_blocks_foreign_host(world):
    guard = OutboundGuard("127.0.0.1")
    p = LprPusher(world, url="http://evil.example/x", guard=guard, delays=())
    await p.start()
    assert await p.deliver({"plateText": "AA1"}) is False
    assert guard.denied_total == 1
    with pytest.raises(OutboundDenied):
        guard.check("evil.example")
    await p.stop()


async def test_token_sent_as_x_f3d_token_header(world):
    """ST-2: http_push колектора з `token_ref` чекає `X-F3D-Token` (SPEC §8.7) — інакше 401."""
    rec = Recorder()
    p = make(world, rec, token="tok-0123456789abcdef")
    assert await p.deliver({"plateText": "AA1"}) is True
    req = rec.calls[0]
    assert req.headers["x-f3d-token"] == "tok-0123456789abcdef"
    assert req.headers["content-type"] == "application/json"


async def test_no_token_header_by_default(world):
    rec = Recorder()
    p = make(world, rec)
    assert await p.deliver({"plateText": "AA1"}) is True
    assert "x-f3d-token" not in rec.calls[0].headers


async def test_token_resent_on_every_retry(world):
    rec = Recorder(fail_first=2)
    p = make(world, rec, token="tok-0123456789abcdef")
    assert await p.deliver({"plateText": "AA1"}) is True
    assert [c.headers.get("x-f3d-token") for c in rec.calls] == ["tok-0123456789abcdef"] * 3


def test_settings_read_lpr_push_token_from_env(monkeypatch):
    from iot_sim.config import Settings
    monkeypatch.setenv("SIM_LPR_PUSH_TOKEN", "tok-0123456789abcdef")
    assert Settings(_env_file=None).lpr_push_token == "tok-0123456789abcdef"
    monkeypatch.delenv("SIM_LPR_PUSH_TOKEN")
    assert Settings(_env_file=None).lpr_push_token == ""
