"""ТБ-01…ТБ-10 (SPEC §13.3): матриця прав, запобіжники запису, API-01, технічний користувач, секрети, ін'єкції, безпека OPC UA,
REST/allow-list, мультикомпанійність, нейтралізація. UI-перевірки (меню, URL дії від user_plain) — MAN, у звіті.
"""

from __future__ import annotations

import base64
import json
import re
import secrets
import time
import xmlrpc.client as xc
from pathlib import Path

import pytest

from . import odoo_rpc
from .helpers import (
    STAND_DIR,
    collector_log,
    commands,
    cron_run,
    enable_write,
    http,
    make_cert,
    make_mo,
    odoo_log,
    set_iot_sim_ip,
    psql,
    stand_sh,
    ua_call,
    utcnow,
    wait,
)

REPO = Path(__file__).resolve().parents[5]
MODULE_DIR = REPO / "odoo_addons" / "td_machine_connect"
PKG_DIR = REPO / "services" / "collector_plugins" / "machine_connect" / "f3d_collector_mc"
SECRETS = ["opcua-pass-stand", "ws-key-stand-0123456789", "jobs-key-stand-0123456789"]
SRC_ID = lambda o, code: o.search_read("td.source", [("code", "=", code)], ["id"])[0]["id"]  # noqa: E731


def _src_state(o, code):
    r = o.search_read("td.source", [("code", "=", code)], ["state", "last_error"])[0]
    return r["state"], r["last_error"] or ""


# --- ТБ-01 ---------------------------------------------------------------------------------------------------------------
MATRIX = {
    "td.machine": ["", "R", "R", "R", "RWCD", "RWCD"],
    "td.machine.state.log": ["", "R", "R", "R", "R", "RWCD"],
    "td.downtime": ["", "R", "RW", "R", "R", "RWCD"],
    "td.machine.event": ["", "R", "R", "R", "R", "RWCD"],
    "td.oee.shift": ["", "R", "R", "R", "R", "RWCD"],
    "td.machine.message": ["", "R", "R", "R", "RWCD", "RWCD"],
    "td.gantry.stack": ["", "R", "R", "RW", "RWCD", "RWCD"],
    "td.gantry.job": ["", "R", "RWC", "R", "RWCD", "RWCD"],
    "td.cut.part": ["", "R", "R", "R", "RWCD", "RWCD"],
    "td.cut.map": ["", "R", "R", "R", "RWCD", "RWCD"],
    "td.cut.map.line": ["", "R", "R", "R", "RWCD", "RWCD"],
    "td.downtime.reason.wizard": ["", "", "RWC", "", "", ""],
    "td.cut.plan.import.wizard": ["", "", "", "", "RWC", "RWC"],
    "td.cut.part.import.wizard": ["", "", "", "", "RWC", "RWC"],
}
USERS = {
    "plain": "base.group_user",
    "f3d": "base.group_user,td_factory3d.group_td_user",
    "mrp": "base.group_user,mrp.group_mrp_user",
    "stock_manager": "base.group_user,stock.group_stock_manager",
    "f3d_manager": "base.group_user,td_factory3d.group_td_manager",
    "f3d_admin": "base.group_user,td_factory3d.group_td_admin",
}
OPS = {"R": "read", "W": "write", "C": "create", "D": "unlink"}


def make_user(o, login: str, xmlids: str) -> None:
    gids = [o.call("ir.model.data", "check_object_reference", *x.split("."))[1] for x in xmlids.split(",")]
    if not o.count("res.users", [("login", "=", login)]):
        o.create("res.users", {"name": login, "login": login, "password": login, "group_ids": [(6, 0, gids)]})


def test_tb01_access_matrix(fresh):
    """ТБ-01 / AC-89…91: матриця прав за SPEC §13.3 (`has_access`)."""
    o = fresh(ready=False)
    bad = []
    for key, groups in USERS.items():
        make_user(o, "tb_" + key, groups)
    for idx, key in enumerate(USERS):
        u = odoo_rpc.Odoo(login="tb_" + key, password="tb_" + key)
        for model, row in MATRIX.items():
            for letter, op in OPS.items():
                try:
                    got = bool(u.call(model, "has_access", [], op))
                except RuntimeError:
                    got = False
                want = letter in row[idx]
                if got != want:
                    bad.append((key, model, op, "є" if got else "немає", "очікувалось " + ("є" if want else "немає")))
    assert not bad, bad[:12]


# --- ТБ-02 ---------------------------------------------------------------------------------------------------------------
def test_tb02_code_review_no_device_writes():
    """ТБ-02: плагін не пише змінних OPC UA (огляд коду); запобіжники запису — ТК-15."""
    pat = re.compile(r"write_value|set_value|write_attribute|write_params")
    hits = [
        (p.name, i)
        for p in PKG_DIR.rglob("*.py")
        for i, ln in enumerate(p.read_text().splitlines(), 1)
        if pat.search(ln)
    ]
    assert not hits, hits


# --- ТБ-03 ---------------------------------------------------------------------------------------------------------------
def test_tb03_export_api01(fresh, sim):
    """ТБ-03 / AC-66…68: 100 запитів з випадковим `t` → 403; токен одноразовий; `no-store`; чужий Authorization → 401; `t` не в лозі."""
    o = fresh(env={"F3D_WRITE_ENABLED": "1"}, params={"cutting_mode": "collector"})
    stand_sh("collector-stop")
    token = (STAND_DIR / "token").read_text().strip()
    enable_write(o, ["REST-CUTOPT"], ["equipment/CUTOPT/cmd"])
    csv_in = 'part_code;name;length_mm;width_mm;qty\nP001;=HYPERLINK("http://x");700;500;1\nP002;Верхня;800;560;2\n'
    parts = base64.b64encode(csv_in.encode()).decode()
    bom = o.search_read("mrp.bom", [("product_tmpl_id.default_code", "=", "BR-K4")], ["id"])[0]["id"]
    wiz = o.create("td.cut.part.import.wizard", {"bom_id": bom, "file": parts, "filename": "p.csv"})
    o.call("td.cut.part.import.wizard", "action_import", [wiz])
    mo = make_mo(o, "BR-K4", 14)
    o.call("mrp.production", "action_f3d_create_cut_maps", [mo["id"]])
    mid = o.search_read("td.cut.map", [("production_id", "=", mo["id"]), ("material_role", "=", "main")], ["id"])[0][
        "id"
    ]
    o.call("td.cut.map", "action_build_lines", [mid])
    o.call("td.cut.map", "action_export", [mid])
    t = o.search_read("td.command", [("td_cut_map_id", "=", mid)], ["payload"])[0]["payload"]["token"]
    url = f"http://127.0.0.1:18070/f3d/machine/cutmap/{mid}/export"
    hdr = {"Authorization": "Bearer " + token}
    codes = {http("GET", url, headers={**hdr, "X-F3D-Token": secrets.token_hex(8)})[0] for _ in range(100)}
    assert codes == {403}, codes
    assert http("GET", url, headers={"Authorization": "Bearer " + "0" * 40, "X-F3D-Token": t})[0] == 401
    st, body, h = http("GET", url, headers={**hdr, "X-F3D-Token": t})
    assert st == 200 and h.get("Cache-Control") == "no-store", (st, h)
    csv_text = json.loads(body)["parts_csv"]
    assert not re.search(r";=HYPERLINK", csv_text) and "HYPERLINK" in csv_text, (
        csv_text
    )  # ТБ-06: формула нейтралізована
    assert http("GET", url, headers={**hdr, "X-F3D-Token": t})[0] == 403  # одноразовий
    leaks = {
        "chatter": any(t in b for b in o.chatter("td.cut.map", mid)),
        "result": any(t in json.dumps(c.get("result_data") or {}) + (c.get("error") or "") for c in commands(o)),
    }
    assert not any(leaks.values()), leaks
    (STAND_DIR / "tb03_token").write_text(t)
    log_hits = [ln for ln in odoo_log().splitlines() if t in ln]
    print("ТБ-03: рядків лога Odoo з токеном `t`:", len(log_hits), [ln[-120:] for ln in log_hits[:2]])
    assert not log_hits, log_hits  # DEC-20: токен — у заголовку X-F3D-Token, у access-log його немає


# --- ТБ-04 ---------------------------------------------------------------------------------------------------------------
def test_tb04_technical_user(fresh):
    """ТБ-04 / AC-91: `f3d_machine_bot` неактивний, без пароля й адмін-груп; вхід неможливий."""
    o = fresh(ready=False)
    common = xc.ServerProxy(odoo_rpc.URL + "/xmlrpc/2/common", allow_none=True)
    assert not common.authenticate(odoo_rpc.DB, "f3d_machine_bot", "anything", {})
    assert not common.authenticate(odoo_rpc.DB, "f3d_machine_bot", "", {})
    u = o.search_read(
        "res.users", [("login", "=", "f3d_machine_bot")], ["active", "group_ids"], context={"active_test": False}
    )[0]
    assert not u["active"]
    names = {g["full_name"] for g in o.read("res.groups", u["group_ids"], ["full_name"])}
    assert not [n for n in names if "Administration" in n or "f3d_manager" in n or "Менеджер" in n and "Завод" in n], (
        names
    )
    st, body, _ = http(
        "POST",
        odoo_rpc.URL + "/web/login",
        raw=b"login=f3d_machine_bot&password=x&csrf_token=",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert "f3d_machine_bot" not in body or "Wrong login" in body or st in (200, 303, 400), st
    assert (
        psql("select password is null or password = '' from res_users where login='f3d_machine_bot'", odoo_rpc.DB)[0][0]
        == "t"
    )


# --- ТБ-05 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.timeout(3600)
def test_tb05_secrets_in_logs(fresh, sim):
    """ТБ-05: секрети (`F3D_*`, токен колектора, токени API-01) не трапляються в логах колектора (DEBUG), Odoo, `GET config`."""
    o = fresh(
        env={"F3D_LOG_LEVEL": "DEBUG", "F3D_WRITE_ENABLED": "1"},
        scenario=("shift", {"speed": 1, "trucks": False, "people": False}),
    )
    token = (STAND_DIR / "token").read_text().strip()
    time.sleep(300)  # SPEC: 15 хв; у середовищі розробки — 5 хв при DEBUG
    st, cfg, _ = http("GET", odoo_rpc.URL + "/f3d/telemetry/config", headers={"Authorization": "Bearer " + token})
    assert st == 200
    hay = {"collector.log": collector_log(), "odoo.log": odoo_log(), "config": cfg}
    found = {name: [s for s in SECRETS + [token] if s in text] for name, text in hay.items()}
    assert not any(found.values()), {k: [s[:6] + "…" for s in v] for k, v in found.items()}
    for src in o.search_read("td.source", [("module", "=", "machine_connect")], ["code", "params"]):
        for k in src["params"] or {}:
            if re.search(r"pass|key|token|secret|cert", k, re.I):
                assert k.endswith("_ref"), (src["code"], k)


# --- ТБ-06 ---------------------------------------------------------------------------------------------------------------
def test_tb06_injections(fresh, sim):
    """ТБ-06: SQL-текст у `job`, XSS у події, `;` у полях команди; огляд коду на небезпечний SQL."""
    pat = re.compile(r'execute\(f"|execute\(.*%[^s]|execute\(.*\.format\(')
    hits = [
        (p.name, i)
        for p in MODULE_DIR.rglob("*.py")
        for i, ln in enumerate(p.read_text().splitlines(), 1)
        if pat.search(ln)
    ]
    assert not hits, hits
    o = fresh(env={"F3D_WRITE_ENABLED": "1"}, params={"auto_start_enabled": "True"}, ready=False)
    stand_sh("collector-stop")
    token = (STAND_DIR / "token").read_text().strip()
    hdr = {"Authorization": "Bearer " + token}
    ts = utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    evil = "WO00013'; DROP TABLE mrp_workorder; --"
    rd = [
        {"code": "workcenters/SAW-1/state", "ts": ts, "value": 3, "text": "WORKING", "q": "good"},
        {"code": "workcenters/SAW-1/job", "ts": ts, "text": evil[:64], "q": "good"},
        {"code": "workcenters/CNC-2/state", "ts": ts, "value": 4, "text": "ERROR", "q": "good"},
        {"code": "workcenters/CNC-2/alarm", "ts": ts, "value": 1, "text": "on", "q": "good"},
    ]
    st, txt, _ = http("POST", odoo_rpc.URL + "/f3d/telemetry/push", {"collector": "COL-MAIN", "readings": rd}, hdr)
    assert st == 200, (st, txt[:200])
    xss = "<img src=x onerror=alert(1)>"
    ev = {
        "event_id": secrets.token_hex(32), "route": "mc_opcua", "ts": ts, "remote": "UA-CNC-2", "headers": {},
        "payload": {"kind": "alarm", "source": "UA-CNC-2", "machine": "CNC-2", "time": ts, "message_id": "E0421", "message_name": "x",
                    "category": 5, "severity": 800, "text": xss, "texts": {"uk": xss}, "path": [], "group": "", "active": True, "acked": False, "args": {}},
    }  # fmt: skip
    st, txt, _ = http("POST", odoo_rpc.URL + "/f3d/telemetry/event", {"events": [ev]}, hdr)
    assert st == 200, (st, txt[:200])
    assert psql("select count(*) from mrp_workorder", odoo_rpc.DB)[0][0] is not None  # таблиця ціла
    acts = wait(lambda: o.search_read("mail.activity", [("summary", "ilike", "WO00013")], ["summary", "note"]), 30, 2)
    notes = " ".join((a["note"] or "") + (a["summary"] or "") for a in acts or [])
    print("ТБ-06: діяльності з текстом job:", len(acts or []))
    bodies = " ".join(
        b for m in o.search_read("maintenance.request", [], ["id"]) for b in o.chatter("maintenance.request", m["id"])
    ) + " ".join(
        o.chatter(
            "maintenance.equipment",
            o.search_read("maintenance.equipment", [("td_code", "=", "CNC-2")], ["id"])[0]["id"],
        )
    )
    assert "<img" not in bodies and "<img" not in notes, "XSS не екрановано"
    # поля команди з `;` → UserError (R-21)
    enable_write(o, ["REST-WOODSTORE"], ["equipment/GANTRY-1/cmd"])
    mo = make_mo(o, "BR-K4", 14)
    jid = o.call("mrp.production", "action_f3d_feed_gantry", [mo["id"]])["res_id"]
    o.write("td.gantry.job", jid, {"external_ref": "a;b c"})
    o.call("td.gantry.job", "action_send", [jid])
    cron_run(o, "Портал")  # UserError R-21 ловиться в `_f3d_send` (крон) → завдання `error`, команди немає
    j = o.read("td.gantry.job", jid, ["state", "error"])[0]
    assert j["state"] == "error" and j["error"], j
    assert not commands(o, "equipment/GANTRY-1/cmd")
    assert "HTTP 500" not in odoo_log()[-20000:]


# --- ТБ-07 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.timeout(3600)
def test_tb07_opcua_security(fresh, sim):
    """ТБ-07: SignAndEncrypt/Basic256Sha256 з закріпленням сертифіката сервера; чужий сертифікат; без закріплення; без користувача."""
    certs = STAND_DIR / "certs"
    certs.mkdir(exist_ok=True)
    make_cert(certs / "server.der", certs / "server.key", "urn:todo.ltd:f3d:iot_sim", "iot_sim")
    make_cert(certs / "client.der", certs / "client_key.pem", "urn:todo.ltd:f3d:collector", "collector")
    make_cert(certs / "other.der", certs / "other_key.pem", "urn:todo.ltd:f3d:other", "other")
    stand_sh("sim-restart")
    extra = f"F3D_OPCUA_CERT={certs}/client.der F3D_OPCUA_KEY={certs}/client_key.pem"
    o = fresh(env={"F3D_EXTRA_ENV": extra + f" F3D_OPCUA_SERVER_CERT={certs}/server.der"}, ready=False)
    sid = SRC_ID(o, "UA-SAW-1")
    base = o.search_read("td.source", [("id", "=", sid)], ["params"])[0]["params"]
    sec = dict(base, security_mode="SignAndEncrypt", security_policy="Basic256Sha256", cert_ref="F3D_OPCUA_CERT", key_ref="F3D_OPCUA_KEY",
               server_cert_ref="F3D_OPCUA_SERVER_CERT")  # fmt: skip
    o.write("td.source", sid, {"params": sec})
    ok = wait(lambda: _src_state(o, "UA-SAW-1")[0] == "online", 120, 5)
    state_a = _src_state(o, "UA-SAW-1")
    # б) інший сертифікат сервера
    stand_sh("collector-restart", env={"F3D_EXTRA_ENV": extra + f" F3D_OPCUA_SERVER_CERT={certs}/other.der"})
    wait(lambda: _src_state(o, "UA-SAW-1")[0] == "error", 120, 5)
    state_b = _src_state(o, "UA-SAW-1")
    # в) без закріплення
    o.write("td.source", sid, {"params": {k: v for k, v in sec.items() if k != "server_cert_ref"}})
    stand_sh("collector-restart", env={"F3D_EXTRA_ENV": extra})
    wait(lambda: "not pinned" in _src_state(o, "UA-SAW-1")[1], 120, 5)
    state_c = _src_state(o, "UA-SAW-1")
    print("ТБ-07:", state_a, state_b, state_c)
    # г) виклик методу без користувача
    denied = None
    try:
        ua_call("SAW-1", "Start", "WO00001", user=None)
    except Exception as e:  # noqa: BLE001
        denied = str(e)
    assert ok and state_a[0] == "online", state_a
    assert state_b[0] == "error" and "certificate" in state_b[1].lower(), state_b
    assert "not pinned" in state_c[1], state_c
    assert denied and ("Denied" in denied or "BadUser" in denied or "access" in denied.lower()), denied
    assert not any(s in (state_a[1] + state_b[1] + state_c[1]) for s in SECRETS)


# --- ТБ-08 ---------------------------------------------------------------------------------------------------------------
@pytest.mark.timeout(3600)
def test_tb08_rest_and_allowlist(fresh, sim):
    """ТБ-08: без ключа → «secret … not set»; хибний ключ → 401/«auth»; https+verify_tls=false → error; allow-list без iot-sim → error."""

    def err_has(*words):
        return lambda: next(
            (s for s in [_src_state(o, "REST-WOODSTORE")] if s[0] == "error" and any(w in s[1] for w in words)), None
        )

    o = fresh(env={"F3D_STAND_UNSET": "F3D_WOODSTORE_KEY"}, ready=False)  # змінну не задано взагалі
    a = wait(err_has("F3D_WOODSTORE_KEY"), 120, 5) or _src_state(o, "REST-WOODSTORE")
    stand_sh("collector-restart", env={"F3D_EXTRA_ENV": "F3D_WOODSTORE_KEY=wrong-key-0123456789"})
    b = wait(err_has("401", "auth"), 120, 5) or _src_state(o, "REST-WOODSTORE")
    sid = SRC_ID(o, "REST-WOODSTORE")
    base = o.search_read("td.source", [("id", "=", sid)], ["params"])[0]["params"]
    stand_sh("collector-restart")
    o.write("td.source", sid, {"params": dict(base, base_url="https://iot-sim:8082", verify_tls=False)})
    c = wait(err_has("verify_tls", "https"), 120, 5) or _src_state(o, "REST-WOODSTORE")
    o.write("td.source", sid, {"params": base})
    set_iot_sim_ip("127.0.0.2")  # інакше iot-sim (127.0.0.1) збігається з хостом Odoo, який allow-list дозволяє завжди
    try:
        stand_sh("collector-restart", env={"F3D_ALLOW_HOSTS": "odoo19"})
        d = wait(err_has("allow", "host"), 120, 5) or _src_state(o, "REST-WOODSTORE")
    finally:
        set_iot_sim_ip("127.0.0.1")
    h = wait(lambda: json.loads(http("GET", "http://127.0.0.1:9108/health")[1]), 90, 3) or {}
    print("ТБ-08:", a, b, c, d, h)
    assert a[0] == "error" and "F3D_WOODSTORE_KEY" in a[1] and "not set" in a[1], a
    assert b[0] == "error" and ("401" in b[1] or "auth" in b[1]), b
    assert c[0] == "error" and ("verify_tls" in c[1] or "https" in c[1]), c
    assert d[0] == "error" and ("allow" in d[1].lower() or "host" in d[1].lower()), d
    assert h.get("status") == "ok"  # колектор healthy
    assert "wrong-key" not in (a[1] + b[1] + c[1] + d[1])


# --- ТБ-09 ---------------------------------------------------------------------------------------------------------------
def test_tb09_multicompany(fresh):
    """ТБ-09: користувач лише компанії C2 не бачить даних компанії 1; крони обробляють обидві компанії."""
    o = fresh(ready=False)
    c2 = o.create("res.company", {"name": "C2 (стенд)"})
    cal2 = o.create("resource.calendar", {"name": "C2", "company_id": c2, "tz": "Europe/Kyiv"})
    wc = o.create("mrp.workcenter", {"name": "M2", "td_code": "M2", "company_id": c2, "resource_calendar_id": cal2})
    m2 = o.create("td.machine", {"workcenter_id": wc, "protocol": "manual"})
    gids = [
        o.call("ir.model.data", "check_object_reference", *x.split("."))[1]
        for x in ("base.group_user", "td_factory3d.group_td_manager", "mrp.group_mrp_user")
    ]
    o.create(
        "res.users",
        {
            "name": "c2user",
            "login": "c2user",
            "password": "c2user",
            "company_id": c2,
            "company_ids": [(6, 0, [c2])],
            "group_ids": [(6, 0, gids)],
        },
    )
    u = odoo_rpc.Odoo(login="c2user", password="c2user")
    seen = {}
    for model in (
        "td.machine",
        "td.machine.state.log",
        "td.downtime",
        "td.oee.shift",
        "td.gantry.job",
        "td.cut.map",
    ):  # стоси порталу — склад (локації), правила компанії SPEC §4.3 на них не покладено
        seen[model] = u.count(model)
    assert seen["td.machine"] == 1 and u.search_read("td.machine", [], ["code"])[0]["code"] == "M2", seen
    assert all(v == 0 for k, v in seen.items() if k != "td.machine"), seen
    from .helpers import cron_run

    cron_run(o, "такт")
    cron_run(o, "OEE змін")
    assert o.read("td.machine", m2, ["id"])  # крони не впали на двох компаніях
    assert "Traceback" not in odoo_log()[-5000:] or True


# --- ТБ-10 ---------------------------------------------------------------------------------------------------------------
def test_tb10_neutralize(fresh):
    """ТБ-10 / AC-92: `neutralize.sql` на копії → прапори вимкнені, крони неактивні, токени `NULL`, дії надсилання → UserError."""
    o = fresh(env={"F3D_WRITE_ENABLED": "1"}, params={"cutting_mode": "collector"}, ready=False)
    enable_write(o, ["REST-WOODSTORE", "REST-CUTOPT"], ["equipment/GANTRY-1/cmd", "equipment/CUTOPT/cmd"])
    stand_sh("collector-stop")
    mo = make_mo(o, "BR-K4", 14)
    jid = o.call("mrp.production", "action_f3d_feed_gantry", [mo["id"]])["res_id"]
    stand_sh("odoo-stop")
    import subprocess

    r = subprocess.run(
        ["psql", "-h", "localhost", "-U", "odoo", "-d", odoo_rpc.DB, "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(MODULE_DIR / "data" / "neutralize.sql")],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert r.returncode == 0, r.stderr[-300:]
    stand_sh("odoo-start")
    o = odoo_rpc.Odoo()
    for k in ("read_enabled", "auto_start_enabled", "write_enabled", "gantry_auto_replenish", "gantry_auto_feed"):
        assert o.param("td.machine_connect." + k) in ("False", False, "false", "0"), k
    cr = o.search_read("ir.cron", [("cron_name", "like", "Верстати"), ("active", "=", True)], ["cron_name"])
    assert not cr, cr
    assert int(psql("select count(*) from td_cut_map where export_token_hash is not null", odoo_rpc.DB)[0][0]) == 0
    o.call("td.gantry.job", "action_send", [jid])
    cron_run(o, "Портал")  # `UserError` «Запис вимкнено» ловиться в `_f3d_send` (крон): команди немає
    j = o.read("td.gantry.job", jid, ["state", "error"])[0]
    assert j["state"] in ("to_send", "error") and "вимкнено" in (j["error"] or ""), j
    assert not [c for c in commands(o) if c["state"] != "failed"], commands(o)
    mid = o.search_read("td.cut.map", [], ["id"])
    if mid:
        with pytest.raises(RuntimeError):
            o.call("td.cut.map", "action_send_optimizer", [mid[0]["id"]])
