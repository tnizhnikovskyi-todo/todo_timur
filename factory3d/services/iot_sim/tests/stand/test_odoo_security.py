"""ТБ-08 (права Odoo), ТБ-09 (токени навхрест), ТБ-10 (neutralize.sql) — на Odoo із шаблонною базою f3d_w6
(STAND_ODOO_*)."""

import os
import subprocess
import time
import xmlrpc.client as xmlrpc
from pathlib import Path

import httpx
import pytest

from .test_odoo_e2e import DB, EXPORT, ODOO, Odoo

TOOLS = Path(__file__).resolve().parents[4] / "tools" / "odoo"
MODELS = ["td.sim.panel", "td.sim.device", "td.sim.signal", "td.sim.scenario", "td.sim.run", "td.sim.event"]
TOKEN_FIELDS = ("td_sim_token", "td_sim_export_token", "td_sim_url")


@pytest.fixture(scope="module")
def odoo():
    try:
        httpx.get(ODOO + "/f3d/sim/health", timeout=3)
        return Odoo()
    except Exception:  # noqa: BLE001
        pytest.skip("Odoo з td_iot_sim недоступний (STAND_ODOO_URL)")


def _user(od, login, group_xmlids):
    gids = [od.xid(*g.split(".")) for g in group_xmlids]
    uid = od.k("res.users", "search", [("login", "=", login)])
    if not uid:
        uid = [
            od.k(
                "res.users",
                "create",
                {"name": login, "login": login, "password": "Pw-" + login + "-1!", "group_ids": [(6, 0, gids)]},
            )
        ]
    return uid[0], "Pw-" + login + "-1!"


def _as(login, pw):
    uid = xmlrpc.ServerProxy(ODOO + "/xmlrpc/2/common").authenticate(DB, login, pw, {})
    proxy = xmlrpc.ServerProxy(ODOO + "/xmlrpc/2/object", allow_none=True)

    def call(model, method, *args, **kw):
        return proxy.execute_kw(DB, uid, pw, model, method, list(args), kw)

    return call


def test_tb08_group_user_cannot_write_and_manager_has_no_tokens(odoo):
    _user(odoo, "f3d_sim_reader_t", ["base.group_user", "td_factory3d.group_td_user"])
    reader = _as("f3d_sim_reader_t", "Pw-f3d_sim_reader_t-1!")
    for m in MODELS:
        assert reader(m, "search_count", []) >= 0  # читати можна
        ids = reader(m, "search", [], limit=1)
        with pytest.raises(xmlrpc.Fault, match="AccessError|not allowed|доступ"):
            reader(m, "create", {})
        if ids:
            with pytest.raises(xmlrpc.Fault, match="AccessError|not allowed|доступ"):
                reader(m, "write", ids, {"create_uid": 1})
            with pytest.raises(xmlrpc.Fault, match="AccessError|not allowed|доступ"):
                reader(m, "unlink", ids)
    _user(odoo, "f3d_sim_mgr_t", ["base.group_user", "td_factory3d.group_td_manager"])
    mgr = _as("f3d_sim_mgr_t", "Pw-f3d_sim_mgr_t-1!")
    f = mgr("res.config.settings", "fields_get")
    assert not any(n in f for n in TOKEN_FIELDS)
    admin_f = odoo.k("res.config.settings", "fields_get")
    assert all(n in admin_f for n in TOKEN_FIELDS)


def test_tb09_tokens_not_interchangeable(odoo):
    odoo.param("token", "panel-token-0123456789abcdef0123456789")
    odoo.param("export_token", EXPORT)
    swapped = {"Authorization": "Bearer panel-token-0123456789abcdef0123456789"}  # token замість export_token
    assert httpx.get(ODOO + "/f3d/sim/devices", headers=swapped).status_code == 401
    assert httpx.post(ODOO + "/f3d/sim/events", json={"events": []}, headers=swapped).status_code == 401
    assert httpx.get(ODOO + "/f3d/sim/devices", headers={"Authorization": "Bearer " + EXPORT}).status_code == 200
    assert httpx.get(ODOO + "/f3d/sim/devices").status_code == 401
    # «навхрест» у зворотний бік: export_token не приймається сервісом як токен REST керування
    api = httpx.get("http://127.0.0.1:8090/sim/v1/status", headers={"Authorization": "Bearer " + EXPORT})
    assert api.status_code in (401, 429)


@pytest.mark.timeout(400)
def test_tb10_neutralize_sql_on_copy():
    """neutralize.sql на копії бази: крони неактивні, кнопки → UserError «не налаштовано»."""
    env = {**os.environ, "F3D_TEST_INSTALL": "td_iot_sim", "ODOO_HTTP_INTERFACE": "127.0.0.1"}
    db, port = "f3d_w6n", "18070"
    run = lambda *a, **kw: subprocess.run(a, env=env, check=True, capture_output=True, text=True, **kw)
    subprocess.run([str(TOOLS / "serve.sh"), "stop", db], env=env, check=False, capture_output=True)
    subprocess.run([str(TOOLS / "drop_db.sh"), db], env=env, check=False, capture_output=True)
    run(str(TOOLS / "new_db.sh"), db)
    run(str(TOOLS / "update.sh"), db)
    psql = ["bash", "-c", f'source {TOOLS}/env.sh; "$PG_BINDIR/psql" -X -q -d {db} -v ON_ERROR_STOP=1 -c "$1"', "_"]
    run(*psql, "UPDATE ir_config_parameter SET value='http://127.0.0.1:8090' WHERE key='td.iot_sim.url'")
    run(*psql, "UPDATE ir_config_parameter SET value='tok' WHERE key='td.iot_sim.token'")
    run(
        *psql,
        "UPDATE ir_cron SET active=true WHERE id IN (SELECT res_id FROM ir_model_data WHERE module="
        "'td_iot_sim' AND model='ir.cron')",
    )
    sql = (Path(__file__).resolve().parents[4] / "odoo_addons" / "td_iot_sim" / "neutralize.sql").read_text()
    subprocess.run(
        ["bash", "-c", f'source {TOOLS}/env.sh; "$PG_BINDIR/psql" -X -q -d {db} -v ON_ERROR_STOP=1 -f -'],
        input=sql,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    run(str(TOOLS / "serve.sh"), db, port)
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                if httpx.get(url + "/f3d/sim/health", timeout=2).status_code == 200:
                    break
            except Exception:  # noqa: BLE001, S110
                pass
            time.sleep(2)
        uid = xmlrpc.ServerProxy(url + "/xmlrpc/2/common").authenticate(db, "admin", "admin", {})
        o = xmlrpc.ServerProxy(url + "/xmlrpc/2/object", allow_none=True)

        def k(model, method, *a, **kw):
            return o.execute_kw(db, uid, "admin", model, method, list(a), kw)

        crons = k(
            "ir.cron",
            "read",
            [
                k("ir.model.data", "search_read", [("module", "=", "td_iot_sim"), ("name", "=", n)], fields=["res_id"])[
                    0
                ]["res_id"]
                for n in ("cron_iot_sim", "cron_td_sim_status")
            ],
            fields=["active"],
        )
        assert crons and not any(c["active"] for c in crons)
        panel = k("td.sim.panel", "search", [], limit=1)[0]
        assert k("td.sim.panel", "read", [panel], fields=["state"])[0]["state"] == "unconfigured"
        res = k("td.sim.panel", "action_check", [panel])  # перевірка зв'язку — повідомлення danger, не виняток
        assert res["params"]["type"] == "danger" and any(
            w in res["params"]["message"] for w in ("налаштовано", "вимкнено")
        )
        for method in ("action_stop_all", "action_reset", "action_apply_factor"):
            with pytest.raises(xmlrpc.Fault, match="налаштовано|configured|вимкнено|заборонен"):
                k("td.sim.panel", method, [panel])
    finally:
        subprocess.run([str(TOOLS / "serve.sh"), "stop", db], env=env, check=False, capture_output=True)


def test_tb05_odoo_devices_endpoint_signal_set(odoo):
    """ТБ-05, 4-те джерело: GET /f3d/sim/devices (сигнали) = множина code+address з catalog/signals.csv."""
    import csv
    import io

    cat = Path(__file__).resolve().parents[2] / "catalog" / "signals.csv"
    want = {(r["code"], r["address"]) for r in csv.DictReader(io.StringIO(cat.read_text(encoding="utf-8")))}
    odoo.param("export_token", EXPORT)
    r = httpx.get(ODOO + "/f3d/sim/devices", headers={"Authorization": "Bearer " + EXPORT}, timeout=60)
    assert r.status_code == 200
    got = {(s["code"], s["address"]) for d in r.json()["devices"] for s in d["signals"]}
    assert got == want, (len(got), len(want), sorted(want - got)[:3], sorted(got - want)[:3])
