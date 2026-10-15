"""Режим follow_odoo (SPEC §8.9.7, A-08, A-12; AC-07, AC-63) і клієнт Odoo (API-01/API-03)."""
import json

import httpx
import pytest

from iot_sim.odoo.devices_client import DevicesClient, EventForwarder
from iot_sim.odoo.follow import FollowOdoo, OdooReadOnly


class FakeOdoo:
    configured = True

    def __init__(self):
        self.calls = []
        self.fail = False
        self.plate_field = True
        self.data = {
            "mrp.workcenter": [{"id": 1, "code": "SAW-1", "working_state": "normal"},
                               {"id": 2, "code": "CNC-2", "working_state": "blocked"},
                               {"id": 3, "code": "EDGE-1", "working_state": "normal"}],
            "mrp.workorder": [
                {"id": 13, "name": "Розкрій", "state": "progress", "workcenter_id": [1, "SAW-1"],
                 "production_id": [5, "WH/MO/00231"], "qty_produced": 6.0, "qty_production": 40.0,
                 "duration": 12.0, "duration_expected": 60.0, "date_start": "2026-10-12 06:00:00",
                 "working_state": "normal"},
                {"id": 94, "name": "Кромка", "state": "ready", "workcenter_id": [3, "EDGE-1"],
                 "production_id": [5, "WH/MO/00231"], "qty_produced": 0, "qty_production": 40.0,
                 "duration": 0, "duration_expected": 30.0, "date_start": False, "working_state": "normal"},
                {"id": 20, "name": "Присадка", "state": "progress", "workcenter_id": [2, "CNC-2"],
                 "production_id": [6, "WH/MO/00232"], "qty_produced": 1.0, "qty_production": 10.0,
                 "duration": 3.0, "duration_expected": 20.0, "date_start": "2026-10-12 06:30:00",
                 "working_state": "blocked"},
                {"id": 7, "name": "Збирання", "state": "done", "workcenter_id": [1, "SAW-1"],
                 "production_id": [4, "WH/MO/00230"], "qty_produced": 10, "qty_production": 10,
                 "duration": 30, "duration_expected": 30, "date_start": "2026-10-12 05:00:00",
                 "working_state": "normal"}],
            "stock.picking.batch": [
                {"id": 1, "name": "BATCH/IN/00001", "dock_id": [11, "DOCK-W1"], "scheduled_date": "2026-10-12 03:30:00",
                 "state": "in_progress", "picking_ids": [101], "f3d_code": "TRUCK-IN-1", "f3d_truck": "Фура Iveco",
                 "f3d_plate": "AA7777KT"},
                {"id": 2, "name": "BATCH/OUT/00004", "dock_id": [12, "DOCK-E2"], "scheduled_date": "2026-10-12 08:00:00",
                 "state": "draft", "picking_ids": [102], "f3d_code": "TRUCK-OUT-1", "f3d_truck": "Фура Volvo",
                 "f3d_plate": False}],
            "stock.location": [{"id": 11, "f3d_code": "DOCK-W1"}, {"id": 12, "f3d_code": "DOCK-E2"}],
            "stock.picking": [{"id": 101, "name": "WH/IN/1", "state": "assigned", "picking_type_code": "incoming"},
                              {"id": 102, "name": "WH/OUT/4", "state": "assigned", "picking_type_code": "outgoing"}],
            "stock.move": [{"picking_id": [101, "x"], "quantity": 6.0, "product_uom_qty": 10.0},
                           {"picking_id": [102, "y"], "quantity": 0.0, "product_uom_qty": 5.0}],
            "hr.employee": [{"id": 1, "name": "Олег Мельник", "barcode": "OPSAW1", "job_title": "Оператор",
                             "resource_calendar_id": [1, "Зміна 1"]}],
            "resource.calendar.attendance": [
                {"dayofweek": str(d), "hour_from": h0, "hour_to": h1}
                for d in range(5) for h0, h1 in ((7.0, 11.5), (12.0, 15.5))],
            "maintenance.request": [{"id": 35, "equipment_id": [9, "RV-05"]}],
            "maintenance.equipment": [{"id": 9, "f3d_code": "RV-05"}]}

    async def search_read(self, model, domain, fields, **kw):
        self.calls.append(("search_read", model, domain))
        if self.fail:
            raise ConnectionError("odoo down")
        if model not in self.data:
            raise KeyError(model)  # x_f3d_signal тощо відсутні
        return [dict(r) for r in self.data[model]]

    async def read(self, model, ids, fields):
        self.calls.append(("read", model, ids))
        if self.fail:
            raise ConnectionError("odoo down")
        return [dict(r) for r in self.data[model] if r["id"] in ids]

    async def fields_get(self, model, attributes=None):
        self.calls.append(("fields_get", model))
        return {"f3d_code": {}, **({"f3d_plate": {}} if self.plate_field else {})}


class Mono:
    t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def mono():
    return Mono()


@pytest.fixture
def odoo():
    return FakeOdoo()


@pytest.fixture
def follow(world, odoo, mono):
    world.set_mode("follow_odoo")
    return FollowOdoo(world, odoo, follow_s=10, slow_s=60, stale_s=120, mono=mono)


def count(odoo, model):
    return sum(1 for c in odoo.calls if c[1] == model and c[0] == "search_read")


async def test_fast_poll_maps_workorders(follow, world):
    await follow.poll_fast()
    assert world.workcenters["SAW-1"]["state"] == "WORKING" and world.workcenters["SAW-1"]["job"]["id"] == "WO00013"
    assert world.workcenters["CNC-2"]["state"] == "ERROR" and world.workcenters["CNC-2"]["blocked"] is True
    assert world.workcenters["EDGE-1"]["state"] == "READY"
    ids = {j["id"]: j for j in world.jobs}
    assert ids["WO00013"]["isa_state"] == "Running" and ids["WO00094"]["isa_state"] == "AllowedToStart"
    assert ids["WO00007"]["isa_state"] == "Ended/Completed" and ids["WO00013"]["workcenter"] == "SAW-1"
    assert ids["WO00013"]["qty_produced"] == 6.0


async def test_fast_domain_has_states_and_recent_done(follow, odoo):
    await follow.poll_fast()
    dom = next(c[2] for c in odoo.calls if c[1] == "mrp.workorder")
    assert ("state", "in", ["ready", "progress", "done"]) in dom
    assert any(isinstance(t, tuple) and t[0] == "date_finished" and t[1] == ">=" for t in dom)


async def test_slow_poll_trucks_people_shift_maintenance(follow, world):
    await follow.poll_slow()
    t = {x["code"]: x for x in world.trucks}
    assert t["TRUCK-IN-1"]["plate"] == "AA7777KT" and t["TRUCK-IN-1"]["dock"] == "DOCK-W1"
    assert t["TRUCK-IN-1"]["type"] == "incoming" and t["TRUCK-IN-1"]["progress"] == 0.6
    assert t["TRUCK-OUT-1"]["plate"] is None and t["TRUCK-OUT-1"]["type"] == "outgoing"
    assert t["TRUCK-OUT-1"]["description"] == "Фура Volvo"  # назва, не номер (X-15)
    assert world.people == [{"name": "Олег Мельник", "barcode": "OPSAW1", "job": "Оператор", "shift": "Зміна 1"}]
    cal = world.shift
    assert (cal.start.hour, cal.end.hour, cal.end.minute) == (7, 15, 30)
    assert (cal.lunch_from.hour, cal.lunch_from.minute, cal.lunch_to.hour) == (11, 30, 12)
    assert cal.workdays == (0, 1, 2, 3, 4)
    assert "RV-05" in world.maintenance_closed


async def test_plate_skipped_without_yard_field(follow, odoo, world):
    odoo.plate_field = False
    await follow.poll_slow()
    assert all(t["plate"] is None for t in world.trucks)


async def test_periods_10s_and_60s(follow, odoo, mono):
    for _ in range(61):
        await follow.step()
        mono.t += 1
    assert count(odoo, "mrp.workorder") == 7  # t=0,10,…,60
    assert count(odoo, "stock.picking.batch") == 2  # t=0, 60
    assert follow.last_ok is not None and follow.status()["stale"] is False


async def test_idle_in_scenario_mode(world, odoo, mono):
    f = FollowOdoo(world, odoo, mono=mono)  # world.mode == scenario
    await f.step()
    assert odoo.calls == []


async def test_stale_after_threshold_then_full_resync(follow, odoo, world, mono):
    await follow.step()
    assert world.odoo_stale is False
    odoo.fail = True
    for _ in range(14):  # 140 с помилок > stale_s=120
        mono.t += 10
        await follow.step()
    assert world.odoo_stale is True and follow.status()["stale"] is True
    assert world.events.last("error") is not None
    assert world.workcenters["SAW-1"]["state"] == "WORKING"  # стан заморожено, не стерто
    odoo.fail = False
    odoo.calls.clear()
    mono.t += 1
    await follow.step()
    assert world.odoo_stale is False
    assert count(odoo, "mrp.workorder") == 1 and count(odoo, "stock.picking.batch") == 1  # повна синхронізація
    assert "відновлено" in world.events.last("info").message


def test_readonly_client_has_no_write_methods():
    c = OdooReadOnly("http://odoo", "db", "u", "k")
    for name in ("write", "create", "unlink", "execute_kw", "call"):
        assert not hasattr(c, name)
    with pytest.raises(PermissionError):
        c._call("res.partner", "write", [[1], {"name": "x"}], {})
    with pytest.raises(PermissionError):
        c._call("res.partner", "unlink", [[1]], {})
    assert set(OdooReadOnly.ALLOWED) == {"search_read", "read", "search_count", "fields_get"}
    assert OdooReadOnly("", "", "", "").configured is False


def test_readonly_client_respects_allow_list():
    from iot_sim.core.outbound import OutboundDenied, OutboundGuard
    c = OdooReadOnly("http://evil.example:8069", "db", "u", "k", guard=OutboundGuard("odoo19"))
    with pytest.raises(OutboundDenied):
        c._call("res.partner", "search_read", [[]], {})


# --- devices_client -----------------------------------------------------------------------
def client_with(handler):
    return DevicesClient("http://odoo19:8069/", "export-token", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_get_devices_bearer_etag_304():
    seen = []

    def handler(req):
        seen.append(req)
        if req.headers.get("if-none-match") == '"abc"':
            return httpx.Response(304)
        return httpx.Response(200, json={"version": 1, "devices": []}, headers={"ETag": '"abc"'})

    c = client_with(handler)
    assert (await c.get_devices())["version"] == 1
    assert seen[0].url.path == "/f3d/sim/devices" and seen[0].headers["authorization"] == "Bearer export-token"
    assert await c.get_devices() is None  # 304: каталог не змінився
    await c.get_devices(protocol="P-01")
    assert seen[-1].url.params["protocol"] == "P-01" and "if-none-match" not in seen[-1].headers


async def test_post_events_format(world):
    sent = []

    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(200, json={"accepted": len(sent[-1]["events"]), "rejected": []})

    c = client_with(handler)
    fw = EventForwarder(world, c)
    fw.on_event(world.events.emit("alarm", "тривога", device="RV-05"))
    fw.on_event(world.events.emit("info", "без запуску"))  # info без run_id не пересилається
    fw.on_event(world.events.emit("yard", "двір"))
    from iot_sim.core.scenarios import ScenarioRunner
    run = ScenarioRunner(world).start("spark", {}, "RUN/2026/0007")
    fw.on_event(world.events.emit("scenario", "старт", run_id=run.id, payload={"state": "running"}))
    assert await fw.flush() == 2 and fw.queue == []
    evs = sent[0]["events"]
    assert [e["kind"] for e in evs] == ["alarm", "scenario"]
    e = evs[1]
    assert e["run_ref"] == "RUN/2026/0007" and e["sim_run_id"] == run.id and e["payload"]["event_id"].startswith("e-")
    assert e["ts"].endswith(("+03:00", "+02:00")) and evs[0]["device"] == "RV-05"
    assert len({x["payload"]["event_id"] for x in evs}) == 2


async def test_forwarder_keeps_queue_on_failure_and_batches(world):
    state = {"ok": False, "sizes": []}

    def handler(req):
        if not state["ok"]:
            return httpx.Response(500)
        n = len(json.loads(req.content)["events"])
        state["sizes"].append(n)
        return httpx.Response(200, json={"accepted": n, "rejected": []})

    fw = EventForwarder(world, client_with(handler))
    for i in range(250):
        fw.on_event(world.events.emit("fault", f"f{i}", device="CNC-2"))
    assert await fw.flush() == 0 and len(fw.queue) == 250
    state["ok"] = True
    assert await fw.flush() == 250 and state["sizes"] == [100, 100, 50]
