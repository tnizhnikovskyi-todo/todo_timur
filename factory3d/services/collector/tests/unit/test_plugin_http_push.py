"""AC-80: приймач http_push (HttpPushServer + плагін) на aiohttp test client."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import aiohttp
import pytest

from collector.core.errors import ConnectError
from collector.core.scheduler import Emitter
from collector.plugins._common import canonical_json
from collector.plugins.http_push import HttpPushPlugin

from . import mk_signal, mk_source

PAYLOAD = {"sensorProviderID": "CAM-05", "plateText": "AA4512KT", "capture_timestamp": 1791954905507}
SECRETS = {"F3D_HTTP_PUSH_TOKEN_LPR": "tok-lpr", "F3D_HTTP_PUSH_SECRET_LPR": "sec-lpr"}


def _src(**params):
    sg = mk_signal("yard/lpr/CAM-05/plate", kind="event",
                   address={"route": "lpr", "match": {"sensorProviderID": "CAM-05"}, "path": "$.plateText",
                            "ts_path": "$.capture_timestamp"})
    return mk_source("HP", "http_push", [sg], params={"routes": ["lpr"], "allow_ips": ["127.0.0.1"], **params})


async def _setup(make_ctx, buffer, **params):
    emitter = Emitter(buffer, {})
    box = make_ctx(secrets=SECRETS.__getitem__)
    box.ctx.emit_event = emitter.emit_event
    p = HttpPushPlugin(_src(**params), box.ctx)
    await p.connect()
    await p.subscribe()
    return p, emitter


async def _events(emitter, buffer):
    await emitter.flush()
    return [e for _id, e in await buffer.take_events(100)]


async def test_accept_event(http_push_client, make_ctx, buffer):
    p, em = await _setup(make_ctx, buffer)
    resp = await http_push_client.post("/f3d/lpr", json=PAYLOAD)
    assert resp.status == 200 and await resp.json() == {"received": True}
    (ev,) = await _events(em, buffer)
    assert ev.route == "lpr" and ev.remote == "127.0.0.1" and ev.payload == PAYLOAD
    assert ev.ts == datetime.fromtimestamp(1791954905.507, UTC)  # ts_path сигналу маршруту
    assert "authorization" not in ev.headers
    h = p.health()
    assert h.state == "online" and h.stats["requests"] == 1 and h.stats["events"] == 1
    r = await http_push_client.get("/f3d/health")
    assert r.status == 200
    await p.disconnect()
    await buffer.close()


async def test_event_id_dedup(http_push_client, make_ctx, buffer):
    _p, em = await _setup(make_ctx, buffer)
    for _ in range(2):
        assert (await http_push_client.post("/f3d/lpr", json=PAYLOAD)).status == 200
    evs = await _events(em, buffer)
    assert len(evs) == 1
    assert evs[0].event_id == hashlib.sha256(("lpr\n127.0.0.1\n" + canonical_json(PAYLOAD)).encode()).hexdigest()
    await buffer.close()


async def test_event_ts_fallback_to_clock(http_push_client, make_ctx, buffer, vclock):
    _p, em = await _setup(make_ctx, buffer)
    await http_push_client.post("/f3d/lpr", json={"plateText": "X"})
    (ev,) = await _events(em, buffer)
    assert ev.ts == vclock.now()
    await buffer.close()


async def test_ip_denied(http_push_client, make_ctx, buffer):
    p, em = await _setup(make_ctx, buffer, allow_ips=["10.1.2.3", "192.168.0.0/16"])
    assert (await http_push_client.post("/f3d/lpr", json=PAYLOAD)).status == 403
    assert await _events(em, buffer) == []
    assert p.health().stats["rejected_ip"] == 1
    await buffer.close()


async def test_env_allow_ips_union(http_push_client, make_ctx, buffer):
    http_push_client.f3d_server.settings.http_push_allow_ips = ["127.0.0.0/8"]  # F3D_HTTP_PUSH_ALLOW_IPS
    box = make_ctx()
    em = Emitter(buffer, {})
    box.ctx.emit_event = em.emit_event
    p = HttpPushPlugin(_src(allow_ips=["10.1.2.3"]), box.ctx)
    await p.connect()
    await p.subscribe()
    assert (await http_push_client.post("/f3d/lpr", json=PAYLOAD)).status == 200
    await buffer.close()


async def test_secret_path(http_push_client, make_ctx, buffer):
    _p, em = await _setup(make_ctx, buffer, secret_ref="F3D_HTTP_PUSH_SECRET_LPR")
    assert (await http_push_client.post("/f3d/lpr", json=PAYLOAD)).status == 404
    assert (await http_push_client.post("/f3d/lpr/wrong", json=PAYLOAD)).status == 404
    assert (await http_push_client.post("/f3d/lpr/sec-lpr", json=PAYLOAD)).status == 200
    assert len(await _events(em, buffer)) == 1
    await buffer.close()


async def test_token_header(http_push_client, make_ctx, buffer):
    _p, em = await _setup(make_ctx, buffer, token_ref="F3D_HTTP_PUSH_TOKEN_LPR")
    assert (await http_push_client.post("/f3d/lpr", json=PAYLOAD)).status == 401
    bad = await http_push_client.post("/f3d/lpr", json=PAYLOAD, headers={"X-F3D-Token": "nope"})
    assert bad.status == 401
    ok = await http_push_client.post("/f3d/lpr", json=PAYLOAD, headers={"X-F3D-Token": "tok-lpr"})
    assert ok.status == 200
    bearer = await http_push_client.post("/f3d/lpr", json={**PAYLOAD, "n": 2},
                                         headers={"Authorization": "Bearer tok-lpr"})
    assert bearer.status == 200
    evs = await _events(em, buffer)
    assert len(evs) == 2 and all("authorization" not in e.headers for e in evs)
    await buffer.close()


async def test_413_415_400(http_push_client, make_ctx, buffer):
    _p, em = await _setup(make_ctx, buffer)
    big = b"{" + b" " * (1024 * 1024 - 1) + b"}"  # 1 МБ + 1 байт
    assert len(big) == 1024 * 1024 + 1
    r = await http_push_client.post("/f3d/lpr", data=big, headers={"Content-Type": "application/json"})
    assert r.status == 413
    r = await http_push_client.post("/f3d/lpr", data=b"hello", headers={"Content-Type": "text/plain"})
    assert r.status == 415
    assert (await http_push_client.post("/f3d/lpr", json=[1, 2])).status == 400
    r = await http_push_client.post("/f3d/lpr", data=b"{bad", headers={"Content-Type": "application/json"})
    assert r.status == 400
    assert await _events(em, buffer) == []
    await buffer.close()


async def test_chunked_body_limit(http_push_client, make_ctx, buffer):
    _p, _em = await _setup(make_ctx, buffer, max_body_kb=1)

    async def gen():
        for _ in range(3):
            yield b" " * 600

    r = await http_push_client.post("/f3d/lpr", data=gen(), headers={"Content-Type": "application/json"})
    assert r.status == 413
    await buffer.close()


async def test_unknown_route(http_push_client, make_ctx, buffer):
    _p, _em = await _setup(make_ctx, buffer)
    assert (await http_push_client.post("/f3d/unknown", json=PAYLOAD)).status == 404
    await buffer.close()


async def test_multipart_json_part(http_push_client, make_ctx, buffer):
    _p, em = await _setup(make_ctx, buffer)
    form = aiohttp.FormData()
    form.add_field("event", json.dumps(PAYLOAD), content_type="application/json")
    form.add_field("image", b"\xff\xd8\xff\xe0" + bytes(range(256)) * 4, filename="p.jpg",
                   content_type="image/jpeg")
    r = await http_push_client.post("/f3d/lpr", data=form)
    assert r.status == 200
    (ev,) = await _events(em, buffer)
    assert ev.payload == PAYLOAD
    form2 = aiohttp.FormData()
    form2.add_field("image", b"\xff\xd8", filename="p.jpg", content_type="image/jpeg")
    assert (await http_push_client.post("/f3d/lpr", data=form2)).status == 400
    await buffer.close()


async def test_duplicate_route_and_missing_secret(http_push_client, make_ctx, buffer):
    p, _ = await _setup(make_ctx, buffer)
    p2 = HttpPushPlugin(_src(), make_ctx().ctx)
    await p2.connect()
    with pytest.raises(ConnectError, match="already registered"):
        await p2.subscribe()
    p3 = HttpPushPlugin(_src(token_ref="F3D_NOPE"), make_ctx(secrets=SECRETS.__getitem__).ctx)
    await p3.connect()
    with pytest.raises(ConnectError, match="F3D_NOPE"):
        await p3.subscribe()
    await p.disconnect()
    assert (await http_push_client.post("/f3d/lpr", json=PAYLOAD)).status == 404
    await buffer.close()


async def test_connect_without_server(make_ctx):
    from collector.core.http_push import HttpPushServer

    HttpPushServer._instance = None
    p = HttpPushPlugin(_src(), make_ctx().ctx)
    with pytest.raises(ConnectError):
        await p.connect()


def test_validate():
    assert HttpPushPlugin.validate(_src()) == []
    bad = mk_source("HP", "http_push", [
        mk_signal("yard/a/b", address={"route": "other", "path": "$.x"}),
        mk_signal("yard/a/c", address={"route": "lpr", "path": "x"}),
    ], params={"routes": ["lpr"], "secret": "x", "token_ref": "lower"})
    text = "\n".join(HttpPushPlugin.validate(bad))
    assert "other" in text and "path" in text and "секрети" in text and "token_ref" in text
