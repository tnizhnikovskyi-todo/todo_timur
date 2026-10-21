"""REST цілей верстатів (C-LP-01; SPEC API-26, AC-69…AC-73): ``/api/v1/machines/targets`` на застосунку керування."""

from datetime import UTC, datetime, timedelta

import pytest
from asyncua import Client
from fastapi.testclient import TestClient
from iot_sim.core.machine_targets import real_epoch
from iot_sim.protocols.opcua_server import OpcUaServer

from .test_control_api import AUTH, make

URL = "/api/v1/machines/targets"
NS_INST = "http://todo.ltd/f3d/iot_sim/instances/"


def until(world, seconds=600):
    return datetime.fromtimestamp(real_epoch(world) + seconds, UTC).isoformat().replace("+00:00", "Z")


def sig(world, code):
    return world.signals[code].value


@pytest.fixture
def api(world):
    with TestClient(make(world), headers=AUTH) as c:
        c.world = world
        yield c


def test_token_required_and_rate_limited_like_other_routes(world):
    body = [{"code": "SAW-1", "state": "idle", "until": until(world)}]
    with TestClient(make(world)) as c:
        assert c.post(URL, json=body).status_code == 401
        assert c.get(URL).status_code == 401
        assert c.post(URL, json=body, headers={"Authorization": "Bearer bad"}).json() == {"detail": "invalid token"}
        assert c.post(URL, json=body, headers=AUTH).status_code == 200


def test_post_list_body_and_signals_after_one_tick(api):
    w = api.world
    w.step(10)
    body = [
        {"code": "SAW-3", "state": "working", "reason": None, "until": until(w)},  # демо: був READY
        {"code": "SAW-1", "state": "idle", "reason": "очікує матеріал", "until": until(w)},
        {"code": "SAW-2", "state": "down", "reason": "spindle", "until": until(w)},
        {"code": "NOPE-1", "state": "idle", "until": until(w)},
    ]
    r = api.post(URL, json=body)
    assert r.status_code == 200 and r.json() == {"ok": 3, "unknown": ["NOPE-1"], "expired": []}
    w.step(1)  # один тік — і сигнали, які читає збирач, збігаються з цілями
    assert (
        sig(w, "workcenters/SAW-3/state"),
        sig(w, "workcenters/SAW-1/state"),
        sig(w, "workcenters/SAW-2/state"),
    ) == (
        3,
        2,
        4,
    )
    assert sig(w, "workcenters/SAW-2/alarm") is True and sig(w, "workcenters/SAW-2/event") == "E0421"
    assert api.get("/sim/v1/signals/workcenters/SAW-3/state").json()["value"] == 3  # REST сигналів — те саме
    ev = api.get("/sim/v1/events", params={"device": "SAW-2"}).json()["items"]
    assert any(e["payload"].get("target") and e["payload"]["message_id"] == "E0421" for e in ev)


def test_post_object_body_and_sim_prefix_alias(api):
    w = api.world
    item = {"code": "SAW-1", "state": "down", "until": until(w)}
    assert api.post(URL, json={"targets": [item]}).json()["ok"] == 1
    assert api.post("/sim/v1/machines/targets", json=[dict(item, state="idle")]).json()["ok"] == 1
    assert [t["state"] for t in api.get("/sim/v1/machines/targets").json()["items"]] == ["idle"]


def test_get_lists_targets_with_machine_state(api):
    w = api.world
    api.post(URL, json=[{"code": "SAW-3", "state": "working", "reason": "WH/MO/00231", "until": until(w, 120)}])
    w.step(1)
    data = api.get(URL).json()
    assert data["count"] == 1
    (t,) = data["items"]
    assert t["code"] == "SAW-3" and t["state"] == "working" and t["reason"] == "WH/MO/00231"
    assert t["machine_state"] == "WORKING" and t["until"].endswith("Z") and 100 < t["remaining_s"] <= 120


def test_until_past_removes_and_expired_target_disappears(api):
    w = api.world
    api.post(URL, json=[{"code": "SAW-1", "state": "down", "until": until(w, 30)}])
    w.advance(10)
    assert api.get(URL).json()["count"] == 1
    w.advance(30)  # until минув: ціль зникла з GET, верстат знову автономний
    assert api.get(URL).json() == {"count": 0, "items": []}
    assert sig(w, "workcenters/SAW-1/state") == 3
    api.post(URL, json=[{"code": "SAW-1", "state": "down", "until": until(w)}])
    r = api.post(URL, json=[{"code": "SAW-1", "state": "idle", "until": until(w, -5)}])
    assert r.json() == {"ok": 0, "unknown": [], "expired": ["SAW-1"]}
    assert api.get(URL).json()["count"] == 0


@pytest.mark.parametrize(
    "item",
    [
        {"code": "SAW-1", "state": "broken", "until": "2030-01-01T00:00:00Z"},
        {"code": "SAW-1", "state": "idle"},
        {"code": "SAW-1", "state": "idle", "until": "завтра"},
        {"state": "idle", "until": "2030-01-01T00:00:00Z"},
    ],
)
def test_validation_422(api, item):
    assert api.post(URL, json=[item]).status_code == 422
    assert api.get(URL).json()["count"] == 0


def test_too_many_targets_422(api):
    item = {"code": "SAW-1", "state": "idle", "until": "2030-01-01T00:00:00Z"}
    assert api.post(URL, json=[item] * 501).status_code == 422


def test_naive_until_is_utc(api):
    w = api.world
    naive = datetime.fromtimestamp(real_epoch(w) + 300, UTC).replace(tzinfo=None).isoformat()
    assert api.post(URL, json=[{"code": "SAW-1", "state": "idle", "until": naive}]).json()["ok"] == 1
    assert 290 < api.get(URL).json()["items"][0]["remaining_s"] <= 300
    plus3 = (datetime.fromtimestamp(real_epoch(w) + 300, UTC) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
    api.post(URL, json=[{"code": "SAW-2", "state": "idle", "until": plus3}])
    assert 290 < next(t for t in api.get(URL).json()["items"] if t["code"] == "SAW-2")["remaining_s"] <= 300


def test_readonly_and_locked(world):
    body = [{"code": "SAW-1", "state": "idle", "until": until(world)}]
    with TestClient(make(world, readonly_api=True), headers=AUTH) as c:
        assert c.post(URL, json=body).status_code == 403
        assert c.get(URL).status_code == 200  # читання — можна
    with TestClient(make(world), headers=AUTH) as c:
        assert c.post("/sim/v1/stop-all").status_code == 200
        assert c.post(URL, json=body).status_code == 423
        assert c.get(URL).status_code == 200


def test_reset_clears_targets(api):
    w = api.world
    api.post(URL, json=[{"code": "SAW-1", "state": "down", "until": until(w)}])
    assert api.get(URL).json()["count"] == 1
    assert api.post("/sim/v1/reset").status_code == 200
    assert api.get(URL).json()["count"] == 0


@pytest.fixture
async def opc(world, port):
    srv = OpcUaServer(world, port=port, host="127.0.0.1", user="collector", password="pw")
    await srv.start()
    yield srv
    await srv.stop()


async def test_opcua_collector_view_matches_target(opc, world):
    """Збирач td_machine_connect читає OPC UA: CurrentState/Alarm/потужність збігаються з ціллю за один цикл."""
    world.step(10)
    with TestClient(make(world), headers=AUTH) as c:
        body = [
            {"code": "SAW-1", "state": "down", "reason": "spindle", "until": until(world)},
            {"code": "SAW-3", "state": "working", "until": until(world)},
            {"code": "SAW-2", "state": "idle", "until": until(world)},
        ]
        assert c.post(URL, json=body).json()["ok"] == 3
    world.step(1)
    await opc.refresh()
    async with Client(f"opc.tcp://127.0.0.1:{opc.port}/f3d/") as cl:
        ns = await cl.get_namespace_index(NS_INST)

        async def read(code, leaf):
            return await cl.get_node(f"ns={ns};s={code}.{leaf}").read_value()

        assert await read("SAW-1", "State.Machine.Overview.CurrentState") == 4
        assert await read("SAW-1", "State.Machine.Flags.Alarm") is True
        assert await read("SAW-1", "ManufacturerSpecific.PowerActive") == 0
        assert await read("SAW-3", "State.Machine.Overview.CurrentState") == 3
        assert await read("SAW-3", "ManufacturerSpecific.PowerActive") > 10
        assert await read("SAW-2", "State.Machine.Overview.CurrentState") == 2
        assert await read("SAW-2", "State.Machine.Flags.RecipeInRun") is False
