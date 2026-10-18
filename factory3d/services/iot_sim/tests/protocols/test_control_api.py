"""REST керування /sim/v1 (SPEC §7.2, API-10…API-19; AC-21; §11)."""
import pytest
from fastapi.testclient import TestClient
from iot_sim.config import Settings
from iot_sim.core.scenarios import ScenarioRunner
from iot_sim.protocols.control_api import create_app

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeFollow:
    configured = True
    last_ok = None

    def __init__(self):
        self.kicked = 0

    def status(self):
        return {"configured": True, "last_ok": None, "stale": False}

    def kick(self):
        self.kicked += 1


def make(world, **kw):
    settings = Settings(_env_file=None, api_token=TOKEN, **kw)
    runner = ScenarioRunner(world)
    app = create_app(settings, world=world, runner=runner, follow=FakeFollow())
    return app


@pytest.fixture
def api(world):
    with TestClient(make(world), headers=AUTH) as c:
        c.world = world
        yield c


def test_auth_required_and_open_endpoints(world):
    with TestClient(make(world)) as c:
        assert c.get("/sim/v1/status").status_code == 401
        assert c.get("/sim/v1/status", headers={"Authorization": "Bearer x"}).json() == {"detail": "invalid token"}
        assert c.get("/sim/v1/health").status_code == 200
        assert c.get("/sim/v1/metrics").status_code == 200
        assert c.post("/sim/v1/lpr-sink", json={"plateText": "AA1234KT", "sensorProviderID": "CAM-05",
                                                "carState": "new"}).json() == {"received": True}


def test_rate_limit_429(world):
    now = [100.0]
    settings = Settings(_env_file=None, api_token=TOKEN)
    app = create_app(settings, world=world, runner=ScenarioRunner(world), mono=lambda: now[0])
    with TestClient(app) as c:
        codes = [c.get("/sim/v1/status", headers={"Authorization": "Bearer bad"}).status_code for _ in range(6)]
        assert codes[:5] == [401] * 5 and codes[5] == 429
        assert c.get("/sim/v1/status", headers=AUTH).status_code == 429  # блок 60 с, навіть із добрим токеном
        now[0] += 61
        assert c.get("/sim/v1/status", headers=AUTH).status_code == 200


def test_status_shape(api):
    st = api.get("/sim/v1/status").json()
    assert st["enabled"] is True and st["mode"] == "scenario" and st["factor"] == 1.0
    assert st["devices"] == len(api.world.devices) and st["signals"] == len(api.world.signals)
    assert st["catalog_hash"].startswith("sha256:") and st["protocols"]["control"] == "ok"
    assert st["odoo"]["configured"] is True and st["runs"] == []


def test_devices_fault_clear(api):
    d = api.get("/sim/v1/devices/CNC-2").json()
    assert d["state"] == "ok" and d["fault"] is None and d["signals"]
    r = api.post("/sim/v1/device/CNC-2/fault", json={"reason": "spindle", "note": "тест"})
    assert r.status_code == 200 and r.json() == {"code": "CNC-2", "state": "fault"}
    assert api.post("/sim/v1/device/CNC-2/fault", json={"reason": "spindle"}).status_code == 200  # повтор
    d = api.get("/sim/v1/devices/CNC-2").json()
    assert d["fault"]["reason"] == "spindle" and d["fault"]["note"] == "тест"
    assert "CNC-2" in api.get("/sim/v1/status").json()["devices_fault"]
    assert [x["code"] for x in api.get("/sim/v1/devices", params={"state": "fault"}).json()] == ["CNC-2"]
    assert api.post("/sim/v1/device/CNC-2/clear").json()["state"] == "ok"
    assert api.post("/sim/v1/device/CNC-2/fault", json={"reason": "bogus"}).status_code == 422
    assert api.post("/sim/v1/device/NOPE/fault", json={}).status_code == 404
    assert api.post("/sim/v1/device/CUTOPT/fault", json={}).status_code == 422  # passive


def test_scenarios_start_conflict_stop(api):
    names = {s["name"] for s in api.get("/sim/v1/scenarios").json()}
    assert len(names) == 16 and "filter_clogged" in names
    r = api.post("/sim/v1/scenario/filter_clogged/start",
                 json={"run_ref": "RUN/2026/0007", "params": {"device": "RV-05", "value": 285}})
    assert r.status_code == 201
    run = r.json()
    assert run["scenario"] == "filter_clogged" and run["state"] == "running" and run["id"].startswith("r-")
    again = api.post("/sim/v1/scenario/filter_clogged/start", json={"params": {"device": "RV-05"}})
    assert again.status_code == 409 and "busy" in again.json()["detail"]
    assert api.post("/sim/v1/scenario/filter_clogged/start", json={"params": {"device": "XX"}}).status_code == 422
    assert api.post("/sim/v1/scenario/nope/start", json={}).status_code == 404
    runs = api.get("/sim/v1/runs").json()
    assert runs[0]["run_ref"] == "RUN/2026/0007" and runs[0]["events"] >= 1
    assert api.get(f"/sim/v1/runs/{run['id']}").json()["state"] == "running"
    assert api.get("/sim/v1/status").json()["runs"][0]["id"] == run["id"]
    st = api.post("/sim/v1/scenario/filter_clogged/stop", json={"run_id": run["id"]})
    assert st.status_code == 200 and st.json()["id"] == run["id"]
    assert api.get(f"/sim/v1/runs/{run['id']}").json()["state"] == "stopped"
    assert api.get("/sim/v1/runs/r-none").status_code == 404


def test_time_factor_and_follow_conflict(api):
    r = api.post("/sim/v1/time", json={"factor": 10.0})
    assert r.status_code == 200 and r.json()["factor"] == 10.0
    assert api.post("/sim/v1/time", json={"factor": 100}).status_code == 422
    assert api.post("/sim/v1/time", json={}).status_code == 422
    r = api.post("/sim/v1/time", json={"set": "2026-10-12T07:00:00+03:00"})
    assert r.status_code == 200 and r.json()["sim_now"].startswith("2026-10-12T07:00")
    assert api.post("/sim/v1/mode", json={"mode": "follow_odoo"}).json() == {"mode": "follow_odoo", "factor": 1.0}
    assert api.post("/sim/v1/time", json={"factor": 10}).status_code == 409
    assert api.post("/sim/v1/time", json={"factor": 1}).status_code == 200


def test_mode_without_odoo_is_422(world):
    app = create_app(Settings(_env_file=None, api_token=TOKEN), world=world, runner=ScenarioRunner(world))
    with TestClient(app, headers=AUTH) as c:
        assert c.post("/sim/v1/mode", json={"mode": "follow_odoo"}).status_code == 422
        assert c.post("/sim/v1/mode", json={"mode": "scenario"}).json()["mode"] == "scenario"


def test_signals_get_put_release(api):
    code = "equipment/FL-1/battery"
    lst = api.get("/sim/v1/signals", params={"prefix": "equipment/FL-1/"}).json()
    assert lst["count"] >= 3 and all(i["code"].startswith("equipment/FL-1/") for i in lst["items"])
    assert api.get("/sim/v1/signals", params={"limit": 5}).json()["items"].__len__() == 5
    r = api.put(f"/sim/v1/signals/{code}", json={"value": 12.5, "hold_s": 600})
    assert r.status_code == 200 and r.json()["value"] == 12.5 and r.json()["held_until"]
    assert api.world.signals[code].held(api.world.now())
    assert api.get(f"/sim/v1/signals/{code}").json()["value"] == 12.5
    assert api.put(f"/sim/v1/signals/{code}", json={"value": 1, "hold_s": 90_000}).status_code == 422
    assert api.put(f"/sim/v1/signals/{code}", json={"release": True}).json()["held_until"] is None
    assert api.get("/sim/v1/signals/no/such").status_code == 404
    none_row = next(s for s in api.world.signals.values() if not s.spec.emulated)
    r = api.get(f"/sim/v1/signals/{none_row.code}")
    assert r.status_code == 404 and r.json()["detail"].startswith("computed by")
    assert none_row.code not in {i["code"] for i in api.get("/sim/v1/signals", params={"limit": 5000}).json()["items"]}


def test_stop_all_resume_and_readonly(world):
    with TestClient(make(world), headers=AUTH) as c:
        assert c.post("/sim/v1/stop-all").json()["ok"] is True
        assert c.get("/sim/v1/health").json()["status"] == "locked"
        assert c.post("/sim/v1/device/CNC-2/fault", json={}).status_code == 423
        assert c.get("/sim/v1/status").json()["enabled"] is False
        assert c.post("/sim/v1/resume").status_code == 200
        assert c.get("/sim/v1/health").json()["status"] == "ok"
        assert c.post("/sim/v1/device/CNC-2/fault", json={}).status_code == 200
    with TestClient(make(world, readonly_api=True), headers=AUTH) as c:
        assert c.post("/sim/v1/device/CNC-2/clear").status_code == 403
        assert c.get("/sim/v1/devices").status_code == 200
    with TestClient(make(world, enabled=False), headers=AUTH) as c:
        assert c.get("/sim/v1/health").json()["status"] == "locked"
        assert c.post("/sim/v1/scenario/shift/start", json={}).status_code == 423
        assert c.post("/sim/v1/resume").status_code == 423


def test_reset_restores_nominal(api):
    code = "equipment/FL-1/battery"
    api.world.signals[code].value = 1.0
    api.post("/sim/v1/device/CNC-2/fault", json={})
    r = api.post("/sim/v1/reset", json={"keep_time": True, "seed": 7})
    assert r.json()["ok"] is True and api.world.seed == 7
    assert api.world.signals[code].value == api.world.signals[code].spec.initial_value()
    assert api.get("/sim/v1/devices/CNC-2").json()["fault"] is None


def test_events_cursor_and_410(api):
    ev = api.world.events
    for i in range(3):
        ev.emit("info", f"e{i}", device="CNC-2")
    items = api.get("/sim/v1/events", params={"limit": 2}).json()
    assert [e["message"] for e in items["items"]] == ["e0", "e1"] and items["next"] == items["items"][-1]["id"]
    rest = api.get("/sim/v1/events", params={"since": items["next"]}).json()
    assert [e["message"] for e in rest["items"]] == ["e2"]
    assert api.get("/sim/v1/events", params={"since": rest["next"]}).json()["items"] == []
    assert api.get("/sim/v1/events", params={"kind": "alarm"}).json()["items"] == []
    gone = api.get("/sim/v1/events", params={"since": "e-NOPE"})
    assert gone.status_code == 410 and "detail" in gone.json()


def test_lpr_sink_becomes_event(api):
    api.post("/sim/v1/lpr-sink", json={"plateText": "AA4512KT", "sensorProviderID": "CAM-05", "carState": "new"})
    ev = api.get("/sim/v1/events", params={"device": "CAM-05"}).json()["items"]
    assert ev and ev[-1]["kind"] == "info" and "AA4512KT" in ev[-1]["message"]


def test_metrics_and_catalog(api):
    text = api.get("/sim/v1/metrics").text
    for name in ("iot_sim_up", "iot_sim_signals_total", "iot_sim_tick_seconds", "iot_sim_alarms",
                 "iot_sim_protocol_up", "iot_sim_events_total", "iot_sim_runs_active"):
        assert name in text
    assert "iot_sim_signal_value{code=" in text
    csv = api.get("/sim/v1/catalog/signals.csv")
    assert csv.status_code == 200 and csv.text.startswith("n,code")
    assert len(api.get("/sim/v1/catalog/devices.json").json()) == len(api.world.devices)


def test_tick_lag_is_overshoot_over_period(world):
    """ТП-01: tick lag = запізнення понад період тіку (а не час від останнього тіку)."""
    now = [100.0]
    app = create_app(Settings(_env_file=None, api_token=TOKEN, tick_ms=1000), world=world, mono=lambda: now[0])

    def lag():
        text = TestClient(app).get("/sim/v1/metrics").text
        return float(next(ln.split()[-1] for ln in text.splitlines() if ln.startswith("iot_sim_tick_lag_seconds ")))

    world.last_tick_real = 99.4
    assert lag() == 0.0
    world.last_tick_real = 98.2
    assert lag() == pytest.approx(0.8)
