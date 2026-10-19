"""P-03 woodStore API v1 (SPEC §8.5)."""

import httpx
import pytest
from iot_sim.protocols.woodstore_api import WoodStoreApi

KEY = {"X-Api-Key": "k-wood"}


@pytest.fixture
async def api(world, port):
    srv = WoodStoreApi(world, port=port, host="127.0.0.1", apikey="k-wood", sheet_period_s=10)
    await srv.start()
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}/api/v1", headers=KEY) as c:
        c.srv = srv
        yield c
    await srv.stop()


async def test_auth_required(api):
    r = await api.get("/status", headers={"X-Api-Key": "bad"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_status_and_stacks(api):
    st = (await api.get("/status")).json()
    assert st["state"] == "idle" and len(st["aisles"]) == 9 and st["current_job"] is None
    stacks = (await api.get("/stacks")).json()
    assert sum(1 for s in stacks if s["qty"] > 0) == 23
    one = (await api.get("/stacks/PLT-01A")).json()
    assert one["id"] == "PLT-01A" and one["max"] == 60
    assert (await api.get("/stacks/NOPE")).status_code == 404
    by_row = (await api.get("/stacks", params={"row": 2})).json()
    assert by_row and all(s["row"] == 2 for s in by_row)


async def test_patch_stack(api):
    r = await api.patch("/stacks/PLT-01A", json={"qty": 35, "reason": "odoo_inventory"})
    assert r.status_code == 200 and r.json()["qty"] == 35
    assert (await api.patch("/stacks/PLT-01A", json={"qty": 999})).status_code == 422
    evs = (await api.get("/events")).json()
    assert evs[-1]["type"] == "stack_updated"


async def test_feed_job_lifecycle(api, world):
    stack = (await api.get("/stacks/PLT-01A")).json()
    r = await api.post(
        "/jobs",
        json={"type": "feed", "source": "PLT-01A", "target": "SAW-1", "sheets": 2, "external_ref": "WH/MO/00231"},
    )
    assert r.status_code == 201
    job = r.json()
    assert job["state"] == "queued"
    world.advance(1)
    assert (await api.get(f"/jobs/{job['id']}")).json()["state"] == "active"
    assert (await api.get("/status")).json()["current_job"] == job["id"]
    world.advance(25)
    done = (await api.get(f"/jobs/{job['id']}")).json()
    assert done["state"] == "done" and done["done"] == 2
    assert (await api.get("/stacks/PLT-01A")).json()["qty"] == stack["qty"] - 2
    types = [e["type"] for e in (await api.get("/events")).json()]
    assert "job_started" in types and "sheet_placed" in types and "job_finished" in types
    assert len((await api.get("/jobs", params={"state": "done"})).json()) == 1


async def test_job_conflicts_and_cancel(api, world):
    r = await api.post("/jobs", json={"type": "feed", "source": "PLT-01A", "target": "SAW-1", "sheets": 500})
    assert r.status_code == 409 and r.json()["error"]["code"] == "CONFLICT"
    r = await api.post("/jobs", json={"type": "feed", "target": "XXX", "sheets": 1})
    assert r.status_code == 422
    job = (await api.post("/jobs", json={"target": "SAW-2", "sheets": 3, "product": None})).json()
    d = await api.delete(f"/jobs/{job['id']}")
    assert d.json() == {"id": job["id"], "state": "cancelled"}


async def test_open_aisle_blocks(api, world):
    world.set_flag("aisles_open", [3])
    world.advance(1)
    st = (await api.get("/status")).json()
    assert st["state"] == "blocked" and st["aisles"][2]["gate_open"] is True


async def test_job_from_jobs_api_via_world(api, world):
    world.post("woodstore_jobs", {"type": "feed", "target": "SAW-1", "sheets": 1, "product": "DSP16-SON"})
    world.advance(1)
    jobs = (await api.get("/jobs")).json()
    assert len(jobs) == 1 and jobs[0]["target"] == "SAW-1"
