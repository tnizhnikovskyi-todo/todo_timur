"""P-10: BioStar 2 REST (SPEC §8.12, API-40…API-46; X-50)."""
import datetime as dt

import httpx
import pytest

from iot_sim.protocols.biostar_api import BioStarApi

PWD = "bio-pass"
DAY = dt.datetime(2026, 10, 14, 3, 0, tzinfo=dt.UTC)


@pytest.fixture
async def bs(world, port, tmp_path):
    world.people = [{"name": "Олег Мельник", "barcode": "OPSAW1"}, {"name": "Іван Шевчук", "barcode": "OPSAW2"}]
    srv = BioStarApi(world, port_http=port, port_https=None, host="127.0.0.1", user="admin",
                     password=PWD, cert_dir=tmp_path)
    await srv.start()
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as c:
        r = await c.post("/api/login", json={"User": {"login_id": "admin", "password": PWD}})
        c.headers["bs-session-id"] = r.headers["bs-session-id"]
        c.srv = srv
        yield c
    await srv.stop()


async def test_login_ok_and_failures(world, port, tmp_path):
    srv = BioStarApi(world, port_http=port, port_https=None, host="127.0.0.1", user="admin",
                     password=PWD, cert_dir=tmp_path)
    await srv.start()
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as c:
            r = await c.post("/api/login", json={"User": {"login_id": "admin", "password": PWD}})
            assert r.status_code == 200 and r.headers["bs-session-id"]
            body = r.json()
            assert body["Response"] == {"code": "0", "message": "Success"} and body["User"]["login_id"] == "admin"
            bad = await c.post("/api/login", json={"User": {"login_id": "admin", "password": "x"}})
            assert bad.status_code == 401 and bad.json()["Response"]["code"] == "101"
            assert (await c.post("/api/login", content=b"zzz")).status_code == 401
            assert (await c.get("/api/users")).status_code == 401  # без сесії
            assert (await c.get("/api/users", headers={"bs-session-id": "nope"})).status_code == 401
    finally:
        await srv.stop()


async def test_session_limits_expiry_logout(bs):
    store = bs.srv.store
    sid = bs.headers["bs-session-id"]
    clock = [store._clock()]
    store._clock = lambda: clock[0]
    store.sessions[sid] = clock[0]
    assert (await bs.get("/api/devices")).status_code == 200
    clock[0] += 31 * 60
    assert (await bs.get("/api/devices")).status_code == 401  # 30 хв бездіяльності
    store.sessions.clear()
    ids = [store.new_session() for _ in range(10)]
    assert all(ids) and store.new_session() is None  # ≤ 10 одночасних
    bs.headers["bs-session-id"] = ids[0]
    assert (await bs.post("/api/logout")).json()["Response"]["code"] == "0"
    assert (await bs.get("/api/devices")).status_code == 401


async def test_users_devices_doors_types(bs):
    users = (await bs.get("/api/users", params={"limit": 100, "offset": 0})).json()["UserCollection"]
    assert users["total"] == "3" and users["rows"][0]["login_id"] == "admin"
    row = users["rows"][1]
    assert row["user_id"] == "OPSAW1" and row["name"] == "Олег Мельник" and row["disabled"] == "false"
    assert row["user_group_id"] == {"id": "1", "name": "Виробництво"}
    page = (await bs.get("/api/users", params={"limit": 1, "offset": 2})).json()["UserCollection"]
    assert page["total"] == "3" and [r["user_id"] for r in page["rows"]] == ["OPSAW2"]
    devs = (await bs.get("/api/devices")).json()["DeviceCollection"]["rows"]
    assert [d["id"] for d in devs] == ["5390001", "5390002", "5390003", "5390004", "5390005"]
    doors = (await bs.get("/api/doors")).json()["DoorCollection"]["rows"]
    assert len(doors) == 5 and doors[0]["entry_device_id"] == {"id": "5390001"}
    types = (await bs.get("/api/event_types")).json()["EventTypeCollection"]["rows"]
    assert {"4102", "4867", "6400", "20480", "26368"} <= {t["code"] for t in types}
    assert (await bs.post("/api/users", json={})).status_code == 405  # незмінний ресурс
    assert (await bs.delete("/api/devices")).status_code == 405


def add_events(bs, n=7):
    store = bs.srv.store
    for i in range(n):
        store.add_event("OPSAW1" if i % 2 == 0 else "OPSAW2", "ACR-IN" if i < 5 else "ACR-ELEC",
                        4102 if i % 2 == 0 else 4867, tna_key="1", ts=DAY + dt.timedelta(minutes=i))


async def search(bs, **q):
    r = await bs.post("/api/events/search", json={"Query": q})
    assert r.status_code == 200, r.text
    return r.json()["EventCollection"]


async def test_event_row_format(bs):
    bs.srv.store.add_event("OPSAW1", "ACR-IN", 4102, tna_key="1", ts=DAY + dt.timedelta(seconds=10))
    col = await search(bs, limit=10)
    row = col["rows"][0]
    assert col["total"] == "1" and row["datetime"] == "2026-10-14T03:00:10.00Z"
    assert row["user_id"] == {"user_id": "OPSAW1", "name": "Олег Мельник", "photo_exists": "false"}
    assert row["device_id"]["id"] == "5390001" and row["door_id"] == [{"id": "1", "name": "Турнікет TURN-1"}]
    assert row["event_type_id"] == {"code": "4102"} and row["tna_key"] == "1"
    assert row["timezone"] == {"half": "0", "hour": "3", "negative": "0"}  # Київ, літо
    assert all(isinstance(v, (str, dict, list)) for v in row.values())


async def test_search_conditions_between_and_equal(bs):
    add_events(bs)
    t0, t1 = "2026-10-14T03:01:00.000Z", "2026-10-14T03:03:59.000Z"
    col = await search(bs, conditions=[{"column": "datetime", "operator": 3, "values": [t0, t1]}])
    assert col["total"] == "3"
    col = await search(bs, conditions=[{"column": "device_id.id", "operator": 0, "values": ["5390002"]}])
    assert col["total"] == "2" and {r["device_id"]["id"] for r in col["rows"]} == {"5390002"}
    col = await search(bs, conditions=[{"column": "event_type_id.code", "operator": 0, "values": ["4867"]}])
    assert col["total"] == "3"
    col = await search(bs, conditions=[{"column": "user_id.user_id", "operator": 0, "values": ["OPSAW1"]}])
    assert col["total"] == "4"
    col = await search(bs, conditions=[{"column": "id", "operator": 5, "values": ["5"]}])
    assert [r["id"] for r in col["rows"]] == ["6", "7"]  # id > last_id
    col = await search(bs, conditions=[{"column": "door_id.id", "operator": 1, "values": ["1"]}])
    assert col["total"] == "2"


async def test_ordering_ascending_default_and_descending(bs):
    add_events(bs)
    asc = [r["id"] for r in (await search(bs))["rows"]]
    assert asc == [str(i) for i in range(1, 8)]
    desc = await search(bs, orders=[{"column": "datetime", "descending": True}], limit=3)
    assert [r["id"] for r in desc["rows"]] == ["7", "6", "5"] and desc["total"] == "7"


async def test_offset_pagination_and_hint(bs):
    add_events(bs)
    p1 = await search(bs, limit=3, offset=0)
    p2 = await search(bs, limit=3, offset=3)
    assert [r["id"] for r in p1["rows"] + p2["rows"]] == ["1", "2", "3", "4", "5", "6"]
    assert p1["total"] == p2["total"] == "7"
    # hint: рядки після рядка з цим hint (BioStar 2.8+, без offset)
    h = p1["rows"][-1]["hint"]
    nxt = await search(bs, limit=10, hint=h)
    assert [r["id"] for r in nxt["rows"]] == ["4", "5", "6", "7"] and nxt["total"] == "7"
    bad = await bs.post("/api/events/search", json={"Query": {"limit": 5, "hint": "zzz"}})
    assert bad.status_code == 400
    capped = await search(bs, limit=99999)
    assert len(capped["rows"]) == 7  # limit ≤ 2000


async def test_invalid_query(bs):
    assert (await bs.post("/api/events/search", json={})).status_code == 400
    r = await bs.post("/api/events/search", json={"Query": {"conditions": [{"column": "nope", "operator": 0, "values": ["1"]}]}})
    assert r.status_code == 400


async def test_access_events_from_bus(bs, world):
    world.events.emit("access", "вхід", device="ACR-IN", payload={"user_id": "OPSAW1", "event_code": 4102, "tna_key": "1"})
    world.events.emit("access", "без коду", device="ACR-IN", payload={})
    world.events.emit("info", "інше", payload={"event_code": 1})
    col = await search(bs)
    assert col["total"] == "1" and col["rows"][0]["event_type_id"]["code"] == "4102"
    assert col["rows"][0]["device_id"]["name"].startswith("ACR-IN")


async def test_https_listener_self_signed(world, port, tmp_path):
    from tests.protocols.conftest import free_port
    https = free_port()
    srv = BioStarApi(world, port_http=port, port_https=https, host="127.0.0.1", user="admin",
                     password=PWD, cert_dir=tmp_path)
    await srv.start()
    try:
        async with httpx.AsyncClient(base_url=f"https://127.0.0.1:{https}", verify=False) as c:
            r = await c.post("/api/login", json={"User": {"login_id": "admin", "password": PWD}})
            assert r.status_code == 200 and r.headers["bs-session-id"]
        assert srv.health()["up"] and (tmp_path / "biostar.crt").exists()
    finally:
        await srv.stop()
