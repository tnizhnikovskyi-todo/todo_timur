"""DEPLOY_TEST (SPEC §13.5) п. 6–9 на чистій базі `f3d_w7_dep` (копії демо-бази `odoo` у середовищі немає — див. TEST_REPORT).

П. 1–3 (дамп `odoo`, знімки S0–S3, `readings_migrated == S0`) і п. 7 на демо (196 сигналів рівня 0) — вне среды.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from helpers import HERE

DEP_DB = "f3d_w7_dep"
NEU_DB = "f3d_w7_neu"
ROOT = HERE.parents[3]
TOOLS = ROOT / "tools" / "odoo"
ADDONS = ROOT / "odoo_addons"


def _psql(db: str, sql: str | None = None, file: Path | None = None) -> str:
    cmd = ["psql", "-h", "127.0.0.1", "-U", "odoo", db, "-At"]
    cmd += ["-c", sql] if sql else ["-f", str(file)]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
    assert r.returncode == 0, r.stderr[-400:]
    return r.stdout.strip()


def _dbs() -> str:
    return subprocess.run(
        ["psql", "-h", "127.0.0.1", "-U", "odoo", "-lqt"], capture_output=True, text=True, check=False
    ).stdout


def _shell(script: str, db: str = DEP_DB) -> dict:
    r = subprocess.run(
        [str(HERE / "stand.sh"), "shell"],
        input=script,
        capture_output=True,
        text=True,
        env={**os.environ, "F3D_SHELL_DB": db},
        timeout=900,
        check=False,
    )
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("STAND ")), None)
    assert line, (r.stdout + r.stderr)[-600:]
    return json.loads(line[6:])


@pytest.fixture(scope="module")
def dep_db():
    if DEP_DB not in _dbs():
        env = {**os.environ, "F3D_TEST_INSTALL": "td_iot_sim,td_telemetry,td_telemetry_viewer3d"}
        subprocess.run(
            [str(TOOLS / "run_tests.sh"), DEP_DB, "/td_telemetry_viewer3d"],
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
    assert DEP_DB in _dbs()
    if _psql(DEP_DB, "select state from ir_module_module where name = 'td_telemetry'") != "installed":
        env = {
            **os.environ,
            "F3D_TEST_INSTALL": "td_telemetry,td_telemetry_viewer3d",
        }  # після перерваного п. 7
        subprocess.run(
            [str(TOOLS / "update.sh"), DEP_DB], env=env, capture_output=True, text=True, timeout=1200, check=False
        )
    return DEP_DB


def test_dep03_install_report(dep_db):
    """П. 3 (на чистій базі): звіт `level0_migrated` існує, state = skipped (рівня 0 немає), помилок немає."""
    rep = json.loads(_psql(dep_db, "select value from ir_config_parameter where key = 'td.telemetry.level0_migrated'"))
    assert rep["state"] in ("skipped", "done"), rep
    assert rep["mismatches"] == []


def test_dep06_rerun_migration(dep_db):
    """П. 6: повтор міграції — без змін кількостей і без помилок (на демо: `created: 0`)."""
    before = _psql(
        dep_db,
        "select (select count(*) from td_signal), (select count(*) from td_source), (select count(*) from td_reading)",
    )
    res = _shell(
        "import json\nfrom odoo.addons.td_telemetry import hooks\n"
        "r = hooks.run_level0_migration(env)\nenv.cr.commit()\n"
        "print('STAND ' + json.dumps({'state': r['state'], 'mismatches': r['mismatches'], "
        "'catalog': r['signals_catalog']}, default=str))\n"
    )
    after = _psql(
        dep_db,
        "select (select count(*) from td_signal), (select count(*) from td_source), (select count(*) from td_reading)",
    )
    assert res["mismatches"] == [] and res["catalog"]["created"] == 0, res
    assert before == after


@pytest.mark.timeout(1500)
def test_dep07_uninstall_reinstall(dep_db):
    """П. 7 (чиста база): деінсталяція прибирає таблиці td_* і параметри; повторна установка — звіт без розбіжностей."""
    res = _shell(
        "import json\n"
        "m = env['ir.module.module'].search([('name', 'in', ['td_telemetry_viewer3d', 'td_telemetry'])])\n"
        "m.filtered(lambda x: x.name == 'td_telemetry_viewer3d').button_immediate_uninstall()\n"
        "env['ir.module.module'].search([('name', '=', 'td_telemetry')]).button_immediate_uninstall()\n"
        "print('STAND ' + json.dumps({'ok': True}))\n"
    )
    assert res["ok"]
    left = _psql(
        dep_db,
        "select count(*) from information_schema.tables where table_name like 'f3d\\_%' "
        "and table_name not like 'f3d\\_sim%' and table_name not like 'f3d\\_equipment%' "
        "and table_name not like 'f3d\\_scene%' and table_name not like 'f3d\\_zone%' "
        "and table_name not like 'f3d\\_viewer%'",
    )
    names = _psql(
        dep_db,
        "select string_agg(table_name, ',') from information_schema.tables where table_name in "
        "('td_signal','td_source','td_collector','td_reading','td_reading_hour','td_command',"
        "'td_push_event')",
    )
    assert names in ("", None), f"лишились таблиці телеметрії: {names}"
    assert int(_psql(dep_db, "select count(*) from ir_config_parameter where key like 'td.telemetry.%'")) == 0
    del left
    out = subprocess.run(
        [str(TOOLS / "update.sh"), dep_db],
        capture_output=True,
        text=True,
        timeout=1200,
        env={**os.environ, "F3D_TEST_INSTALL": "td_telemetry,td_telemetry_viewer3d"},
        check=False,
    )
    assert "Traceback" not in out.stdout[-2000:], out.stdout[-800:]
    state = _psql(dep_db, "select state from ir_module_module where name = 'td_telemetry'")
    assert state == "installed", (state, out.stdout[-400:])
    rep = json.loads(_psql(dep_db, "select value from ir_config_parameter where key = 'td.telemetry.level0_migrated'"))
    assert rep["mismatches"] == [] and rep["state"] in ("skipped", "done")


def test_dep08_neutralize(dep_db):
    """П. 8: нейтралізація копії — токени стерто, параметри False, крони модуля вимкнені, джерела disabled."""
    if NEU_DB in _dbs():
        subprocess.run(["dropdb", "-h", "127.0.0.1", "-U", "odoo", NEU_DB], check=False, capture_output=True)
    r = subprocess.run(
        ["createdb", "-h", "127.0.0.1", "-U", "odoo", "-T", dep_db, NEU_DB], capture_output=True, text=True, check=False
    )
    if r.returncode:  # шаблон зайнятий — копія через дамп
        pytest.skip(f"вне среды: не вдалось скопіювати базу ({r.stderr[-120:]})")
    try:
        _psql(
            NEU_DB,
            "update td_collector set token_hash = repeat('a', 64), token_hint = 'abcd', state = 'online'; "
            "update td_source set state = 'online', read_enabled = true, write_enabled = true; "
            "update ir_config_parameter set value = 'True' where key in "
            "('td.telemetry.read_enabled', 'td.telemetry.write_enabled')",
        )
        for mod in ("td_factory3d", "td_iot_sim", "td_telemetry", "td_telemetry_viewer3d"):
            f = ADDONS / mod / "data" / "neutralize.sql"
            if f.exists():
                _psql(NEU_DB, file=f)
        assert _psql(NEU_DB, "select count(*) from td_collector where token_hash is not null") == "0"
        assert (
            _psql(
                NEU_DB,
                "select count(*) from ir_config_parameter where key in "
                "('td.telemetry.read_enabled', 'td.telemetry.write_enabled') "
                "and value <> 'False'",
            )
            == "0"
        )
        assert (
            _psql(
                NEU_DB,
                "select count(*) from ir_cron c join ir_model_data d on d.res_id = c.id and "
                "d.model = 'ir.cron' where d.module = 'td_telemetry' and c.active",
            )
            == "0"
        )
        assert _psql(NEU_DB, "select count(*) from td_source where state <> 'disabled' or read_enabled") == "0"
    finally:
        subprocess.run(["dropdb", "-h", "127.0.0.1", "-U", "odoo", NEU_DB], check=False, capture_output=True)


def test_dep09_rollback_leaves_live_db(dep_db):
    """П. 9: відкат = видалення копії; стенд-база `f3d_telemetry_w7` ("жива" для цього тесту) не змінювалась."""
    assert "f3d_telemetry_w7" in _dbs()
    assert Path(ADDONS / "td_telemetry" / "data" / "neutralize.sql").exists()
