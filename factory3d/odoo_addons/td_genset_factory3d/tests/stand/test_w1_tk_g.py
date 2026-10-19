"""ТК-G14, ТК-G15 (W1_SPEC B.13): стенд з td_genset + fake_relay (профіль D700) + міст + td_energy.

ТК-G15, перший крок («лише td_genset — плитка активна, 223 тести td_genset») перевіряється окремою базою:
``F3D_TEST_INSTALL=td_genset run_tests.sh <db> /td_genset`` (AC-82); тут — решта кроків на стенді з мостом.
"""

from __future__ import annotations

from conftest import need_destructive, need_genset
from helpers import wait_for

SECTION = "td_energy.menu_td_energy_generation"
TILE = "td_genset.menu_root"
BRIDGE = "td_genset_factory3d"
NO_FILTER = {"context": {"active_test": False}}


def tile_active(odoo) -> bool:
    return odoo.k("ir.ui.menu", "read", [odoo.ref_id(TILE)], ["active"], **NO_FILTER)[0]["active"]


def module_state(odoo, name: str) -> str:
    return odoo.k("ir.module.module", "search_read", [("name", "=", name)], ["state"], limit=1)[0]["state"]


@need_genset
def test_tk_g14_section_menus_open(odoo):
    """Меню розділу «Генерація й резерв» відкриваються: 25 пунктів мосту, кожен з дією — з валідним записом."""
    section = odoo.ref_id(SECTION)
    host = odoo.k(
        "ir.model.data",
        "search_read",
        [("module", "=", BRIDGE), ("model", "=", "ir.ui.menu"), ("name", "=like", "menu_gf_%")],
        ["res_id"],
    )
    assert len(host) == 25
    menus = odoo.k("ir.ui.menu", "read", [r["res_id"] for r in host], ["name", "action", "parent_id"])
    top = {m["name"] for m in menus if m["parent_id"][0] == section}
    assert {"Генератор", "Показання", "Події генератора", "Заправка", "Аналітика генератора"} <= top
    assert {"Зв'язка з заводом", "Заявки ТО генератора", "Налаштування"} <= top
    for menu in menus:
        if menu["action"]:
            model, res_id = menu["action"].split(",")
            assert odoo.k(model, "search_count", [("id", "=", int(res_id))]) == 1, menu["name"]


@need_genset
def test_tk_g14_genset_pult_under_section(odoo):
    """Пульт td_genset працює як клієнтська дія під розділом: дія «Генератор» і стан пульта за fake_relay."""
    gensets = odoo.k("td.genset", "search", [("active", "=", True)])
    assert gensets, "у БД стенда немає генератора td_genset"
    action = odoo.k("td.genset", "action_open_main", [])
    assert action["res_model"] == "td.genset"
    state = odoo.k("td.genset", "get_pult_state", [gensets[0]])
    assert {"buttons", "gauges", "status"} <= set(state)


@need_genset
def test_tk_g14_pult_shows_genset_reserve(odoo):
    """Пульт енергетики: «ДГУ · резерв» (state=reserve) і картка ДГУ в «Генерації й резерві»."""

    def genset():
        pult = odoo.k("td.energy.dashboard", "get_pult", period="now", parts=["kpis"])
        return (pult["kpis"]["generation"] or {}).get("genset")

    summary = wait_for(lambda: (genset() or {}).get("state") == "reserve" and genset(), timeout=180, step=10)
    assert summary and summary["label"] == "резерв"
    assert summary["fuel_pct"] is not None
    cards = odoo.k("td.energy.dashboard", "get_generation")["cards"]
    assert [c["code"] for c in cards][-1] == "GENSET"
    assert cards[-1]["state"] == "off" and cards[-1]["can_3d"] is True


@need_genset
@need_destructive
def test_tk_g15_tile_hidden_and_restored(odoo):
    """Міст установлено — плитка прихована; -u td_genset — лишається прихованою; видалити міст — повертається."""
    assert module_state(odoo, BRIDGE) == "installed"
    assert tile_active(odoo) is False
    td_genset = odoo.k("ir.module.module", "search", [("name", "=", "td_genset")])
    odoo.k("ir.module.module", "button_immediate_upgrade", td_genset)
    assert tile_active(odoo) is False  # AC-83
    bridge = odoo.k("ir.module.module", "search", [("name", "=", BRIDGE)])
    try:
        odoo.k("ir.module.module", "button_immediate_uninstall", bridge)
        assert tile_active(odoo) is True  # AC-75
    finally:
        odoo.k("ir.module.module", "button_immediate_install", bridge)
    assert module_state(odoo, BRIDGE) == "installed"
    assert tile_active(odoo) is False
