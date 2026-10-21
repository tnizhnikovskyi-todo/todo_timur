"""API-13: маршрут МО чи переміщення, якого немає в живому payload (виконане, скасоване, старе, майбутнє).

Читання з правами користувача запиту (без `sudo`): запис, до якого немає доступу, віддається як `not_found`.
Відповідь — завжди dict із `kind`, `name` і `reason`: `None` — маршрут є; `no_workorders` / `no_codes` / `no_locations` —
документ знайдено, але підсвічувати нічого; `not_found`, `forbidden`, `bad_request` — документа немає або немає прав.
"""

from . import dates
from .payload import access_ok

WO_STATE = {"waiting": "pending", "blocked": "pending"}  # станів «Чекає…» у маршруті немає: вони не про верстат
MAX_LOCATIONS = 24


def _dt(value):
    return dates.local(value) if value else None


def _empty(kind, name, reason):
    return {"kind": kind, "name": name, "reason": reason}


def mo_route(env, name):
    """МО за назвою: операції за порядком (код центру, стан, дати) і основні поля картки."""
    if not all(access_ok(env, m) for m in ("mrp.production", "mrp.workorder", "mrp.workcenter")):
        return _empty("mo", name, "forbidden")
    mo = env["mrp.production"].search([("name", "=", name)], limit=1)
    if not mo:
        return _empty("mo", name, "not_found")
    wos = env["mrp.workorder"].search([("production_id", "=", mo.id)], order="sequence, id")
    steps = [
        {
            "code": wo.workcenter_id.td_code or "",
            "name": wo.name,
            "workcenter": wo.workcenter_id.name or "",
            "state": WO_STATE.get(wo.state, wo.state),
            "sequence": k + 1,
            "date_start": _dt(wo.date_start),
            "date_finished": _dt(wo.date_finished),
        }
        for k, wo in enumerate(wos)
    ]
    reason = None
    if not steps:
        reason = "no_workorders"
    elif not any(s["code"] for s in steps):
        reason = "no_codes"
    state = "progress" if mo.state == "to_close" else mo.state
    return {
        "kind": "mo",
        "name": mo.name,
        "reason": reason,
        "state": state,
        "product": mo.product_id.default_code or "",
        "product_name": mo.product_id.name or "",
        "qty": mo.product_qty,
        "uom": mo.product_uom_id.name or "",
        "origin": mo.origin or "",
        "route": mo.bom_id.code or "",
        "date": _dt(mo.date_finished if mo.state == "done" else (mo.date_start or mo.date_deadline)),
        "date_start": _dt(mo.date_start),
        "date_finished": _dt(mo.date_finished),
        "steps": steps,
    }


def picking_route(env, name):
    """Переміщення за назвою: комірки зі сценою (звідки → ворота → куди) і основні поля картки."""
    if not (access_ok(env, "stock.picking") and access_ok(env, "stock.location")):
        return _empty("picking", name, "forbidden")
    p = env["stock.picking"].search([("name", "=", name)], limit=1)
    if not p:
        return _empty("picking", name, "not_found")
    locations = []

    def add(loc, role):
        if loc.td_code and len(locations) < MAX_LOCATIONS and all(x["code"] != loc.td_code for x in locations):
            locations.append({"code": loc.td_code, "name": loc.complete_name or loc.name, "role": role})

    mls, moves = p.move_line_ids, p.move_ids
    for loc in p.location_id | mls.location_id | moves.location_id:
        add(loc, "from")
    add(p.batch_id.dock_id, "dock")
    for loc in p.location_dest_id | mls.location_dest_id | moves.location_dest_id:
        add(loc, "to")
    sched = p.date_done if p.state == "done" and p.date_done else p.scheduled_date
    return {
        "kind": "picking",
        "name": p.name,
        "reason": None if locations else "no_locations",
        "state": p.state,
        "type": p.picking_type_code,
        "picking_type": p.picking_type_id.name or "",
        "partner": p.partner_id.name or "",
        "origin": p.origin or "",
        "date": _dt(sched),
        "locations": locations,
    }


def build(env, kind, name):
    return (mo_route if kind == "mo" else picking_route)(env, name)
