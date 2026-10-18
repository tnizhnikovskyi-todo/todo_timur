"""ТК-B1 = AC-B10: вкладка «Тепло» на стенді (мости td_energy_resources_bms встановлено, емулятор + збирач працюють).

pytest проти стенда; XML-RPC до Odoo. Змінні: F3D_ODOO_URL, F3D_ODOO_DB, F3D_ODOO_USER (admin), F3D_ODOO_PASSWORD.
Без F3D_ODOO_URL тести пропускаються (як стендові тести td_energy). Перед запуском: `_td_backfill(days=90)`.
"""

from __future__ import annotations

import os
import xmlrpc.client

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("F3D_ODOO_URL"), reason="F3D_ODOO_URL не задано: стенд не піднято")


@pytest.fixture(scope="module")
def heat():
    url, db = os.environ["F3D_ODOO_URL"].rstrip("/"), os.environ["F3D_ODOO_DB"]
    user, password = os.environ.get("F3D_ODOO_USER", "admin"), os.environ["F3D_ODOO_PASSWORD"]
    uid = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/common").authenticate(db, user, password, {})
    models = xmlrpc.client.ServerProxy(url + "/xmlrpc/2/object")
    return models.execute_kw(db, uid, password, "td.energy.res.dashboard", "get_resources", ["heat"])


def test_tk_b1_kpis_and_list(heat):
    res = heat["resource"]
    kpis = {k["id"]: k for k in res["kpis"]}
    assert {"power", "today", "indoor", "recovery"} <= set(kpis)  # 4 KPI
    assert kpis["recovery"]["quality"] == "estimated"  # підпис «оцінка» (UI-B1) показується за цією ознакою
    assert kpis["recovery"]["note"].startswith(("норма ≥", "—"))
    assert kpis["indoor"]["unit"] == "°C"
    codes = [i["code"] for i in res["list"]["items"]]
    assert {"RV-ALL", "AHU-1", "OFFICE"} <= set(codes)  # «Куди йде тепло»


def test_tk_b1_chart_without_limit(heat):
    chart = heat["resource"]["chart"]
    assert chart["limit"] is None  # D-43: лінії ліміту на вкладці «Тепло» немає
    assert "котли" in chart["note"] and "кВт" in chart["note"]
    assert len(chart["series"]) == 96
