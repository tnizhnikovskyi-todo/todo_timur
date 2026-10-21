"""ТК-B11 (SPEC td_chp_factory3d): стенд з `iot_sim` — Пуск з пульта (1/2 + 2/2) → один `chp_start` у журналі
Енергетики, `state=2`; «Аварійний стоп» → `chp_estop` `done`, `state=3`; «Скинути» → `chp_reset`, `state=0`.

Потрібні: колектор із джерелом `MB-U72-CHP`, `td.energy_control.write_enabled` і `remote_switching_enabled`, запис у
`chp/ctl/*` (`td.telemetry.write_enabled`, джерело, сигнали), користувач — головний енергетик (`F3D_ODOO_USER`,
одноосібно); для 2/2 від енергетика — другий користувач F3D_ODOO_USER2 / F3D_ODOO_PASSWORD2.
"""

from __future__ import annotations

import os

import pytest
from helpers import wait_for

PULT = "td.chp.pult"


def state(odoo) -> float | None:
    return odoo.signal("chp/ctl/state").get("last_value")


def command(odoo, op, **kw):
    return odoo.k(PULT, "command", op, **kw)


def run_to_end(odoo, kind, params=None):
    """prepare → confirm (→ confirm_second); повертає ref дії."""
    prep = command(odoo, "prepare", kind=kind, params=params or {})
    assert not prep["blocked"], prep["blocked_reason"]
    res = command(odoo, "confirm", ref=prep["ref"], token=prep["token"])
    if res["state"] == "awaiting_second":
        second_user(odoo).k(PULT, "command", "confirm_second", ref=prep["ref"])
    return prep["ref"]


def second_user(odoo):
    user = os.environ.get("F3D_ODOO_USER2")
    if not user:
        pytest.skip("потрібен другий користувач для 2/2 (F3D_ODOO_USER2, F3D_ODOO_PASSWORD2)")
    return odoo.as_user(user, os.environ["F3D_ODOO_PASSWORD2"])


def finished(odoo, ref, timeout=90):
    got = {}

    def done():
        got.update(command(odoo, "get", ref=ref))
        return got["state"] in ("done", "failed", "blocked", "expired")

    wait_for(done, timeout=timeout, step=2)
    return got


def test_tk_b11_start_estop_reset_through_energy_journal(odoo):
    if state(odoo) != 0:
        pytest.skip("КГУ не в резерві (state != 0)")
    action_ids = odoo.k("td.energy.action", "search", [("kind_code", "in", ["chp_start", "chp_estop", "chp_reset"])])
    ref = run_to_end(odoo, "start")
    assert finished(odoo, ref)["state"] == "done"
    wait_for(lambda: state(odoo) == 2, timeout=90, step=2)
    new = odoo.k(
        "td.energy.action", "search_read", [("kind_code", "=", "chp_start"), ("id", "not in", action_ids)], ["state"]
    )
    assert [r["state"] for r in new] == ["done"]  # один chp_start на пуск
    assert odoo.k("td.chp.command", "search_count", []) == 0  # td.chp.command не створюється
    ref = run_to_end(odoo, "estop")
    assert finished(odoo, ref)["state"] == "done"
    wait_for(lambda: state(odoo) == 3, timeout=30, step=2)
    ref = run_to_end(odoo, "reset")
    assert finished(odoo, ref)["state"] == "done"
    wait_for(lambda: state(odoo) == 0, timeout=30, step=2)
    journal = odoo.k(PULT, "get_journal", limit=20)["items"]
    assert {"Команда «Аварійний стоп»: Виконано", "Команда «Скидання аварії»: Виконано"} <= {
        r["text"].split(" · ")[0] for r in journal if r["type"] == "command"
    }
