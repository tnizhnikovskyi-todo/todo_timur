"""Спільні утиліти td_chp: параметри `td.chp.*`, час, свіжість сигналів (R-01), завантаження карти (R-14)."""

import json
from datetime import datetime

from odoo import _, fields
from odoo.exceptions import UserError
from odoo.tools import file_open

PARAM = "td.chp."
PREFIX = "chp/"
MAP_FILE = "td_chp/data/chp_signals.json"
STORE_FAST = {"chp/gen/p_kw", "chp/ht/q_total", "chp/gas/flow"}  # джерело тренду: зберігаємо кожні 30 с
STORE_FAST_S = 30
STORE_DEFAULT_S = 300
THRESHOLDS = ("warn_low", "warn_high", "alarm_low", "alarm_high")
# значення стоп-кранів і TTL за замовчуванням (SPEC §5.1)
DEFAULTS = {
    "read_enabled": "True",
    "write_enabled": "False",
    "remote_switching_enabled": "False",
    "confirm_ttl_s": "60",
    "second_ttl_s": "600",
    "verify_timeout_s": "30",
    "command_ttl_s": "60",
    "stale_s": "30",
    "event_keep_days": "365",
    "bus_throttle_s": "1",
}


# --- параметри ---------------------------------------------------------------------------------------------------
def cparam(env, name, default=None):
    val = env["ir.config_parameter"].sudo().get_param(PARAM + name)
    if val in (None, False, ""):
        return DEFAULTS.get(name) if default is None else default
    return val


def cparam_bool(env, name, default=None):
    val = cparam(env, name, default)
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def cparam_float(env, name, default=None):
    try:
        return float(cparam(env, name, default))
    except (TypeError, ValueError):
        return float(default or 0)


def cparam_int(env, name, default=None):
    return int(cparam_float(env, name, default))


def telemetry_write_enabled(env):
    val = env["ir.config_parameter"].sudo().get_param("td.telemetry.write_enabled", "False")
    return str(val).strip().lower() in ("1", "true", "yes", "on")


# --- час ---------------------------------------------------------------------------------------------------------
def now(env):
    """Поточний час (naive UTC); у тестах підміняється контекстом `td_chp_now`."""
    return env.context.get("td_chp_now") or fields.Datetime.now()


def iso(dt):
    """naive UTC → `2026-10-20T10:00:00Z`."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_iso(text):
    """`2026-10-20T10:00:00Z` (або без `Z`/з пробілом) → naive UTC; порожнє → None."""
    if not text:
        return None
    if isinstance(text, datetime):
        return text
    try:
        return datetime.fromisoformat(str(text).replace("Z", "").replace("T", " ").strip()[:26])
    except ValueError as e:
        raise UserError(_("Невірний формат часу: %s.", text)) from e


def is_fresh(last_ts, period_s, at, stale_s):
    """R-01: свіжий, якщо `now − last_ts ≤ max(3·period_s, stale_s)`."""
    if not last_ts:
        return False
    return (at - last_ts).total_seconds() <= max(3 * (period_s or 0), stale_s)


def write_off_reason(env, signal_code):
    """R-07 `write_enabled`: що саме вимкнено для запису в сигнал `signal_code` (без `chp/`) — або '' (запис дозволено).
    `td.chp.write_enabled` перевіряє `prepare` окремо (UserError)."""
    sig = env["td.signal"].sudo().search([("code", "=", PREFIX + signal_code)], limit=1)
    if not telemetry_write_enabled(env):
        return "td.telemetry.write_enabled"
    if not sig:
        return f"сигнал {PREFIX}{signal_code}"
    if sig.source_id and not sig.source_id.write_enabled:
        return f"джерело {sig.source_id.code}"
    if not sig.write_enabled:
        return f"сигнал {sig.code}"
    return ""


# --- карта сигналів (C-chp-01, R-14) -----------------------------------------------------------------------------
def load_map():
    with file_open(MAP_FILE, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def signal_vals(row, seq=0):
    """Рядок JSON → значення `td.signal` (без `source_id`/`equipment_id`)."""
    address = {"fc": 3, "addr": row["pdu"], "type": row["type"], "scale": row["scale"]}
    if "W" in row["rw"]:
        address["write"] = {"fc": 6, "addr": row["pdu"]}
    vals = {
        "code": row["code"],
        "name": row["name"],
        "unit": row["unit"] or False,
        "kind": row["kind"],
        "address": address,
        "scale": 1.0,
        "period_s": row["period_s"],
        "decimals": row["decimals"],
        "store_period_s": STORE_FAST_S if row["code"] in STORE_FAST else STORE_DEFAULT_S,
        "create_request": bool(row["create_request"]),
        "module": "chp",
        "origin": "module",
        "write_enabled": False,
        "viewer_visible": False,
        "sequence": seq,
        "note": row.get("note") or False,
    }
    for key in THRESHOLDS:
        vals[key] = row[key] if row[key] is not None else 0.0
        vals[key + "_on"] = row[key] is not None
    return vals


# поля, які правка інженера не чіпає при повторному `post_init` і які повертає `action_reset_map()`
MAP_FIELDS = (
    "address",
    "scale",
    "unit",
    "period_s",
    "decimals",
    "store_period_s",
    "create_request",
    *THRESHOLDS,
    *(k + "_on" for k in THRESHOLDS),
)


def sync_map(env, unit, reset=False):
    """R-14: немає сигналу за `code` → створити; є → лишити (`reset=True` — перезаписати поля карти з JSON)."""
    Signal = env["td.signal"].sudo().with_context(active_test=False, mail_create_nolog=True, tracking_disable=True)
    rows = load_map()
    existing = {s.code: s for s in Signal.search([("code", "in", [r["code"] for r in rows])])}
    source, equipment = unit.source_id, unit.equipment_id
    created = updated = 0
    to_create = []
    for seq, row in enumerate(rows, 1):
        vals = signal_vals(row, seq * 10)
        rec = existing.get(row["code"])
        if rec is None:
            vals.update(source_id=source.id or False, equipment_id=equipment.id or False)
            to_create.append(vals)
        elif reset:
            rec.write({k: vals[k] for k in MAP_FIELDS})
            updated += 1
    if to_create:
        Signal.create(to_create)
        created = len(to_create)
    return {"created": created, "updated": updated, "total": len(rows)}


# --- знімок значень (R-01) -----------------------------------------------------------------------------------------
class Snapshot:
    """Свіжі значення сигналів КГУ одним запитом: ключ — код без `chp/`; несвіже/відсутнє → None (R-01)."""

    def __init__(self, env, now_ts=None):
        self.env = env
        self.now = now_ts or now(env)
        stale_s = cparam_int(env, "stale_s")
        recs = (
            env["td.signal"]
            .sudo()
            .search_read(
                [("module", "=", "chp"), ("code", "=like", PREFIX + "%")],
                ["code", "last_value", "last_ts", "status", "period_s", "unit"],
            )
        )
        self.rows = {}
        for r in recs:
            key = r["code"][len(PREFIX) :]
            fresh = is_fresh(r["last_ts"], r["period_s"], self.now, stale_s)
            if not r["last_ts"] or not fresh:
                status = "stale"
            else:
                status = r["status"] if r["status"] in ("warn", "alarm") else "ok"
            self.rows[key] = {
                "value": r["last_value"] if fresh else None,
                "age_s": int((self.now - r["last_ts"]).total_seconds()) if r["last_ts"] else None,
                "fresh": fresh,
                "status": status,
                "unit": r["unit"] or "",
            }

    def get(self, key):
        row = self.rows.get(key)
        return row["value"] if row else None

    def values(self):
        return {k: r["value"] for k, r in self.rows.items()}

    def units(self):
        return {k: r["unit"] for k, r in self.rows.items()}

    def statuses(self):
        return {k: r["status"] for k, r in self.rows.items()}

    def age(self, key):
        row = self.rows.get(key)
        return row["age_s"] if row else None
