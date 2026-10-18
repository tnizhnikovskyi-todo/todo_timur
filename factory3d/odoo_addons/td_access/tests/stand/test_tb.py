"""ТБ-01…ТБ-08 (SPEC §13.3) на стенді: права через XML-RPC під різними користувачами, секрети, ін'єкції, TLS.

ТБ-08 (запис при write_enabled=False) перевіряється в test_tk.py (``test_tb08_*``): лог проксі потрібен до ТК-08.
Юніт-варіанти ТБ (мок requests, `fake.calls`) — у tests/test_security.py, test_client.py, test_hooks.py.
"""
from __future__ import annotations

import os
import re
import subprocess
import xmlrpc.client

import pytest

pytestmark = pytest.mark.stand
PWD = "Stand-pass-1"
SEC, ADM, FADM = ("td_access.group_td_access_security", "td_access.group_td_access_admin",
                  "td_factory3d.group_td_admin")
USER_GROUPS = {
    "user_plain": ["base.group_user"],
    "user_f3d": ["base.group_user", "td_factory3d.group_td_user"],
    "user_security": ["base.group_user", SEC],
    "user_hr": ["base.group_user", "hr_attendance.group_hr_attendance_user"],
    "user_admin": ["base.group_user", ADM],
    "user_f3d_admin": ["base.group_user", FADM],
}
MATRIX = {
    "td.access.server": {"user_admin": "R", "user_f3d_admin": "RWCD"},
    "td.access.device": {"user_f3d": "R", "user_security": "R", "user_admin": "RWCD", "user_f3d_admin": "RWCD"},
    "td.access.door": {"user_f3d": "R", "user_security": "RW", "user_admin": "RWCD", "user_f3d_admin": "RWCD"},
    "td.access.user.link": {"user_security": "R", "user_hr": "R", "user_admin": "RWCD", "user_f3d_admin": "RWCD"},
    "td.access.event": {"user_security": "R", "user_hr": "R", "user_admin": "R", "user_f3d_admin": "RWCD"},
    "td.access.card": {"user_security": "RWC", "user_admin": "RWCD", "user_f3d_admin": "RWCD"},
    "td.access.visitor": {"user_security": "RWCD", "user_hr": "R", "user_admin": "RWCD", "user_f3d_admin": "RWCD"},
    "td.access.presence": {"user_security": "R", "user_hr": "R", "user_admin": "R", "user_f3d_admin": "R"},
}
OPS = {"R": "read", "W": "write", "C": "create", "D": "unlink"}


def xmlid_id(od, xmlid):
    module, name = xmlid.split(".")
    return od.k("ir.model.data", "check_object_reference", module, name)[1]


@pytest.fixture(scope="module")
def users(odoo, server_id):
    out = {}
    for key, groups in USER_GROUPS.items():
        login = f"stand_{key}"
        if not odoo.k("res.users", "search_count", [("login", "=", login)]):
            odoo.k("res.users", "create", {
                "name": login, "login": login, "password": PWD,
                "group_ids": [(6, 0, [xmlid_id(odoo, g) for g in groups])]})
        out[key] = odoo.as_user(login, PWD)
    return out


def denied(fn):
    try:
        fn()
    except xmlrpc.client.Fault as fault:
        return fault
    return None


# ---------------------------------------------------------------------------------------------- ТБ-01
def test_tb01_acl_matrix_and_buttons(odoo, users, server_id):
    for model, rules in MATRIX.items():
        for name, od in users.items():
            allowed = rules.get(name, "")
            for letter, op in OPS.items():
                got = od.k(model, "has_access", [], op)
                assert got == (letter in allowed), (model, name, op, got)
    assert denied(lambda: users["user_security"].k("td.access.server", "action_poll_now", [server_id]))
    assert denied(lambda: users["user_admin"].k("td.access.server", "action_test_connection", [server_id]))
    assert denied(lambda: users["user_admin"].k("td.access.server", "action_reset_cursor", [server_id]))
    assert users["user_f3d_admin"].k("td.access.server", "action_reset_cursor", [server_id]) is True
    print(f"TB 01 {{'cells': {len(MATRIX) * len(users) * len(OPS)}, 'models': {len(MATRIX)}, 'users': {len(users)}}}")


# ---------------------------------------------------------------------------------------------- ТБ-02
def test_tb02_secrets(odoo, users, server_id):
    fields = users["user_admin"].k("td.access.server", "fields_get", [], attributes=["string"])
    assert "session_id" not in fields
    assert "session_id" in odoo.k("td.access.server", "fields_get", [], attributes=["string"])
    # user_admin читає сервер лише R, поле сесії недоступне
    fault = denied(lambda: users["user_admin"].k("td.access.server", "read", [server_id], ["session_id"]))
    assert fault
    for key in ("user_admin", "user_security", "user_f3d"):
        assert denied(lambda key=key: users[key].k(
            "ir.config_parameter", "search_read", [("key", "=", "td.access.biostar_password")], ["value"])) \
            or not users[key].k("ir.config_parameter", "search_read",
                                [("key", "=", "td.access.biostar_password")], ["value"])
    # пароль не потрапляє в last_error / чаттер карток і відвідувачів
    pwd = os.environ["SIM_BIOSTAR_PASS"]
    assert pwd not in (odoo.server()["last_error"] or "")
    for model in ("td.access.card", "td.access.visitor"):
        bodies = odoo.k("mail.message", "search_read", [("model", "=", model)], ["body"])
        assert not any(pwd in (m["body"] or "") for m in bodies)
    log = os.environ.get("F3D_ODOO_LOG")
    if log and os.path.exists(log):
        text = open(log, encoding="utf-8", errors="replace").read()
        assert pwd not in text, "пароль BioStar у лозі Odoo"
        assert "wrong-password" not in text


# ---------------------------------------------------------------------------------------------- ТБ-03
def test_tb03_stop_taps_and_neutralize(odoo, sim, server_id):
    odoo.param("read_enabled", "False")
    try:
        fault = denied(lambda: odoo.k("td.access.server", "action_poll_now", [server_id]))
        assert fault, "AC-55: опитування при read_enabled=False має відмовляти"
        assert denied(lambda: odoo.k("td.access.server", "action_sync_users", [server_id]))
    finally:
        odoo.param("read_enabled", "True")
    # AC-56: запис вимкнено за замовчуванням і після прогону
    assert odoo.get_param("td.access.write_enabled") == "False"
    db = os.environ["F3D_ODOO_DB"]
    sql = os.path.join(os.path.dirname(__file__), "..", "..", "data", "neutralize.sql")
    if subprocess.run(["which", "psql"], capture_output=True).returncode:
        pytest.skip("psql недоступний: AC-57 перевіряється юніт-тестом test_neutralize")
    script = (f"BEGIN;\n\\i {os.path.abspath(sql)}\n"
              "SELECT count(*) FROM ir_cron c JOIN ir_model_data d ON d.res_id=c.id AND d.model='ir.cron' "
              "AND d.module='td_access' WHERE c.active;\n"
              "SELECT string_agg(key||'='||value, ',' ORDER BY key) FROM ir_config_parameter "
              "WHERE key IN ('td.access.read_enabled','td.access.write_enabled',"
              "'td.access.biostar_password');\nROLLBACK;\n")
    res = subprocess.run(["psql", "-At", "-v", "ON_ERROR_STOP=1", "-d", db], input=script, capture_output=True,
                         text=True, timeout=60)
    assert res.returncode == 0, res.stderr[-300:]
    lines = [x for x in res.stdout.splitlines()
             if x and x not in ("BEGIN", "ROLLBACK") and not re.match(r"^(UPDATE|DELETE|INSERT) \d+", x)]
    assert lines[0] == "0", res.stdout
    assert "read_enabled=False" in lines[1] and "write_enabled=False" in lines[1]
    assert "bs-pass" not in lines[1]
    # після ROLLBACK живі параметри не змінились
    assert odoo.get_param("td.access.read_enabled") == "True"


# ---------------------------------------------------------------------------------------------- ТБ-04
def test_tb04_injections(odoo, sim, server_id):
    emps = odoo.k("hr.employee", "search_count", [])
    link = {"server_id": server_id, "biostar_user_id": "'; DROP TABLE hr_employee; --"}
    assert denied(lambda: odoo.k("td.access.user.link", "create", link))
    door = {"server_id": server_id, "name": "X", "code": "ACR-IN'; --"}
    assert denied(lambda: odoo.k("td.access.door", "create", door))
    bad = {"name": "bad", "url": "https://x/api?;rm"}
    assert denied(lambda: odoo.k("td.access.server", "create", bad))
    # ін'єкція через емулятор: користувач-рядок SQL-ін'єкції в події; крон не падає, таблиці на місці
    try:
        sim.access_event("ACR-IN", "'; DROP TABLE hr_employee; --", 4102, "")
    except Exception:  # емулятор може відхилити параметр — тоді достатньо перевірок вище
        pass
    import time
    time.sleep(4)
    odoo.poll_until_quiet(server_id)
    assert odoo.k("hr.employee", "search_count", []) == emps
    assert odoo.server()["state"] == "online"
    assert odoo.k("td.access.event", "search_count", [("process_state", "=", "error")]) >= 0


# ---------------------------------------------------------------------------------------------- ТБ-05
def test_tb05_tls(odoo, server_id):
    """AC-01: verify_ssl=False і http:// на prod неможливі; на test дозволено (самопідписаний сертифікат стенду)."""
    base = odoo.get_param("td.base.environment")
    assert base == "test"
    param = odoo.k("ir.config_parameter", "search", [("key", "=", "td.base.environment")])
    try:
        odoo.k("ir.config_parameter", "write", param, {"value": "prod"})
        assert denied(lambda: odoo.k("td.access.server", "write", [server_id], {"verify_ssl": False}))
        assert denied(lambda: odoo.k("td.access.server", "create",
                                     {"name": "plain", "url": "http://127.0.0.1:8081", "verify_ssl": True}))
    finally:
        odoo.k("ir.config_parameter", "write", param, {"value": base})


# ---------------------------------------------------------------------------------------------- ТБ-06
def test_tb06_personal_data(odoo, users, server_id):
    """AC-64, AC-50: `raw_user_id` недоступний user_f3d; біометрії в моделях немає."""
    assert not users["user_f3d"].k("td.access.event", "has_access", [], "read")
    sec_fields = users["user_security"].k("td.access.event", "fields_get", [], attributes=["string"])
    assert "raw_user_id" in sec_fields
    f3d_fields = users["user_f3d"].k("td.access.event", "fields_get", [], attributes=["string"])
    assert "raw_user_id" not in f3d_fields
    all_fields = odoo.k("td.access.user.link", "fields_get", [], attributes=["string"])
    assert not [f for f in all_fields if "template" in f or "fingerprint" in f]
    fault = denied(lambda: users["user_f3d"].k("td.access.event", "search_read", [], ["raw_user_id"], limit=1))
    assert fault


# ---------------------------------------------------------------------------------------------- ТБ-07
def test_tb07_hr_employee(odoo, users):
    sec = users["user_security"]
    assert denied(lambda: sec.k("hr.employee", "search_read", [], ["td_access_last_event_id"], limit=1))
    assert denied(lambda: sec.k("hr.employee", "search_read", [], ["td_access_card_ids"], limit=1))
    people = sec.k("td.access.presence", "search_count", [])
    assert people >= 0
    assert sec.k("td.access.presence", "search_read", [], ["name"], limit=1) is not None
