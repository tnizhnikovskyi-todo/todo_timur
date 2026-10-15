"""post_init_hook / uninstall_hook пожежної безпеки (SPEC §5.4, §5.5)."""

import json
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace

from odoo import fields

_logger = logging.getLogger("odoo.addons.factory3d_fire_safety.hooks")
PREFIX = "factory3d.fire_safety."
MODULE = "factory3d_fire_safety"


def params(env):
    """Крок 1 (§5.4): лише за `migration_report == '{}'`: read_enabled за CB-10 і team_id."""
    icp = env["ir.config_parameter"].sudo()
    if (icp.get_param(PREFIX + "migration_report") or "{}") != "{}":
        return {}
    read_enabled = icp.get_param("factory3d.base.environment") == "test"
    icp.set_param(PREFIX + "read_enabled", "True" if read_enabled else "False")
    team = env["maintenance.team"].sudo().search([("name", "=", "Служба головного механіка")], limit=1)
    icp.set_param(PREFIX + "team_id", str(team.id) if team else "")
    return {"read_enabled": read_enabled, "team_id": team.id or None}


def _signal_equipment_code(code):
    """R-24: код сигналу → код обладнання (`None` — правила немає, напр. `fire/devices/…`)."""
    parts = code.split("/")
    if parts[0] != "fire" or len(parts) < 3:
        return None
    if parts[1] == "groups":
        return parts[2]
    if parts[1] in ("loops", "totals"):
        return "FACP-1"
    if parts[1] in ("spark", "smoke"):
        return parts[2]
    return None


def _link(env):
    """Крок 2: зв'язок приладу, зон, пристроїв, систем, виходів, джерел і сигналів з обладнанням (R-24)."""
    Equipment = env["maintenance.equipment"].sudo()
    cache = {}
    stats = {"linked": set(), "missing": set()}

    def eq(code):
        if code not in cache:
            cache[code] = Equipment.search([("f3d_code", "=", code)], limit=1)
            stats["linked" if cache[code] else "missing"].add(code)
        return cache[code]

    def put(record, field, code):
        found = eq(code)
        if found and record[field] != found:
            record[field] = found

    env_su = env(su=True)
    for panel in env_su["f3d.fire.panel"].search([]):
        put(panel, "equipment_id", "FACP-1")
        if panel.source_id:
            put(panel.source_id, "equipment_id", "FACP-1")
        if panel.io_source_id:
            put(panel.io_source_id, "equipment_id", "SPARK-1")
    zones = env_su["f3d.fire.zone"].search([])
    for zone in zones:
        put(zone, "equipment_id", zone.code)
    kind_code = {"mcp": "FA-MCP", "sounder": "FA-SND", "flame": "FA-FLAME", "spark_detector": "SPARK-1",
                 "spark_nozzle": "SPARK-1", "smoke_vent": "SMOKE-VENTS"}
    for dev in env_su["f3d.fire.device"].with_context(active_test=False).search([]):
        put(dev, "equipment_id", kind_code.get(dev.type) or dev.zone_id.code or "FA-MCP")
    for system in env_su["f3d.fire.system"].with_context(active_test=False).search([]):
        put(system, "equipment_id", {"spark": "SPARK-1", "smoke": "SMOKE-CTRL", "sprinkler": "SPRINKLERS"}[
            system.system_type])
        if system.system_type == "smoke":
            put(system, "vents_equipment_id", "SMOKE-VENTS")
        if system.system_type == "sprinkler":
            pressure = env_su["f3d.signal"].search([("code", "=", "equipment/SPRINKLERS/pressure_bar")], limit=1)
            if pressure and system.pressure_signal_id != pressure:
                system.pressure_signal_id = pressure
    if "equipment_id" in env_su["f3d.fire.exit"]._fields:
        for exit_ in env_su["f3d.fire.exit"].with_context(active_test=False).search([]):
            put(exit_, "equipment_id", "EXITS")
    for signal in env_su["f3d.signal"].with_context(active_test=False).search(
            [("module", "=", "fire_safety"), ("code", "like", "fire/%")]):
        code = _signal_equipment_code(signal.code)
        if code:
            put(signal, "equipment_id", code)
    if stats["missing"]:
        _logger.warning("Обладнання не знайдено (%d): %s", len(stats["missing"]), ", ".join(sorted(stats["missing"])))
    pressure = env_su["f3d.fire.system"].search([("system_type", "=", "sprinkler")], limit=1).pressure_signal_id
    return {
        "linked": len(stats["linked"]), "missing": len(stats["missing"]),
        "devices_linked": env_su["f3d.fire.device"].with_context(active_test=False).search_count(
            [("equipment_id", "!=", False)]),
        "signals_linked": env_su["f3d.signal"].with_context(active_test=False).search_count(
            [("module", "=", "fire_safety"), ("code", "like", "fire/%"), ("equipment_id", "!=", False)]),
        "pressure_signal": bool(pressure)}


DUST_CODE = "fire/groups/FA-FAC/dust"


def _dust(env):
    """Крок 3: сигнал запиленості 2.FAC.07 (R-24, X-16, X-37, X-44)."""
    env_su = env(su=True)
    Signal = env_su["f3d.signal"].with_context(active_test=False)
    vals = {
        "source_id": env_su.ref(MODULE + ".source_bacnet_facp_1").id,
        "address": {"object": "PIV", "instance": 21607, "mode": "poll"},
        "period_s": 600, "store_period_s": 3600, "module": "fire_safety", "kind": "gauge", "unit": "%",
        "warn_high": 80, "warn_high_on": True, "alarm_high": 90, "alarm_high_on": True, "hysteresis": 1.8,
        "decimals": 1, "write_enabled": False,
        "alarm_title": "Очистити сповіщувач 2.FAC.07 (Дільниця фасадів МДФ): запиленість {value} % при нормі до "
                       "{threshold}"}
    equipment = env_su["maintenance.equipment"].search([("f3d_code", "=", "FA-FAC")], limit=1)
    if equipment:
        vals["equipment_id"] = equipment.id
    sig = Signal.search([("code", "=", DUST_CODE)], limit=1)
    if sig:
        sig.write(vals)
        mode = "reused"
    else:
        # без xml-id: сигнал переживає деінсталяцію (X-16)
        sig = Signal.create(dict(vals, code=DUST_CODE, name="Запиленість сповіщувача 2.FAC.07", origin="module",
                                 create_request=True))
        mode = "created"
    zone = env_su.ref(MODULE + ".fire_zone_fa_fac")
    device = env_su.ref(MODULE + ".dev_2_fac_07")
    zone.dust_signal_id = sig
    device.write({"dust_signal_id": sig.id, "monitor": True})
    if sig.last_ts:
        device._set_dust(sig.last_value, sig.last_ts, log=False)
    return {"dust_signal": mode, "dust_pct": round(device.dust_pct, 1) if sig.last_ts else None}


def _requests_link(env):
    """Крок 4: зв'язок заявок із зонами (R-22): сигнал модуля й порожнє `f3d_fire_zone_id`."""
    Request = env["maintenance.request"].sudo().with_context(active_test=False)
    todo = Request.search([("f3d_signal_id.module", "=", "fire_safety"), ("f3d_fire_zone_id", "=", False)])
    todo._f3d_fire_link()
    return {"requests_linked": len(todo.filtered("f3d_fire_zone_id"))}


DEMO_EVENTS = (
    ("demo:1", datetime(2026, 10, 12, 5, 47), "spark", "warn", "SPARK-1", "SPARK-1", {"system": "system_spark_1"},
     "Іскрогасіння: іскру виявлено на магістралі аспірації над лінією A, гасіння 0,6 с, лінію не зупиняли."),
    ("demo:2", datetime(2026, 10, 12, 6, 58), "dust_warn", "warn", "2.FAC.07", "FA-FAC",
     {"zone": "fire_zone_fa_fac", "device": "dev_2_fac_07"},
     "Попередження про запиленість: сповіщувач 2.FAC.07 (дільниця фасадів, шліфування)."),
    ("demo:3", datetime(2026, 10, 12, 4, 0), "info", "info", "FACP-1", "FACP-1", {"panel": "panel_facp_1"},
     "Щотижнева перевірка оповіщувачів: усі 4 шлейфи — норма."),
    ("demo:4", datetime(2026, 10, 11, 20, 10), "info", "info", "SPARK-1", "SPARK-1", {"system": "system_spark_1"},
     "Самотест іскрогасіння: датчики й клапан гасіння — норма."),
)


def _events_demo(env):
    """Крок 5: 4 демо-події макета (A-31); ідемпотентність — за `dedup_key`."""
    Event = env["f3d.fire.event"].sudo()
    created = 0
    for key, ts, etype, level, object_code, scene_code, links, text in DEMO_EVENTS:
        if Event.search_count([("dedup_key", "=", key)]):
            continue
        kwargs = {name: env.ref("%s.%s" % (MODULE, xml_id)) for name, xml_id in links.items()}
        Event._log(etype, object_code, ts, text, level=level, source="demo", key=key, scene_code=scene_code,
                   **kwargs)
        created += 1
    return {"events_demo": created}


def _drills_demo(env):
    """Крок 6: демо-навчання «Присадка» (A-30): структура протоколу з людьми з `f3d_code`."""
    Drill = env["f3d.fire.drill"].sudo().with_context(tracking_disable=True, mail_notrack=True)
    if Drill.search_count([("origin", "=", "demo")]):
        return {"drills_demo": 0}
    start = datetime(2026, 9, 30, 7, 0, 0)
    employees = env["hr.employee"].sudo().search([("f3d_code", "!=", False)], order="f3d_code, id")
    total = len(employees)
    people = [(0, 0, {
        "seq": k, "employee_id": emp.id, "since": start - timedelta(hours=3), "source": "demo",
        "exit_ts": start + timedelta(seconds=round(240 * k / total)), "exit_point": "Демо"})
        for k, emp in enumerate(employees, 1)]
    drill = Drill.create({
        "title": "Навчальна тривога — демо (Присадка)", "origin": "demo", "mode": "tabletop",
        "zone_id": env.ref(MODULE + ".fire_zone_fa_cnc").id, "device_id": env.ref(MODULE + ".dev_2_cnc_05").id,
        "planned_ts": start, "start_ts": start, "end_ts": start + timedelta(seconds=300), "state": "done",
        "result": "ok", "conclusions": "Демо-запис: показує структуру протоколу навчання.",
        "passage_source": "demo", "evac_time_s": 240, "person_ids": people})
    for step in drill.step_ids:
        step.write({"done": True, "t_fact_s": step.t_plan_s, "done_by": "auto",
                    "done_ts": start + timedelta(seconds=step.t_plan_s)})
    return {"drills_demo": 1, "drill_people": total, "drill_evac_time_s": drill.evac_time_s,
            "drill_evac_pct": drill.evac_pct}


def _sync_first(env):
    """Крок 7: перший sync (R-19); без показань прилад отримує `comm='lost'` без події й заявки."""
    env["f3d.fire.panel"].sudo()._f3d_fire_sync(full=True)
    panel = env["f3d.fire.panel"].sudo().search([], limit=1)
    return {"sync": "ok", "comm": panel.comm}


def compliance(env):
    """Крок 8: перерахунок відповідності (R-01…R-09)."""
    panel = env["f3d.fire.panel"].sudo().search([], limit=1)
    if not panel:
        return {}
    panel.action_recompute_compliance()
    return {"zones_ok": panel.compliance_zones_ok, "mcp_max_m": panel.compliance_mcp_max_m,
            "routes_ok": panel.compliance_routes_ok, "exits_ok": panel.compliance_exits_ok,
            "smoke_ok": panel.compliance_smoke_ok, "missing_zones": panel.compliance_missing_zones or False}


def _report_write(env, report):
    """Крок 9: запис migration_report (`state`: done, якщо `missing == 0` і кроки 7–8 без помилок)."""
    report = dict(report)
    report["state"] = "done" if report.get("missing", 0) == 0 and not report.get("errors") else "partial"
    report["ts"] = fields.Datetime.to_string(fields.Datetime.now())
    env["ir.config_parameter"].sudo().set_param(PREFIX + "migration_report", json.dumps(report, ensure_ascii=False))
    return report


# Тести (FireCase) викликають hooks.equipment.link(env) — простір імен, як підмодулі зі SPEC §5.4
equipment = SimpleNamespace(link=_link)
signals = SimpleNamespace(dust=_dust)
requests = SimpleNamespace(link=_requests_link)
events = SimpleNamespace(demo=_events_demo)
drills = SimpleNamespace(demo=_drills_demo)
sync = SimpleNamespace(first=_sync_first)
report = SimpleNamespace(write=_report_write)


def run_all(env):
    """Виконує кроки 1–9; повертає звіт. Кроки 1–6 — виняток відкочує установку, 7–8 — у savepoint."""
    result = {}
    for name, func in (("params", params), ("link", _link), ("dust", _dust), ("requests", _requests_link),
                       ("events", _events_demo), ("drills", _drills_demo)):
        part = func(env)
        _logger.info("Крок %s: %s", name, part)
        result.update(part)
    errors = []
    for name, func in (("sync", _sync_first), ("compliance", compliance)):
        try:
            with env.cr.savepoint():
                part = func(env)
            _logger.info("Крок %s: %s", name, part)
            result.update(part)
        except Exception:
            _logger.warning("Крок %s завершився помилкою; звіт — partial", name, exc_info=True)
            errors.append(name)
    if errors:
        result["errors"] = errors
    return report.write(env, result)


def post_init_hook(env):
    run_all(env)


def uninstall_hook(env):
    """§5.5: сигнал запиленості відв'язується від джерела, параметри `factory3d.fire_safety.*` видаляються."""
    _logger.warning(
        "Видаляються журнал подій (%d) і навчання (%d) пожежної безпеки; експортуйте протоколи (інструкція 4.6)",
        env["f3d.fire.event"].sudo().search_count([]), env["f3d.fire.drill"].sudo().with_context(
            active_test=False).search_count([]))
    sig = env["f3d.signal"].sudo().with_context(active_test=False).search([("code", "=", DUST_CODE)], limit=1)
    if sig:
        sig.write({"source_id": False, "address": {}})
    env["ir.config_parameter"].sudo().search([("key", "=like", PREFIX + "%")]).unlink()
