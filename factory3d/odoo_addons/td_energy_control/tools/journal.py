"""R-56: журнал — дії `td.energy.action` + події `td.energy.event` (kind pfc/control), пагінація `before_id`."""

from datetime import timedelta

from odoo.addons.td_energy.tools import dates

from . import cparam_int, local_hhmm

ACTION_STATES = ("awaiting_second", "queued", "sent", "executing", "done", "failed", "blocked", "expired")
EVENT_KINDS = ("pfc", "control")
FETCH_ACTIONS = 300
FETCH_EVENTS = 100


def _event_row(ev, now):
    request = ev.request_id
    if request:
        result, kind = "створено", "info"
    elif ev.state == "resolved":
        result, kind = "виконано", "ok"
    else:
        result, kind = "активно", "info"
    return {
        "id": -ev.id,
        "time": local_hhmm(ev.ts, now),
        "what": "Заявка ТО" if request else (ev.title or ev.text),
        "detail": ev.detail or ev.title or ev.text or "",
        "who": "автоматика",
        "result": result,
        "result_kind": kind,
        "state": ev.state,
        "undo_available": False,
        "awaiting_second": False,
        "ref": {"model": "maintenance.request", "id": request.id} if request else None,
    }


def _action_time(rec):
    return rec.finished_at or rec.started_at or rec.confirmed_at or rec.prepared_at or rec.create_date


def get_journal(env, limit=None, before_id=None, origin=None):
    """→ `{"items": [...], "more": bool}`; сортування за часом спадання; `before_id` — id дії або `-id` події."""
    cap = cparam_int(env, "journal_limit", 50) or 50
    limit = min(int(limit or cap), cap)
    now = dates.now_utc(env)
    domain = [("state", "in", ACTION_STATES)]
    if origin:
        domain.append(("origin", "=", origin))
    entries = []
    for rec in env["td.energy.action"].sudo().search(domain, order="id desc", limit=FETCH_ACTIONS):
        entries.append((_action_time(rec), rec.id, rec))
    if origin in (None, False, "", "auto"):
        events = (
            env["td.energy.event"]
            .sudo()
            .search(
                [("kind", "in", EVENT_KINDS), ("ts", ">=", now - timedelta(hours=24))],
                order="ts desc",
                limit=FETCH_EVENTS,
            )
        )
        for ev in events:
            entries.append((ev.ts, -ev.id, ev))
    entries.sort(key=lambda e: (e[0], e[1]), reverse=True)
    if before_id:
        keys = [e[1] for e in entries]
        if before_id in keys:
            entries = entries[keys.index(before_id) + 1 :]
    page = entries[: limit + 1]
    items = []
    for _t, key, rec in page[:limit]:
        items.append(rec._td_journal_row(now) if key > 0 else _event_row(rec, now))
    return {"items": items, "more": len(page) > limit}
