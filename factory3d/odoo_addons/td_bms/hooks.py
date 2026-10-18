"""Хуки модуля «Будівля»: установка даних (SPEC §5.3, R-29), прапори запису (R-30), деінсталяція (§5.4).

`run_install(env) -> dict` — кроки 1…10; `post_init_hook` = `run_install`. Кроки ідемпотентні (повторний запуск
нічого не дублює). Відкат — винятком на будь-якому кроці.
"""

import csv
import io
import json
import logging
import math
import re
from collections import Counter

from odoo import fields
from odoo.tools import file_open

from .tools import rules

_logger = logging.getLogger(__name__)

P = "td.bms."
CSV_FILE = "td_bms/data/bms_signals.csv"
DERIVED_CODE = "BMS-DERIVED"
EXPECTED_SIGNALS = 549
CTX = {"active_test": False, "tracking_disable": True, "mail_create_nolog": True, "mail_notrack": True}

# R-30: джерела, що стають керованими разом із write_enabled
WRITE_SOURCE_CODES = (
    {"HN-LP-%d" % r for r in (1, 2, 3)} | {"BAC-%d-RV-%02d" % (100 + n, n) for n in range(1, 26)} | {"BAC-130-AHU-1"}
)

# поле моделі ← роль сигналу (колонка `role` CSV)
UNIT_ROLES = {
    "airflow": "airflow_signal_id",
    "supply": "supply_signal_id",
    "indoor": "indoor_signal_id",
    "filter": "filter_signal_id",
    "filter_extract": "filter_extract_signal_id",
    "valve": "valve_signal_id",
    "heat": "heat_signal_id",
    "power": "power_signal_id",
    "mode": "mode_signal_id",
    "state": "state_signal_id",
    "sp_day": "sp_day_signal_id",
    "sp_night": "sp_night_signal_id",
    "pressure": "pressure_signal_id",
    "interlock": "interlock_signal_id",
    "check": "check_signal_id",
}
GROUP_ROLES = {
    "level": "level_signal_id",
    "power": "power_signal_id",
    "scene": "scene_signal_id",
    "faults": "faults_signal_id",
    "faulty": "faulty_signal_id",
    "check": "check_signal_id",
}
PANEL_ROLES = {"state": "state_signal_id"}
BALANCE_ROLES = {
    "outdoor": "outdoor_signal_id",
    "boiler_state": "boiler_state_signal_id",
    "boiler_return": "boiler_return_signal_id",
    "boiler_heat": "boiler_heat_signal_id",
    "check": "check_signal_id",
}
# сигнали інших модулів: поле балансу ← код (обов'язкові telemetry, необов'язкові energy / fire_safety)
BALANCE_FIXED = {
    "boiler_supply_signal_id": "equipment/BOILER/supply_c",
    "silo_signal_id": "equipment/BOILER/silo_fill",
}
BALANCE_OPTIONAL = {
    "chp_heat_signal_id": "infra/chp/heat_kw",
    "chp_el_signal_id": "infra/totals/chp_kw",
    "mains_signal_id": "infra/ats/src1_ok",
    "fire_signal_id": "fire/totals/system_state",
}


# --- допоміжне -------------------------------------------------------------------------------------------
def _flag(value):
    return str(value).strip().lower() in ("1", "true", "yes", "так")


def _num(value):
    if value in (None, "", False):
        return None
    return float(str(value).replace(",", "."))


def _json(value):
    if value in (None, ""):
        return None
    return json.loads(value) if isinstance(value, str) else value


def _changed(rec, vals):
    """Лише значення, що відрізняються від поточних (щоб не писати зайвого й не чіпати статус)."""
    diff = {}
    for key, value in vals.items():
        current = rec[key]
        if hasattr(current, "ids"):
            current = current.id or False
        if isinstance(value, float) and isinstance(current, (int, float)):
            same = math.isclose(current, value, rel_tol=0, abs_tol=1e-9)
        elif isinstance(value, (dict, list)):
            same = (current or type(value)()) == value
        else:
            same = (current or False) == (value or False)
        if not same:
            diff[key] = value
    return diff


def _slug(code):
    return re.sub(r"[^0-9A-Za-z]+", "_", code).strip("_").lower()


def _signals(env):
    return env["td.signal"].sudo().with_context(**CTX)


def _sources(env):
    return env["td.source"].sudo().with_context(**CTX)


def _csv_rows():
    with file_open(CSV_FILE, "rb") as raw:
        text = raw.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def _read_param(env):
    return env["ir.config_parameter"].sudo().get_param(P + "read_enabled", "False") in ("True", "true", "1")


def _write_param(env):
    return env["ir.config_parameter"].sudo().get_param(P + "write_enabled", "False") in ("True", "true", "1")


# --- крок 1 ----------------------------------------------------------------------------------------------
def params(env):
    """`read_enabled = (td.base.environment == 'test')`, `write_enabled = False` (CB-10)."""
    icp = env["ir.config_parameter"].sudo()
    read = icp.get_param("td.base.environment") == "test"
    icp.set_param(P + "read_enabled", "True" if read else "False")
    icp.set_param(P + "write_enabled", "False")
    return {"read_enabled": read}


# --- крок 2 ----------------------------------------------------------------------------------------------
def derived_source(env):
    """Джерело `BMS-DERIVED` (M-12) з xml-id `td_bms.source_bms_derived`; upsert за `code`."""
    Source = _sources(env)
    vals = {
        "name": "Будівля: обчислені перевірки",
        "type": "f3d_bms",
        "collector_id": False,
        "params": {},
        "module": "bms",
        "period_s_default": 60,
    }
    src = Source.search([("code", "=", DERIVED_CODE)], limit=1)
    created = 0
    if src:
        diff = _changed(src, vals)
        if diff:
            src.write(diff)
    else:
        src = Source.create({**vals, "code": DERIVED_CODE, "read_enabled": _read_param(env), "write_enabled": False})
        created = 1
    env["ir.model.data"]._update_xmlids(
        [{"xml_id": "td_bms.source_bms_derived", "record": src, "noupdate": True}]
    )
    return {"created": created}


# --- крок 3 ----------------------------------------------------------------------------------------------
def _source_equipment_code(code):
    m = re.match(r"^BAC-\d+-(.+)$", code)
    if m:
        return m.group(1)
    m = re.match(r"^HN-(LP-\d+)$", code)
    return m.group(1) if m else None


def link_equipment(env):
    """`equipment_id` для щитів, груп, установок, балансу й джерел модуля (лише порожні)."""
    env = env(su=True)
    Equipment = env["maintenance.equipment"].sudo()
    stats = Counter(panels=0, groups=0, units=0, balance=0, sources=0, not_found=0)

    def link(records, key, field="equipment_id"):
        for rec in records.filtered(lambda r: not r[field]):
            eq = Equipment.search_f3d(rec.code)
            if eq:
                rec.write({field: eq.id})
                stats[key] += 1
            else:
                stats["not_found"] += 1
                _logger.warning("link_equipment: обладнання %s не знайдено", rec.code)

    ctx = {"active_test": False, "tracking_disable": True}
    link(env["td.bms.light.panel"].with_context(**ctx).search([]), "panels")
    link(env["td.bms.light.group"].with_context(**ctx).search([]), "groups")
    link(env["td.bms.hvac.unit"].with_context(**ctx).search([]), "units")
    for balance in env["td.bms.heat.balance"].with_context(**ctx).search([]):
        for field, code in (("boiler_equipment_id", "BOILER"), ("chp_equipment_id", "CHP")):
            if balance[field]:
                continue
            eq = Equipment.search_f3d(code)
            if eq:
                balance.write({field: eq.id})
                stats["balance"] += 1
            else:
                stats["not_found"] += 1
                _logger.warning("link_equipment: обладнання %s не знайдено", code)
    for src in _sources(env).search([("module", "=", "bms"), ("code", "!=", DERIVED_CODE)]):
        if src.equipment_id:
            continue
        code = _source_equipment_code(src.code)
        eq = Equipment.search_f3d(code) if code else Equipment
        if eq:
            src.write({"equipment_id": eq.id})
            stats["sources"] += 1
        else:
            _logger.warning("link_equipment: обладнання %s для джерела %s не знайдено", code, src.code)
    report = dict(stats)
    _logger.info("link_equipment: %s", report)
    return report


# --- крок 4 ----------------------------------------------------------------------------------------------
def _binding_vals(row, source):
    """Поля прив'язки рядка CSV; пороги й заголовок — лише з непорожніх колонок."""
    vals = {"module": "bms", "active": True}
    if source:
        vals["source_id"] = source.id
    address = _json(row.get("address"))
    if address is not None:
        vals["address"] = address
    for col in ("period_s", "store_period_s", "decimals", "min_duration_s"):
        if _num(row.get(col)) is not None:
            vals[col] = int(_num(row[col]))
    if _num(row.get("scale")) is not None:
        vals["scale"] = _num(row["scale"])
    if row.get("viewer_visible") not in (None, ""):
        vals["viewer_visible"] = _flag(row["viewer_visible"])
    if _num(row.get("hysteresis")) is not None:
        vals["hysteresis"] = _num(row["hysteresis"])
    for col in ("alarm_low", "alarm_high", "warn_high"):
        if _num(row.get(col)) is not None:
            vals[col] = _num(row[col])
            vals[col + "_on"] = True
    if row.get("alarm_title"):
        vals["alarm_title"] = row["alarm_title"]
    return vals


def _definition_vals(row):
    """Визначення сигналу (без `last_*`, `status`, `origin`)."""
    vals = {"name": row["name"], "kind": row.get("kind") or "gauge"}
    for col in ("quantity", "unit"):
        vals[col] = row.get(col) or False
    for col in ("states", "alarm_states"):
        value = _json(row.get(col))
        if value is not None:
            vals[col] = value
    if row.get("create_request") not in (None, ""):
        vals["create_request"] = _flag(row["create_request"])
    return vals


def signals(env):
    """CSV → `td.signal`: прив'язка `new=0`, створення відсутніх, оновлення визначень `new=1`."""
    env = env(su=True)
    Signal = _signals(env)
    Equipment = env["maintenance.equipment"].sudo()
    rows = _csv_rows()
    sources = {
        s.code: s for s in _sources(env).search([("code", "in", sorted({r["source"] for r in rows if r["source"]}))])
    }
    existing = {s.code: s for s in Signal.search([("code", "in", [r["code"] for r in rows])])}
    equipment_cache = {}

    def find_equipment(code):
        if code not in equipment_cache:
            equipment_cache[code] = Equipment.search_f3d(code) if code else Equipment
        return equipment_cache[code]

    stats = Counter(created=0, updated=0, no_equipment=0)
    to_create = []
    for row in rows:
        code = row["code"]
        source = sources.get(row["source"])
        if row["source"] and not source:
            _logger.warning("signals: джерело %s для %s не знайдено", row["source"], code)
        vals = _binding_vals(row, source)
        sig = existing.get(code)
        eq = False
        if row.get("equipment") and (not sig or not sig.equipment_id):
            found = find_equipment(row["equipment"])
            if found:
                eq = found.id
            else:
                stats["no_equipment"] += 1
        if eq:
            vals["equipment_id"] = eq
        if sig:
            if _flag(row.get("new")):
                vals.update(_definition_vals(row))
            diff = _changed(sig, vals)
            if diff:
                sig.write(diff)
            stats["updated"] += 1
        else:
            to_create.append(
                {
                    **_definition_vals(row),
                    **vals,
                    "code": code,
                    # DEC-7: `sim_data` з CSV створюємо як `catalog` — інакше verify() міграції telemetry
                    # (рівень 0) рахує їх як перенесені з x_f3d_signal і лишає міграцію `partial`
                    "origin": "catalog" if row.get("origin") == "sim_data" else (row.get("origin") or "module"),
                    "write_enabled": False,
                }
            )
    if to_create:
        created = Signal.create(to_create)
        env["ir.model.data"]._update_xmlids(
            [{"xml_id": "td_bms.sig_" + _slug(sig.code), "record": sig, "noupdate": True} for sig in created]
        )
        stats["created"] = len(created)
    report = dict(stats)
    _logger.info("signals: %s", report)
    return report


# --- крок 5 ----------------------------------------------------------------------------------------------
def link_signals(env):
    """Поля `*_signal_id` моделей модуля за `(object, role)` CSV й явні сигнали балансу."""
    env = env(su=True)
    Signal = _signals(env)
    ctx = {"active_test": False, "tracking_disable": True}
    targets = {}
    for model, roles in (
        ("td.bms.hvac.unit", UNIT_ROLES),
        ("td.bms.light.group", GROUP_ROLES),
        ("td.bms.light.panel", PANEL_ROLES),
    ):
        for rec in env[model].with_context(**ctx).search([]):
            targets[rec.code] = (rec, roles)
    balance = env["td.bms.heat.balance"].with_context(**ctx).search([], limit=1)
    if balance:
        targets["BALANCE"] = (balance, BALANCE_ROLES)
    rows = _csv_rows()
    sigs = {
        s.code: s
        for s in Signal.search(
            [("code", "in", [r["code"] for r in rows] + list(BALANCE_FIXED.values()) + list(BALANCE_OPTIONAL.values()))]
        )
    }
    values = {}
    links = 0
    for row in rows:
        target = targets.get(row["object"])
        sig = sigs.get(row["code"])
        if not target or not sig:
            continue
        field = target[1].get(row["role"])
        if field:
            values.setdefault(row["object"], {})[field] = sig.id
            links += 1
    optional_missing = []
    for field, code in BALANCE_FIXED.items():
        sig = sigs.get(code)
        if sig and balance:
            values.setdefault("BALANCE", {})[field] = sig.id
            links += 1
        else:
            _logger.warning("link_signals: сигнал %s не знайдено", code)
    for field, code in BALANCE_OPTIONAL.items():
        sig = sigs.get(code)
        if sig and balance:
            values.setdefault("BALANCE", {})[field] = sig.id
            links += 1
        else:
            optional_missing.append(code)
    for key, vals in values.items():
        rec = targets[key][0]
        diff = _changed(rec, vals)
        if diff:
            rec.write(diff)
    report = {"links": links, "optional_missing": optional_missing}
    _logger.info("link_signals: %s", report)
    return report


# --- кроки 6, 7 ------------------------------------------------------------------------------------------
def read_flags(env, enabled=None):
    """Джерела модуля (32 + `BMS-DERIVED`): `read_enabled` = параметр (R-29 п. 8)."""
    env = env(su=True)
    if enabled is None:
        enabled = _read_param(env)
    sources = _sources(env).search([("module", "=", "bms")])
    todo = sources.filtered(lambda s: s.read_enabled != enabled)
    if todo:
        todo.write({"read_enabled": enabled})
    return {"sources_read": len(sources)}


def write_flags(env, enabled=None):
    """R-30 (A-21): `enabled` → 29 джерел і 142 сигнали `writable=1` мають `write_enabled=True`; інакше все `False`,
    відкриті команди модуля в `queued` → `cancelled`."""
    env = env(su=True)
    if enabled is None:
        enabled = _write_param(env)
    writable = {r["code"] for r in _csv_rows() if _flag(r.get("writable"))}
    Signal = _signals(env)
    signals_ = Signal.search([("module", "=", "bms")])
    want = lambda s: bool(enabled and s.code in writable)  # noqa: E731
    on, off = (
        signals_.filtered(lambda s: want(s) and not s.write_enabled),
        signals_.filtered(lambda s: not want(s) and s.write_enabled),
    )
    if off:
        off.write({"write_enabled": False})
    sources = _sources(env).search([("module", "=", "bms")])
    for src in sources:
        target = bool(enabled and src.code in WRITE_SOURCE_CODES)
        if src.write_enabled != target:
            src.write({"write_enabled": target})
    if on:
        on.write({"write_enabled": True})
    cancelled = 0
    if not enabled and "td.command" in env:
        queued = env["td.command"].sudo().search([("signal_id.module", "=", "bms"), ("state", "=", "queued")])
        if queued:
            queued.action_cancel()
            cancelled = len(queued)
    report = {
        "signals_write": len(Signal.search([("module", "=", "bms"), ("write_enabled", "=", True)])),
        "sources_write": len(sources.filtered("write_enabled")),
        "commands_cancelled": cancelled,
    }
    _logger.info("write_flags: %s", report)
    return report


# --- крок 8 ----------------------------------------------------------------------------------------------
def recompute(env):
    balance = env(su=True)["td.bms.heat.balance"]._f3d_bms_get()
    balance.action_recompute()
    return {"total_kw": balance.total_kw}


# --- крок 9 ----------------------------------------------------------------------------------------------
def _deviation_meta(code, text=None):
    """(rule, object_kind, object_code) за кодом сигналу (R-22)."""
    kind, obj = rules.object_of(code)
    return rules.rule_of(code, text), kind or False, obj or False


def demo_request(env):
    """Епізод журналу `open` для відкритих заявок на сигналах модуля у стані `alarm` (демо-дані base/telemetry)."""
    env = env(su=True)
    if "td.bms.deviation" not in env:
        return {"deviations": 0}
    Deviation = env["td.bms.deviation"].with_context(tracking_disable=True)
    requests = env["maintenance.request"].search(
        [("td_signal_id.module", "=", "bms"), ("td_signal_id.status", "=", "alarm"), ("stage_id.done", "=", False)]
    )
    created = 0
    for req in requests:
        sig = req.td_signal_id
        if Deviation.search_count([("signal_id", "=", sig.id), ("state", "=", "open")]):
            continue
        rule, kind, obj = _deviation_meta(sig.code, sig.last_text)
        Deviation.create(
            {
                "name": req.name,
                "signal_id": sig.id,
                "rule": rule,
                "object_kind": kind,
                "object_code": obj,
                "started": req.create_date,
                "state": "open",
                "value": req.td_value,
                "threshold": req.td_threshold,
                "unit": sig.unit or False,
                "request_id": req.id,
            }
        )
        created += 1
    return {"deviations": created}


# --- крок 10 ---------------------------------------------------------------------------------------------
def report(env, data):
    """`install_report` = JSON звіту; `state=partial`, якщо є ненайдене обладнання або неповні сигнали."""
    complete = (data.get("created", 0) + data.get("updated", 0)) >= EXPECTED_SIGNALS
    data["state"] = "partial" if data.get("not_found", 0) > 0 or not complete else "done"
    data["ts"] = fields.Datetime.now().isoformat()
    env["ir.config_parameter"].sudo().set_param(P + "install_report", json.dumps(data, ensure_ascii=False, default=str))
    return data


def run_install(env):
    """Кроки 1…10 (§5.3); ідемпотентно. Повертає звіт: плоскі лічильники кроків + `steps` (по кроках)."""
    env = env(su=True)
    steps = {}
    steps["params"] = params(env)
    steps["derived_source"] = derived_source(env)
    steps["link_equipment"] = link_equipment(env)
    steps["signals"] = signals(env)
    steps["link_signals"] = link_signals(env)
    steps["read_flags"] = read_flags(env)
    steps["write_flags"] = write_flags(env, enabled=False)
    steps["recompute"] = recompute(env)
    steps["demo_request"] = demo_request(env)
    data = {}
    for name, res in steps.items():
        for key, value in res.items():
            data["derived_created" if name == "derived_source" else key] = value
    data["steps"] = steps
    data = report(env, data)
    _logger.info(
        "run_install: state=%s created=%s updated=%s not_found=%s",
        data["state"],
        data.get("created"),
        data.get("updated"),
        data.get("not_found"),
    )
    return data


def post_init_hook(env):
    run_install(env)


# --- деінсталяція (§5.4) ---------------------------------------------------------------------------------
def uninstall_hook(env):
    """Параметри, сигнали модуля (історія й заявки лишаються), відкриті команди."""
    env = env(su=True)
    env["ir.config_parameter"].sudo().search([("key", "=like", P + "%")]).unlink()
    Signal = _signals(env)
    module_signals = Signal.search([("module", "=", "bms")])
    # xml-id сигналів прибираємо, щоб видалення модуля не знищило сигнали з історією показань
    env["ir.model.data"].sudo().search([("module", "=", "td_bms"), ("model", "=", "td.signal")]).unlink()
    owned = module_signals.filtered(lambda s: s.origin in ("catalog", "module"))
    sim = module_signals.filtered(lambda s: s.origin == "sim_data")
    if "td.command" in env:
        queued = env["td.command"].sudo().search([("signal_id", "in", module_signals.ids), ("state", "=", "queued")])
        if queued:
            queued.action_cancel()
    if owned:
        owned.write({"write_enabled": False})
        owned.write({"active": False, "source_id": False})
    if sim:
        sim.write({"write_enabled": False})
        sim.write({"source_id": False, "address": {}})
    _logger.info("uninstall_hook: сигналів вимкнено %s, відв'язано %s", len(owned), len(sim))
