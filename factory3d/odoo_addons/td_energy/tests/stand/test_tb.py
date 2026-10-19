"""ТБ-01…ТБ-06 (SPEC §13.3) на стенді: права через XML-RPC під різними користувачами, ін'єкції, нейтралізація.

Виконуються проти бази стенду (F3D_ODOO_DB); користувачі `tb_*` створюються ідемпотентно. Юніт-варіанти ТБ —
у tests/test_security.py. Без модуля viewer секцію ``denied`` (viewer R-01) перевірити не можна: ТБ-06 перевіряє
відсутність винятку й відсутність даних у payload користувача без доступу.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from helpers import OdooFault, shell_json

pytestmark = pytest.mark.stand
PWD = "Stand-pass-1"
NEUTRALIZE = Path(__file__).resolve().parents[2] / "data" / "neutralize.sql"
GROUPS = {
    "tb_plain": ["base.group_user"],
    "tb_master": ["base.group_user", "mrp.group_mrp_user"],
    "tb_energy": ["base.group_user", "td_energy.group_td_energy_manager"],
    "tb_cost": ["base.group_user", "td_energy.group_td_energy_cost"],
    "tb_f3d_admin": ["base.group_user", "td_factory3d.group_td_admin"],
}


def xmlid(od, name):
    return od.ref_id(name)


@pytest.fixture(scope="module")
def users(odoo):
    out = {}
    for login, groups in GROUPS.items():
        ids = odoo.k("res.users", "search", [("login", "=", login)])
        if not ids:
            odoo.k(
                "res.users",
                "create",
                {
                    "name": login,
                    "login": login,
                    "password": PWD,
                    "group_ids": [(6, 0, [xmlid(odoo, g) if False else _gid(odoo, g) for g in groups])],
                },
            )
        out[login] = odoo.as_user(login, PWD)
    return out


def _gid(od, xml):
    return od.ref_id(xml)


def expect_fault(fn, *needles):
    with pytest.raises(OdooFault) as e:
        fn()
    msg = str(e.value)
    assert not needles or any(n.lower() in msg.lower() for n in needles), msg
    return msg


def test_tb01_no_group_no_access(odoo, users):
    """Користувач без груп енергетики: search на вузол → AccessError; меню «Енергетика» не видно."""
    expect_fault(lambda: users["tb_plain"].k("td.energy.node", "search", []), "доступ", "access")
    # search ir.ui.menu не фільтрує за групами (це робить load_menus), тому звіряємо групи меню з групами користувача
    mine = set(users["tb_plain"].k("res.users", "read", [users["tb_plain"].uid], ["group_ids"])[0]["group_ids"])
    menus = odoo.k("ir.ui.menu", "search_read", [("name", "ilike", "Енергетика")], ["name", "group_ids"])
    assert menus
    for m in menus:
        assert m["group_ids"] and not (set(m["group_ids"]) & mine), m


def test_tb02_master_money_fields(odoo, users):
    """AC-54: майстер не читає грошові поля; AC-65: payload кіоску без грн."""
    m = users["tb_master"]
    for model, field in (
        ("mrp.production", "td_energy_cost"),
        ("td.energy.interval", "cost"),
        ("td.energy.interval", "price"),
        ("td.energy.alloc", "cost"),
    ):
        expect_fault(
            lambda model=model, field=field: m.k(model, "search_read", [], [field], limit=1),
            "доступ",
            "access",
            "поле",
            "field",
            "доступн",
            "groups",
            "групи",
        )
    assert m.k("mrp.production", "search_read", [], ["td_energy_kwh"], limit=1) is not None
    kiosk = shell_json("payload_shell.py", "PAYLOAD", PAYLOAD_KIOSK="1")
    assert kiosk["error"] is None
    assert "cost_today" not in kiosk["energy_totals_keys"] and not any(kiosk["productions_cost"])


def test_tb03_setpoints_forbidden(odoo):
    """AC-81: write_enabled=True на сигналі energy → ValidationError; td.command на сигнал енергетики → відмова."""
    sig = odoo.k("td.signal", "search", [("module", "=", "energy")], limit=1)[0]
    msg = expect_fault(lambda: odoo.k("td.signal", "write", [sig], {"write_enabled": True}), "заборонено")
    assert "заборонено" in msg.lower()
    expect_fault(lambda: odoo.k("td.command", "create", {"signal_id": sig, "value": 1.0}))
    other = odoo.k("td.signal", "search", [("module", "!=", "energy")], limit=1)
    if other:  # сигнал іншого модуля — дозволено
        odoo.k("td.signal", "write", other, {"write_enabled": False})


def test_tb04_injections(odoo):
    """Ін'єкції: код вузла, weekdays, ключ адреси сигналу з `_x` → ValidationError; таблиця на місці."""
    expect_fault(
        lambda: odoo.k(
            "td.energy.node", "create", {"code": "SAW-1'; DROP TABLE td_energy_node;--", "name": "x", "kind": "input"}
        )
    )
    tariff = odoo.k("td.energy.tariff", "search", [], limit=1)[0]
    expect_fault(
        lambda: odoo.k(
            "td.energy.tariff.zone",
            "create",
            {
                "tariff_id": tariff,
                "name": "x",
                "code": "day",
                "price": 1.0,
                "weekdays": "0;1",
                "hour_from": 0,
                "hour_to": 1,
            },
        )
    )
    sig = odoo.k("td.signal", "search", [("module", "=", "energy")], limit=1)[0]
    expect_fault(lambda: odoo.k("td.signal", "write", [sig], {"address": {"fc": 3, "addr": 1, "_x": 1}}))
    assert odoo.k("td.energy.node", "search_count", []) > 0  # таблиця td_energy_node на місці


def test_tb05_neutralize_and_rebind(odoo, users):
    """AC-82: neutralize.sql у транзакції (ROLLBACK): read/write/costing False, крони неактивні, джерела disabled;
    AC-14: rebind без group_td_admin → AccessError."""
    sql = NEUTRALIZE.read_text()
    check = """
SELECT (SELECT count(*) FROM ir_config_parameter WHERE key IN ('td.energy.read_enabled',
         'td.energy.write_enabled','td.energy.costing_enabled') AND value <> 'False'),
       (SELECT count(*) FROM ir_cron c JOIN ir_model_data d ON d.res_id=c.id AND d.model='ir.cron'
         WHERE d.module='td_energy' AND c.active),
       (SELECT count(*) FROM td_source s JOIN ir_model_data d ON d.res_id=s.id AND d.model='td.source'
         WHERE d.module='td_energy' AND s.read_enabled);
"""
    res = subprocess.run(
        [
            "psql",
            "-U",
            os.environ.get("PGUSER", "odoo"),
            "-h",
            os.environ.get("PGHOST", "127.0.0.1"),
            os.environ["F3D_ODOO_DB"],
            "-At",
            "-F",
            ",",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input="BEGIN;\n" + sql + "\n" + check + "ROLLBACK;\n",
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 0, res.stderr[-400:]
    last = [ln for ln in res.stdout.splitlines() if ln.count(",") == 2][-1]
    assert last == "0,0,0", last
    expect_fault(lambda: users["tb_energy"].k("td.energy.node", "action_td_energy_rebind"), "доступ", "access", "адмін")
    assert users["tb_f3d_admin"].k("td.energy.node", "action_td_energy_rebind") is not None


def test_tb06_provider_no_sudo(odoo, users):
    """Провайдери читають без sudo: користувач без доступу до вузлів — без винятку й без даних енергетики."""
    res = shell_json("payload_shell.py", "PAYLOAD", PAYLOAD_LOGIN="tb_plain")
    assert res["error"] is None, res
    assert not res["energy_present"] and not res["infra_totals"]
    admin = shell_json("payload_shell.py", "PAYLOAD")
    assert admin["energy_present"] and admin["infra_totals"]
