"""ТБ-01…ТБ-10 (SPEC §13.3), що перевіряються на стенді; решта (UT/PT) — див. TEST_REPORT."""

from __future__ import annotations

import re
import subprocess
import time
import xmlrpc.client as xc
from pathlib import Path

import pytest

import odoo_rpc
from bms_lib import restart_collector, sleep_until, source
from conftest import HERE

ROOT = HERE.parents[3]
LOG = Path("/tmp/f3dstand/collector.log")


def _user(odoo, login, groups_xmlids):
    gids = [
        odoo.search_read(
            "ir.model.data", [("module", "=", x.split(".")[0]), ("name", "=", x.split(".")[1])], ["res_id"]
        )[0]["res_id"]
        for x in groups_xmlids
    ]
    uid = odoo.search_read("res.users", [("login", "=", login)], ["id"])
    if uid:
        odoo.write("res.users", uid[0]["id"], {"group_ids": [(6, 0, gids)], "password": "Tb-pass-123456"})
    else:
        odoo.call(
            "res.users",
            "create",
            {"name": login, "login": login, "password": "Tb-pass-123456", "group_ids": [(6, 0, gids)]},
        )
    return odoo_rpc.Odoo(odoo.url, odoo.db, login, "Tb-pass-123456")


def test_tb01_tb02_acl(odoo):
    """ТБ-01: без group_td_user моделі модуля недоступні. ТБ-02: оператор не змінює налаштування, не видаляє журнал."""
    plain = _user(odoo, "tb_plain", ["base.group_user"])
    for model in ("td.bms.light.group", "td.bms.hvac.unit", "td.bms.heat.balance", "td.bms.deviation"):
        with pytest.raises(xc.Fault) as ei:
            plain.search_read(model, [], ["id"], limit=1)
        assert "AccessError" in str(ei.value) or "доступ" in str(ei.value).lower() or "access" in str(ei.value).lower()
    op = _user(odoo, "tb_oper", ["base.group_user", "td_bms.group_td_bms_operator"])
    assert op.count("td.bms.light.group") == 32
    gid = op.search_read("td.bms.light.group", [], ["id"], limit=1)[0]["id"]
    for model, vals in (("td.bms.light.group", {"e_norm": 1}),):
        with pytest.raises(xc.Fault):
            op.write(model, gid, vals)
    with pytest.raises(xc.Fault):
        op.call("td.bms.light.group", "unlink", [gid])
    ep = op.search_read("td.bms.deviation", [], ["id"], limit=1)
    if ep:
        with pytest.raises(xc.Fault):
            op.call("td.bms.deviation", "unlink", [ep[0]["id"]])


def test_tb05_tb09_injection(odoo):
    """ТБ-05: dali_devices з ';DROP' → ValidationError; ТБ-09: action_open приймає лише 4 моделі."""
    mgr = _user(odoo, "tb_mgr", ["base.group_user", "td_factory3d.group_td_manager"])
    gid = mgr.search_read("td.bms.light.group", [], ["id", "dali_devices"], limit=1)[0]
    for bad in ("@1.2.1.1-27;DROP", "@1.2.1.1#", ">V:2"):
        with pytest.raises(xc.Fault) as ei:
            mgr.write("td.bms.light.group", gid["id"], {"dali_devices": bad})
        assert "ValidationError" in str(ei.value) or "dali" in str(ei.value).lower() or "адрес" in str(ei.value).lower()
    with pytest.raises(xc.Fault):
        mgr.call("td.bms.overview", "action_open", "res.partner", 1, "form")
    with pytest.raises(xc.Fault):
        mgr.call("td.bms.overview", "action_open", "res.users", 1, "form")


def test_tb06_allowlist(odoo, fresh_sim):
    """ТБ-06: роутер поза allow-list колектора → джерело error, запитів до нього немає."""
    src = source(odoo, "HN-LP-3")
    sid = odoo.search_read("td.source", [("code", "=", "HN-LP-3")], ["id"])[0]["id"]
    try:
        odoo.write("td.source", sid, {"params": {**src["params"], "host": "evil.example.com"}})
        assert sleep_until(lambda: source(odoo, "HN-LP-3")["state"] == "error", 180, 10), source(odoo, "HN-LP-3")
        err = source(odoo, "HN-LP-3")["last_error"] or ""
        print("TB06 last_error:", err)
        assert "allow" in err.lower() or "dozvol" in err.lower() or "denied" in err.lower() or "evil" in err
    finally:
        odoo.write("td.source", sid, {"params": src["params"]})
    assert sleep_until(lambda: source(odoo, "HN-LP-3")["state"] == "online", 180, 10)


def test_tb10_logs_no_frames():
    """ТБ-10: лог колектора на INFO не містить кадрів HelvarNet."""
    text = LOG.read_text(errors="replace")
    assert not re.search(r"[>?!]V:\d,C:\d+", text), re.findall(r".{0,40}[>?!]V:\d,C:\d+.{0,40}", text)[:3]


def test_tb03_write_off_expires(odoo, fresh_sim):
    """ТБ-03: прапори БД увімкнені, але F3D_WRITE_ENABLED=0 → колектор не забирає команду → expired за строк."""
    from test_tk_b import _settings  # noqa: PLC0415

    _settings(odoo, True)
    try:
        restart_collector({"F3D_WRITE_ENABLED": "0"})
        gid = odoo.search_read("td.bms.light.group", [("code", "=", "LT-MAINT")], ["id"])[0]["id"]
        scene = odoo.search_read("td.bms.light.scene", [("number", "=", 3)], ["id"], limit=1)[0]["id"]
        w = odoo.call(
            "td.bms.light.command.wizard",
            "create",
            {"group_ids": [(6, 0, [gid])], "action": "scene", "scene_id": scene, "expires_min": 1},
        )
        act = odoo.call("td.bms.light.command.wizard", "action_apply", [w])
        ids = act["domain"][0][2]
        t0 = time.time()
        states = set()

        def done():
            st = odoo.search_read("td.command", [("id", "in", ids)], ["state"])[0]["state"]
            states.add(st)
            return st == "expired"

        if not sleep_until(done, 120, 10):  # крон прострочених команд — раз на 10 хв; запускаємо вручну
            cron = odoo.search_read("ir.cron", [("cron_name", "=", "Телеметрія: прострочені команди")], ["id"])[0]["id"]
            odoo.call("ir.cron", "method_direct_trigger", [cron])
        assert done()
        assert not states & {"sent", "done"}, states  # колектор команду не забирав
        print(
            f"TB03 стани команди {sorted(states)}, expired за {time.time() - t0:.0f} с (колектор F3D_WRITE_ENABLED=0)"
        )
    finally:
        _settings(odoo, False)
        restart_collector({"F3D_WRITE_ENABLED": "0"})


def test_tb07_neutralize():
    """ТБ-07: neutralize.sql на окремій базі вимикає читання, запис і крон модуля."""
    t = ROOT / "tools" / "odoo"
    db = "f3d_factory3d_bms_w7_neu"
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(Path.home()),
        "F3D_TEST_INSTALL": "td_factory3d,td_telemetry,td_bms",
    }
    subprocess.run([str(t / "drop_db.sh"), db], capture_output=True, env=env)
    assert subprocess.run([str(t / "new_db.sh"), db], capture_output=True, env=env).returncode == 0
    assert subprocess.run([str(t / "update.sh"), db], capture_output=True, env=env, timeout=600).returncode == 0
    sql = (ROOT / "odoo_addons" / "td_bms" / "data" / "neutralize.sql").read_text()
    q = (
        "SELECT (SELECT count(*) FROM ir_config_parameter WHERE key LIKE 'td.bms.%%_enabled' AND value='True'),"
        "(SELECT count(*) FROM td_source WHERE module='bms' AND (read_enabled OR write_enabled)),"
        "(SELECT count(*) FROM ir_cron WHERE cron_name LIKE 'Будівля%%' AND active)"
    )
    def pg(sql):
        return subprocess.run(
            ["psql", "-h", "127.0.0.1", "-U", "odoo", "-At", "-d", db, "-c", sql], capture_output=True, text=True
        ).stdout.strip()

    pg_before = pg(q.replace("%%", "%"))
    r = subprocess.run(
        ["psql", "-h", "127.0.0.1", "-U", "odoo", "-d", db, "-v", "ON_ERROR_STOP=1"],
        input=sql,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr[-300:]
    after = pg(q.replace("%%", "%"))
    print("TB07 до:", pg_before, "після:", after)
    assert after == "0|0|0"
    subprocess.run([str(t / "drop_db.sh"), db], capture_output=True, env=env)
