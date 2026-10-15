"""Тести безпеки ТБ-01…ТБ-10 (SPEC §13.3) на стенді."""

from __future__ import annotations

import http.client as httpclient
import json
import re
import secrets
import statistics
import subprocess
import time
import xmlrpc.client
from pathlib import Path

import pytest
from bacnet_sniffer import Sniffer
from helpers import HERE, http, wait

ODOO_LOG = Path("/home/user/odoo19-data/logs/serve-f3d_telemetry_w7.log")
REPO = HERE.parents[3]
HTTP_SECRET = "stand-lpr-secret-0123456789"


def _auth(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def _new_collector(odoo, code: str) -> tuple[int, str]:
    cid = odoo.call("f3d.collector", "create", {"code": code, "name": code})
    return cid, odoo.new_token(code)


def _drop_collector(odoo, cid: int) -> None:
    for s in odoo.search_read("f3d.source", [("collector_id", "=", cid)], ["id"]):
        odoo.call(
            "f3d.signal",
            "unlink",
            [x["id"] for x in odoo.search_read("f3d.signal", [("source_id", "=", s["id"])], ["id"])],
        )
        odoo.call("f3d.source", "unlink", [s["id"]])
    odoo.call("f3d.collector", "unlink", [cid])


def test_tb01_tokens(odoo, token):
    """ТБ-01 / AC-37: 100 випадкових токенів → 401; час не залежить від префікса; відкликаний → 401, архівний → 403."""
    for i in range(100):
        t = secrets.token_urlsafe(32)
        assert http("GET", odoo.url + "/f3d/telemetry/config", headers=_auth(t))[0] == 401
        if i % 4 == 0:
            st, body, _ = http("POST", odoo.url + "/f3d/telemetry/push", {"readings": []}, _auth(t))
            assert st == 401 and t not in body
    near = token[:-1] + ("A" if token[-1] != "A" else "B")
    samples = {"near": [], "rand": []}
    for _ in range(60):
        for name, tok in (("near", near), ("rand", secrets.token_urlsafe(32))):
            t0 = time.perf_counter()
            assert http("GET", odoo.url + "/f3d/telemetry/config", headers=_auth(tok))[0] == 401
            samples[name].append(time.perf_counter() - t0)
    m_near, m_rand = statistics.median(samples["near"]), statistics.median(samples["rand"])
    assert abs(m_near - m_rand) <= 0.5 * max(m_near, m_rand) + 0.005, (m_near, m_rand)
    cid, tok = _new_collector(odoo, "COL-TB01")
    try:
        assert http("GET", odoo.url + "/f3d/telemetry/health", headers=_auth(tok))[0] == 200
        odoo.call("f3d.collector", "action_revoke_token", [cid])
        st, body, _ = http("GET", odoo.url + "/f3d/telemetry/config", headers=_auth(tok))
        assert st == 401 and tok not in body
        tok2 = odoo.new_token("COL-TB01")
        odoo.write("f3d.collector", cid, {"active": False})
        assert http("GET", odoo.url + "/f3d/telemetry/config", headers=_auth(tok2))[0] == 403
        assert http("GET", odoo.url + "/f3d/telemetry/health", headers=_auth(tok2))[0] == 200
    finally:
        odoo.write("f3d.collector", cid, {"active": True})
        _drop_collector(odoo, cid)


def test_tb02_secrets_do_not_leak(odoo, token, col):
    """ТБ-02 / AC-60, AC-82: сирий токен, F3D_MQTT_PASSWORD, секрет http_push — 0 збігів у логах колектора й Odoo та в config."""
    secrets_ = [token, "collpass", HTTP_SECRET]
    st, body, _ = http("GET", odoo.url + "/f3d/telemetry/config", headers=_auth(token))
    assert st == 200
    for logname, text in (
        ("config", body),
        ("collector.log", col.log()),
        ("odoo.log", ODOO_LOG.read_text(errors="replace") if ODOO_LOG.exists() else ""),
    ):
        for s in secrets_:
            assert s not in text, f"секрет у {logname}"
    cfg = json.loads(body)
    for src in cfg.get("sources", []):
        for k, v in (src.get("params") or {}).items():
            if k.endswith("_ref"):
                assert v.startswith("F3D_"), (k, v)
            assert k not in ("password", "token", "secret"), k
    left = odoo.search_read("f3d.collector.token.wizard", [("token", "!=", False)], ["id"])
    assert not left, "токен лишився в f3d_collector_token_wizard"


def _user(odoo, login: str, groups: list[str]) -> str:
    ids = []
    for g in groups:
        mod, name = g.split(".")
        ids.append(
            odoo.search_read("ir.model.data", [("module", "=", mod), ("name", "=", name)], ["res_id"])[0]["res_id"]
        )
    found = odoo.search_read("res.users", [("login", "=", login)], ["id"])
    vals = {"name": login, "login": login, "password": "Tb-pass-12345", "group_ids": [(6, 0, ids)]}
    if found:
        odoo.write("res.users", found[0]["id"], {"group_ids": [(6, 0, ids)], "password": "Tb-pass-12345"})
    else:
        odoo.call("res.users", "create", vals)
    return login


MATRIX = {  # модель -> {користувач: операції}
    "f3d.collector": {"plain": "", "reader": "R", "manager": "R", "admin": "RWCD"},
    "f3d.source": {"plain": "", "reader": "R", "manager": "RWCD", "admin": "RWCD"},
    "f3d.signal": {"plain": "", "reader": "R", "manager": "RWCD", "admin": "RWCD"},
    "f3d.reading": {"plain": "", "reader": "R", "manager": "RC", "admin": "RWCD"},  # W менеджера — UserError (нижче)
    "f3d.reading.hour": {"plain": "", "reader": "R", "manager": "R", "admin": "RWCD"},
    "f3d.command": {"plain": "", "reader": "R", "manager": "RWC", "admin": "RWCD"},
    "f3d.push.event": {"plain": "", "reader": "R", "manager": "R", "admin": "RWCD"},
    "f3d.collector.token.wizard": {"plain": "", "reader": "", "manager": "", "admin": "RWCD"},
}
OPS = {"R": "read", "W": "write", "C": "create", "D": "unlink"}


def test_tb03_access_matrix(odoo):
    """ТБ-03 / AC-59: матриця прав чотирьох користувачів за таблицею §13.3; user_plain не бачить меню «Телеметрія»."""
    from odoo_rpc import Odoo

    users = {
        "plain": _user(odoo, "f3dtb_plain", ["base.group_user"]),
        "reader": _user(odoo, "f3dtb_reader", ["base.group_user", "factory3d_base.group_f3d_user"]),
        "manager": _user(odoo, "f3dtb_manager", ["base.group_user", "factory3d_base.group_f3d_manager"]),
        "admin": _user(odoo, "f3dtb_admin", ["base.group_user", "factory3d_base.group_f3d_admin"]),
    }
    bad = []
    for kind, login in users.items():
        o = Odoo(login=login, password="Tb-pass-12345")
        for model, per in MATRIX.items():
            want = per[kind]
            for letter, op in OPS.items():
                got = o.call(model, "has_access", [], op)
                if got != (letter in want):
                    bad.append((kind, model, op, got))
        gids = set(odoo.call("res.users", "read", [o.uid], ["all_group_ids"])[0]["all_group_ids"])
        menus = [
            m
            for m in odoo.search_read("ir.ui.menu", [("name", "ilike", "Телеметрія")], ["name", "group_ids"])
            if not m["group_ids"] or gids & set(m["group_ids"])
        ]
        if kind == "plain":
            assert not menus, "user_plain бачить меню «Телеметрія»: %s" % [m["name"] for m in menus]
        else:
            assert menus, f"{kind} не бачить меню «Телеметрія»"
    assert not bad, bad
    # f3d.reading: менеджер створює, але не змінює (UserError)
    mgr = Odoo(login=users["manager"], password="Tb-pass-12345")
    rid = odoo.search_read("f3d.reading", [], ["id"], limit=1)[0]["id"]
    with pytest.raises(xmlrpc.client.Fault) as e:
        mgr.write("f3d.reading", rid, {"value": 1.0})
    assert e.value.faultCode == 2 and "Показання не редагуються" in e.value.faultString  # 2 = UserError
    plain = Odoo(login=users["plain"], password="Tb-pass-12345")
    with pytest.raises(xmlrpc.client.Fault) as e:
        plain.search_read("f3d.signal", [], ["code"])
    assert e.value.faultCode == 4 and "not allowed" in e.value.faultString  # 4 = AccessError


def test_tb04_injections(odoo, token, col):
    """ТБ-04 / AC-08, AC-09, AC-39: ін'єкції в коди, адреси, MQTT-шляхи, маршрути; огляд коду на динамічний SQL."""
    n_sig, n_rd = odoo.count("f3d.signal"), odoo.count("f3d.reading")
    src = odoo.search_read("f3d.source", [("code", "=", "MB-U70-COMPRESSOR")], ["id"])[0]["id"]
    mq = odoo.search_read("f3d.source", [("code", "=", "MQTT-MOBILE")], ["id"])[0]["id"]
    bad_codes = [
        "equipment/FL-T/x;DROP TABLE f3d_signal",
        "equipment/FL-T/x'--",
        "Equipment/FL-T/x",
        "equipment/FL T/x",
    ]
    for code in bad_codes:
        with pytest.raises(xmlrpc.client.Fault) as e:
            odoo.call("f3d.signal", "create", {"code": code, "name": "x", "kind": "gauge"})
        assert "Код сигналу" in e.value.faultString, code
    body = {
        "collector": "COL-MAIN",
        "readings": [{"code": "'; DELETE FROM f3d_reading; --", "ts": "2026-10-15T08:00:00Z", "value": 1}],
    }
    st, txt, _ = http("POST", odoo.url + "/f3d/telemetry/push", body, _auth(token))
    assert st == 200 and "bad_code_format" in txt, txt
    with pytest.raises(xmlrpc.client.Fault) as e:
        odoo.call(
            "f3d.signal",
            "create",
            {
                "code": "equipment/TB/inj",
                "name": "x",
                "kind": "gauge",
                "source_id": src,
                "address": {"fc": 3, "addr": "3001; DROP", "type": "u16"},
            },
        )
    assert "Адреса сигналу" in e.value.faultString, e.value.faultString[-200:]
    with pytest.raises(xmlrpc.client.Fault) as e:
        odoo.call(
            "f3d.signal",
            "create",
            {
                "code": "equipment/TB/mq",
                "name": "x",
                "kind": "gauge",
                "source_id": mq,
                "address": {"topic": "f3d/mobile/FL-1/telemetry", "path": '$.a"]; drop'},
            },
        )
    assert "Адреса сигналу" in e.value.faultString, e.value.faultString[-200:]
    assert odoo.count("f3d.signal") == n_sig and odoo.count("f3d.reading") >= n_rd
    for path in ("/f3d/lpr/../admin", "/f3d/LPR", "/f3d/lpr/%2e%2e/admin"):
        c = http_client()
        c.putrequest("POST", path, skip_host=False)
        c.putheader("Content-Type", "application/json")
        c.putheader("Content-Length", "2")
        c.endheaders(b"{}")
        assert c.getresponse().status == 404, path
    pat = re.compile(r'execute\(f"|execute\(.*%[^s]|execute\(.*\.format\(')
    hits = []
    base = REPO / "odoo_addons" / "factory3d_telemetry"
    for sub in ("models", "tools", "controllers"):
        for f in (base / sub).rglob("*.py"):
            hits += [f"{f.name}:{i}" for i, ln in enumerate(f.read_text().splitlines(), 1) if pat.search(ln)]
    hits += [f"hooks.py:{i}" for i, ln in enumerate((base / "hooks.py").read_text().splitlines(), 1) if pat.search(ln)]
    assert not hits, hits


def http_client() -> httpclient.HTTPConnection:
    return httpclient.HTTPConnection("127.0.0.1", 8080, timeout=5)


def test_tb05_write_flags(odoo, token):
    """ТБ-05 / AC-44: параметр write_enabled=False → GET commands порожній із write_enabled:false; повний сценарій — ТК-15."""
    odoo.param("factory3d.telemetry.write_enabled", "False")
    st, body, _ = http("GET", odoo.url + "/f3d/telemetry/commands", headers=_auth(token))
    d = json.loads(body)
    assert st == 200 and d["commands"] == [] and d["write_enabled"] is False, d


def test_tb06_fire_panel_read_only(fresh_sim, odoo, col, token):
    """ТБ-06: пожежна панель dev 200 — read_only: лише Who-Is/I-Am/ReadProperty/RPM у мережі (власний сніфер замість
    tcpdump/tshark), команда в обхід перевірок (SQL) → failed «read-only device»; сигнали fire/* на read_only → ValidationError."""
    colid = odoo.search_read("f3d.collector", [("code", "=", "COL-MAIN")], ["id"])[0]["id"]
    boiler = odoo.search_read("f3d.source", [("code", "=", "BAC-140-BOILER")], ["id"])[0]["id"]
    facp = odoo.call(
        "f3d.source",
        "create",
        {
            "code": "BAC-200-FACP",
            "name": "Пожежна панель (dev 200)",
            "type": "bacnet_ip",
            "collector_id": colid,
            "params": {"host": "iot-sim", "device": 200, "network": 2, "read_only": True},
        },
    )
    sig_state = odoo.call(
        "f3d.signal",
        "create",
        {
            "code": "fire/groups/FA-CUT/state",
            "name": "FA-CUT",
            "kind": "state",
            "source_id": facp,
            "period_s": 10,
            "address": {"object": "life-safety-zone", "instance": 12},
            "states": ["quiet", "pre-alarm", "alarm"],
            "origin": "manual",
        },
    )
    sig_dust = odoo.call(
        "f3d.signal",
        "create",
        {
            "code": "fire/groups/FA-FAC/dust",
            "name": "FA-FAC dust",
            "kind": "gauge",
            "source_id": facp,
            "period_s": 10,
            "address": {"object": "positive-integer-value", "instance": 21607},
            "origin": "manual",
        },
    )
    try:
        with pytest.raises(xmlrpc.client.Fault) as e:
            odoo.write("f3d.signal", sig_state, {"write_enabled": True})
        assert "Запис у пожежну панель заборонено" in e.value.faultString
        with pytest.raises(xmlrpc.client.Fault) as e:
            odoo.write("f3d.source", facp, {"write_enabled": True})
        assert "лише для читання" in e.value.faultString
        odoo.write("f3d.source", boiler, {"read_enabled": False})  # у мережі лишається лише трафік до dev 200
        psql = ["psql", "-h", "127.0.0.1", "-U", "odoo", "f3d_telemetry_w7", "-Atc"]
        cmd_sql = (
            "insert into f3d_command (signal_id, source_id, collector_id, value, state, requested_at, expires_at, "
            "requested_by, create_uid, write_uid, create_date, write_date) "
            f"select {sig_state}, {facp}, {colid}, 1, 'queued', now() at time zone 'utc', "
            "now() at time zone 'utc' + interval '10 minutes', 1, 1, 1, now(), now()"
        )
        # фаза 1 — обхід перевірок Odoo (SQL): прапори запису + команда в черзі, F3D_WRITE_ENABLED=1. Другий рубіж —
        # валідація конфігурації в колекторі (write_enabled заборонено для read_only) — джерело не підключається, команда
        # завершується failed: «read-only device» (плагін) або «source … unavailable» (джерело відхилене валідатором)
        subprocess.run(
            [
                *psql,
                f"update f3d_source set write_enabled = true where id = {facp}; "
                f"update f3d_signal set write_enabled = true where id = {sig_state}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        odoo.param("factory3d.telemetry.write_enabled", "True")
        col.restart(env={"F3D_WRITE_ENABLED": "1"})
        time.sleep(40)
        subprocess.run([*psql, cmd_sql], check=True, capture_output=True, text=True)
        cmd = wait(
            lambda: [
                c
                for c in odoo.search_read("f3d.command", [("signal_id", "=", sig_state)], ["state", "error", "result"])
                if c["state"] != "queued"
            ],
            120,
            3,
        )
        assert cmd and cmd[0]["state"] == "failed", cmd
        assert any(t in (cmd[0]["error"] or "") for t in ("read-only device", "unavailable")), cmd
        # фаза 2 — чисте read_only-джерело (прапори False), F3D_WRITE_ENABLED=1: на дроті лише Who-Is/I-Am/RP/RPM
        subprocess.run(
            [
                *psql,
                f"update f3d_source set write_enabled = false where id = {facp}; "
                f"update f3d_signal set write_enabled = false where id = {sig_state}; "
                f"delete from f3d_command where source_id = {facp}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        odoo.param("factory3d.telemetry.write_enabled", "False")
        col.restart(env={"F3D_WRITE_ENABLED": "1"})
        assert wait(
            lambda: odoo.search_read("f3d.source", [("id", "=", facp)], ["state"])[0]["state"] == "online", 150, 3
        ), "BAC-200-FACP не стало online"
        with Sniffer(src="127.0.0.2") as sn:
            subprocess.run([*psql, cmd_sql], check=True, capture_output=True, text=True)
            time.sleep(90)
        kinds = {(p.kind, p.service) for p in sn.packets}
        assert sn.packets, "сніфер не бачить жодного BACnet-пакета колектора"
        bad = [
            (k, sv)
            for k, sv in kinds
            if (k == "confirmed" and sv not in ("read-property", "read-property-multiple"))
            or (k == "unconfirmed" and sv not in ("who-is", "i-am"))
        ]
        assert not bad, f"заборонені сервіси BACnet від колектора: {bad}"
        assert not [p for p in sn.packets if p.kind == "confirmed" and p.service == "write-property"]
    finally:
        subprocess.run(
            [
                "psql",
                "-h",
                "127.0.0.1",
                "-U",
                "odoo",
                "f3d_telemetry_w7",
                "-Atc",
                f"update f3d_signal set write_enabled = false where id in ({sig_state}, {sig_dust}); "
                f"update f3d_source set write_enabled = false where id = {facp}; "
                f"delete from f3d_command where source_id = {facp}",
            ],
            check=False,
            capture_output=True,
        )
        odoo.param("factory3d.telemetry.write_enabled", "False")
        odoo.write("f3d.source", boiler, {"read_enabled": True})
        odoo.call("f3d.signal", "unlink", [sig_state, sig_dust])
        odoo.call("f3d.source", "unlink", [facp])
        col.restart(env={"F3D_WRITE_ENABLED": "0"})


def test_tb07_http_push_receiver(odoo, metrics, col):
    """ТБ-07 / AC-80: джерело поза allow_ips → 403; без секретного суфікса → 404; 1000 запитів за ≈10 с: колектор живий,
    RSS росте < 50 МБ, у Odoo лише унікальні події."""

    def post(path, body=b"{}", src=None):
        c = httpclient.HTTPConnection("127.0.0.1", 8080, timeout=5, source_address=(src, 0) if src else None)
        c.request("POST", path, body, {"Content-Type": "application/json"})
        r = c.getresponse()
        r.read()
        return r.status

    assert post(f"/f3d/lpr/{HTTP_SECRET}", src="127.0.0.9") == 403
    assert post("/f3d/lpr") == 404
    assert post(f"/f3d/lpr/{HTTP_SECRET}x") == 404
    pid = int(subprocess.run(["pgrep", "-f", "[f]3d-collector run"], capture_output=True, text=True).stdout.split()[0])

    def rss() -> int:
        return int(re.search(r"VmRSS:\s+(\d+)", Path(f"/proc/{pid}/status").read_text()).group(1))

    r0 = rss()
    marker = secrets.token_hex(4)
    t0, codes = time.time(), []
    for i in range(1000):
        which = i % 4
        if which == 0:
            codes.append(post(f"/f3d/lpr/{HTTP_SECRET}", src="127.0.0.9"))
        elif which == 1:
            codes.append(post("/f3d/lpr"))
        else:
            body = json.dumps(
                {"sensorProviderID": "CAM-05", "plateText": f"TB{marker}{i % 5}", "capture_timestamp": "1760000000000"}
            ).encode()
            codes.append(post(f"/f3d/lpr/{HTTP_SECRET}", body))
    assert time.time() - t0 < 120
    assert set(codes) <= {200, 202, 403, 404, 429, 413}, set(codes)
    assert metrics.health()["status"] in ("ok", "degraded")
    assert rss() - r0 < 50 * 1024, (r0, rss())
    time.sleep(15)
    evs = odoo.search_read("f3d.push.event", [("route", "=", "lpr")], ["payload"], order="id desc", limit=50)
    mine = [
        e["payload"].get("plateText") for e in evs if str(e["payload"].get("plateText", "")).startswith("TB" + marker)
    ]
    assert len(mine) == len(set(mine)) <= 5, mine


def test_tb08_container_and_allowlist(col, metrics, odoo, fresh_sim):
    """ТБ-08: контейнерні властивості — за docker-compose.collector.yml (процесний стенд без контейнера колектора);
    F3D_ALLOW_HOSTS=mosquitto → джерела iot-sim `error` «хост не в allow-list», 0 пакетів до iot-sim за 2 хв.
    Allow-list порівнює IP, а на процесному стенді обидва імена — 127.0.0.1, тому на час тесту iot-sim → 127.0.0.6."""
    text = (HERE.parents[1] / "docker-compose.collector.yml").read_text()
    assert 'user: "10002:10002"' in text and "read_only: true" in text and "cap_drop: [ALL]" in text
    assert "ports:" not in text, "колектор не публікує портів (docker port порожньо)"
    hosts = Path("/etc/hosts")
    orig = hosts.read_text()
    names = {"iot-sim", "mosquitto", "collector"}
    kept = [ln for ln in orig.splitlines() if not names & set(ln.split())]
    hosts.write_text("\n".join([*kept, "127.0.0.1 mosquitto collector", "127.0.0.6 iot-sim"]) + "\n")
    try:
        col.restart(env={"F3D_ALLOW_HOSTS": "mosquitto"})
        with Sniffer(src=None, ports=(47808,), tcp_dports=(502,)) as sn:
            time.sleep(120)
        to_sim = [p for p in sn.packets if p.dst == "127.0.0.6"]
        syn = [t for t in sn.tcp_syn if t[1] == "127.0.0.6"]
        assert not to_sim and not syn, f"пакети до iot-sim: UDP {len(to_sim)}, TCP SYN {len(syn)}"
        states = {
            s["code"]: (s["state"], s["last_error"] or "")
            for s in odoo.search_read(
                "f3d.source", [("type", "in", ("modbus_tcp", "bacnet_ip"))], ["code", "state", "last_error"]
            )
        }
        assert states
        for code, (state, err) in states.items():
            assert state == "error" and "allow" in err.lower(), (code, state, err)
    finally:
        hosts.write_text(orig)
        col.restart(env={"F3D_ALLOW_HOSTS": "iot-sim,mosquitto"})


def test_tb09_health_and_metrics(odoo, metrics, token):
    """ТБ-09 / AC-42, AC-82, AC-83: health без токена — рівно 4 ключі; /metrics без секретів."""
    st, body, _ = http("GET", odoo.url + "/f3d/telemetry/health")
    assert st == 200 and set(json.loads(body)) == {"ok", "module", "version", "server_time"}
    st, body, _ = http("GET", odoo.url + "/f3d/telemetry/health", headers=_auth("wrong"))
    assert st == 200 and set(json.loads(body)) == {"ok", "module", "version", "server_time"}
    txt = metrics.text()
    for s in (token, "collpass", HTTP_SECRET):
        assert s not in txt
    h = json.dumps(metrics.health())
    assert token not in h and "collpass" not in h


def test_tb10_limits(odoo, token):
    """ТБ-10 / AC-39, AC-41, AC-43: 2 001 показання → 413; 501 джерело у status → 413; 101 подія → 413; Odoo не падає."""
    url = odoo.url + "/f3d/telemetry"
    rd = [{"code": "equipment/COMPRESSOR/pressure_bar", "ts": "2026-10-15T08:00:00Z", "value": 7.0}] * 2001
    st, body, _ = http("POST", url + "/push", {"collector": "COL-MAIN", "readings": rd}, _auth(token))
    assert st == 413 and "too_many_readings" in body, (st, body[:200])
    st, _, _ = http(
        "POST",
        url + "/status",
        {"collector": "COL-MAIN", "sources": [{"code": f"S{i}"} for i in range(501)]},
        _auth(token),
    )
    assert st == 413
    ev = [
        {"event_id": f"tb-{i}", "route": "lpr", "ts": "2026-10-15T08:00:00Z", "payload": {"a": i}} for i in range(101)
    ]
    st, _, _ = http("POST", url + "/event", {"collector": "COL-MAIN", "events": ev}, _auth(token))
    assert st == 413
    big = b'{"readings": [], "pad": "' + b"x" * (1024 * 1024 + 10) + b'"}'
    st, body, _ = http("POST", url + "/push", raw=big, headers={**_auth(token), "Content-Type": "application/json"})
    assert st == 413 and "payload_too_large" in body
    assert http("GET", url + "/health")[0] == 200
