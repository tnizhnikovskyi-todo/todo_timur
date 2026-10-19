"""ТК-10 (BioStar), ТК-11 (двір: LPR/шлагбаум/ваги), ТК-17 (HelvarNet), ТБ-04 (BioStar DELETE). AC-16/17/18/39/41/42/54/55/57."""

import socket
import time

import httpx
import pytest

from .conftest import container_ip
from .helpers import NOON, Mb


# ------------------------------------------------------------------ BioStar 2
@pytest.fixture
def bs(host, env_get):
    c = httpx.Client(base_url=f"http://{host}:8081", timeout=10)
    r = c.post("/api/login", json={"User": {"login_id": "admin", "password": env_get("SIM_BIOSTAR_PASS")}})
    assert r.status_code == 200, r.text
    c.headers["bs-session-id"] = r.headers["bs-session-id"]
    c.sid = r.headers["bs-session-id"]
    yield c
    c.close()


def _search(bs, **q):
    r = bs.post("/api/events/search", json={"Query": q})
    assert r.status_code == 200, r.text
    return r.json()["EventCollection"]


def test_tk10_biostar_session_and_6400(api, host, bs):
    """AC-41, ТБ-04: сесія, помилки входу, подія 6400 з дверима 2, logout → 401, DELETE відхилено."""
    api.post("/time", {"set": "2026-10-12T06:30:00+03:00", "factor": 1})
    r = api.post("/scenario/access_event/start", {"params": {"device": "ACR-ELEC", "code": 6400}})
    assert r.status_code == 201, r.text
    time.sleep(3)
    ev = _search(
        bs,
        limit=20,
        orders=[{"column": "datetime", "descending": True}],
        conditions=[{"column": "event_type_id.code", "operator": 0, "values": ["6400"]}],
    )
    assert int(ev["total"]) >= 1 and ev["rows"][0]["door_id"][0]["id"] == "2"
    bad = httpx.post(f"http://{host}:8081/api/login", json={"User": {"login_id": "admin", "password": "x"}})
    assert bad.status_code == 401 and bad.json()["Response"]["code"] == "101"
    r = httpx.post(f"http://{host}:8081/api/events/search", json={"Query": {}})
    assert r.status_code == 401 and r.json()["Response"]["code"] == "10"
    assert bs.delete("/api/users/1").status_code in (403, 404, 405)
    assert bs.get("/api/users").status_code == 200
    assert bs.post("/api/logout").json()["Response"]["code"] == "0"
    assert bs.post("/api/events/search", json={"Query": {}}).status_code == 401


@pytest.mark.timeout(240)
def test_tk10_biostar_shift_events_and_paging(api, bs):
    """AC-16/AC-55: події входу працівників (API-01 employees) і пагінація offset/hint."""
    total_users = int(bs.get("/api/users", params={"limit": 1}).json()["UserCollection"]["total"])
    if total_users <= 1:
        pytest.skip("немає працівників API-01 (сценарій без Odoo): ТК-10 п. 2–3 прогонити у follow_odoo")
    api.post("/time", {"set": "2026-10-12T06:30:00+03:00", "factor": 10})
    api.scenario("shift")
    time.sleep(100)  # ТК-10: 5 хв реального → скорочено до 100 с при factor=10 (≈17 хв sim)
    q = {"orders": [{"column": "datetime", "descending": False}]}
    full = _search(bs, limit=200, **q)
    assert int(full["total"]) > 0
    rows = full["rows"]
    assert all(r["event_type_id"]["code"] in ("4102", "4867") for r in rows if r["tna_key"] == "1")
    dts = [r["datetime"] for r in rows]
    assert dts == sorted(dts)
    p1 = _search(bs, limit=3, offset=0, **q)
    p2 = _search(bs, limit=3, offset=3, **q)
    n2 = _search(bs, limit=3, hint=p1["rows"][-1]["hint"], **q)
    assert [r["id"] for r in p2["rows"]] == [r["id"] for r in n2["rows"]]
    assert len({r["id"] for r in p1["rows"] + p2["rows"]}) == 6
    desc = _search(bs, limit=50, orders=[{"column": "datetime", "descending": True}])["rows"]
    d = [r["datetime"] for r in desc]
    assert d == sorted(d, reverse=True)


# ------------------------------------------------------------------ двір
def _sics(host, cmds, timeout=3):
    out = []
    with socket.create_connection((host, 4001), timeout=timeout) as s:
        s.settimeout(timeout)
        for c in cmds:
            s.sendall(c.encode() + b"\r\n")
            time.sleep(0.2)
            out.append(s.recv(256).decode(errors="replace"))
    return out


def test_ac42_sics_basic(host):
    r = _sics(host, ["SI", "XYZ", "Z"])
    assert r[0].startswith("S S") and r[0].rstrip().endswith("kg")
    assert r[1].strip() == "ES" and r[2].strip() == "Z A"


@pytest.mark.timeout(300)
def test_tk11_yard(api, host):
    mb = Mb(host)
    api.post("/time", {"set": "2026-10-14T06:25:00+03:00", "factor": 3})
    api.scenario("shift")
    r = api.post("/scenario/truck_arrival/start", {"params": {"booking": "BATCH/IN/00001"}})
    assert r.status_code == 201, r.text
    weights, di0 = [], []
    t_end = time.time() + 120
    while time.time() < t_end:
        di0.append(mb.di(86, 0, 6))
        weights.append(_sics(host, ["SI"])[0])
        if any("25200" in w for w in weights) and weights[-1].startswith("S S          0"):
            break
        time.sleep(0.15)
    assert any(d[0] == 1 for d in di0), "DI0 (авто на в'їзді) не піднявся"  # AC-17
    assert any(abs(int(w.split()[2]) - 25200) <= 20 for w in weights if w.startswith("S S")), weights[-3:]
    ev = api.get("/events", params={"kind": "info"}).json()["items"]
    lpr = [e for e in ev if (e.get("payload") or {}).get("plateList") == "f3d_bookings"]
    assert lpr, "LPR POST не отримано (/lpr-sink)"
    p = lpr[0]["payload"]
    assert p["plateListMode"] == "allow" and p["GEOtarget"] == "GATE-W" and p["capture_timestamp"]
    # AC-54: вихідна фура з номером з td_plate
    api.post("/scenario/truck_arrival/stop")
    r = api.post("/scenario/truck_arrival/start", {"params": {"booking": "BATCH/OUT/00004"}})
    assert r.status_code == 201, r.text
    got = api.wait(
        lambda: [
            e
            for e in api.get("/events", params={"kind": "info"}).json()["items"]
            if (e.get("payload") or {}).get("plateText") == "AA4512KT"
        ],
        timeout=90,
        step=1,
    )
    assert got and got[0]["payload"]["plateUnicode"] == "АА4512КТ"
    assert got[0]["payload"]["plateListDescription"].startswith("BATCH/OUT/00004")
    api.post("/scenario/truck_arrival/stop")
    # AC-18: без бронювання
    r = api.post("/scenario/truck_no_booking/start", {"params": {"wait_min": 3}})
    assert r.status_code == 201, r.text
    nb = api.wait(
        lambda: [
            e
            for e in api.get("/events", params={"kind": "info"}).json()["items"]
            if (e.get("payload") or {}).get("plateListMode") == "none"
        ],
        timeout=90,
        step=1,
    )
    assert nb and nb[0]["payload"]["plateList"] == ""
    assert mb.di(86, 0, 1) == [0]  # AC-18: DI0 лишається 0 (немає бронювання)
    mb.close()


# ------------------------------------------------------------------ HelvarNet
class Helvar:
    def __init__(self, host):
        self.s = socket.create_connection((host, 50000), timeout=3)
        self.s.settimeout(1.5)
        self.buf = ""

    def send(self, cmd):
        self.s.sendall(cmd.encode())

    def frames(self, wait=1.5):
        end = time.time() + wait
        out = []
        while time.time() < end:
            try:
                d = self.s.recv(65536).decode()
            except TimeoutError:
                break
            if not d:
                break
            self.buf += d
            while True:
                idx = [i for i in (self.buf.find("#"), self.buf.find("$")) if i >= 0]
                if not idx:
                    break
                i = min(idx)
                out.append(self.buf[: i + 1])
                self.buf = self.buf[i + 1 :]
            if out:
                time.sleep(0.2)
        return out

    def close(self):
        self.s.close()


def test_tk17_helvarnet(api, host):
    api.post("/time", {"set": NOON, "factor": 1})
    a, b = Helvar(host), Helvar(host)
    a.send(">V:2,C:152,@1.2.1.1#")
    fr = a.frames()
    assert any(f.startswith("?V:2,C:152,@1.2.1.1=") for f in fr), fr  # AC-39
    a.send(">V:2,C:152,@1.2.1.99#")
    assert "!V:2,C:152,@1.2.1.99=11#" in a.frames()
    # C:13 з A:1 і без A
    a.send(">V:2,C:13,G:19,L:50,F:200,A:1#")
    fa, fb = a.frames(), b.frames()
    assert "!V:2,C:13,G:19,L:50,F:200,A:1=0#" in fa, fa  # AC-57
    assert ">V:2,C:13,G:19,L:50,F:200#" in fb and ">V:2,C:13,G:19,L:50,F:200#" in fa
    a.send(">V:2,C:13,G:12,L:30,F:100#")
    fa, fb = a.frames(), b.frames()
    assert fa == [] or all("!" not in f for f in fa)  # без A — лише push
    assert ">V:2,C:13,G:12,L:30,F:100#" in fb
    assert api.sig("lighting/groups/LT-CUT/level") == pytest.approx(30)
    # V:1 і V:2 (версія відповіді = версії запиту)
    a.send(">V:1,C:152,@1.3.1.20#")
    assert any(f.startswith("?V:1,C:152,@1.3.1.20=") for f in a.frames())
    # C:164 для G:16: два кадри, перший закінчується на «$»
    a.send(">V:2,C:164,G:16#")
    fr = a.frames()
    assert len(fr) == 2 and fr[0].startswith("?V:2,C:164,G:16=@1.2.3.1") and fr[0].endswith("$")
    assert fr[1].startswith("?V:2,C:164,G:16=@1.2.4.1") and fr[1].endswith("#")
    assert "@1.2.3.64" in fr[0] and "@1.2.4.27" in fr[1]
    a.send(">V:2,C:191#")
    assert "?V:2,C:191=2#" in a.frames()
    a.send(">V:1,C:191#")
    assert "?V:1,C:191=2#" in a.frames()  # SIM_HELVAR_VERSION=2: версія роутера в тілі (X-64)
    # C:110 після lighting_scene fault_device
    r = api.post("/scenario/lighting_scene/start", {"params": {"group": "LT-CUT", "fault_device": "@1.2.1.5"}})
    assert r.status_code == 201, r.text
    time.sleep(2)
    a.send(">V:2,C:110,@1.2.1.5#")
    assert any(f.startswith("?V:2,C:110,@1.2.1.5=2") for f in a.frames())
    a.close()
    b.close()


def test_tk17_helvarnet_version1(api, token):
    """AC-57: SIM_HELVAR_VERSION=1 (рестарт з env), потім повернення до 2."""
    import subprocess

    from .conftest import ROOT

    off = ROOT / "tests" / "stand" / "_helvar1.override.yml"
    off.write_text('services:\n  iot_sim:\n    environment:\n      SIM_HELVAR_VERSION: "1"\n')
    base = "docker compose -f docker-compose.sim.yml --profile dev"
    try:
        subprocess.run(
            (base + f" -f {off} up -d --force-recreate iot_sim").split(), cwd=ROOT, check=True, capture_output=True
        )
        for _ in range(60):
            try:
                if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)
        time.sleep(3)
        h = Helvar(container_ip())  # після recreate IP контейнера міг змінитись
        h.send(">V:2,C:152,@1.2.1.1#")
        assert "!V:2,C:152,@1.2.1.1=18#" in h.frames()
        h.send(">V:1,C:191#")
        assert "?V:1,C:191=1#" in h.frames()
        h.close()
    finally:
        off.unlink()
        subprocess.run((base + " up -d --force-recreate iot_sim").split(), cwd=ROOT, check=True, capture_output=True)
        for _ in range(60):
            try:
                if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(1)


@pytest.mark.timeout(120)
def test_tk08_fire_drill_side_effects(api, host, env_get):
    """AC-15/53: fire_drill → +9 с u85 DI4=1, +12 с BioStar 20480 на дверях 1–5 і u86 fc1 pdu20/21 = [1,1]."""
    mb = Mb(host)
    api.post("/time", {"set": NOON, "factor": 1})
    r = api.post("/scenario/fire_drill/start", {"params": {"zone": "FA-CNC"}})
    assert r.status_code == 201, r.text
    assert api.wait(lambda: mb.di(85, 4)[0] == 1, timeout=14, step=0.5), "u85 DI4 (клапани) не став 1"
    assert api.wait(lambda: mb.coils(86, 20, 2) == [1, 1], timeout=15, step=0.5), "u86 DO4/DO5 не стали 1"
    c = httpx.Client(base_url=f"http://{host}:8081", timeout=10)
    sid = c.post("/api/login", json={"User": {"login_id": "admin", "password": env_get("SIM_BIOSTAR_PASS")}}).headers[
        "bs-session-id"
    ]
    c.headers["bs-session-id"] = sid
    rows = c.post(
        "/api/events/search",
        json={
            "Query": {
                "limit": 200,
                "conditions": [{"column": "event_type_id.code", "operator": 0, "values": ["20480"]}],
            }
        },
    ).json()["EventCollection"]["rows"]
    doors = {d["id"] for r_ in rows for d in r_["door_id"]}
    assert {"1", "2", "3", "4", "5"} <= doors, doors
    mb.close()
