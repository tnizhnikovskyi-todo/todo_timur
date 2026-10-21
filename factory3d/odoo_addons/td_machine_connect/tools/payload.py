"""Побудова фрагментів payload переглядача (R-25, M-22). Без імпорту моделей viewer: працює з `env` і словниками."""

import logging
from datetime import timezone

from odoo import fields

from ..models.td_machine import KYIV, local

_logger = logging.getLogger(__name__)
GANTRY = "GANTRY-1"
STATUS = {"fault": "stop", "working": "work"}
ACTIVE_JOB = ("queued", "active")


def _nodes(container, key):
    """Вузли-словники контейнера: `dict` за ключем або список словників за полем `key` → `{ключ: вузол}`."""
    if isinstance(container, dict):
        return {k: v for k, v in container.items() if isinstance(v, dict)}
    if isinstance(container, list):
        return {n[key]: n for n in container if isinstance(n, dict) and n.get(key)}
    return {}


def _num(value):
    return int(value) if float(value).is_integer() else round(value, 1)


def _shift_start(machine):
    """Початок поточної зміни (naive UTC): `oee_shift_id.date_start`, інакше початок київської доби."""
    shift = machine.oee_shift_id
    if shift and shift.date_start:
        return shift.date_start
    now = fields.Datetime.now().replace(tzinfo=timezone.utc).astimezone(KYIV)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).replace(tzinfo=None)


def _machine_node(env, machine, costs=None):
    """R-25 п. 1: живі поля одного верстата; `costs` — `{workcenter_id: сума}` простоїв за місяць (DT-3) або `None`."""
    node = {
        "machine_state": machine.state,
        "link": machine.protocol,
        "online": machine.state != "nodata",
    }
    if machine.state_since:
        node["state_since"] = local(machine.state_since, "%Y-%m-%d %H:%M")
    shift = machine.oee_shift_id
    if shift and shift.has_data:
        node.update(
            oee=round(shift.oee, 2),
            availability=round(shift.availability, 2),
            performance=round(shift.performance, 2),
            quality=round(shift.quality, 2),
        )
    dt = machine.current_downtime_id
    if dt and not dt.date_end:
        down = {
            "reason": dt.loss_id.name,
            "since": local(dt.date_start, "%H:%M"),
            "minutes": int(dt.duration_live),
            "kind": dt.state_kind,
            "state": dt.reason_state,
        }
        if dt.hint_text:
            down["hint"] = dt.hint_text
        node["downtime"] = down
    logs = env["td.machine.state.log"].search(
        [("machine_id", "=", machine.id), ("date_start", ">=", _shift_start(machine))]
    )
    node["pieces_shift"] = int(sum(logs.mapped("pieces")))
    if costs is not None:
        node["downtime_cost"] = round(costs.get(machine.workcenter_id.id, 0.0), 2)
    wo = machine.active_workorder_id
    if wo:
        node["counted"] = _num(wo.td_qty_counted)
    if machine.state in STATUS:
        node["status"] = STATUS[machine.state]
    return node


def apply_flow(env, payload, full):
    """R-30 п. 6: `flow` (показники ділянки, вузьке місце) у вузли верстатів `payload`; збій аналітики не ламає payload.

    Повний payload (`full`) — вузлам, що вже є. Дельта — зведення `flow` усіх верстатів ділянок із рейтингу, а не лише
    вузлів патча: воно мале, а зміна вузького місця чи черги торкається й вузлів, яких у патчі немає (стара стопка
    знімається, нова ставиться); вузол без патча створюється з одним ключем `flow` (клієнт зливає глибоко).
    """
    try:
        with env.cr.savepoint():
            flows = env["td.bottleneck"].sudo()._td_flow_nodes()
    except Exception:
        _logger.exception("machine_connect: flow вузького місця не пораховано")
        return
    nodes = payload.get("workcenters")
    if full:
        for code, node in _nodes(nodes, "code").items():
            if code in flows:
                node["flow"] = flows[code]
    elif flows and isinstance(nodes, dict):
        for code, flow in flows.items():
            if isinstance(nodes.get(code), dict):
                nodes[code]["flow"] = flow
            else:
                nodes[code] = {"flow": flow}
    elif flows and nodes is None:
        payload["workcenters"] = {code: {"flow": flow} for code, flow in flows.items()}
    elif flows and isinstance(nodes, list):
        known = {n.get("code"): n for n in nodes if isinstance(n, dict)}
        for code, flow in flows.items():
            if code in known:
                known[code]["flow"] = flow
            else:
                nodes.append({"code": code, "flow": flow})


def _gantry_node(env):
    """R-25 п. 2: стан порталу з `gantry_status` і активного завдання."""
    Job = env["td.gantry.job"]
    status = Job._td_gantry_status()
    job = Job.search([("state", "=", "active")], order="started, id", limit=1)
    return {
        "state": status.get("state"),
        "job": {
            "id": job.ws_id,
            "target": job.target_code or "",
            "sheets": job.sheets,
            "done": job.done,
            "ref": job.external_ref or "",
        }
        if job
        else None,
        "stacks": env["td.gantry.stack"].search_count([("ws_qty", ">", 0)]),
        "aisles_open": list(status.get("aisles_open") or []),
        "alarms": list(status.get("alarms") or []),
    }


def build_machines(env, ctx, payload=None):
    """Фрагмент payload R-25 п. 1–5 лише для вузлів, що є в `payload` (немає — пропускаються без помилок).

    Результат: `{"workcenters": {код: {…}}, "equipment": {"GANTRY-1": {"gantry": {…}}}, "locations": {код: {"gantry":
    {…}}}, "productions": {name: {"cut_map": {…}, "supply": {"gantry": {…}}}}, "sheet_chain": {"stock": str}}`;
    застосовує його до payload `apply_machines`. `payload=None` — усі верстати й стоси (без МО та ланцюжка).
    """
    full = payload is None
    payload = payload if isinstance(payload, dict) else {}
    out = {}
    wcs = _nodes(payload.get("workcenters"), "code")
    machines = env["td.machine"].search(
        [("active", "=", True), ("code", "in", list(wcs))] if not full else [("active", "=", True)]
    )
    if machines:
        # DT-3: вартість простоїв — управлінські дані: лише менеджеру «Завод 3D» і не в кіоску (як `energy_cost`, X-25)
        Downtime = env["td.downtime"]
        costs = (
            Downtime._td_cost_by_workcenter() if not (ctx or {}).get("kiosk") and Downtime._td_cost_can_see() else None
        )
        out["workcenters"] = {m.code: _machine_node(env, m, costs) for m in machines}
    if GANTRY in _nodes(payload.get("equipment"), "code") or full:
        out["equipment"] = {GANTRY: {"gantry": _gantry_node(env)}}
    plt = [c for c in _nodes(payload.get("locations"), "code") if c.startswith("PLT-")]
    stacks = env["td.gantry.stack"].search([("code", "in", plt)] if not full else [])
    stacks = stacks.filtered("ws_seen")
    if stacks:
        out["locations"] = {
            s.code: {
                "gantry": {
                    "qty": s.ws_qty,
                    "expected": round(s.expected_qty, 1),
                    "diff": round(s.diff, 1),
                    "state": s.state,
                }
            }
            for s in stacks
        }
    _portal(env, out, None if full else plt, GANTRY in out.get("equipment", {}))
    prods = _nodes(payload.get("productions"), "name")
    if prods:
        out["productions"] = _productions(env, prods)
    jobs = env["td.gantry.job"].search([("state", "in", ACTIVE_JOB)]) if payload.get("sheet_chain") else False
    if jobs:
        out["sheet_chain"] = {
            "stock": "портал: %d завд. · %d арк." % (len(jobs), sum(max(j.sheets - j.done, 0) for j in jobs))
        }
    return out


def _portal(env, out, codes, with_equipment):
    """R-31: `equipment.GANTRY-1.portal` (завдання доби, ланцюжок до МО) і `locations[PLT-*].portal` (стоси для 3D).

    Збій розрахунку лише логується: решта payload віддається без портальних вузлів (3D-шар неактивний).
    """
    try:
        with env.cr.savepoint():
            portal = env["td.portal"]
            now = portal._td_now()
            equipment = portal._td_equipment_node(now) if with_equipment else None
            stacks = portal._td_stack_nodes(codes, now)
        if equipment is not None:
            out.setdefault("equipment", {}).setdefault(GANTRY, {})["portal"] = equipment
        for code, node in stacks.items():
            out.setdefault("locations", {}).setdefault(code, {})["portal"] = node
    except Exception:  # необов'язковий шар 3D не повинен ламати payload
        _logger.exception("machine_connect: вузли порталу (R-31) не пораховано")


def _productions(env, prods):
    res = {}
    names = list(prods)
    maps = env["td.cut.map"].search([("production_id.name", "in", names), ("state", "!=", "cancel")], order="id desc")
    jobs = env["td.gantry.job"].search(
        [("production_id.name", "in", names), ("state", "!=", "cancelled")], order="id desc"
    )
    map_of, job_of = {}, {}
    for cmap in maps:
        map_of.setdefault(cmap.production_id.name, cmap)
    for job in jobs:
        job_of.setdefault(job.production_id.name, job)
    for name, node in prods.items():
        item = {}
        cmap, job = map_of.get(name), job_of.get(name)
        if cmap:
            item["cut_map"] = {
                "name": cmap.name,
                "state": cmap.state,
                "sheets": cmap.plan_sheets,
                "waste_pct": round(cmap.plan_waste_pct, 1),
            }
        if job and isinstance(node.get("supply"), dict):
            item["supply"] = {"gantry": {"job": job.name, "sheets": job.sheets, "done": job.done, "state": job.state}}
        if item:
            res[name] = item
    return res


def apply_machines(payload, fragment):
    """Дописує `fragment` (`build_machines`) у payload/patch: лише R-25 п. 1–5, інші ключі вузлів не чіпає."""
    for code, data in (fragment.get("workcenters") or {}).items():
        _nodes(payload.get("workcenters"), "code")[code].update(data)
    for code, data in (fragment.get("equipment") or {}).items():
        _nodes(payload.get("equipment"), "code")[code].update(data)
    for code, data in (fragment.get("locations") or {}).items():
        _nodes(payload.get("locations"), "code")[code].update(data)
    prods = _nodes(payload.get("productions"), "name")
    for name, data in (fragment.get("productions") or {}).items():
        node = prods[name]
        if "cut_map" in data:
            node["cut_map"] = data["cut_map"]
        if "supply" in data:
            node["supply"].update(data["supply"])
    stock = (fragment.get("sheet_chain") or {}).get("stock")
    steps = (payload.get("sheet_chain") or {}).get("steps")
    if stock and isinstance(steps, list) and len(steps) >= 5 and isinstance(steps[4], dict):
        steps[4]["stock"] = stock
