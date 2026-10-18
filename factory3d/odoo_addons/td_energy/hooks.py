"""post_init_hook / uninstall_hook (SPEC §5.3–§5.4). `run_bind(env)` — ідемпотентна прив'язка даних енергетики."""

import csv
import io
import json
import logging
import math
import re

from odoo import Command, fields
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

MODULE = "td_energy"
PARAM = "td.energy."
SHIFT_CALENDAR_NAME = "Зміна 1 (07:00–15:30)"
DERIVED_CODE = "EN-DERIVED"
THRESHOLDS = ("warn_low", "warn_high", "alarm_low", "alarm_high")
SIGNAL_DEFINITION = (
    "kind", "unit", "equipment_id", "source_id", "address", "period_s", "store_period_s", "decimals", "states",
    "alarm_states", "alarm_title", "hysteresis", "min_duration_s", "viewer_visible",
)  # fmt: skip
NODE_STR = ("name", "kind", "cell_type", "line_kind", "gen_kind", "p_inst_source", "alloc_role", "group", "note")
NODE_INT = {"section": "section", "sequence": "sequence", "rating_a": "rating_a", "rating_kva": "rating_kva",
            "rating_kvar": "rating_kvar", "unit": "unit_id"}  # fmt: skip
NODE_FLOAT = {"voltage_kv": "voltage_kv", "p_inst_kw": "p_inst_kw", "load_factor": "load_factor",
              "idle_factor": "idle_factor", "cos_phi": "cos_phi_nominal"}  # fmt: skip
FIXED_MAX_KW = {"sun2000": 125, "luna2000": 200, "tedom": 900}


def dump(report):
    return json.dumps(report, ensure_ascii=False, sort_keys=True)


def _rows(name):
    with file_open("%s/data/%s" % (MODULE, name), "rb") as f:
        text = f.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text, newline="")))


def _slug(code):
    return re.sub(r"[^a-z0-9]+", "_", code.lower()).strip("_")


def _step(name):
    _logger.info("td_energy: крок %s", name)


def _ensure_xmlid(env, name, record):
    xmlid = "%s.%s" % (MODULE, name)
    if env.ref(xmlid, raise_if_not_found=False) != record:
        env["ir.model.data"]._update_xmlids([{"xml_id": xmlid, "record": record, "noupdate": True}])


def _find(env, model, domain, xmlid=None):
    if xmlid:
        rec = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
        if rec and rec.exists():
            return rec
    return env[model].with_context(active_test=False).search(domain, limit=1)


def _upsert(env, model, code, vals, xmlid=None):
    """Знайти за `code` (або xml-id) і оновити, інакше створити. Повертає (запис, створено?)."""
    rec = _find(env, model, [("code", "=", code)], xmlid)
    created = not rec
    if rec:
        rec.write(vals)
    else:
        rec = env[model].create(dict(vals, code=code))
    if xmlid:
        _ensure_xmlid(env, xmlid, rec)
    return rec, created


def _param(env, key, default=""):
    return env["ir.config_parameter"].sudo().get_param(PARAM + key, default)


def _bool_param(env, key):
    return _param(env, key, "False") in ("True", "true", "1")


# --- кроки ------------------------------------------------------------------------------------------
def params(env, report):
    _step("1 params")
    icp = env["ir.config_parameter"].sudo()
    first_run = icp.get_param(PARAM + "install_report", "{}") in ("", "{}")
    if first_run:
        icp.set_param(PARAM + "read_enabled", str(icp.get_param("td.base.environment") == "test"))
    if not icp.get_param(PARAM + "shift_calendar_id"):
        calendar = env["resource.calendar"].search([("name", "=", SHIFT_CALENDAR_NAME)], limit=1)
        calendar = calendar or env.company.resource_calendar_id
        if calendar:
            icp.set_param(PARAM + "shift_calendar_id", str(calendar.id))


def derived_source(env, report):
    _step("2 derived_source")
    _, created = _upsert(
        env,
        "td.source",
        DERIVED_CODE,
        {
            "name": "Енергетика: обчислені показники",
            "type": "f3d_energy",
            "collector_id": False,
            "params": {},
            "module": "energy",
            "read_enabled": _bool_param(env, "read_enabled"),
        },
        xmlid="source_en_derived",
    )
    report["derived_source"] = {"created": int(created)}


def pools(env, report):
    _step("3 pools")
    wc_missing = 0
    rows = _rows("energy_pools.csv")
    for row in rows:
        codes = [c for c in (row["workcenters"] or "").split(";") if c]
        workcenters = env["mrp.workcenter"]
        for code in codes:
            found = env["mrp.workcenter"].search_f3d(code)
            if found:
                workcenters |= found
            else:
                wc_missing += 1
                _logger.warning("td_energy: пул %s: немає робочого центру %s", row["code"], code)
        _upsert(
            env,
            "td.energy.pool",
            row["code"],
            {
                "name": row["name"],
                "sequence": int(row["sequence"] or 10),
                "driver": row["driver"],
                "workcenter_ids": [Command.set(workcenters.ids)],
            },
        )
    report["pools"] = len(rows)
    report["wc_missing"] = wc_missing


def _depth(code, parents, seen=()):
    parent = parents.get(code)
    if not parent or parent not in parents or parent in seen:
        return 0
    return 1 + _depth(parent, parents, seen + (code,))


def nodes(env, report):
    _step("4 nodes")
    Node = env["td.energy.node"].with_context(active_test=False)
    rows = _rows("energy_nodes.csv")
    parents = {r["code"]: r["parent"] for r in rows}
    ordered = sorted(rows, key=lambda r: _depth(r["code"], parents))  # предки — першими (обмеження: батько)
    by_code = {}
    stats = {"equipment_linked": 0, "workcenter_linked": 0, "unmatched_equipment": 0, "direct_without_wc": 0}
    for row in ordered:
        rec = Node.search([("code", "=", row["code"])], limit=1)
        vals = {f: row[f] for f in NODE_STR if row[f]}
        vals.update({v: int(row[k]) for k, v in NODE_INT.items() if row[k]})
        vals.update({v: float(row[k]) for k, v in NODE_FLOAT.items() if row[k]})
        vals["is_critical"] = row["is_critical"] in ("1", "True", "true")
        if row["equipment"]:
            equipment = env["maintenance.equipment"].search_f3d(row["equipment"])
            if equipment:
                vals["equipment_id"] = equipment.id
                stats["equipment_linked"] += 1
            else:
                stats["unmatched_equipment"] += 1
        workcenter = env["mrp.workcenter"].search_f3d(row["workcenter"]) if row["workcenter"] else None
        if workcenter:
            vals["workcenter_id"] = workcenter.id
            stats["workcenter_linked"] += 1
        has_wc = bool(workcenter) or bool(rec.workcenter_id)
        if vals.get("alloc_role") == "direct" and not has_wc:
            vals["alloc_role"] = "none"
            stats["direct_without_wc"] += 1
            _logger.warning("td_energy: вузол %s: прямий споживач без робочого центру", row["code"])
        if row["pool"]:
            pool = env["td.energy.pool"].search([("code", "=", row["pool"])], limit=1)
            if pool:
                vals["pool_id"] = pool.id
        if row["parent"] and by_code.get(row["parent"]):
            vals["parent_id"] = by_code[row["parent"]].id
        if rec:
            rec.write(vals)
        else:
            rec = Node.create(dict(vals, code=row["code"]))
        by_code[row["code"]] = rec
    for row in rows:  # прохід 2: посилання вперед
        rec = by_code[row["code"]]
        vals = {}
        for column, field in (("parent", "parent_id"), ("cabinet", "cabinet_id"), ("peer", "peer_id")):
            target = by_code.get(row[column]) if row[column] else None
            if target and rec[field] != target:
                vals[field] = target.id
        if vals:
            rec.write(vals)
    report["nodes"] = len(rows)
    report["critical"] = Node.search_count([("is_critical", "=", True)])
    report.update(stats)


def _source_vals(env, row, collector, read_enabled):
    equipment = env["maintenance.equipment"].search_f3d(row["equipment"]) if row["equipment"] else None
    return {
        "name": row["name"],
        "type": "modbus_tcp",
        "collector_id": collector.id,
        "params": {
            "host": row["host"],
            "port": int(row["port"]),
            "unit": int(row["unit"]),
            "timeout_s": int(row["timeout_s"]),
            "retries": int(row["retries"]),
            "max_block": int(row["max_block"]),
            "gap_max": int(row["gap_max"]),
        },
        "module": "energy",
        "equipment_id": equipment.id if equipment else False,
        "read_enabled": read_enabled,
        "write_enabled": False,
    }


def sources(env, report):
    _step("5 sources")
    collector = env.ref("td_telemetry.collector_main")
    read_enabled = _bool_param(env, "read_enabled")
    rows = _rows("energy_sources.csv")
    for row in rows:
        _upsert(
            env, "td.source", row["code"], _source_vals(env, row, collector, read_enabled),
            xmlid="source_" + _slug(row["code"]),
        )  # fmt: skip
    report["sources"] = len(rows)


def _json(text):
    return json.loads(text) if text else None


def _signal_vals(env, row, sources_by_code, thresholds_only=False):
    vals = {}
    for field in THRESHOLDS:
        if row[field] != "":
            vals[field] = float(row[field])
            vals[field + "_on"] = True
        elif not thresholds_only:
            vals[field + "_on"] = False
    for col, field in (("alarm_title", "alarm_title"), ("hysteresis", "hysteresis"),
                       ("min_duration_s", "min_duration_s")):  # fmt: skip
        if row[col] != "":
            vals[field] = (
                float(row[col]) if field == "hysteresis" else (int(row[col]) if field == "min_duration_s" else row[col])
            )
    if thresholds_only:
        return vals
    equipment = env["maintenance.equipment"].search_f3d(row["equipment"]) if row["equipment"] else None
    vals.update(
        {
            "kind": row["kind"],
            "unit": row["unit"] or False,
            "equipment_id": equipment.id if equipment else False,
            "source_id": sources_by_code[row["source"]].id if row["source"] else False,
            "address": _json(row["address"]) or {},
            "period_s": int(row["period_s"]),
            "store_period_s": int(row["store_period_s"]),
            "decimals": int(row["decimals"]),
            "states": _json(row["states"]) or False,
            "alarm_states": _json(row["alarm_states"]) or False,
            "viewer_visible": row["viewer_visible"] in ("1", "True", "true"),
            "module": "energy",
            "active": True,
        }
    )
    return vals


def signals(env, report):
    _step("6 signals")
    Signal = env["td.signal"].with_context(active_test=False)
    sources_by_code = {s.code: s for s in env["td.source"].with_context(active_test=False).search([])}
    rows = _rows("energy_signals.csv")
    existing = {s.code: s for s in Signal.search([("code", "in", [r["code"] for r in rows])])}
    created = updated = thresholds = 0
    to_create = []
    for row in rows:
        rec = existing.get(row["code"])
        if rec and row["binding"] == "thresholds":
            rec.write(_signal_vals(env, row, sources_by_code, thresholds_only=True))
            thresholds += 1
            updated += 1
        elif rec:
            rec.write(_signal_vals(env, row, sources_by_code))
            updated += 1
        else:
            vals = _signal_vals(env, row, sources_by_code)
            vals.update(code=row["code"], name=row["name"], quantity=row["quantity"])
            # DEC-3: origin з CSV `sim_data` створюємо як `catalog` (рівень 0 не мігрований)
            vals["origin"] = "catalog" if row["origin"] == "sim_data" else row["origin"]
            to_create.append(vals)
    for rec in Signal.create(to_create):
        _ensure_xmlid(env, "sig_" + _slug(rec.code), rec)
        existing[rec.code] = rec
        created += 1
    for row in rows:  # другий прохід: похідні сигнали
        if row["derived_from"] and row["derived_from"] in existing:
            rec = existing[row["code"]]
            vals = {"derived_from_id": existing[row["derived_from"]].id}
            if row["code"].startswith("energy/consumers/") and row["code"].endswith("/kwh_shift"):
                vals["source_id"] = sources_by_code[DERIVED_CODE].id
                vals["derive_rule"] = "none"
            rec.write(vals)
    report["signals"] = {
        "created": created,
        "updated": updated,
        "thresholds": thresholds,
        "module_energy": Signal.search_count([("module", "=", "energy")]),
    }


def _max_kw(row, node):
    """Додаток D.1: PM5560 ввід/фідер — `ceil(I_ном·0,4·√3)`, споживач — `max(10, ceil(2·P_вст))`."""
    if row["model"] in FIXED_MAX_KW:
        return float(FIXED_MAX_KW[row["model"]])
    if row["role"] == "consumer":
        return float(max(10, math.ceil(2 * node.p_inst_kw - 1e-9)))
    return float(math.ceil(node.rating_a * 0.4 * math.sqrt(3) - 1e-9)) or 10.0


def meters(env, report):
    _step("7 meters")
    rows = _rows("energy_meters.csv")
    Signal = env["td.signal"].with_context(active_test=False)

    def sig(code):
        return Signal.search([("code", "=", code)], limit=1).id if code else False

    for row in rows:
        node = env["td.energy.node"].search([("code", "=", row["node"])], limit=1)
        source = env["td.source"].with_context(active_test=False).search([("code", "=", row["source"])], limit=1)
        _upsert(
            env,
            "td.energy.meter",
            row["code"],
            {
                "name": row["name"],
                "node_id": node.id,
                "model": row["model"],
                "role": row["role"],
                "source_id": source.id,
                "p_signal_id": sig(row["p_signal"]),
                "e_import_signal_id": sig(row["e_import_signal"]),
                "e_export_signal_id": sig(row["e_export_signal"]),
                "ct_ratio": row["ct_ratio"] or False,
                "max_kw": _max_kw(row, node),
            },
        )
    report["meters"] = len(rows)


def contract(env, report):
    _step("8 contract")
    Tariff = env["td.energy.tariff"]
    for company in env["res.company"].search([]):
        Tariff._f3d_tariff_at(fields.Datetime.now(), company)._f3d_apply_contract_thresholds()


# --- W1 (A-24, A-27): схема Пульту, сигнали контролера ГРЩ, пороги cos φ ---------------------------------------
W1_SIGNAL_PREFIXES = ("energy/cells/QS/", "energy/cells/PFC-", "energy/sections/")
W1_SOURCE = "MB-U73-SWB-CTRL"


def _ensure_w1_signals(env):
    """W1_SPEC 5.3: ідемпотентно створює відсутні W1-сигнали й джерело `MB-U73-SWB-CTRL`; існуючі не змінює."""
    env = env(su=True, context=dict(env.context, tracking_disable=True, f3d_energy_internal=True))
    Source = env["td.source"].with_context(active_test=False)
    Signal = env["td.signal"].with_context(active_test=False)
    created = {"sources": 0, "signals": 0}
    collector = env.ref("td_telemetry.collector_main", raise_if_not_found=False)
    if collector:
        read_enabled = _bool_param(env, "read_enabled")
        for row in _rows("energy_sources.csv"):
            if row["code"] == W1_SOURCE and not Source.search_count([("code", "=", W1_SOURCE)]):
                _upsert(
                    env, "td.source", row["code"], _source_vals(env, row, collector, read_enabled),
                    xmlid="source_" + _slug(row["code"]),
                )  # fmt: skip
                created["sources"] += 1
    sources_by_code = {s.code: s for s in Source.search([])}
    rows = [r for r in _rows("energy_signals.csv") if r["code"].startswith(W1_SIGNAL_PREFIXES)]
    have = set(Signal.search([("code", "in", [r["code"] for r in rows])]).mapped("code"))
    for row in rows:
        if row["code"] in have:
            continue
        vals = _signal_vals(env, row, sources_by_code)
        vals.update(code=row["code"], name=row["name"], quantity=row["quantity"])
        vals["origin"] = "catalog" if row["origin"] == "sim_data" else row["origin"]
        _ensure_xmlid(env, "sig_" + _slug(row["code"]), Signal.create(vals))
        created["signals"] += 1
    return created


def _load_sld_layout(env):
    """W1_SPEC 5.2: геометрія схеми Пульту з `data/sld_layout.csv`; правки користувача не перезаписуються."""
    env = env(su=True, context=dict(env.context, tracking_disable=True))
    Node = env["td.energy.node"].with_context(active_test=False)
    rows = _rows("sld_layout.csv")
    wanted = {r["code"] for r in rows} | {r["anchor"] for r in rows if r["anchor"]}
    by_code = {n.code: n for n in Node.search([("code", "in", sorted(wanted))])}
    stats = {"loaded": 0, "kept": 0, "missing": 0}
    for row in rows:
        node = by_code.get(row["code"])
        if not node:
            _logger.warning("td_energy: схема Пульту: немає вузла %s", row["code"])
            stats["missing"] += 1
            continue
        if node.sld_show or node.sld_x or node.sld_y:
            stats["kept"] += 1
            continue
        anchor = by_code.get(row["anchor"]) if row["anchor"] else None
        node.write(
            {
                "sld_show": True,
                "sld_shape": row["shape"],
                "sld_x": int(row["x"]),
                "sld_y": int(row["y"]),
                "sld_w": int(row["w"]),
                "sld_h": int(row["h"]),
                "sld_label": row["label"] or False,
                "sld_anchor_id": anchor.id if anchor else False,
            }
        )
        stats["loaded"] += 1
    return stats


def sld_layout(env, report):
    _step("10 sld_layout")
    report["sld"] = _load_sld_layout(env)


def cos_thresholds(env, report):
    _step("11 cos_thresholds")
    env["res.config.settings"]._td_apply_cos_thresholds()


EVENT_BATCH = 5000


def _migrate_events(env):
    """W1_SPEC 5.4 п. 4: `title`/`detail` за R-24 для подій без заголовка; `warn|bad → resolved`, `info → na`."""
    from .models.td_energy_event import split_text  # відкладено: models імпортується пакетом до hooks

    cr, total = env.cr, 0
    while True:
        cr.execute(
            "SELECT id, level, text FROM td_energy_event WHERE title IS NULL ORDER BY id LIMIT %s", (EVENT_BATCH,)
        )
        rows = cr.fetchall()
        if not rows:
            return total
        data = []
        for event_id, level, text in rows:
            title, detail = split_text(text)
            data.append((event_id, title, detail, "na" if level == "info" else "resolved"))
        cr.execute_values(
            """UPDATE td_energy_event e SET title = v.title, detail = v.detail, state = v.state,
                      resolved_at = CASE WHEN v.state = 'resolved' THEN e.ts END
                 FROM (VALUES %s) AS v(id, title, detail, state) WHERE e.id = v.id""",
            data,
            template="(%s::int, %s, %s, %s)",
            page_size=EVENT_BATCH,
        )
        total += len(rows)


def _migrate_w1(env):
    """Міграція 19.0.1.1.0 (5.4): сигнали й джерело, пороги cos φ, геометрія схеми, події. Ідемпотентна."""
    env = env(su=True, context=dict(env.context, tracking_disable=True, f3d_energy_internal=True))
    report = {"signals": _ensure_w1_signals(env)}
    env["res.config.settings"]._td_apply_cos_thresholds()
    report["sld"] = _load_sld_layout(env)
    report["events"] = _migrate_events(env)
    _logger.info("td_energy: міграція W1: %s", dump(report))
    return report


def finish(env, report):
    _step("9 report")
    partial = report.get("unmatched_equipment", 0) > 0 or report.get("direct_without_wc", 0) > 0
    report = dict(report, state="partial" if partial else "done", ts=fields.Datetime.to_string(fields.Datetime.now()))
    env["ir.config_parameter"].sudo().set_param(PARAM + "install_report", dump(report))
    return report


def run_bind(env):
    """Кроки §5.3 в одній транзакції; повертає звіт (`state`, `ts`, лічильники)."""
    env = env(su=True, context=dict(env.context, tracking_disable=True, f3d_energy_internal=True))
    report = {}
    for step in (params, derived_source, pools, nodes, sources, signals, meters, contract, sld_layout, cos_thresholds):
        step(env, report)
    return finish(env, report)


def post_init_hook(env):
    report = run_bind(env)
    _logger.info("td_energy: прив'язка даних: %s", dump(report))


def uninstall_hook(env):
    """§5.4: сигнали з CSV — без джерела; створені модулем — неактивні; джерела енергетики — неактивні."""
    env = env(su=True, context=dict(env.context, tracking_disable=True))
    codes = [r["code"] for r in _rows("energy_signals.csv")]
    Signal = env["td.signal"].with_context(active_test=False)
    signals_ = Signal.search([("code", "in", codes)])
    signals_.write({"source_id": False})
    created = env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "td.signal"),
                                            ("name", "=like", "sig\\_%")])  # fmt: skip
    ids = set(created.mapped("res_id"))
    signals_.filtered(lambda s: s.id in ids and s.origin in ("catalog", "module")).write({"active": False})
    env["td.source"].with_context(active_test=False).search([("module", "=", "energy")]).filtered(
        lambda s: s.type != "f3d_energy"
    ).write({"active": False})
    env["ir.config_parameter"].sudo().search([("key", "=like", PARAM + "%")]).unlink()
