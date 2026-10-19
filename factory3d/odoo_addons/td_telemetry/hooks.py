"""Хуки модуля: міграція рівня 0 td_iot_sim → td.* (SPEC §5.3–§5.5), деінсталяція (§5.4).

`run_migration(env) -> dict` — кроки 1…11; `post_init_hook` = `run_migration` + розклад ротації.
Кроки 2, 5, 6, 9, 10 потребують моделей рівня 0 (`x_f3d_signal`, `x_f3d_reading`) і без них пропускаються.
"""

import csv
import io
import json
import logging
import math
import re
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.tools import file_open

from .models.td_reading_hour import AGGREGATE_SQL
from .tools import sim_catalog as simcat

_logger = logging.getLogger(__name__)

P = "td.telemetry."
KYIV = ZoneInfo("Europe/Kyiv")
IOT = "td_iot_sim."
TEAM_NAME = "Служба головного механіка"
READINGS_BATCH = 5000
CATALOG_FILE = "td_telemetry/data/signal_catalog.csv"

# Додаток C.3: ключ джерела з адреси → код джерела
SOURCE_MAP = {
    "mqtt": "MQTT-MOBILE",
    "u70": "MB-U70-COMPRESSOR",
    "u84": "MB-U84-IO5",
    "u90": "MB-U90-AI1",
    "u96": "MB-U96-RTD1",
    "dev140": "BAC-140-BOILER",
    "http:lpr": "HTTP-PUSH",
}
# Додаток C.1: головне обладнання джерела (ставиться, якщо порожнє)
SOURCE_EQUIPMENT = {"MB-U70-COMPRESSOR": "COMPRESSOR", "BAC-140-BOILER": "BOILER"}
# Додаток C.4: (обладнання, сигнал, інтервал, значення останнього ТО або None = floor(last_value / інтервал))
MOBILE = ["FL-1", "FL-2", "FL-3", "FL-4", "FL-5", "FL-C1", "FL-C2", "TUGGER-1"]
METERS = [("COMPRESSOR", "equipment/COMPRESSOR/hours", 2000.0, 16000.0)] + [
    (c, "equipment/%s/hours" % c, 1000.0, None) for c in MOBILE
]
# Представлення, меню й дії рівня 0 (xml-id `td_iot_sim.*`)
LEVEL0_VIEWS = [
    "view_signal_list",
    "view_signal_form",
    "view_signal_search",
    "view_reading_list",
    "view_reading_graph",
    "view_reading_search",
    "view_equipment_form_signals",
]
LEVEL0_MENUS = [
    "menu_iot_tick",
    "menu_iot_start",
    "menu_iot_stop",
    "menu_iot_signals",
    "menu_iot_readings",
    "menu_iot_root",
]
LEVEL0_ACTIONS = ["action_signals", "action_readings"]

ALARM_TITLES = {
    ("Перепад", "above"): "Заміна фільтрів: перепад тиску {value} {unit} при нормі до {threshold}",
    ("Запиленість", "above"): "Очистити сповіщувач: запиленість {value} % при нормі до {threshold}",
    ("Тиск", "below"): "{equipment}: тиск {value} бар при нормі від {threshold}",
    ("Температура", "above"): "{equipment}: температура {value} °C при нормі до {threshold}",
    ("Вакуум", "above"): "Портал: вакуум {value} кПа при нормі нижче {threshold}",
}
DEFINITION_ONLY = ("last_value", "last_ts", "last_quality", "last_stored_ts", "status", "status_since")
SIGNAL_CTX = {"active_test": False, "tracking_disable": True, "mail_create_nolog": True, "mail_notrack": True}
XFIELDS = (
    "x_code",
    "x_name",
    "x_sequence",
    "x_equipment_id",
    "x_workcenter_id",
    "x_source_id",
    "x_kind",
    "x_unit",
    "x_mode",
    "x_value",
    "x_nominal",
    "x_noise",
    "x_rate",
    "x_limit",
    "x_seed",
    "x_alarm",
    "x_threshold",
    "x_state",
    "x_charging",
    "x_updated",
    "x_request_id",
)


# --- допоміжне -----------------------------------------------------------------------------------------
def _slug(code):
    return re.sub(r"[^0-9A-Za-z]+", "_", code).strip("_").lower()


def _signals(env):
    return env["td.signal"].sudo().with_context(**SIGNAL_CTX)


def _changed(rec, vals):
    """Лише ті значення, що відрізняються від поточних (щоб не писати зайвого й не чіпати статус)."""
    diff = {}
    for key, value in vals.items():
        current = rec[key]
        if hasattr(current, "ids"):
            current = current.id or False
        if isinstance(value, float) and isinstance(current, (int, float)):
            same = math.isclose(current, value, rel_tol=0, abs_tol=1e-9)
        else:
            same = (current or False) == (value or False)
        if not same:
            diff[key] = value
    return diff


def _m2o(value):
    return value.id if value else False


def _num(value):
    if value in (None, "", False):
        return None
    return float(str(value).replace(",", "."))


def _json(value):
    if value in (None, ""):
        return None
    return json.loads(value) if isinstance(value, str) else value


def _flag(value):
    return str(value).strip().lower() in ("1", "true", "yes", "так")


def _level0(env):
    return "x_f3d_signal" in env


def _ref(env, name):
    return env.ref(IOT + name, raise_if_not_found=False)


def _decimals(unit):
    if unit in ("Па", "%", "шт"):
        return 0
    if unit in ("кВт·год", "год"):
        return 1
    return 2


def _read_catalog_file():
    with file_open(CATALOG_FILE, "rb") as raw:
        return list(csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline="")))


def _catalog_rows(env):
    """Рядки `data/signal_catalog.csv` (єдина точка читання; у тестах підміняється)."""
    return _read_catalog_file()


# --- крок 1 --------------------------------------------------------------------------------------------
def params(env):
    """CB-10: `read_enabled` за середовищем; `default_team_id` — «Служба головного механіка» або перша команда."""
    icp = env["ir.config_parameter"].sudo()
    read = "True" if icp.get_param("td.base.environment") == "test" else "False"
    icp.set_param(P + "read_enabled", read)
    current = icp.get_param(P + "default_team_id") or ""
    Team = env["maintenance.team"].sudo()
    team = Team.browse(int(current)).exists() if current.isdigit() else Team
    if not team:
        team = Team.search([("name", "=", TEAM_NAME)], limit=1) or Team.search([], order="id", limit=1)
        icp.set_param(P + "default_team_id", str(team.id) if team else "")
    _logger.info("params: read_enabled=%s, default_team_id=%s", read, team.id or "")
    return {"read_enabled": read, "default_team_id": team.id or False}


# --- крок 2 --------------------------------------------------------------------------------------------
def _level0_vals(x):
    """R-15 + Додаток D: `vals` td.signal за записом `x_f3d_signal`."""
    get = lambda name: x[name] if name in x._fields else False  # noqa: E731
    mode, alarm, threshold = get("x_mode") or "", get("x_alarm") or "", get("x_threshold") or 0.0
    unit, quantity = get("x_unit") or "", get("x_kind") or ""
    vals = {
        "code": x.x_code,
        "name": get("x_name") or x.x_code,
        "sequence": get("x_sequence") or 10,
        "equipment_id": _m2o(get("x_equipment_id")),
        "workcenter_id": _m2o(get("x_workcenter_id")),
        "quantity": quantity,
        "unit": unit,
        "sim_mode": mode,
        "kind": simcat.kind_for_mode(mode),
        "module": simcat.module_for_code(x.x_code),
        "decimals": _decimals(unit),
        "nominal": get("x_nominal") or 0.0,
        "origin": "sim_data",
        "period_s": 60,
        "store_period_s": 300,
        "viewer_visible": True,
        "create_request": True,
        "active": True,
        "alarm_title": ALARM_TITLES.get((quantity, alarm), False),
        "hysteresis": abs(threshold) * 0.02 if mode == "drift" and alarm in ("above", "below") else 0.0,
        "sim_params": {
            "nominal": get("x_nominal"),
            "noise": get("x_noise"),
            "rate": get("x_rate"),
            "limit": get("x_limit"),
            "seed": get("x_seed"),
            "alarm": alarm or None,
            "threshold": get("x_threshold"),
            "charging": bool(get("x_charging")),
        },
    }
    if alarm == "above":
        vals.update(alarm_high=threshold, alarm_high_on=True)
    elif alarm == "below":
        vals.update(alarm_low=threshold, alarm_low_on=True)
    return vals


def _level0_snapshot(x, written):
    """Що саме перенесла міграція з `x_f3d_signal` (для кроку 8): значення, стан, час, поріг рівня 0."""
    return {
        "value": x.x_value or 0.0,
        "state": x.x_state or "",
        "ts": x.x_updated or False,
        "alarm": (x["x_alarm"] if "x_alarm" in x._fields else "") or "",
        "written": written,
    }


def signals_level0(env, snapshot=None):
    """Крок 2: `x_f3d_signal` → `td.signal` (upsert за `code`), xml-id `sig_<slug>`, `derived_from_id`.

    `snapshot` (dict, заповнюється тут) — знімок того, що перенесено; крок 8 звіряє саме його, а не живий
    рівень 0, який між кроками продовжує змінюватись (T-1). При повторному запуску сигнал `sim_data`, чиє
    значення на рівні 0 свіжіше за `last_ts`, підхоплюється з рівня 0 (рівень 0 ще живий); новіше значення
    телеметрії не відкочується (R-17 п. 7).
    """
    if not _level0(env):
        return {"skipped": True}
    snapshot = {} if snapshot is None else snapshot
    Signal = _signals(env)
    xs = env["x_f3d_signal"].sudo().with_context(active_test=False).search([], order="x_sequence, id")
    existing = {s.code: s for s in Signal.search([("code", "in", xs.mapped("x_code"))])}
    by_code, created, to_create = {}, 0, []
    refreshed = Signal
    for x in xs:
        vals = _level0_vals(x)
        sig = existing.get(x.x_code)
        snapshot[x.x_code] = _level0_snapshot(x, written=True)
        if sig is None:
            vals.update(
                last_value=x.x_value or 0.0,
                last_quality="good",
                last_ts=x.x_updated or False,
                last_stored_ts=x.x_updated or False,
                status_since=x.x_updated or False,
                status="alarm" if x.x_state == "тривога" else "ok",
            )
            to_create.append(vals)
            continue
        if sig.origin == "sim_data":
            vals = {k: v for k, v in vals.items() if k not in DEFINITION_ONLY}
            if x.x_updated and (not sig.last_ts or x.x_updated > sig.last_ts):
                refreshed |= sig
                vals.update(
                    last_value=x.x_value or 0.0,
                    last_quality="good",
                    last_ts=x.x_updated,
                    last_stored_ts=x.x_updated,
                )
                if (x.x_state == "тривога") != (sig.status == "alarm"):
                    vals.update(status="alarm" if x.x_state == "тривога" else "ok", status_since=x.x_updated)
            else:
                snapshot[x.x_code]["written"] = False
        else:
            vals.update(
                last_value=x.x_value or 0.0,
                last_quality="good",
                last_ts=x.x_updated or False,
                last_stored_ts=x.x_updated or False,
                status_since=x.x_updated or False,
                status="alarm" if x.x_state == "тривога" else "ok",
            )
        diff = _changed(sig, vals)
        if diff:
            sig.write(diff)
        by_code[x.x_code] = sig
    if to_create:
        for sig in Signal.create(to_create):
            by_code[sig.code] = sig
            created += 1
    refreshed._recompute_status()  # пороги каталогу (warn) для підхоплених значень, як при першому запуску
    for x in xs:  # другий прохід: похідні
        source = x.x_source_id if "x_source_id" in x._fields else False
        sig = by_code[x.x_code]
        if source and by_code.get(source.x_code) and sig.derived_from_id != by_code[source.x_code]:
            sig.write({"derived_from_id": by_code[source.x_code].id, "derive_rule": "none"})
    env["ir.model.data"]._update_xmlids(
        [
            {"xml_id": "td_telemetry.sig_" + _slug(code), "record": sig, "noupdate": True}
            for code, sig in by_code.items()
        ]
    )
    by_module = Counter(s.module for s in by_code.values())
    report = {
        "signals_migrated": len(xs),
        "created": created,
        "by_module": dict(by_module),
        "alarm": sum(1 for x in xs if x.x_state == "тривога"),
        "with_request": sum(1 for x in xs if "x_request_id" in x._fields and x.x_request_id),
    }
    _logger.info("signals_level0: %s", report)
    return report


# --- крок 3 --------------------------------------------------------------------------------------------
def _binding_vals(row, sources, stats):
    """Поля прив'язки рядка каталогу (непорожні колонки)."""
    vals = {}
    code = (row.get("source") or "").strip()
    if code:
        source = sources.get(code)
        if source:
            vals["source_id"] = source.id
            stats["bound"] += 1
        else:
            _logger.warning("signals_catalog: джерело %s для %s не знайдено", code, row.get("code"))
    address = _json(row.get("address"))
    if address is not None:
        vals["address"] = address
    for col in ("period_s", "store_period_s", "decimals", "min_duration_s"):
        if _num(row.get(col)) is not None:
            vals[col] = int(_num(row[col]))
    if _num(row.get("hysteresis")) is not None:
        vals["hysteresis"] = _num(row["hysteresis"])
    for col in ("warn_low", "warn_high", "alarm_low", "alarm_high"):
        if _num(row.get(col)) is not None:
            vals[col] = _num(row[col])
            vals[col + "_on"] = True
    if row.get("alarm_title"):
        vals["alarm_title"] = row["alarm_title"]
    return vals


def _create_vals(row, derived):
    vals = {
        "code": row["code"],
        "name": row.get("name") or row["code"],
        "kind": row.get("kind") or "gauge",
        "origin": row.get("origin") or "catalog",
        "module": row.get("module") or simcat.module_for_code(row["code"]),
        "viewer_visible": _flag(row["viewer_visible"]) if row.get("viewer_visible") not in (None, "") else True,
        "derive_rule": row.get("derive_rule") or "none",
    }
    for col in ("quantity", "unit", "sim_mode"):
        if row.get(col):
            vals[col] = row[col]
    for col in ("states", "alarm_states", "sim_params"):
        if _json(row.get(col)) is not None:
            vals[col] = _json(row[col])
    if _num(row.get("scale")) is not None:
        vals["scale"] = _num(row["scale"])
    if _num(row.get("nominal")) is not None:
        vals["nominal"] = _num(row["nominal"])
    if derived:
        vals["derived_from_id"] = derived.id
    return vals


def signals_catalog(env):
    """Крок 3: `signal_catalog.csv` → створення нових і прив'язка наявних сигналів; джерелам — обладнання."""
    Signal = _signals(env)
    sources = {s.code: s for s in env["td.source"].sudo().with_context(active_test=False).search([])}
    Equipment = env["maintenance.equipment"].sudo()
    stats = Counter(created=0, bound=0, bind_missing=0, no_equipment=0)
    for row in _catalog_rows(env):
        code, new = row["code"], _flag(row.get("new"))
        sig = Signal.search([("code", "=", code)], limit=1)
        if not sig and not new:
            stats["bind_missing"] += 1
            continue
        vals = _binding_vals(row, sources, stats)
        equipment = False
        if row.get("equipment") and (not sig or not sig.equipment_id):
            equipment = Equipment.search_f3d(row["equipment"])
            if not equipment:
                stats["no_equipment"] += 1
                _logger.warning("signals_catalog: обладнання %s для %s не знайдено", row["equipment"], code)
        if equipment:
            vals["equipment_id"] = equipment.id
        if not sig:
            derived = (
                Signal.search([("code", "=", row["derived_from"])], limit=1) if row.get("derived_from") else Signal
            )
            sig = Signal.create({**_create_vals(row, derived), **vals})
            stats["created"] += 1
        else:
            diff = _changed(sig, vals)
            if diff:
                sig.write(diff)
    for source_code, equipment_code in SOURCE_EQUIPMENT.items():
        source = sources.get(source_code)
        if source and not source.equipment_id:
            equipment = Equipment.search_f3d(equipment_code)
            if equipment:
                source.write({"equipment_id": equipment.id})
    _fill_state_from_charging(env)
    report = {k: stats[k] for k in ("created", "bound", "bind_missing", "no_equipment")}
    _logger.info("signals_catalog: %s", report)
    return report


def _fill_state_from_charging(env):
    """Додаток D: `x_charging` → `last_text` сигналу `equipment/<код>/state` (`charging` / `busy`)."""
    Signal = _signals(env)
    for battery in Signal.search([("sim_mode", "=", "drain"), ("code", "=like", "equipment/%/battery")]):
        state = Signal.search([("code", "=", battery.code.rsplit("/", 1)[0] + "/state")], limit=1)
        if state:
            text = "charging" if (battery.sim_params or {}).get("charging") else "busy"
            if state.last_text != text:
                state.write({"last_text": text})


# --- крок 3а -------------------------------------------------------------------------------------------
def meters(env):
    """Додаток C.4: ТО за лічильником на обладнанні з порожнім `td_meter_signal_id` + прив'язка заявок."""
    Signal, Equipment = _signals(env), env["maintenance.equipment"].sudo()
    Request = env["maintenance.request"].sudo().with_context(mail_notrack=True, tracking_disable=True)
    lead = float(env["ir.config_parameter"].sudo().get_param(P + "meter_lead_pct", "5") or 5)
    done = linked = 0
    for equipment_code, signal_code, interval, last in METERS:
        equipment = Equipment.search_f3d(equipment_code)
        sig = Signal.search([("code", "=", signal_code)], limit=1)
        if not equipment or not sig or equipment.td_meter_signal_id:
            continue
        if last is None:
            last = math.floor(sig.last_value / interval) * interval
        equipment.with_context(mail_notrack=True).write(
            {
                "td_meter_signal_id": sig.id,
                "td_meter_interval": interval,
                "td_meter_last_value": last,
                "td_meter_lead_pct": lead,
            }
        )
        done += 1
        request = Request.search(
            [
                ("equipment_id", "=", equipment.id),
                ("maintenance_type", "=", "preventive"),
                ("stage_id.done", "=", False),
            ],
            order="id desc",
            limit=1,
        )
        if request:
            request.write({"td_signal_id": sig.id, "td_origin": "meter", "td_threshold": last + interval})
            equipment.with_context(mail_notrack=True).write({"td_meter_request_id": request.id})
            linked += 1
    report = {"meters": done, "meter_requests_linked": linked}
    _logger.info("meters: %s", report)
    return report


# --- крок 4 --------------------------------------------------------------------------------------------
def sim_catalog(env):
    """Крок 4: CT-11 над каталогом `td.sim.signal` (якщо модель є); адреси, `sim_params`, `nominal`."""
    if "td.sim.signal" not in env:
        _logger.info("sim_catalog: td.sim.signal відсутня — пропуск")
        return {"state": "skipped"}
    codes = _signals(env).search([("origin", "in", ("sim_data", "catalog"))]).mapped("code")
    report = env["td.signal"].sudo()._td_import_sim_catalog(codes=codes, source_map=SOURCE_MAP, defaults={})
    report = {
        "created": report["created"],
        "updated": report["updated"],
        "unparsed": len(report["unparsed"]),
        "skipped": len(report["skipped"]),
    }
    _logger.info("sim_catalog: %s", report)
    return report


# --- крок 5 --------------------------------------------------------------------------------------------
READINGS_SQL = """
INSERT INTO td_reading (signal_id, equipment_id, ts, value, quality, src, received_at)
SELECT s.id, s.equipment_id, r.x_time, r.x_value, 'good', 'sim_data', COALESCE(r.create_date, r.x_time)
  FROM x_f3d_reading r
  JOIN x_f3d_signal x ON x.id = r.x_signal_id
  JOIN td_signal s ON s.code = x.x_code
 WHERE r.id >= %s AND r.id < %s AND r.x_time IS NOT NULL
ON CONFLICT (signal_id, ts) DO NOTHING
"""


def readings_level0(env):
    """Крок 5: `x_f3d_reading` → `td.reading` батчами по 5 000 (`ON CONFLICT DO NOTHING`)."""
    if "x_f3d_reading" not in env:
        return {"skipped": True}
    cr = env.cr
    cr.execute(
        "SELECT count(*) FILTER (WHERE x_time IS NOT NULL), count(*) FILTER (WHERE x_time IS NULL), "
        "min(id), max(id) FROM x_f3d_reading"
    )
    total, null_ts, low, high = cr.fetchone()
    inserted = 0
    start = low or 0
    while low is not None and start <= high:
        cr.execute(READINGS_SQL, (start, start + READINGS_BATCH))
        inserted += cr.rowcount
        start += READINGS_BATCH
    env["td.reading"].invalidate_model()
    report = {"readings_migrated": total, "skipped_null_ts": null_ts, "readings_inserted": inserted, "max_id": high}
    _logger.info("readings_level0: %s", report)
    return report


# --- крок 6 --------------------------------------------------------------------------------------------
def requests_level0(env):
    """Крок 6: заявки рівня 0 (`x_request_id`) ↔ сигнали; закрита заявка → `request_closed_at`."""
    if not _level0(env) or "x_request_id" not in env["x_f3d_signal"]._fields:
        return {"skipped": True}
    Signal = _signals(env)
    linked = 0
    for x in env["x_f3d_signal"].sudo().with_context(active_test=False).search([("x_request_id", "!=", False)]):
        sig = Signal.search([("code", "=", x.x_code)], limit=1)
        request = x.x_request_id.sudo().with_context(mail_notrack=True, tracking_disable=True)
        if not sig or not request.exists():
            continue
        threshold = sig.alarm_high if sig.alarm_high_on else (sig.alarm_low if sig.alarm_low_on else 0.0)
        request.write(
            {
                "td_signal_id": sig.id,
                "td_origin": "threshold",
                "td_value": sig.last_value,
                "td_threshold": threshold,
            }
        )
        if request.stage_id.done:
            sig.write({"maintenance_request_id": False, "request_closed_at": request.write_date})
        else:
            sig.write({"maintenance_request_id": request.id})
        linked += 1
    _logger.info("requests_level0: requests_linked=%s", linked)
    return {"requests_linked": linked}


# --- крок 7 --------------------------------------------------------------------------------------------
def hours_rebuild(env):
    """Крок 7: годинні агрегати (R-09) за всіма закритими годинами, де є показання."""
    cr = env.cr
    cr.execute("SELECT min(ts) FROM td_reading")
    first = cr.fetchone()[0]
    end = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
    hours = 0
    if first:
        start = first.replace(minute=0, second=0, microsecond=0)
        if start < end:
            cr.execute(AGGREGATE_SQL, {"start": start, "end": end})
            hours = cr.rowcount
            env.invalidate_all()
    _logger.info("hours_rebuild: hours=%s", hours)
    return {"hours": hours}


# --- крок 8 -------------------------------------------------------------------------------------------
READINGS_MISSING_SQL = """
SELECT count(*)
  FROM x_f3d_reading r
  JOIN x_f3d_signal x ON x.id = r.x_signal_id
  LEFT JOIN td_signal s ON s.code = x.x_code
  LEFT JOIN td_reading fr ON fr.signal_id = s.id AND fr.ts = r.x_time
 WHERE r.x_time IS NOT NULL AND fr.id IS NULL{bound}
"""
THRESHOLD_COLS = ("warn_low", "warn_high", "alarm_low", "alarm_high")


TIME_DERIVED_STATUSES = ("stale", "offline", "unknown")  # статус від часу (немає свіжих даних), а не від значення


def _status_from_catalog(sig, snap):
    """Статус відрізняється від рівня 0 лише через пороги каталогу, яких на рівні 0 не було (T-1).

    Рівень 0 знає лише «норма»/«тривога» і один поріг `x_alarm`; каталог (Додаток C.2) додає «увагу» й нижні/верхні
    пороги. Якщо рівень 0 вважав значення нормою, а td.signal — «увага»/«тривога» через додаткові пороги, це не
    розбіжність міграції. Тривога рівня 0, якої немає в td.signal, лишається розбіжністю.
    """
    if snap["state"] == "тривога" or sig.status not in ("warn", "alarm"):
        return False
    own = {"above": "alarm_high", "below": "alarm_low"}.get(snap["alarm"])
    extra = [col for col in THRESHOLD_COLS if sig[col + "_on"] and col != own]
    return bool(extra or sig.alarm_states)


def verify(env, snapshot=None, notes=None, max_reading_id=None):
    """Крок 8: звірка рівня 0 з td.*; повертає список розбіжностей.

    Порівнюється зі знімком, який зробив крок 2 (`snapshot`), а не з живим рівнем 0: значення й стан
    звіряються лише для сигналів, чиє `last_*` взято з цього знімка (записане цим запуском або з тим самим
    `last_ts`); новіші дані телеметрії не перевіряються. Різниця статусу через пороги каталогу або через час
    (`stale`/`offline`/`unknown` — немає свіжих даних) — не розбіжність, вона додається в `notes` (якщо передано
    список). Показання: кожне `x_f3d_reading` (до `max_reading_id`,
    знятого кроком 5) має мати `td.reading`; зайві (рівень 0 чистить свої рядки) не заважають.
    """
    if not _level0(env):
        return []
    mismatches = []
    if snapshot is None:
        snapshot = {}
        for x in env["x_f3d_signal"].sudo().with_context(active_test=False).search([]):
            snapshot[x.x_code] = _level0_snapshot(x, written=True)
    Signal = _signals(env)
    count = Signal.search_count([("origin", "=", "sim_data")])
    if count != len(snapshot):
        mismatches.append("signals: td.signal(sim_data) %d != x_f3d_signal %d" % (count, len(snapshot)))
    sigs = {s.code: s for s in Signal.search([("code", "in", list(snapshot))])}
    for code, snap in snapshot.items():
        sig = sigs.get(code)
        if not sig:
            mismatches.append("%s: сигнал відсутній" % code)
            continue
        if not snap["written"] and not (snap["ts"] and (sig.last_ts or False) == snap["ts"]):
            continue  # значення вже новіше за міграцію (телеметрія), порівнювати нема з чим
        if abs(sig.last_value - snap["value"]) >= 1e-6:
            mismatches.append("%s: last_value %.3f != x_value %.3f" % (code, sig.last_value, snap["value"]))
        expected = "alarm" if snap["state"] == "тривога" else "ok"
        if snap["state"] and sig.status != expected:
            if sig.status in TIME_DERIVED_STATUSES:
                # T-1b: «немає даних» залежить від часу (стенд зупинено), а не від значення — не розбіжність
                if notes is not None:
                    notes.append("%s: status %s (немає свіжих даних), x_state %s" % (code, sig.status, snap["state"]))
            elif _status_from_catalog(sig, snap):
                if notes is not None:
                    notes.append("%s: status %s (пороги каталогу), x_state %s" % (code, sig.status, snap["state"]))
            else:
                mismatches.append("%s: status %s != x_state %s" % (code, sig.status, snap["state"]))
    if "x_f3d_reading" in env:
        bound = " AND r.id <= %s" if max_reading_id is not None else ""
        env.cr.execute(READINGS_MISSING_SQL.format(bound=bound), (max_reading_id,) if bound else ())
        missing = env.cr.fetchone()[0]
        if missing:
            mismatches.append("readings: %d x_f3d_reading без відповідного td.reading(sim_data)" % missing)
    return mismatches


# --- крок 9 --------------------------------------------------------------------------------------------
def level0_off(env):
    """Крок 9: вимкнути рівень 0 (крон, `x_active`, меню, представлення, параметр iot_sim)."""
    cron = _ref(env, "cron_iot_sim")
    if cron:
        cron.sudo().write({"active": False})
    env.cr.execute("UPDATE x_f3d_signal SET x_active = false")
    x_inactive = env.cr.rowcount
    env["x_f3d_signal"].invalidate_model()
    menu = _ref(env, "menu_iot_root")
    if menu:
        menu.sudo().write({"active": False})
    view = _ref(env, "view_equipment_form_signals")
    if view:
        view.sudo().write({"active": False})
    param = env["ir.config_parameter"].sudo().search([("key", "=", "td.iot_sim.level0_enabled")])
    if param:
        param.write({"value": "False"})
    report = {
        "cron_off": bool(cron),
        "x_inactive": x_inactive,
        "menu_off": 1 if menu else 0,
        "view_off": 1 if view else 0,
        "iot_sim_param": bool(param),
    }
    _logger.info("level0_off: %s", report)
    return report


# --- крок 10 -------------------------------------------------------------------------------------------
def drop_level0(env):
    """Крок 10: видалити представлення, меню, поле й моделі рівня 0 (лише `drop_level0=True`)."""
    from odoo.addons.td_factory3d.hooks.x_fields import drop_manual_fields  # noqa: PLC0415

    views = env["ir.ui.view"]
    for name in LEVEL0_VIEWS:
        views |= _ref(env, name) or views.browse()
    views.sudo().unlink()
    menus = env["ir.ui.menu"]
    for name in LEVEL0_MENUS:
        menus |= _ref(env, name) or menus.browse()
    menus.sudo().unlink()
    actions = env["ir.actions.act_window"]
    for name in LEVEL0_ACTIONS:
        actions |= _ref(env, name) or actions.browse()
    actions.sudo().unlink()
    fields_dropped = drop_manual_fields(env, "maintenance.equipment", ["x_f3d_signal_ids"])
    Model = env["ir.model"].sudo()
    for model in ("x_f3d_reading", "x_f3d_signal"):  # спершу reading — FK
        Model.search([("model", "=", model)]).unlink()
    report = {"views_dropped": len(views), "fields_dropped": fields_dropped, "dropped": True}
    _logger.info("drop_level0: %s", report)
    return report


# --- крок 11 -------------------------------------------------------------------------------------------
def report(env, data):
    env["ir.config_parameter"].sudo().set_param(
        P + "level0_migrated", json.dumps(data, ensure_ascii=False, default=str)
    )


def run_migration(env):
    """Кроки 1…11 (§5.3); ідемпотентно. Крок 6 і 9–10 — лише при `mismatches == []` (`status_notes` не рахуються)."""
    env = env(su=True)
    data = {"state": "pending", "ts": fields.Datetime.now().isoformat(), "mismatches": []}
    params(env)
    snapshot = {}  # що перенесено кроком 2: крок 8 звіряє його, а не живий рівень 0
    level0 = signals_level0(env, snapshot)
    skipped = bool(level0.get("skipped"))
    if not skipped:
        data.update({k: level0[k] for k in ("signals_migrated", "created", "by_module", "alarm", "with_request")})
    data["signals_catalog"] = signals_catalog(env)
    data.update(meters(env))
    data["sim_catalog"] = sim_catalog(env)
    max_reading_id = None
    if not skipped:
        readings = readings_level0(env)
        max_reading_id = readings.get("max_id")
        data.update({k: v for k, v in readings.items() if k in ("readings_migrated", "skipped_null_ts")})
    data.update(hours_rebuild(env))
    notes = []  # різниця статусу через пороги каталогу — не розбіжність
    data["mismatches"] = verify(env, snapshot, notes, max_reading_id)
    if notes:
        data["status_notes"] = notes[:20]
        data["status_notes_total"] = len(notes)
    clean = not data["mismatches"]
    if not skipped and clean:
        data["requests_linked"] = requests_level0(env).get("requests_linked", 0)
        data.update(level0_off(env))
        if env["ir.config_parameter"].sudo().get_param(P + "drop_level0") == "True":
            data.update(drop_level0(env))
    data["state"] = "skipped" if skipped else ("done" if clean else "partial")
    if data["mismatches"]:
        _logger.warning("run_migration: розбіжності: %s", data["mismatches"][:20])
    report(env, data)
    _logger.info("run_migration: state=%s", data["state"])
    return data


def run_level0_migration(env):
    """Кнопка «Запустити міграцію» налаштувань (res.config.settings)."""
    return run_migration(env)


def schedule_rotate(env):
    """§6: перший запуск ротації — найближчі 02:40 за Києвом."""
    cron = env.ref("td_telemetry.cron_td_telemetry_rotate", raise_if_not_found=False)
    if not cron:
        return
    now = datetime.now(timezone.utc).astimezone(KYIV)
    target = datetime.combine(now.date(), time(2, 40), tzinfo=KYIV)
    if target <= now:
        target += timedelta(days=1)
        target = datetime.combine(target.date(), time(2, 40), tzinfo=KYIV)
    cron.sudo().write({"nextcall": target.astimezone(timezone.utc).replace(tzinfo=None)})


def post_init_hook(env):
    env = env(su=True)
    schedule_rotate(env)
    run_migration(env)


def uninstall_hook(env):
    """§5.4: повернути рівень 0 (крон лишається вимкненим), прибрати параметри."""
    env = env(su=True)
    if _level0(env):
        env.cr.execute("UPDATE x_f3d_signal SET x_active = true")
        env["x_f3d_signal"].invalidate_model()
        for name in ("menu_iot_root", "view_equipment_form_signals"):
            rec = _ref(env, name)
            if rec:
                rec.write({"active": True})
        _logger.warning("рівень 0 вимкнено; увімкніть вручну або через пульт")
    env.cr.execute("DROP TABLE IF EXISTS td_collector_push")  # DEC-19: журнал пакетів колектора — не модель ORM
    env["ir.config_parameter"].sudo().search([("key", "=like", "td.telemetry.%")]).unlink()
