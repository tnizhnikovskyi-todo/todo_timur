"""Хуки модуля (SPEC §5.3–§5.5, §13.0.1 п. 4).

Каркас W0: `_csv_rows`, `_signal_rows`; `run_migration` повертає звіт `skipped` (кроки 0–7 — W8).
"""

import csv
import io
import json
import logging

from odoo.tools import file_open

_logger = logging.getLogger(__name__)

MODULE = "factory3d_machine_connect"
REPORT_KEY = "factory3d.machine_connect.migration_report"
CSV_NAMES = ("mc_machines", "mc_signals")
# Шаблони сигналів, що застосовуються до протоколу верстата (колонка `protocol` у mc_signals.csv):
# `any` — усім верстатам (обчислений стан); `gantry`, `cutopt` — окремі коди (GANTRY-1, CUTOPT).
PROTOCOL_GROUPS = {
    "opcua": ("opcua", "any"),
    "io": ("io", "any"),
    "manual": ("any",),
    "gantry": ("gantry",),
    "cutopt": ("cutopt",),
}
BOOL_COLS = ("create_request", "viewer_visible", "write_enabled")
INT_COLS = ("period_s", "store_period_s", "decimals")
JSON_COLS = ("states", "alarm_states")


def _csv_rows(env, name):
    """Рядки `data/<name>.csv` (`name` ∈ CSV_NAMES) як список словників (UTF-8, заголовок, порожні — `""`)."""
    if name not in CSV_NAMES:
        raise ValueError("csv: невідомий файл %r" % (name,))
    with file_open("%s/data/%s.csv" % (MODULE, name), "rb") as raw:
        return list(csv.DictReader(io.StringIO(raw.read().decode("utf-8"), newline="")))


def _signal_rows(code, protocol, io_unit, io_slot, name=None, with_meta=False):
    """Значення для `f3d.signal.create` (без `source_id`, `equipment_id`, `workcenter_id`) для коду верстата/пристрою.

    `protocol` ∈ `opcua` | `io` | `manual` | `gantry` | `cutopt`. Підстановки: `{C}` — `code`, `{N}` — `name`
    (за замовчуванням `code`), `{DI_RUN}` = 2·io_slot, `{DI_ALARM}` = 2·io_slot + 1, `{HR}` = 4·io_slot.
    `with_meta=True` додає ключі `template`, `source` (код джерела шаблону; `{SRC}` — з Додатка A) — для хука.
    `io_unit` зараз не використовується в шаблонах (адреса Modbus — у джерелі); параметр зберігає контракт SPEC.
    """
    groups = PROTOCOL_GROUPS.get(protocol)
    if groups is None:
        raise ValueError("protocol: невідомий %r" % (protocol,))
    slot = io_slot or 0
    subst = {
        '"{DI_RUN}"': str(2 * slot),
        '"{DI_ALARM}"': str(2 * slot + 1),
        '"{HR}"': str(4 * slot),
    }
    text_subst = {"{C}": code, "{N}": name or code}
    rows = []
    for row in _csv_rows(None, "mc_signals"):
        if row["protocol"] not in groups:
            continue
        # Шаблони gantry/cutopt мають власні коди (equipment/GANTRY-1/…, equipment/CUTOPT/cmd): `{C}` не потрібен.
        address = row["address"]
        for k, v in subst.items():
            address = address.replace(k, v)
        for k, v in text_subst.items():
            address = address.replace(k, v)
        vals = {
            "code": row["code"].replace("{C}", code),
            "name": row["name"].replace("{N}", name or code).replace("{C}", code),
            "kind": row["kind"],
            "unit": row["unit"] or False,
            "address": json.loads(address),
            "module": "machine_connect",
            "origin": "module",
        }
        for col in INT_COLS:
            if row[col] != "":
                vals[col] = int(row[col])
        for col in JSON_COLS:
            if row[col] != "":
                vals[col] = json.loads(row[col])
        for col in BOOL_COLS:
            vals[col] = row[col] == "True"
        if row["alarm_title"]:
            vals["alarm_title"] = row["alarm_title"]
        if with_meta:
            vals["template"] = row["template"]
            vals["source"] = row["source"]
        rows.append(vals)
    return rows


def run_migration(env):
    """Кроки 0–7 (§5.3) — W8. Каркас: нічого не мігрує, звіт `skipped` (записується в `migration_report`)."""
    report = {"state": "skipped"}
    env["ir.config_parameter"].sudo().set_param(REPORT_KEY, json.dumps(report, ensure_ascii=False))
    _logger.info("machine_connect: міграцію пропущено (каркас)")
    return report


def post_init_hook(env):
    run_migration(env)


def uninstall_hook(env):
    """§5.4 — W8. Каркас: порожній."""
