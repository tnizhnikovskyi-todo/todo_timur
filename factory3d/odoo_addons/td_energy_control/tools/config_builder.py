"""R-43: JSON конфігу для збирача (API-24), канонічний вигляд і ETag. Без секретів і собівартості (окрім зон тарифу)."""

import copy
import hashlib
import json
import re

from odoo.addons.td_energy.tools import dates

from . import cparam_bool, cparam_int, iso, kinds

SCHEMA = 1
NON_CANONICAL = ("schema", "config_version", "etag", "server_time")
LIMITS = {"bess_kw_max": 200, "pv_limit_min_pct": 10, "air_bar_min": 5.0, "air_bar_max": 8.5}
BESS_KWH_DEFAULT = 387.0


def canonical(cfg):
    """Канонічний JSON для ETag: без `schema`, `config_version`, `etag`, `server_time` (R-43 п.2)."""
    body = {k: v for k, v in cfg.items() if k not in NON_CANONICAL}
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def etag(cfg):
    return hashlib.sha256(canonical(cfg).encode("utf-8")).hexdigest()


def plant(env):
    """Заводські константи: договірна потужність, СЕС, BESS, ДГУ, КГУ, номінал QS (SPEC 7.3 `plant`)."""
    now = dates.now_utc(env)
    tariff = env["td.energy.tariff"].sudo()._td_tariff_at(now)
    nodes = {n.code: n for n in env["td.energy.node"].sudo().search([("code", "in", ["GENSET", "CHP", "QS"])])}
    interlock = env["td.energy.interlock"].sudo().search([("code", "=", "bess_reserve_kept")], limit=1)
    peak = env["td.energy.scenario"].sudo().search([("code", "=", "peak")], limit=1)

    def p_inst(code, default):
        node = nodes.get(code)
        return node.p_inst_kw if node and node.p_inst_kw else default

    return {
        "contract_kw": (tariff.contract_kw if tariff else 800.0) or 800.0,
        "pv_kwp": dates.param_float(env, "pv_kwp", 920.0),
        "bess_kwh": (interlock.params or {}).get("capacity_kwh", BESS_KWH_DEFAULT) if interlock else BESS_KWH_DEFAULT,
        "bess_max_kw": float(LIMITS["bess_kw_max"]),
        "bess_max_kw_scenario": (peak._td_params().get("bess_max_kw") if peak else 100.0),
        "bess_reserve_pct": dates.param_float(env, "bess_reserve_pct", 30.0),
        "cos_phi_target": dates.param_float(env, "cos_phi_target", 0.95),
        "genset_kw": p_inst("GENSET", 507.0),
        "chp_kw": p_inst("CHP", 800.0),
        "qs_rating_a": (nodes["QS"].rating_a if nodes.get("QS") and nodes["QS"].rating_a else 1600),
    }


def bms_targets(env):
    """R-43 / SPEC 7.3 п.4: цілі BMS: вентиляція (roofvent), освітлення (аварійні проходи не вимикаються)."""
    vent, light = [], []
    if "td.bms.hvac.unit" in env:
        for u in env["td.bms.hvac.unit"].sudo().search([("kind", "=", "roofvent")], order="code"):
            if u.mode_signal_id:
                item = {"unit": u.code, "mode_signal": u.mode_signal_id.code}
                if u.sp_night_signal_id:
                    item["sp_night_signal"] = u.sp_night_signal_id.code
                vent.append(item)
    if "td.bms.light.group" in env:
        for g in env["td.bms.light.group"].sudo().search([], order="code"):
            if g.scene_signal_id:
                light.append(
                    {"group": g.code, "scene_signal": g.scene_signal_id.code, "aisle": g.fixture_kind == "highbay_rack"}
                )
    vent_eco = [{k: v for k, v in u.items() if k != "sp_night_signal"} for u in vent]
    return {
        "night": {"vent": vent, "light": light},
        "vent_eco": {"vent": vent_eco},
        "light_break": {"light": [g for g in light if not g["aisle"]]},
    }


PV_P_RE = re.compile(r"^infra/pv/PV-INV-\d+/p_kw$")  # як у td_energy.models.td_energy_node_live


def derived(env):
    """D-47: формули для входів `inputs`, які в Odoo обчислює EN-DERIVED (`td_energy` R-06/R-14); збирач не отримує
    їх із пристроїв. Терми — ті самі сирі сигнали й знаки, за якими `td_energy` рахує значення зараз.

    Операції: `sum` (терми `{"code","k"[,"min"]}`: Σ k·max(min, x); необов'язкові `clamp_min` — нижня межа
    результату, `zero_if {"code","eq"}` — результат 0, коли сигнал дорівнює `eq`); `ge` (1.0, якщо значення `code` ≥
    `value`, інакше 0.0). Будь-який терм відсутній або старший за `max_age_s` — похідний вхід відсутній (fail-closed).
    """
    Node = env["td.energy.node"].sudo()
    lines = Node.search([("kind", "=", "line")], order="code")
    terms = {"all": [], 1: [], 2: []}
    for ln in lines:
        term = {"code": "energy/lines/%s/p_now" % ln.code, "k": 1.0}
        terms["all"].append(term)
        section = ln.section or ln.parent_id.section
        if section in (1, 2):
            terms[section].append(dict(term))
    pv = env["td.signal"].sudo().search([("code", "=like", "infra/pv/PV-INV-%/p_kw")], order="code")
    q_terms = [{"code": "energy/cells/Q%d/p_now" % s, "k": 1.0} for s in (1, 2)]
    island = {"code": "infra/ats/position", "eq": 3}
    return {
        "energy/totals/p_now": {"op": "sum", "terms": terms["all"]},
        "energy/sections/S1/p_kw": {"op": "sum", "terms": terms[1]},
        "energy/sections/S2/p_kw": {"op": "sum", "terms": terms[2]},
        "infra/ats/src1_ok": {"op": "ge", "code": "infra/ats/src1_state", "value": 1},
        "infra/totals/grid_kw": {"op": "sum", "terms": q_terms, "clamp_min": 0.0, "zero_if": island},
        "infra/totals/export_kw": {
            "op": "sum",
            "terms": [dict(t, k=-1.0) for t in q_terms],
            "clamp_min": 0.0,
            "zero_if": island,
        },
        "infra/totals/pv_now": {
            "op": "sum",
            "terms": [{"code": s.code, "k": 1.0, "min": 0.0} for s in pv if PV_P_RE.match(s.code)],
        },
    }


def build(env):
    """Повний конфіг API-24 (без `etag` — його додає виклик; `server_time` для відповіді)."""
    env = env(su=True)
    now = dates.now_utc(env)
    state = env["td.energy.control.state"].get()
    pl = plant(env)
    cfg_plant = {k: v for k, v in pl.items() if k != "bess_max_kw_scenario"}
    scenarios = {}
    for sc in env["td.energy.scenario"].search([]):
        params = sc._td_params()
        if sc.code == "pfc":
            params = {"cos_target": pl["cos_phi_target"]}
        scenarios[sc.code] = {"enabled": bool(sc.enabled), "params": copy.deepcopy(params)}
    shed_items = env["td.energy.shed.item"].search([("active", "=", True)], order="sequence, id")
    shed = [
        {
            "id": it.id,
            "seq": i,
            "node": it.node_id.code,
            "action": it.action,
            "param": it.param_value,
            "kw": it.kw_reducible,
            "critical": bool(it.node_id.is_critical),
            "signal": it.signal_id.code or "energy_control/shed/%s/limit_pct" % it.node_id.code,
            "condition": it.condition,
            "condition_value": it.condition_value if it.condition != "none" else None,
        }
        for i, it in enumerate(shed_items, 1)
    ]
    shed_nodes = {it.node_id.id for it in shed_items}
    critical = env["td.energy.node"].search([("is_critical", "=", True)], order="code")
    never = sorted({n.code for n in critical if n.id not in shed_nodes} | set(kinds.NEVER_SHED_CODES))
    slots = [
        {
            "id": s.id,
            "resource": s.resource,
            "date": s.date.isoformat() if s.date else None,
            "weekdays": s.weekdays or "1111111",
            "from": s.time_from,
            "to": s.time_to,
            "mode": s.mode,
            "setpoint_kw": s.setpoint_kw or None,
        }
        for s in env["td.energy.schedule.slot"].search([("executes", "=", True), ("active", "=", True)])
    ]
    tariff = env["td.energy.tariff"]._td_tariff_at(now)
    zones = [
        {"from": z.hour_from, "to": z.hour_to, "price": z.price}
        for z in (tariff.zone_ids.sorted("sequence") if tariff else [])
    ]
    interlocks = {}
    for row in env["td.energy.interlock"].search([("active", "=", True), ("where", "!=", "odoo")]):
        interlocks[row.code] = {
            "hard": bool(row.hard),
            "fail_closed": bool(row.fail_closed),
            "params": copy.deepcopy(row.params or {}),
        }
    return {
        "schema": SCHEMA,
        "config_version": state.config_version,
        "server_time": iso(now),
        "tz": "Europe/Kyiv",
        "flags": {
            "automation_enabled": cparam_bool(env, "automation_enabled"),
            "write_enabled": cparam_bool(env, "write_enabled"),
            "remote_switching_enabled": cparam_bool(env, "remote_switching_enabled"),
        },
        "engine": {
            "tick_s": cparam_int(env, "engine_tick_s", 2),
            "config_poll_s": cparam_int(env, "config_poll_s", 10),
            "stale_hold_s": cparam_int(env, "stale_hold_s", 30),
            "min_write_interval_s": cparam_int(env, "min_write_interval_s", 10),
            "max_writes_per_min": cparam_int(env, "max_writes_per_min", 30),
            "exec_timeout_s": cparam_int(env, "exec_timeout_s", 60),
            "step_timeout_s": cparam_int(env, "step_timeout_s", 8),
            "verify_timeout_s": cparam_int(env, "verify_timeout_s", 30),
            "shed_restore_step_s": cparam_int(env, "shed_restore_step_s", 20),
        },
        "plant": cfg_plant,
        "scenarios": scenarios,
        "shed": shed,
        "never_shed": never,
        "slots": slots,
        "tariff": {"zones": zones, "currency": "UAH"},
        "bms": bms_targets(env),
        "signals": dict(kinds.SIGNALS),
        "inputs": dict(kinds.INPUTS),
        "derived": derived(env),
        "interlocks": interlocks,
        "limits": dict(LIMITS),
    }
