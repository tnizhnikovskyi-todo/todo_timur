"""post_init_hook / uninstall_hook пожежної безпеки (SPEC §5.4, §5.5). W0: скелет без логіки."""

import logging
from types import SimpleNamespace

_logger = logging.getLogger("odoo.addons.factory3d_fire_safety.hooks")


def params(env):
    """Крок 1 (§5.4): read_enabled за CB-10, team_id."""
    return {}


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
    return {"linked": len(stats["linked"]), "missing": len(stats["missing"])}


def _dust(env):
    """Крок 3: сигнал запиленості 2.FAC.07."""
    return {}


def _requests_link(env):
    """Крок 4: зв'язок заявок із зонами (R-22)."""
    return {}


def _events_demo(env):
    """Крок 5: 4 демо-події."""
    return {}


def _drills_demo(env):
    """Крок 6: демо-навчання."""
    return {}


def _sync_first(env):
    """Крок 7: перший sync (R-19)."""
    return {}


def compliance(env):
    """Крок 8: перерахунок відповідності (R-01…R-09)."""
    return {}


def _report_write(env, report):
    """Крок 9: запис migration_report."""
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
    """Виконує кроки 1–9; повертає звіт (лічильники кроків)."""
    return {}


def post_init_hook(env):
    run_all(env)


def uninstall_hook(env):
    """§5.5: видалення параметрів, відв'язування сигналу запиленості."""
