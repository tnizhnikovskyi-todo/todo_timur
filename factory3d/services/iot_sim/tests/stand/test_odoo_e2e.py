"""ТК-01 (follow_odoo, AC-07), ТК-10 (працівники з Odoo), ТК-15 (Odoo-пульт наскрізно), ТП-06 (частково).

Потребує Odoo 19 з модулем td_iot_sim 19.0.2.0.0 на ШАБЛОННІЙ базі (демо-бази немає):
``F3D_TEST_INSTALL=td_iot_sim tools/odoo/new_db.sh f3d_w6 && ... update.sh f3d_w6``;
``ODOO_HTTP_INTERFACE=0.0.0.0 tools/odoo/serve.sh f3d_w6 18069``. Змінні: STAND_ODOO_URL (з хоста), STAND_ODOO_DB.
Дані (РЦ, наряди, працівники) сідуються тут же через XML-RPC. Без Odoo тести пропускаються.
"""
import asyncio
import os
import subprocess
import time
import xmlrpc.client as xmlrpc

import httpx
import pytest
from asyncua import Client

from .conftest import ROOT, docker, fresh_service

ODOO = os.environ.get("STAND_ODOO_URL", "http://127.0.0.1:18069")
DB = os.environ.get("STAND_ODOO_DB", "f3d_w6")
NS = "http://todo.ltd/f3d/iot_sim/instances/"
EXPORT = "export-token-0123456789abcdef0123456789"


class Odoo:
    def __init__(self):
        self.uid = xmlrpc.ServerProxy(ODOO + "/xmlrpc/2/common").authenticate(DB, "admin", "admin", {})
        self.o = xmlrpc.ServerProxy(ODOO + "/xmlrpc/2/object", allow_none=True)

    def k(self, model, method, *args, **kw):
        try:
            return self.o.execute_kw(DB, self.uid, "admin", model, method, list(args), kw)
        except xmlrpc.Fault as exc:   # методи без return None → «cannot marshal None»: дія виконана
            if "cannot marshal None" in exc.faultString:
                return None
            raise

    def xid(self, module, name):
        return self.k("ir.model.data", "search_read", [("module", "=", module), ("name", "=", name)],
                      fields=["res_id"])[0]["res_id"]

    def param(self, key, value):
        self.k("ir.config_parameter", "set_param", "td.iot_sim." + key, value)


@pytest.fixture(scope="module")
def odoo():
    try:
        httpx.get(ODOO + "/f3d/sim/health", timeout=3)
        return Odoo()
    except Exception:  # noqa: BLE001
        pytest.skip("Odoo з td_iot_sim недоступний (STAND_ODOO_URL)")


def _seed(od: Odoo):
    if od.k("mrp.workcenter", "search_count", [("code", "=", "SAW-1")]):
        return
    prod = od.k("product.product", "create", {"name": "Panel X", "is_storable": True})
    for code in ("SAW-1", "CNC-2"):
        wc = od.k("mrp.workcenter", "create", {"name": code, "code": code})
        mo = od.k("mrp.production", "create", {
            "product_id": prod, "product_qty": 10,
            "workorder_ids": [(0, 0, {"name": "Op " + code, "workcenter_id": wc, "duration_expected": 60})]})
        od.k("mrp.production", "action_confirm", [mo])
        wo = od.k("mrp.workorder", "search", [("production_id", "=", mo)])
        if code == "SAW-1":
            od.k("mrp.workorder", "button_start", wo)
        else:
            loss = od.k("mrp.workcenter.productivity.loss", "search", [("loss_type", "!=", "productive")], limit=1)
            od.k("mrp.workcenter.productivity", "create", {
                "workcenter_id": wc, "workorder_id": wo[0], "loss_id": loss[0],
                "date_start": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())})
    if not od.k("hr.employee", "search_count", [("barcode", "!=", False)]):
        for i in range(35):
            od.k("hr.employee", "create", {"name": f"Працівник {i + 1}", "barcode": f"EMP{i + 1:03d}",
                                           "job_title": "Оператор"})


def _wait_health(timeout=60):
    for _ in range(timeout):
        try:
            if httpx.get("http://127.0.0.1:8090/sim/v1/health", timeout=2).status_code == 200:
                return
        except Exception:  # noqa: BLE001, S110
            pass
        time.sleep(1)
    raise AssertionError("сервіс не піднявся")


def _recreate(extra_env: dict | None):
    off = ROOT / "tests" / "stand" / "_odoo.override.yml"
    gw = docker("network", "inspect", "odoo_default", "-f", "{{(index .IPAM.Config 0).Gateway}}")
    env = {"SIM_MODE": "follow_odoo", "SIM_RESTORE_SNAPSHOT": "0", "SIM_ODOO_URL": f"http://{gw}:18069", "SIM_ODOO_DB": DB,
           "SIM_ODOO_USER": "admin", "SIM_ODOO_APIKEY": "admin", "SIM_ODOO_EXPORT_TOKEN": EXPORT,
           "SIM_ALLOW_OUTBOUND": f"mosquitto,127.0.0.1,{gw}", "SIM_ODOO_FOLLOW_S": "3", "SIM_ODOO_FOLLOW_SLOW_S": "10",
           **(extra_env or {})}
    off.write_text("services:\n  iot_sim:\n    environment:\n" + "".join(f'      {k}: "{v}"\n' for k, v in env.items()))
    try:
        subprocess.run(["docker", "compose", "-f", "docker-compose.sim.yml", "--profile", "dev", "-f", str(off), "up",
                        "-d", "--force-recreate", "iot_sim"], cwd=ROOT, check=True, capture_output=True)
        _wait_health()
    finally:
        off.unlink()
    return gw


@pytest.fixture(scope="module")
def follow(odoo, token):
    _seed(odoo)
    odoo.param("url", "http://127.0.0.1:8090")
    odoo.param("token", token)
    odoo.param("export_token", EXPORT)
    odoo.param("write_enabled", "True")
    odoo.param("level0_after_min", "1")
    _recreate(None)
    time.sleep(15)
    yield
    fresh_service()


@pytest.mark.timeout(300)
async def test_tk01_follow_odoo_states(follow, api, host, env_get):
    """AC-07: SAW-1 (workorder progress) → CurrentState=3, CNC-2 (blocked) → 4, Error=True; PM5560 CNC-2 = 0."""
    assert api.post("/mode", {"mode": "follow_odoo"}).status_code == 200        # fixture api ставить scenario
    await asyncio.sleep(12)
    assert api.get("/status").json()["mode"] == "follow_odoo"
    assert api.post("/time", {"set": "2026-10-12T10:30:00+03:00"}).status_code == 200      # робоча зміна (factor лишається 1)
    c = Client(f"opc.tcp://{host}:4840/f3d/", timeout=10)
    c.set_user("collector")
    c.set_password(env_get("SIM_OPCUA_PASS"))
    async with c:
        ns = await c.get_namespace_index(NS)
        for _ in range(30):
            st = await c.get_node(f"ns={ns};s=SAW-1.State.Machine.Overview.CurrentState").read_value()
            if st == 3:
                break
            await asyncio.sleep(2)
        assert st == 3
        cnc = c.get_node(f"ns={ns};s=CNC-2.State.Machine.Overview.CurrentState")
        for _ in range(15):
            if await cnc.read_value() == 4:
                break
            await asyncio.sleep(2)
        assert await cnc.read_value() == 4
        assert await c.get_node(f"ns={ns};s=CNC-2.State.Machine.Flags.Error").read_value() is True
    assert api.post("/time", {"factor": 5}).status_code == 409          # у follow_odoo factor фіксований (A-12)


@pytest.mark.timeout(400)
def test_tk10_biostar_people_from_odoo(follow, api, host, env_get):
    """AC-16/55: 35 працівників з Odoo, sim-час 06:30 → події входу 4102/4867; пагінація offset/hint."""
    assert len(api.get("/status").json()) > 0
    api.post("/mode", {"mode": "scenario"})
    api.post("/time", {"set": "2026-10-12T06:30:00+03:00", "factor": 10})
    api.scenario("shift")
    time.sleep(110)
    c = httpx.Client(base_url=f"http://{host}:8081", timeout=10)
    r = c.post("/api/login", json={"User": {"login_id": "admin", "password": env_get("SIM_BIOSTAR_PASS")}})
    c.headers["bs-session-id"] = r.headers["bs-session-id"]
    q = {"orders": [{"column": "datetime", "descending": False}]}

    def search(**kw):
        return c.post("/api/events/search", json={"Query": {**q, **kw}}).json()["EventCollection"]

    full = search(limit=500)
    assert int(full["total"]) >= 20, full["total"]
    users = {r["user_id"]["user_id"] for r in full["rows"] if r.get("user_id")}
    assert len(users) >= 20
    assert all(r["event_type_id"]["code"] in ("4102", "4867") for r in full["rows"] if r["tna_key"] == "1")
    p1, p2 = search(limit=10, offset=0), search(limit=10, offset=10)
    nxt = search(limit=10, hint=p1["rows"][-1]["hint"])
    assert [r["id"] for r in p2["rows"]] == [r["id"] for r in nxt["rows"]]
    assert len({r["id"] for r in p1["rows"] + p2["rows"]}) == 20
    d = [r["datetime"] for r in p1["rows"] + p2["rows"]]
    assert d == sorted(d)
    api.post("/mode", {"mode": "follow_odoo"})


@pytest.mark.timeout(600)
def test_tk15_odoo_panel_end_to_end(follow, odoo, api):
    """AC-25…29, 33, 58, 59: пульт Odoo: зв'язок, режим/прискорення, сценарій, збій, рівень 0 при зупинці сервісу."""
    panel = odoo.k("td.sim.panel", "search", [], limit=1) or [odoo.k("td.sim.panel", "create", {})]
    pid = panel[0]
    odoo.k("td.sim.panel", "action_check", [pid])
    p = odoo.k("td.sim.panel", "read", [pid], fields=["state", "version", "mode", "level0_state"])[0]
    assert p["state"] in ("online", "degraded") and p["version"]
    cron_id = odoo.xid("td_iot_sim", "cron_iot_sim")
    cron0 = odoo.k("ir.cron", "read", [cron_id], fields=["active"])[0]
    assert cron0["active"] is False and p["level0_state"] == "auto_off"                   # AC-26
    # 2) режим scenario + прискорення 5
    odoo.k("td.sim.panel", "write", [pid], {"mode_new": "scenario", "factor_new": 5})
    odoo.k("td.sim.panel", "action_apply_mode", [pid])
    odoo.k("td.sim.panel", "action_apply_factor", [pid])
    st = api.get("/status").json()
    assert st["mode"] == "scenario" and st["factor"] == 5
    # 3) сценарій filter_clogged RV-05 value=285
    scen = odoo.xid("td_iot_sim", "scenario_filter_clogged")
    dev = odoo.k("td.sim.device", "search", [("code", "=", "RV-05")], limit=1)
    assert dev, "RV-05 немає у td.sim.device"
    wiz = odoo.k("td.sim.run.wizard", "create", {"scenario_id": scen, "device_id": dev[0],
                                                  "params_text": '{"value": 285, "ramp_min": 1}'})
    act = odoo.k("td.sim.run.wizard", "action_confirm", [wiz])
    run = odoo.k("td.sim.run", "read", [act["res_id"]], fields=["state", "name", "sim_run_id"])[0]
    assert run["state"] == "running" and run["sim_run_id"] and run["name"].startswith("RUN/")     # AC-27
    assert api.wait(lambda: api.sig("ventilation/units/RV-05/filter_dp_pa") > 250, timeout=60, step=1)
    ev = odoo.k("td.sim.event", "search_count", [("kind", "=", "command")])
    assert ev >= 1
    # 4) збій CNC-2 і скидання
    cnc = odoo.k("td.sim.device", "search", [("code", "=", "CNC-2")], limit=1)
    fw = odoo.k("td.sim.fault.wizard", "create", {"device_id": cnc[0], "reason": "generic"})
    odoo.k("td.sim.fault.wizard", "action_confirm", [fw])
    assert api.get("/devices/CNC-2").json()["state"] == "fault"                            # AC-28
    odoo.k("td.sim.device", "action_clear", cnc)
    assert api.get("/devices/CNC-2").json()["state"] != "fault"
    # 5) зупинка сервісу → через level0_after_min=1 хв крон рівня 0 вмикається; запуск → вимикається (AC-29/58)
    docker("stop", "iot_sim-iot_sim-1")
    try:
        ok = False
        for _ in range(60):
            time.sleep(5)
            if odoo.k("ir.cron", "read", [cron_id], fields=["active"])[0]["active"]:
                ok = True
                break
        assert ok, "крон рівня 0 не увімкнувся за ≤ 5 хв після зупинки сервісу"
    finally:
        docker("start", "iot_sim-iot_sim-1")
        _wait_health()
    for _ in range(40):
        time.sleep(5)
        if not odoo.k("ir.cron", "read", [cron_id], fields=["active"])[0]["active"]:
            break
    assert odoo.k("ir.cron", "read", [cron_id], fields=["active"])[0]["active"] is False
    odoo.k("td.sim.panel", "write", [pid], {"mode_new": "follow_odoo"})
    odoo.k("td.sim.panel", "action_apply_mode", [pid])


@pytest.mark.timeout(300)
def test_tp06_odoo_signal_refresh_and_events(follow, odoo):
    """ТП-06 (частково, без 24 год): refresh td.sim.signal 1017 записів ≤ 5 с; 2 000 подій через API-03; ротація."""
    panel = odoo.k("td.sim.panel", "search", [], limit=1)[0]
    t0 = time.perf_counter()
    odoo.k("td.sim.panel", "action_refresh_signals", [panel])
    dt = time.perf_counter() - t0
    n = odoo.k("td.sim.signal", "search_count", [("protocol", "!=", "none")])
    assert n >= 1000 and dt <= 5, (n, dt)
    ev0 = odoo.k("td.sim.event", "search_count", [])
    stamp = int(time.time())
    batch = [{"ts": "2026-10-12T10:00:00+03:00", "kind": "info", "device": "SAW-1", "message": f"stand event {i}",
              "payload": {"event_id": f"stand-{stamp}-{i:05d}"}} for i in range(2000)]
    hdr = {"Authorization": "Bearer " + EXPORT}
    t0 = time.perf_counter()
    for i in range(0, 2000, 100):     # API-03: ≤ 100 подій у запиті
        r = httpx.post(ODOO + "/f3d/sim/events", json={"events": batch[i:i + 100]}, headers=hdr, timeout=30)
        assert r.status_code == 200 and r.json()["accepted"] == 100, r.text
    assert time.perf_counter() - t0 < 60
    assert odoo.k("td.sim.event", "search_count", []) >= ev0 + 2000
    again = httpx.post(ODOO + "/f3d/sim/events", json={"events": batch[:50]}, headers=hdr).json()
    assert again["accepted"] == 0                                  # дедуплікація за event_id
