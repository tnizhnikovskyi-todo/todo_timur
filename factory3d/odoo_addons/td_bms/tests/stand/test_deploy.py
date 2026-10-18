"""DEPLOY_TEST §13.5 кроки 4–5: «одна зона → усі» (читання лише для BAC-108-RV-08, BAC-109-RV-09, HN-LP-2)."""

from __future__ import annotations

from bms_lib import bms_requests, close_bms_requests, group, last_request_id, sleep_until, unit
from conftest import wait  # noqa: F401

ONE_ZONE = {"BAC-108-RV-08", "BAC-109-RV-09", "HN-LP-2"}


def _sources(odoo):
    return odoo.search_read(
        "td.source", [("module", "=", "bms"), ("code", "!=", "BMS-DERIVED")], ["code", "state", "read_enabled"]
    )


def test_deploy_one_zone_then_all(odoo, fresh_sim):
    close_bms_requests(odoo)
    base = last_request_id(odoo)
    srcs = _sources(odoo)
    ids = {s["code"]: s["id"] for s in odoo.search_read("td.source", [("module", "=", "bms")], ["code"])}
    try:
        for s in srcs:
            odoo.write("td.source", ids[s["code"]], {"read_enabled": s["code"] in ONE_ZONE})
        assert sleep_until(
            lambda: all(s["state"] == "disabled" for s in _sources(odoo) if s["code"] not in ONE_ZONE), 120, 10
        ), [s for s in _sources(odoo) if s["state"] != "disabled" and s["code"] not in ONE_ZONE][:5]
        assert sleep_until(
            lambda: all(s["state"] == "online" for s in _sources(odoo) if s["code"] in ONE_ZONE), 180, 10
        )
        # ТК-12 для RV-08, RV-09, LT-CUT
        for code in ("RV-08", "RV-09"):
            assert sleep_until(lambda c=code: unit(odoo, c)["live_ts"], 90, 5), code
        assert group(odoo, "LT-CUT")["level_pct"] == fresh_sim.value("lighting/groups/LT-CUT/level")
        print(
            "DEPLOY одна зона: online",
            sorted(s["code"] for s in _sources(odoo) if s["state"] == "online"),
            "disabled",
            sum(s["state"] == "disabled" for s in _sources(odoo)),
        )
        # інших об'єктів у заявках немає (RV-xx поза зоною)
        new = bms_requests(odoo, after_id=base)
        assert not [r for r in new if any(x in r["name"] for x in ("RV-01", "RV-02", "RV-05", "RV-07", "BOILER"))], new
    finally:
        for s in srcs:
            odoo.write("td.source", ids[s["code"]], {"read_enabled": True})
    assert sleep_until(lambda: all(s["state"] == "online" for s in _sources(odoo)), 240, 10), [
        s for s in _sources(odoo) if s["state"] != "online"
    ][:5]
    print("DEPLOY усі джерела online:", len(_sources(odoo)))
