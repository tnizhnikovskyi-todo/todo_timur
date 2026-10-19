"""P-04 /jobs: карти розкрою (SPEC §8.6)."""

import httpx
import pytest
from iot_sim.protocols.jobs_api import JobsApi, optimize, parse_parts

KEY = {"X-Api-Key": "k-jobs"}
HEADER = "PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program\n"
CSV = HEADER + "P001;Side;DSP16-SON;720;560;4;1;EB2-SON;;;;\nP002;Top;DSP16-SON;1200;400;3;0;;;;;side.mpr\n"


@pytest.fixture
async def api(world, port):
    srv = JobsApi(world, port=port, host="127.0.0.1", apikey="k-jobs")
    await srv.start()
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", headers=KEY) as c:
        yield c
    await srv.stop()


def test_optimizer_deterministic():
    parts = parse_parts(CSV)
    a = optimize(parts, 2800, 2070, "DSP16-SON")
    assert a == optimize(parts, 2800, 2070, "DSP16-SON")
    assert a["total_sheets"] == 1
    assert sum(len(s["parts"]) for s in a["sheets"]) == 7
    assert 0 < a["waste_pct"] < 100


async def test_auth(api):
    assert (await api.get("/jobs/cj-00077", headers={"X-Api-Key": "x"})).status_code == 401


async def test_submit_plan_release(api, world):
    r = await api.post(
        "/jobs",
        data={"material": "DSP16-SON", "sheet": "2800x2070x16", "external_ref": "WH/MO/00231", "machine": "SAW-1"},
        files={"parts": ("parts.csv", CSV.encode(), "text/csv")},
    )
    assert r.status_code == 202
    jid = r.json()["job_id"]
    assert r.json()["state"] == "optimizing" and jid.startswith("cj-")
    assert (await api.get(f"/jobs/{jid}")).json()["state"] == "optimizing"
    assert (await api.get(f"/jobs/{jid}/plan")).status_code == 409
    world.advance(6)
    job = (await api.get(f"/jobs/{jid}")).json()
    assert job["state"] == "planned" and job["parts"] == 7 and job["plan"]["sheets"] == 1
    plan = (await api.get(f"/jobs/{jid}/plan")).json()
    assert plan["total_sheets"] == 1 and plan["sheets"][0]["parts"][0]["id"]
    assert (await api.get(f"/jobs/{jid}/mpr")).status_code == 404  # пилка
    rel = await api.post(f"/jobs/{jid}/release", json={"machine": "SAW-1", "priority": 5})
    assert rel.json() == {"job_id": jid, "state": "released", "job_order_id": jid}
    assert world.drain("opc_joborders")[0]["job_order_id"] == jid
    feed = world.drain("woodstore_jobs")[0]
    assert feed["target"] == "SAW-1" and feed["sheets"] == 1
    assert (await api.post(f"/jobs/{jid}/release", json={})).status_code == 409


async def test_json_submit_and_mpr_for_cnc(api, world):
    r = await api.post(
        "/jobs",
        json={
            "material": "DSP16-SON",
            "machine": "CNC-1",
            "parts": [{"PartId": "A1", "Length": 500, "Width": 300, "Quantity": 2}],
        },
    )
    assert r.status_code == 202
    jid = r.json()["job_id"]
    world.advance(6)
    mpr = await api.get(f"/jobs/{jid}/mpr", params={"part": "A1"})
    assert mpr.status_code == 200 and "LA=500" in mpr.text
    assert (await api.get(f"/jobs/{jid}/mpr", params={"part": "ZZ"})).status_code == 404


async def test_validation_errors(api):
    bad = HEADER + "P001;x;M;100;100;1;0;;;;;\nP002;x;M;100;2100;1;0;;;;;\nP003;x;M;3000;100;1;0;;;;;\n"
    r = await api.post("/jobs", data={"material": "M"}, files={"parts": ("p.csv", bad.encode())})
    assert r.status_code == 422
    assert r.json()["detail"] == [{"row": 3, "error": "Width > 2070"}, {"row": 4, "error": "Length > 2800"}]
    r = await api.post("/jobs", data={"material": "M"}, files={"parts": ("p.csv", HEADER.encode())})
    assert r.status_code == 422
