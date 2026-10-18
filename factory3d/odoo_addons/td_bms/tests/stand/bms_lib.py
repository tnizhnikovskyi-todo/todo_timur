"""Допоміжні запити до моделей «Будівля» через XML-RPC (стенд factory3d_bms)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from helpers import wait  # noqa: F401  (реекспорт)

STAND_SH = Path(__file__).resolve().parent / "stand.sh"
UNIT_F = [
    "code",
    "state",
    "mode_code",
    "mode_label",
    "heat_kw",
    "filter_dp_pa",
    "stale",
    "deviation",
    "deviation_text",
    "setpoint_night_c",
    "setpoint_day_c",
    "airflow_m3h",
    "live_ts",
    "supply_c",
    "indoor_c",
    "alarm_count",
    "plan_state",
]
GROUP_F = [
    "code",
    "level_pct",
    "level_source",
    "e_now",
    "e_norm",
    "scene",
    "faults",
    "faulty",
    "stale",
    "deviation",
    "deviation_text",
    "live_ts",
    "f3d_bms_write_enabled",
    "p_now_kw",
]


def unit(o, code):
    return o.search_read("f3d.bms.hvac.unit", [("code", "=", code)], UNIT_F, limit=1)[0]


def group(o, code):
    return o.search_read("f3d.bms.light.group", [("code", "=", code)], GROUP_F, limit=1)[0]


def panel(o, code):
    return o.search_read("f3d.bms.light.panel", [("code", "=", code)], ["code", "state"], limit=1)[0]


def balance(o):
    return o.search_read(
        "f3d.bms.heat.balance",
        [],
        [
            "outdoor_c",
            "heat_need_kw",
            "boilers_on",
            "boiler_state",
            "deficit_kw",
            "total_kw",
            "capacity_kw",
            "chp_heat_now_kw",
        ],
        limit=1,
    )[0]


def last_request_id(o):
    r = o.search_read("maintenance.request", [], ["id"], order="id desc", limit=1)
    return r[0]["id"] if r else 0


def bms_requests(o, rule=None, name=None, only_open=False, after_id=0):
    dom = [("f3d_bms_rule", "!=", False)] if rule is None else [("f3d_bms_rule", "=", rule)]
    if after_id:
        dom.append(("id", ">", after_id))
    if name:
        dom.append(("name", "ilike", name))
    if only_open:
        dom.append(("stage_id.done", "=", False))
    return o.search_read(
        "maintenance.request",
        dom,
        ["name", "f3d_bms_rule", "maintenance_team_id", "stage_id", "description", "equipment_id"],
        order="id",
    )


def episodes(o, rule=None, code=None, state=None):
    dom = []
    if rule:
        dom.append(("rule", "=", rule))
    if code:
        dom.append(("object_code", "=", code))
    if state:
        dom.append(("state", "=", state))
    return o.search_read(
        "f3d.bms.deviation", dom, ["name", "rule", "object_code", "state", "value", "request_id"], order="id"
    )


def close_bms_requests(o):
    ids = [r["id"] for r in bms_requests(o, only_open=True)]
    for rid in ids:
        o.close_request(rid)
    return len(ids)


def sig(o, code):
    return o.signal(code)


def source(o, code):
    return o.search_read(
        "f3d.source",
        [("code", "=", code)],
        ["code", "state", "params", "read_enabled", "write_enabled", "last_error"],
        limit=1,
    )[0]


def trigger_check(o):
    """Позачерговий прогін крону перевірок (як «Виконати зараз»)."""
    cron = o.search_read("ir.cron", [("cron_name", "ilike", "Будівля")], ["id"], limit=5)
    return cron


def restart_collector(env=None):
    import os

    e = {**os.environ, **(env or {})}
    return subprocess.run(
        [str(STAND_SH), "collector-restart"], env=e, capture_output=True, text=True, timeout=120
    ).stdout


def sleep_until(pred, timeout, step=5):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = pred()
        if last:
            return last
        time.sleep(step)
    return None


def use_calendar(o, name=None):
    """Ставить календар перевірок `factory3d.bms.calendar_id` (None — порожньо: календар компанії)."""
    cid = ""
    if name:
        cid = str(o.search_read("resource.calendar", [("name", "=", name)], ["id"], limit=1)[0]["id"])
    o.param("factory3d.bms.calendar_id", cid)
    return cid
