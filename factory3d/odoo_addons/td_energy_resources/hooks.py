"""post_init_hook / uninstall_hook (W3_SPEC 5.5, 5.6). Усі кроки ідемпотентні; ті самі функції викликає міграція.

Кроки `post_init_hook`: `_set_el_on_meters` → `_ensure_resource_signals` → `_seed_points_meters` →
`env["td.energy.point"]._td_bind_extra()` (хук моста) → `_bind_react_signals`. Ресурси, ціни й параметри — XML.
"""

import csv
import io
import json
import logging
import re

from odoo.tools import file_open

from odoo.addons.td_energy import hooks as energy_hooks

_logger = logging.getLogger(__name__)

MODULE = "td_energy_resources"
BATCH = 5000
SOURCES_CSV = "resource_sources.csv"
SIGNALS_CSV = "resource_signals.csv"
REACT_BINDINGS = {"PM-Q1": "energy/cells/Q1/kvarh_total", "PM-Q2": "energy/cells/Q2/kvarh_total"}


def _rows(name):
    with file_open("%s/data/%s" % (MODULE, name), "rb") as f:
        text = f.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def _slug(code):
    return re.sub(r"[^a-z0-9]+", "_", code.lower()).strip("_")


def _internal(env):
    return env(su=True, context=dict(env.context, tracking_disable=True, f3d_energy_internal=True))


def _ensure_xmlid(env, name, record):
    xmlid = "%s.%s" % (MODULE, name)
    if env.ref(xmlid, raise_if_not_found=False) != record:
        env["ir.model.data"]._update_xmlids([{"xml_id": xmlid, "record": record, "noupdate": True}])


# --- крок 1: електричні лічильники -----------------------------------------------------------------------
def _set_el_on_meters(env):
    """`resource_id = el`, `mode = 'counter'` у наявних лічильників (пакетами 5 000)."""
    env = _internal(env)
    el = env.ref("%s.resource_el" % MODULE, raise_if_not_found=False)
    if not el:
        return 0
    total = 0
    while True:
        env.cr.execute(
            """UPDATE td_energy_meter SET resource_id = %s, mode = 'counter'
                WHERE id IN (SELECT id FROM td_energy_meter WHERE resource_id IS NULL LIMIT %s)""",
            (el.id, BATCH),
        )
        total += env.cr.rowcount
        if env.cr.rowcount < BATCH:
            break
    env.cr.execute("UPDATE td_energy_meter SET mode = 'counter' WHERE mode IS NULL")
    env["td.energy.meter"].invalidate_model(["resource_id", "mode"])
    return total


# --- крок 3: сигнали й джерела ---------------------------------------------------------------------------
def _ensure_resource_signals(env):
    """5.4: ідемпотентно створює відсутні сигнали й джерела з `resource_*.csv`; існуючі не змінює."""
    env = _internal(env)
    Source = env["td.source"].with_context(active_test=False)
    Signal = env["td.signal"].with_context(active_test=False)
    created = {"sources": 0, "signals": 0}
    collector = env.ref("td_telemetry.collector_main", raise_if_not_found=False)
    read_enabled = energy_hooks._bool_param(env, "read_enabled")
    if collector:
        for row in _rows(SOURCES_CSV):
            if Source.search_count([("code", "=", row["code"])]):
                continue
            vals = energy_hooks._source_vals(env, row, collector, read_enabled)
            rec = Source.create(dict(vals, code=row["code"]))
            _ensure_xmlid(env, "source_" + _slug(row["code"]), rec)
            created["sources"] += 1
    sources_by_code = {s.code: s for s in Source.search([])}
    rows = _rows(SIGNALS_CSV)
    have = set(Signal.search([("code", "in", [r["code"] for r in rows])]).mapped("code"))
    by_code = {
        s.code: s
        for s in Signal.search(
            [("code", "in", [r["code"] for r in rows] + [r["derived_from"] for r in rows if r["derived_from"]])]
        )
    }
    for row in rows:
        if row["code"] in have:
            continue
        if row["source"] and row["source"] not in sources_by_code:
            _logger.warning("td_energy_resources: сигнал %s: немає джерела %s", row["code"], row["source"])
            continue
        vals = energy_hooks._signal_vals(env, row, sources_by_code)
        vals.update(code=row["code"], name=row["name"], quantity=row["quantity"], create_request=False)
        vals["origin"] = "catalog" if row["origin"] == "sim_data" else row["origin"]
        if row["derived_from"] and row["derived_from"] in by_code:
            vals.update(derived_from_id=by_code[row["derived_from"]].id, derive_rule=row["derive_rule"] or "rate_h")
        rec = Signal.create(vals)
        by_code[rec.code] = rec
        _ensure_xmlid(env, "sig_" + _slug(rec.code), rec)
        created["signals"] += 1
    return created


# --- крок 4: точки й лічильники --------------------------------------------------------------------------
def _seed_points_meters(env):
    """5.3: демо-точки й лічильники газу, повітря, води за `(ресурс, код)`; наявні (ручні правки) не змінюються.

    Лічильник без потрібних сигналів або точка `load_share` без вузла пропускаються з попередженням у лог."""
    env = _internal(env)
    Resource, Point, Meter = env["td.energy.resource"], env["td.energy.point"], env["td.energy.meter"]
    Node, Signal = env["td.energy.node"], env["td.signal"].with_context(active_test=False)
    stats = {"points": 0, "meters": 0, "skipped": 0}
    resources = {r.code: r for r in Resource.search([])}
    for row in _rows("resource_points.csv"):
        res = resources.get(row["resource"])
        if not res or Point.with_context(active_test=False).search_count(
            [("resource_id", "=", res.id), ("code", "=", row["code"]), ("company_id", "=", env.company.id)]
        ):
            continue
        node = Node.search([("code", "=", row["node"])], limit=1) if row["node"] else Node
        cost_node = Node.search([("code", "=", row["cost_node"])], limit=1) if row["cost_node"] else Node
        method = row["estimate_method"] or "none"
        if method == "load_share" and not node:
            _logger.warning(
                "td_energy_resources: точка %s/%s: немає вузла %s — без оцінки",
                row["resource"],
                row["code"],
                row["node"],
            )
            method = "none"
        Point.create(
            {
                "resource_id": res.id,
                "code": row["code"],
                "name": row["name"],
                "kind": row["kind"],
                "sequence": int(row["sequence"] or 10),
                "node_id": node.id or False,
                "cost_node_id": cost_node.id or False,
                "equipment_id": node.equipment_id.id or False,
                "estimate_method": method,
                "rate_nominal": float(row["rate_nominal"] or 0),
                "min_pressure_bar": float(row["min_pressure_bar"] or 0),
                "estimate_params": json.loads(row["estimate_params"]) if row["estimate_params"] else {},
            }
        )
        stats["points"] += 1
    for row in _rows("resource_meters.csv"):
        if Meter.with_context(active_test=False).search_count([("code", "=", row["code"])]):
            continue
        res = resources.get(row["point_resource"])
        point = Point.search([("resource_id", "=", res.id), ("code", "=", row["point"])], limit=1) if res else Point
        qty = Signal.search([("code", "=", row["qty_signal"])], limit=1) if row["qty_signal"] else Signal
        flow = Signal.search([("code", "in", row["flow_signals"].split("|"))]) if row["flow_signals"] else Signal
        ok = bool(point) and (
            (row["mode"] == "counter" and qty)
            or (row["mode"] == "flow_integrate" and flow)
            or (row["mode"] == "estimate" and point.estimate_method != "none")
        )
        if not ok:
            _logger.warning(
                "td_energy_resources: лічильник %s пропущено (немає точки, сигналу або методу оцінки)", row["code"]
            )
            stats["skipped"] += 1
            continue
        Meter.create(
            {
                "code": row["code"],
                "name": row["name"],
                "resource_id": res.id,
                "point_id": point.id,
                "mode": row["mode"],
                "role": "resource",
                "model": row["model"] or "other",
                "qty_signal_id": qty.id or False,
                "flow_signal_ids": [(6, 0, flow.ids)],
                "max_rate": float(row["max_rate"] or 0),
            }
        )
        stats["meters"] += 1
    return stats


# --- крок 5: реактивні сигнали вводів --------------------------------------------------------------------
def _bind_react_signals(env):
    """`PM-Q1.e_react_signal_id`, `PM-Q2.e_react_signal_id` (якщо сигнал є, а поле порожнє)."""
    env = _internal(env)
    bound = 0
    for meter_code, signal_code in REACT_BINDINGS.items():
        meter = env["td.energy.meter"].search([("code", "=", meter_code)], limit=1)
        signal = env["td.signal"].with_context(active_test=False).search([("code", "=", signal_code)], limit=1)
        if meter and signal and not meter.e_react_signal_id and meter.role == "incomer":
            meter.e_react_signal_id = signal
            bound += 1
    return bound


def _run(env):
    env = _internal(env)
    report = {"el_meters": _set_el_on_meters(env), "signals": _ensure_resource_signals(env),
              "seed": _seed_points_meters(env)}  # fmt: skip
    report["bridge"] = env["td.energy.point"]._td_bind_extra()
    report["react"] = _bind_react_signals(env)
    return report


def post_init_hook(env):
    report = _run(env)
    _logger.info("td_energy_resources: прив'язка даних: %s", energy_hooks.dump(report))


def uninstall_hook(env):
    """5.6: видаляє неелектричні лічильники (повертає `node_id` у NOT NULL), знімає `e_react_signal_id`, власні крони й
    параметри. Електричні дані, події й сигнали не чіпаються."""
    env = _internal(env)
    Meter = env["td.energy.meter"].with_context(active_test=False)
    Meter.search([("e_react_signal_id", "!=", False)]).write({"e_react_signal_id": False})
    Meter.search([("resource_id.code", "!=", "el")]).unlink()
    env.cr.execute("DELETE FROM ir_config_parameter WHERE key LIKE %s", ("td.energy\\_resources.%",))
    cron_ids = env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "ir.cron")]).mapped("res_id")
    env["ir.cron"].browse(cron_ids).exists().unlink()
    env.cr.execute("ALTER TABLE td_energy_meter ALTER COLUMN node_id SET NOT NULL")
