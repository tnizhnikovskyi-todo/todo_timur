import csv
import logging
import os

_logger = logging.getLogger("odoo.addons.td_factory3d.hooks")

WC_LINK = "workcenter_id"  # поле maintenance.equipment з mrp_maintenance (Enterprise); у CE його немає
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _read_rows(name):
    """Рядки data-файла; підміняється тестами через hooks.read_data_file, якщо воно є."""
    from odoo.addons.td_factory3d import hooks

    reader = getattr(hooks, "read_data_file", None)
    if reader is not None:
        return reader(name)
    with open(os.path.join(DATA_DIR, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _has_code(model):
    return "td_code" in model._fields and hasattr(model, "search_f3d")


def _assign(records, zone):
    """Записати зону лише тим, хто її ще не має; повертає кількість записів із цією зоною."""
    todo = records.filtered(lambda r: r.td_zone_id != zone)
    if todo:
        todo.write({"td_zone_id": zone.id})
    return len(records)


def bind(env):
    """Крок 7: прив'язати локації, РЦ і обладнання до зон за scene_zone_links.csv (R-08)."""
    Zone = env["td.zone"].with_context(active_test=False)
    Loc, Wc, Eq = env["stock.location"], env["mrp.workcenter"], env["maintenance.equipment"]
    zones = {z.td_code: z for z in Zone.search([])}
    counters = {"roots": 0, "locations": 0, "workcenters": 0, "equipment": 0, "zones": len(zones)}
    for row in _read_rows("scene_zone_links.csv"):
        zone = zones.get(row["zone"])
        kind, value = row["kind"], row["value"]
        if not zone or not value:
            continue
        if kind == "root":
            loc = Loc.search([("complete_name", "=", value)], limit=1)
            if loc:
                if zone.root_location_id != loc:
                    zone.root_location_id = loc
                counters["roots"] += 1
        elif kind == "prefix":
            if "td_code" in Loc._fields:
                found = Loc.search([("td_code", "=like", value + "%")])
                counters["locations"] += _assign(found, zone)
        elif kind == "code":
            if _has_code(Loc):
                counters["locations"] += _assign(Loc.search_f3d(value), zone)
        elif kind == "workcenter":
            if _has_code(Wc):
                counters["workcenters"] += _assign(Wc.search_f3d(value), zone)
        elif kind == "equipment":
            if _has_code(Eq):
                counters["equipment"] += _assign(Eq.search_f3d(value), zone)
    counters["equipment"] += _equipment_from_workcenter(env)
    _logger.info("zones.bind: %s", counters)
    return counters


def _equipment_from_workcenter(env):
    """Обладнання без зони успадковує зону свого РЦ (крок 7 і повтор міграції).

    Зв'язок — workcenter_id (mrp_maintenance, Enterprise); обладнання без зв'язку — і в CE, де поля немає (ENV-1),
    і в Enterprise, де поле є, але порожнє (B-2) — шукає РЦ за однаковим td_code (A-15)."""
    Eq, Wc = env["maintenance.equipment"], env["mrp.workcenter"]
    link = WC_LINK if WC_LINK in Eq._fields else None
    count = 0
    if link:
        for eq in Eq.search([("td_zone_id", "=", False), (link + ".td_zone_id", "!=", False)]):
            eq.td_zone_id = eq[link].td_zone_id
            count += 1
    if _has_code(Eq) and _has_code(Wc):
        for wc in Wc.with_context(active_test=False).search([("td_zone_id", "!=", False), ("td_code", "!=", False)]):
            eq = Eq.search_f3d(wc.td_code)
            if eq and not eq.td_zone_id and not (link and eq[link]):
                eq.td_zone_id = wc.td_zone_id
                count += 1
    return count
