"""Розділи `fire` і `evacuation` payload переглядача (SPEC R-20, R-21, API-02, Додаток C).

Без залежності від td_viewer3d: функції викликає міст-модуль M-17 і тести основного модуля.
Читання — від імені користувача запиту (без sudo); персональних даних навчань у payload немає: ключ `live` (R-21a)
містить людей лише як безособові рядки (№, зона, виходи, час проходу) — рядки людей читаються з sudo.
"""

import calendar
from datetime import timedelta

from odoo import fields

from .dates import local

RULE_KEYS = (
    "smoke_area_6_12m",
    "smoke_spacing_6_12m",
    "smoke_wall_6_12m",
    "heat_area",
    "heat_spacing",
    "mcp_spacing",
    "mcp_height",
    "sounder_level",
    "spark_detection_required",
    "flame_detector_note",
)
SYSTEM_CODES = ("SPARK-1", "SMOKE-CTRL", "SPRINKLERS")
STATE_PASS = ("alarm", "prealarm", "fault", "disabled", "test")
LIVE_KEEP_MAX_MIN = 10  # R-21a: після кінця евакуації 3D тримає навчання `evaluating` не довше (хв), `done`/`cancelled` — ніколи


class _SafeDict(dict):
    def __missing__(self, key):
        return "{%s}" % key


def _num(value):
    """Ціле, якщо значення ціле (30, 65); `None` лишається `None`."""
    if value is None:
        return None
    return int(value) if float(value).is_integer() else round(value, 3)


def _group_state(zone):
    if zone.state in STATE_PASS:
        return zone.state
    return "warn" if zone.warn else "ok"


def build_fire(env, ctx=None):
    """R-20: розділ `fire`; порядок ключів фіксований."""
    Norm, Zone, Device = env["td.fire.norm"], env["td.fire.zone"], env["td.fire.device"]
    panel = env["td.fire.panel"].search([], limit=1)
    rules = {key: _num(Norm.get(key)) for key in RULE_KEYS}
    loops = {}
    for loop in env["td.fire.loop"].search([], order="number"):
        loops[str(loop.number)] = {
            "detectors": loop.detectors_count,
            "mcp": loop.mcp_count,
            "sounders": loop.sounders_count,
            "flame": loop.flame_count,
            "modules": loop.modules_count,
            "state": "ok" if loop.state == "unknown" else loop.state,
        }
    groups, detectors = {}, 0
    for zone in Zone.search([], order="lsz_instance, id"):
        base_code = zone.zone_id.td_code or ""
        item = {
            "zone": "BOILER" if zone.code == "FA-BOILER" else base_code,
            "zone_name": zone.name,
            "kind": zone.kind,
            "kind_name": zone.kind_name or "",
            "n": zone.detector_count,
            "spacing": zone.spacing_m,
            "area": round(zone.area_m2),
            "loop": zone.loop_id.number,
            "state": _group_state(zone),
        }
        if zone.warning:
            item["warning"] = zone.warning
        if zone.maintenance_request_id:
            # viewer R-22: назви заявок не унікальні («Планове ТО»), тож клієнт шукає заявку за id
            item["maintenance_request"] = zone.maintenance_request_name
            item["maintenance_request_id"] = zone.maintenance_request_id.id
        elif ctx and ctx.get("delta"):  # delta зливається поверх даних клієнта: без null стара заявка лишилась би
            item["maintenance_request"] = item["maintenance_request_id"] = None
        if zone.dust_max_pct:
            item["dust"] = round(zone.dust_max_pct / 100.0, 3)
        item.update({"alarm_state": zone.state, "compliance": zone.compliance, "stale": bool(zone.stale)})
        groups[zone.code] = item
        detectors += zone.detector_count
    systems = {s.code: s for s in env["td.fire.system"].search([])}
    sprinkler = systems.get("SPRINKLERS")
    totals = {
        "detectors": detectors,
        "mcp": Device.search_count([("type", "=", "mcp")]),
        "sounders": Device.search_count([("type", "=", "sounder")]),
        "flame": Device.search_count([("type", "=", "flame")]),
        "spark_detectors": Device.search_count([("type", "=", "spark_detector")]),
        "mcp_max_m": panel.compliance_mcp_max_m,
        "state": panel.state_text or "",
        "sprinkler": sprinkler.state_text if sprinkler else "",
    }
    events = [e._payload_item() for e in env["td.fire.event"].search([], order="ts desc, id desc", limit=20)]
    panel_item = {
        "code": panel.code,
        "state": panel.state,
        "state_text": panel.state_text or "",
        "comm": panel.comm,
        "last_seen": local(panel.last_seen) or None,
        "alarms": panel.alarms_count,
        "faults": panel.faults_count,
        "disabled": panel.disabled_count,
        "sounders": bool(panel.sounders_active),
        "brigade": bool(panel.brigade_transmitted),
    }
    out_systems = {}
    for code in SYSTEM_CODES:
        system = systems.get(code)
        if not system:
            continue
        item = {"state": system.state, "text": system.state_text or ""}
        if code == "SPARK-1":
            item["count_today"] = system.count_today
        elif code == "SMOKE-CTRL":
            item["vents_open"] = system.state == "active"
        else:
            item["pressure_bar"] = round(system.pressure_bar, 2) if system.pressure_signal_id else None
        out_systems[code] = item
    result = {
        "rules": rules,
        "loops": loops,
        "groups": groups,
        "totals": totals,
        "events": events,
        "panel": panel_item,
        "systems": out_systems,
    }
    if panel._get_param("viewer_devices", False):
        result["devices"] = {
            d.address: {
                "type": d.type,
                "x": d.x,
                "y": d.y,
                "z": d.z,
                "zone": d.zone_id.code or None,
                "state": d.state,
                "dust": round(d.dust_pct / 100.0, 3) if d.dust_ts else None,
            }
            for d in Device.search([], order="id")
        }
    return result


def _render_steps(steps, drill_ctx):
    out = []
    for step in steps:
        try:
            text = step.text.format_map(drill_ctx)
        except (ValueError, IndexError, KeyError, AttributeError):
            text = step.text
        out.append({"t": step.t_plan_s, "who": step.who, "text": text})
    return out


def _ms(dt):
    """UTC naive datetime → epoch у мілісекундах; порожнє → None."""
    if not dt:
        return None
    return calendar.timegm(dt.timetuple()) * 1000 + dt.microsecond // 1000


def _smoke_for(env, fire_zones):
    """Димові зони, що перетинають контур пожежної зони (R-21a): де в 3D зависає дим."""
    out = []
    for smoke in env["td.fire.smoke.zone"].search([], order="code"):
        for zone in fire_zones:
            if smoke.x0 < zone.x1 and zone.x0 < smoke.x1 and smoke.y0 < zone.y1 and zone.y0 < smoke.y1:
                out.append({"code": smoke.code, "x0": smoke.x0, "y0": smoke.y0, "x1": smoke.x1, "y1": smoke.y1})
                break
    return out


def build_live(env, ctx=None):
    """R-21a: ключ `live` розділу `evacuation` — живий стан тривоги для 3D або `None`.

    `mode='drill'` — навчання `running` (або `evaluating`, що завершилось не раніше `drill_3d_keep_min` хв тому, але не
    більше `LIVE_KEEP_MAX_MIN`): люди навчання безособово; закрите (`done`) і скасоване навчання в 3D не показується;
    `mode='alarm'` — справжня тривога (зона приладу в `alarm`/`prealarm`, навчання немає): лише зона, дим і час,
    лічильники людей клієнт бере з розділу `access`.
    """
    Drill, Zone = env["td.fire.drill"], env["td.fire.zone"]
    now = fields.Datetime.now()
    panel_param = env["td.fire.panel"]._get_param
    drill = Drill.search([("state", "=", "running")], limit=1)
    if not drill:
        keep = min(panel_param("drill_3d_keep_min", LIVE_KEEP_MAX_MIN), LIVE_KEEP_MAX_MIN)
        drill = Drill.search(
            [("state", "=", "evaluating"), ("end_ts", ">=", now - timedelta(minutes=keep))],
            order="end_ts desc, id desc",
            limit=1,
        )
    live = {"now_ms": _ms(now), "stuck_after_s": panel_param("drill_stuck_after_s", 120)}
    if drill:
        zone = drill.zone_id
        live.update(
            {
                "mode": "drill",
                "name": drill.name,
                "state": drill.state,
                "zone": zone.code,
                "zone_code": zone.zone_id.td_code or "",
                "origin": [round((zone.x0 + zone.x1) / 2, 2), round((zone.y0 + zone.y1) / 2, 2)],
                "start_ms": _ms(drill.start_ts),
                "end_ms": _ms(drill.end_ts),
                "limit_s": drill.time_limit_s,
                "total": drill.on_site_count,
                "smoke": _smoke_for(env, zone),
                "people": [
                    {
                        "n": p.seq,
                        "zone": p.zone_id.td_code or None,
                        "exit": p.assigned_exit_id.code or None,
                        "out_ms": _ms(p.exit_ts),
                        "out_exit": p.exit_id.code or None,
                        "wrong": bool(p.wrong_exit),
                    }
                    for p in drill.sudo().person_ids.sorted("seq")
                ],
            }
        )
        return live
    alarm = Zone.search([("state", "in", ("alarm", "prealarm"))], order="state_ts, id")
    if not alarm:
        return None
    first = alarm[0]
    since = env["td.fire.event"].search(
        [("etype", "in", ("alarm", "prealarm")), ("zone_id", "=", first.id)], order="ts desc, id desc", limit=1
    )
    live.update(
        {
            "mode": "alarm",
            "name": "",
            "state": "running",
            "zone": first.code,
            "zone_code": first.zone_id.td_code or "",
            "origin": [round((first.x0 + first.x1) / 2, 2), round((first.y0 + first.y1) / 2, 2)],
            "start_ms": _ms(since.ts or first.state_ts or now),
            "end_ms": None,
            "limit_s": panel_param("drill_time_limit_s", 300),
            "total": 0,
            "smoke": _smoke_for(env, alarm),
            "people": [],
        }
    )
    return live


def build_evacuation(env, ctx=None):
    """R-21: розділ `evacuation`; порядок ключів — viewer A.13 + `drill_active`, `compliance`."""
    Norm = env["td.fire.norm"]
    panel = env["td.fire.panel"].search([], limit=1)
    exits = [
        {"code": e.code, "x": e.x, "y": e.y, "side": e.side, "width": e.width_m, "ok": e.compliance == "ok"}
        for e in env["td.fire.exit"].search([], order="id")
    ]
    route_recs = env["td.fire.route"].search([])
    routes = {}
    for route in route_recs.sorted(lambda r: (r.zone_id.sequence, r.id)):
        routes[route.zone_code] = {
            "name": route.name,
            "exit": route.exit_id.code,
            "length": route.length_m,
            "path": route.path or [],
            "ok": route.compliance == "ok",
            "norm": _num(route.norm_m),
        }
    active = env["td.fire.drill"].search([("state", "=", "running")], limit=1)
    template = env["td.fire.drill.template"].search([("is_default", "=", True)], limit=1)
    zone = active.zone_id if active else template.default_zone_id
    device = active.device_id if active else template.default_device_id
    if active:
        steps = [{"t": s.t_plan_s, "who": s.who, "text": s.text} for s in active.step_ids.sorted("sequence")]
        drill_active = {
            "name": active.name,
            "zone": active.zone_id.name,
            "zone_code": active.zone_id.code,
            "detector": active.device_id.address or "",
            "started": local(active.start_ts),
            "elapsed_s": active.elapsed_s,
            "steps_done": active.steps_done,
            "steps_total": active.steps_total,
            "on_site": active.on_site_count,
            "evacuated": active.evacuated_count,
        }
    else:
        sounders = env["td.fire.device"].search_count([("type", "=", "sounder")])
        steps = _render_steps(
            template.step_ids.sorted("sequence"),
            _SafeDict(detector=device.address or "—", zone=zone.name or "", sounders=sounders),
        )
        drill_active = None
    return {
        "exits": exits,
        "routes": routes,
        "max_distance": panel.evac_max_distance_m,
        "worst_point": [panel.evac_worst_x, panel.evac_worst_y],
        "drill_origin": zone.code or "",
        "drill_zone": zone.name or "",
        "drill_detector": device.address or "",
        "norm_distance": _num(Norm.get("evac_distance_prod_B")),
        "norm_ref": Norm.get_ref("evac_distance_prod_B"),
        "norm_alt": _num(Norm.get("evac_distance_polymer")),
        "norm_alt_ref": Norm.get_ref("evac_distance_polymer"),
        "drill_steps": steps,
        "drill_active": drill_active,
        "compliance": {
            "routes_ok": panel.compliance_routes_ok,
            "routes_total": panel.compliance_routes_total,
            "worst": max(route_recs.mapped("length_m") or [0.0]),
            "norm": _num(Norm.get("evac_distance_prod_B")),
            "exits_ok": bool(panel.compliance_exits_ok),
            "smoke_ok": panel.compliance_smoke_ok,
            "smoke_total": panel.compliance_smoke_total,
        },
        "live": build_live(env, ctx),
    }
