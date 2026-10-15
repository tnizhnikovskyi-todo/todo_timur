"""R-26, R-27: розділи `lighting` і `ventilation` payload переглядача (ORM-доступ від користувача запиту)."""

from . import lighting

LIGHT_GROUP = "f3d.bms.light.group"
LIGHT_PANEL = "f3d.bms.light.panel"
LIGHT_NORM = "f3d.bms.light.norm"
HVAC_UNIT = "f3d.bms.hvac.unit"
HEAT_BALANCE = "f3d.bms.heat.balance"
REQUEST = "maintenance.request"


def r12(value):
    """Округлення payload (telemetry R-12): `|v| < 20` — 2 знаки, інакше 1."""
    if value is None or isinstance(value, bool):
        return value
    return round(value, 2) if abs(value) < 20 else round(value, 1)


def _r(value, st, key):
    """Значення зі статики (R-12) лишається як є; живе — округлюється за R-12."""
    return st[key] if key in st and st[key] == value else r12(value)


def _can_read(env, *models):
    return all(m in env and env[m].has_access("read") for m in models)


def _param(env, key, default):
    try:
        return float(env["ir.config_parameter"].sudo().get_param("factory3d.bms." + key, default))
    except (TypeError, ValueError):
        return float(default)


def _area(zone):
    """Площа зони, м²: за контуром (поле `area_m2` округлене до сотих і ламає півметри)."""
    poly = zone.polygon
    if poly and len(poly) >= 3:
        return lighting.round_half_up(zone._polygon_area(poly))
    return lighting.round_half_up(zone.area_m2)


def build_lighting(env, ctx, static):
    """R-26. `static` — статика макета `lighting`; без доступу до моделей модуля повертається як є."""
    static = static or {}
    if not _can_read(env, LIGHT_GROUP, LIGHT_PANEL, LIGHT_NORM):
        return static
    label = dict(env[LIGHT_GROUP]._fields["control_mode"]._description_selection(env))
    static_groups = static.get("groups") or {}
    groups = {}
    for g in env[LIGHT_GROUP].search([("active", "=", True)], order="sequence, code"):
        rec = dict(static_groups.get(g.code) or {})
        rec.update(
            {
                "zone": g.zone_id.f3d_code,
                "zone_name": g.zone_id.name,
                "task": g.norm_id.key,
                "task_name": g.norm_id.name,
                "kind": g.fixture_kind,
                "panel": g.panel_id.code,
                "n": g.n_fixtures,
                "lumen": g.lumen,
                "watt": g.watt,
                "area": _area(g.zone_id),
                "e_norm": g.e_norm,
                "e_calc": g.e_calc,
                "level": round(g.level_pct / 100.0, 3),
                "e_now": g.e_now,
                "p_inst": g.p_inst_kw,
                "p_now": round(g.p_now_kw, 2),
                "control": label.get(g.control_mode, g.control_mode),
                "dali_group": g.dali_group,
                "faults": g.faults,
                "faulty": g.faulty or "",
                "scene": g.scene,
                "deviation": g.deviation,
                "deviation_text": g.deviation_text or "",
                "stale": bool(g.stale),
                "level_source": g.level_source,
            }
        )
        groups[g.code] = rec
    for code, rec in static_groups.items():
        groups.setdefault(code, rec)
    panels = {}
    for p in env[LIGHT_PANEL].search([("active", "=", True)], order="code"):
        rec = dict((static.get("panels") or {}).get(p.code) or {})
        members = p.group_ids.filtered("active").sorted(lambda g: (g.sequence, g.code))
        rec.update(
            {
                "name": p.name,
                "groups": members.mapped("code"),
                "n": p.n_fixtures,
                "p_inst": round(sum(members.mapped("p_inst_kw")), 1),
                "p_now": round(p.p_now_kw, 1),
                "state": p.state,
                "p_source": p.p_source,
            }
        )
        panels[p.code] = rec
    for code, rec in (static.get("panels") or {}).items():
        panels.setdefault(code, rec)
    out = dict(static)
    out.update(
        {
            "groups": groups,
            "panels": panels,
            "uf": _param(env, "light_uf", 0.7),
            "mf": _param(env, "light_mf", 0.8),
            "norms_ref": {n.key: n.ref_en for n in env[LIGHT_NORM].search([("active", "=", True)])},
        }
    )
    return out


def _oldest_request(env, unit):
    if not env[REQUEST].has_access("read"):
        return False
    reqs = unit.request_ids.sorted(lambda r: (r.create_date or 0, r.id))
    return reqs[:1].name or False


def build_ventilation(env, ctx, static):
    """R-27, R-17. `static` — статика макета `ventilation` (база для установок і підсумків)."""
    static = static or {}
    if not _can_read(env, HVAC_UNIT, HEAT_BALANCE):
        return static
    static_units = static.get("units") or {}
    Unit = env[HVAC_UNIT].with_context(f3d_bms_static_units=static_units)
    # обчислювані поля не кешуються за контекстом: скидаємо до й після розрахунку зі статикою
    Unit.invalidate_model()
    try:
        units = {}
        order = []
        t_set, t_out = Unit._f3d_bms_env_params()
        for u in Unit.search([("active", "=", True)], order="sequence, code"):
            # значення беруться зі словника R-12, а не з полів: поля округлені за `digits`
            v = u.sudo()._live_values(static_units.get(u.code) or {}, t_set, t_out)
            st = static_units.get(u.code) or {}
            rec = dict(st)
            rec.update(
                {
                    "name": u.name,
                    "kind": u.kind,
                    "zone": u.zone_id.f3d_code,
                    "mode": v["mode_label"],
                    "mode_code": v["mode_code"] or "",
                    "airflow_m3h": _r(v["airflow_m3h"], st, "airflow_m3h"),
                    "airflow_nom": int(round(u.airflow_nom)),
                    "supply_c": _r(v["supply_c"], st, "supply_c"),
                    "indoor_c": _r(v["indoor_c"], st, "indoor_c"),
                    "heating_valve": _r(v["heating_valve"], st, "heating_valve"),
                    "p_inst": round(u.p_inst_kw, 3),
                    "p_now": _r(v["p_now_kw"], st, "p_now"),
                    "state": v["state"],
                    "filter_extract_dp_pa": _r(v["filter_extract_dp_pa"], st, "filter_extract_dp_pa"),
                    "setpoint_day_c": _r(v["setpoint_day_c"], st, "setpoint_day_c"),
                    "setpoint_night_c": _r(v["setpoint_night_c"], st, "setpoint_night_c"),
                    "deviation": v["deviation"],
                    "deviation_text": v["deviation_text"] or "",
                    "stale": bool(v["stale"]),
                }
            )
            if u.kind in ("roofvent", "ahu"):
                rec["heat_kw"] = _r(v["heat_kw"], st, "heat_kw")
                rec["filter_dp_pa"] = _r(v["filter_dp_pa"], st, "filter_dp_pa")
            if u.note:
                rec["note"] = u.note
            request = _oldest_request(env, u)
            if request:
                rec["maintenance_request"] = request
            else:
                rec.pop("maintenance_request", None)
            units[u.code] = rec
            order.append(u.code)
        for code, rec in static_units.items():
            units.setdefault(code, rec)
        bal = env[HEAT_BALANCE].with_context(f3d_bms_static_units=static_units)._f3d_bms_get()
        live = bal._f3d_bms_live()
    finally:
        Unit.invalidate_model()
    ventilation = dict(static)
    ventilation["units"] = units
    ventilation["totals"] = _totals(units, bal, live, static.get("totals") or {}, static_units)
    ventilation["heat_balance"] = {
        "t_out": bal.t_out_design,
        "items": [{"name": line.name, "kw": line.kw_round} for line in bal.line_ids.sorted("sequence")],
        "total": bal.total_kw,
        "capacity": bal.capacity_kw,
        "chp_kw": round(bal.chp_heat_kw),
        "reserve": bal.reserve,
        "note": bal.note or "",
    }
    ventilation["boiler"] = {
        "state": live["boiler_state"] or "",
        "supply_c": r12(live["supply_c"]),
        "return_c": r12(live["return_c"]),
        "silo_fill": round(live["silo_fill"], 3),
        "heat_kw": r12(live["boiler_heat_kw"]),
    }
    return ventilation


def _totals(units, bal, live, base, static_units):
    vals = list(units.values())
    need = live["need"]
    chp = live["chp_heat_now_kw"]
    totals = dict(base)
    totals.update(
        {
            "units": len(vals),
            "airflow_m3h": round(sum(v.get("airflow_m3h") or 0.0 for v in vals), -2),
            "heat_kw": round(sum(v.get("heat_kw") or 0.0 for v in vals)),
            "p_now": round(sum(v.get("p_now") or 0.0 for v in vals), 1),
            "p_inst": round(sum(v.get("p_inst") or 0.0 for v in vals), 1),
            "outdoor_c": live["outdoor_c"],
            "indoor_set_c": bal.t_in_set,
            "boilers": bal.boilers,
            "boiler_kw": bal.boiler_kw,
            "boilers_on": live["boilers_on"],
            "boiler_load": live["boiler_load"],
            "design_heat_kw": bal.total_kw,
            "chp_heat_kw": round(min(chp, need)),
            "chp_heat_now": round(chp),
            "chp_heat_rated": round(bal.chp_heat_kw),
            "heat_need_kw": round(need, 1),
            "boilers_on_calc": live["boilers_on_calc"],
            "deficit_kw": live["deficit_kw"],
            "chp_source": live["chp_source"],
        }
    )
    # без живих витрат — підсумок макета (він рахується від незашумлених значень макета, AC-17)
    unchanged = all((static_units.get(c) or {}).get("airflow_m3h") == v.get("airflow_m3h") for c, v in units.items())
    if unchanged and base.get("airflow_m3h") is not None:
        totals["airflow_m3h"] = base["airflow_m3h"]
    return totals
