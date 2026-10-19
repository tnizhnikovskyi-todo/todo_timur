"""Хуки модуля (SPEC §5.3–§5.5, R-27, §13.0.1 п. 4): `run_migration` (кроки 0–7), `post_init_hook`, `uninstall_hook`."""

import csv
import io
import json
import logging
import re
from datetime import datetime

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

MODULE = "td_machine_connect"
REPORT_KEY = "td.machine_connect.migration_report"
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
    """Значення для `td.signal.create` (без `source_id`, `equipment_id`, `workcenter_id`) для коду верстата/пристрою.

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


P = "td.machine_connect."
UK_LOSSES = {
    "block_reason0": "Очікування матеріалу",
    "block_reason1": "Поломка",
    "block_reason2": "Налагодження",
    "block_reason4": "Знижена швидкість",
    "block_reason5": "Дефект процесу",
    "block_reason6": "Знижений вихід",
    "block_reason7": "Повністю продуктивний час",
}
ROLE_FIELDS = {
    "state": "sig_state_id",
    "mode": "sig_mode_id",
    "alarm": "sig_alarm_id",
    "pieces_out": "sig_pieces_id",
    "job": "sig_job_id",
    "event": "sig_event_id",
    "job_cmd": "sig_job_cmd_id",
    "machine_state": "sig_machine_state_id",
}
BIND_FIELDS = ("source_id", "address", "period_s", "store_period_s", "viewer_visible")
SIZE_RE = re.compile(r"(\d{3,4})\s*[×xX]\s*(\d{3,4})")
THICK_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*мм")
COUNTERS = (
    "loss_translated",
    "loss_category_fixed",
    "loss_planned",
    "sheets_sized",
    "machines",
    "with_operator",
    "with_equipment",
    "signals_created",
    "signals_bound",
    "machines_wired",
    "stacks",
    "orderpoints_linked",
    "timelog_marked",
    "downtimes_created",
    "downtimes_open",
    "requests_linked",
)


def _slug(code):
    return re.sub(r"[/.\-]", "_", code).lower()


def _int(value):
    return int(value) if value not in ("", None) else 0


# --- крок 0 ------------------------------------------------------------------------------------------------
def params(env):
    """§5.3 крок 0: `read_enabled`, `cutting_mode` — лише якщо відсутні (за `td.base.environment`)."""
    icp = env["ir.config_parameter"].sudo()
    test = icp.get_param("td.base.environment", "") == "test"
    for key, value in (
        ("read_enabled", "True" if test else "False"),
        ("cutting_mode", "collector" if test else "manual"),
    ):
        if not icp.get_param(P + key):
            icp.set_param(P + key, value)
    return {}


# --- крок 1 ------------------------------------------------------------------------------------------------
def losses(env):
    """R-27 п. 1: переклади uk, категорія «Доступність», `td_planned` для «Перерви»."""
    res = {"loss_translated": 0, "loss_category_fixed": 0, "loss_planned": 0}
    if env["res.lang"]._lang_get("uk_UA"):
        for xmlid, name in UK_LOSSES.items():
            rec = env.ref("mrp." + xmlid, raise_if_not_found=False)
            if not rec:
                continue
            en = rec.with_context(lang="en_US").name
            if rec.with_context(lang="uk_UA").name == en and en != name:
                rec.with_context(lang="uk_UA").write({"name": name})
                res["loss_translated"] += 1
    category = env.ref("mrp.category_availability", raise_if_not_found=False)
    for xmlid in ("factory3d.loss_tool", "factory3d.loss_break"):
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec and category and not rec.loss_id:
            rec.loss_id = category
            res["loss_category_fixed"] += 1
    brk = env.ref("factory3d.loss_break", raise_if_not_found=False)
    if brk and not brk.td_planned:
        brk.td_planned = True
        res["loss_planned"] = 1
    return res


# --- крок 2 ------------------------------------------------------------------------------------------------
def sheets(env):
    """R-27 п. 2: розміри листа з назви для плитних матеріалів з нульовими полями."""
    res = {"sheets_sized": 0}
    cats = env["product.category"].search([("name", "=", "Плитні матеріали")])
    if not cats:
        return res
    products = (
        env["product.template"]
        .with_context(active_test=False)
        .search(
            [
                ("categ_id", "child_of", cats.ids),
                ("td_sheet_length_mm", "=", 0),
                ("td_sheet_width_mm", "=", 0),
                ("td_thickness_mm", "=", 0),
            ]
        )
    )
    for tmpl in products:
        size, thick = SIZE_RE.search(tmpl.name or ""), THICK_RE.search(tmpl.name or "")
        if not (size and thick):
            _logger.warning("machine_connect: розміри листа не розпізнано: %s", tmpl.name)
            continue
        tmpl.write(
            {
                "td_sheet_length_mm": int(size.group(1)),
                "td_sheet_width_mm": int(size.group(2)),
                "td_thickness_mm": round(float(thick.group(1).replace(",", "."))),
            }
        )
        res["sheets_sized"] += 1
    return res


# --- крок 3 ------------------------------------------------------------------------------------------------
def machines(env):
    """§5.3 крок 3: upsert `td.machine` за РЦ з `mc_machines.csv` (наявним — лише порожні зв'язки)."""
    res = {"machines": 0, "with_operator": 0, "with_equipment": 0}
    Machine = env["td.machine"].with_context(active_test=False, tracking_disable=True)
    Source = env["td.source"].with_context(active_test=False)
    missing = []
    for row in _csv_rows(env, "mc_machines"):
        code = row["code"]
        wc = env["mrp.workcenter"].search_f3d(code)
        if not wc:
            missing.append(code)
            continue
        eq = env["maintenance.equipment"].search_f3d(code)
        source = Source.search([("code", "=", row["source"])], limit=1)
        emp = env["hr.employee"].search_f3d(row["operator_code"]) if row["operator_code"] else env["hr.employee"]
        if eq and source and not source.equipment_id and source.code.startswith("UA-"):
            source.equipment_id = eq
        machine = Machine.search([("workcenter_id", "=", wc.id)], limit=1)
        if machine:
            vals = {}
            for fname, rec in (("source_id", source), ("equipment_id", eq), ("employee_id", emp)):
                if rec and not machine[fname]:
                    vals[fname] = rec.id
            if vals:
                machine.write(vals)
        else:
            # `protocol` виставляє крок 4 разом із сигналами (constraint: підключений верстат має сигнал стану).
            machine = Machine.create(
                {
                    "workcenter_id": wc.id,
                    "protocol": "manual",
                    "io_slot": _int(row["io_slot"]),
                    "auto_start_mode": row["auto_start_mode"],
                    "source_id": source.id,
                    "equipment_id": eq.id,
                    "employee_id": emp.id,
                }
            )
        res["machines"] += 1
        res["with_operator"] += bool(machine.employee_id)
        res["with_equipment"] += bool(machine.equipment_id)
    if missing:
        _logger.warning("machine_connect: немає РЦ для верстатів: %s", ", ".join(missing))
    return res


# --- крок 4 ------------------------------------------------------------------------------------------------
def signals(env):
    """R-27 п. 3: upsert сигналів за `code` (207 = 35 верстатів + GANTRY-1 + оптимізатор), проводка `sig_*`."""
    res = {"signals_created": 0, "signals_bound": 0, "machines_wired": 0}
    Signal = env["td.signal"].with_context(active_test=False, tracking_disable=True, mail_create_nolog=True)
    Source = env["td.source"].with_context(active_test=False)
    sources = {s.code: s for s in Source.search([])}
    Machine = env["td.machine"].with_context(active_test=False, tracking_disable=True)
    jobs = [(row["code"], row["protocol"], row["source"], _int(row["io_unit"]), _int(row["io_slot"]), row)
            for row in _csv_rows(env, "mc_machines")]  # fmt: skip
    jobs += [("GANTRY-1", "gantry", "", 0, 0, None), ("CUTOPT", "cutopt", "", 0, 0, None)]
    for code, protocol, src_code, io_unit, io_slot, row in jobs:
        wc = env["mrp.workcenter"].search_f3d(code) if row else env["mrp.workcenter"]
        eq_code = code if row else ("GANTRY-1" if protocol == "gantry" else "")
        eq = env["maintenance.equipment"].search_f3d(eq_code) if eq_code else env["maintenance.equipment"]
        by_role = {}
        for vals in _signal_rows(code, protocol, io_unit, io_slot, name=wc.name or None, with_meta=True):
            template, source_key = vals.pop("template"), vals.pop("source")
            source = sources.get(src_code if source_key == "{SRC}" else source_key)
            vals["source_id"] = source.id if source else False
            sig = Signal.search([("code", "=", vals["code"])], limit=1)
            if not sig:
                if template != "cut_cmd":
                    vals["equipment_id"] = eq.id
                if row and wc:
                    vals["workcenter_id"] = wc.id
                sig = Signal.create(vals)
                env["ir.model.data"].create(
                    {
                        "module": MODULE,
                        "name": "sig_" + _slug(vals["code"]),
                        "model": "td.signal",
                        "res_id": sig.id,
                        "noupdate": True,
                    }
                )
                res["signals_created"] += 1
            elif sig.module != "machine_connect":
                upd = {}
                for fname in BIND_FIELDS:
                    new = vals.get(fname)
                    if fname == "source_id" and not new:
                        continue
                    cur = sig[fname].id if fname == "source_id" else sig[fname]
                    if (cur or False) != (new or False):
                        upd[fname] = new
                if upd:
                    sig.write(upd)
                    res["signals_bound"] += 1
            suffix = vals["code"].rsplit("/", 1)[-1]
            if row and suffix in ROLE_FIELDS:
                by_role[ROLE_FIELDS[suffix]] = sig.id
        machine = Machine.search([("workcenter_id", "=", wc.id)], limit=1) if wc else Machine
        if machine and row:
            upd = {f: v for f, v in by_role.items() if machine[f].id != v}
            if machine.protocol != row["protocol"]:
                upd["protocol"] = row["protocol"]
            if upd:
                machine.write(upd)
                res["machines_wired"] += 1
    return res


# --- міграція 19.0.1.0.1 (ST-1) ---------------------------------------------------------------------------
# Шаблони сигналів стану, для яких `store_period_s` змінено з 0 на 300 (SPEC Додаток C.2).
STORE_PERIOD_TEMPLATES = ("io_state", "io_alarm", "ua_state", "ua_mode", "ua_alarm", "ua_job", "g_state", "g_job")


def migrate_store_period(env):
    """ST-1: `store_period_s` з CSV для вже створених сигналів шаблонів `STORE_PERIOD_TEMPLATES`, лише де він ще 0.

    Записи сигналів `noupdate` (і не мають окремого запису шаблону), тож `-u` нове значення з CSV не застосовує.
    Ручні правки (будь-яке ненульове значення) лишаються. Повертає кількість змінених сигналів; ідемпотентна.
    """
    env = env(su=True)
    patterns = []
    for row in _csv_rows(env, "mc_signals"):
        value = _int(row["store_period_s"])
        if row["template"] in STORE_PERIOD_TEMPLATES and value > 0:
            regex = re.escape(row["code"]).replace(re.escape("{C}"), "[^/]+")
            patterns.append((re.compile(regex), value))
    Signal = env["td.signal"].with_context(active_test=False, tracking_disable=True)
    fixed = 0
    for sig in Signal.search([("module", "=", "machine_connect"), ("store_period_s", "=", 0)]):
        for regex, value in patterns:
            if regex.fullmatch(sig.code or ""):
                sig.store_period_s = value
                fixed += 1
                break
    _logger.info("machine_connect: store_period_s виправлено у %d сигналів (ST-1)", fixed)
    return fixed


# --- крок 5 ------------------------------------------------------------------------------------------------
def stacks(env):
    """§5.3 крок 5: `td.gantry.stack` для локацій-стосів `PLT-*`, правила поповнення."""
    res = {"stacks": 0, "orderpoints_linked": 0}
    Stack = env["td.gantry.stack"].with_context(active_test=False, tracking_disable=True)
    locs = env["stock.location"].search([("td_loc_kind", "=", "stack"), ("td_code", "=like", "PLT-%")])
    for loc in locs:
        stack = Stack.search([("location_id", "=", loc.id)], limit=1) or Stack.create({"location_id": loc.id})
        if not stack.orderpoint_id:
            op = env["stock.warehouse.orderpoint"].search([("location_id", "=", loc.id)], limit=1)
            if op:
                stack.orderpoint_id = op
        stack._td_refresh()
        res["stacks"] += 1
        res["orderpoints_linked"] += bool(stack.orderpoint_id)
    return res


# --- крок 6 ------------------------------------------------------------------------------------------------
def _state_kind(loss):
    name = (loss.with_context(lang="en_US").name or "").strip().lower()
    if name == "equipment failure":
        return "fault"
    if name in ("setup and adjustments", "заміна інструменту"):
        return "setup"
    return "idle"


def demo_journal(env, install_ts):
    """R-27 п. 4: позначити журнал часу `demo`, простої з записів втрат (нових записів журналу — 0)."""
    res = {"timelog_marked": 0, "downtimes_created": 0, "downtimes_open": 0, "requests_linked": 0}
    cr = env.cr
    cr.execute(
        "UPDATE mrp_workcenter_productivity SET td_source = 'demo' "
        "WHERE td_source = 'operator' AND COALESCE(td_auto, false) = false AND td_downtime_id IS NULL "
        "AND create_date < %s",
        (install_ts,),
    )
    res["timelog_marked"] = cr.rowcount
    env["mrp.workcenter.productivity"].invalidate_model(["td_source"])
    Productivity = env["mrp.workcenter.productivity"].with_context(active_test=False)
    Downtime = env["td.downtime"].with_context(tracking_disable=True)
    recs = Productivity.search(
        [
            ("td_source", "=", "demo"),
            ("td_downtime_id", "=", False),
            ("workorder_id", "=", False),
            ("loss_type", "in", ("availability", "quality")),
        ],
        order="date_start, id",
    )
    for rec in recs:
        machine = rec.workcenter_id.td_machine_ids[:1]
        if not machine:
            continue
        is_open = not rec.date_end
        if is_open and Downtime.search_count([("machine_id", "=", machine.id), ("date_end", "=", False)]):
            continue
        dt = Downtime.create(
            {
                "machine_id": machine.id,
                "date_start": rec.date_start,
                "date_end": rec.date_end or False,
                "state_kind": _state_kind(rec.loss_id),
                "loss_id": rec.loss_id.id,
                "reason_source": "demo",
                "reason_state": "confirmed",
                "ppt_min": 0.0 if is_open else rec.duration,
            }
        )
        rec.td_downtime_id = dt
        res["downtimes_created"] += 1
        if not is_open:
            continue
        res["downtimes_open"] += 1
        upd = {"state": "fault", "state_since": rec.date_start, "current_downtime_id": dt.id}
        request = (
            env["maintenance.request"].search(
                [
                    ("equipment_id", "=", machine.equipment_id.id),
                    ("maintenance_type", "=", "corrective"),
                    ("stage_id.done", "=", False),
                ],
                order="id desc",
                limit=1,
            )
            if machine.equipment_id
            else env["maintenance.request"]
        )
        if request:
            dt.maintenance_request_id = request
            res["requests_linked"] += 1
        machine.with_context(tracking_disable=True).write(upd)
    return res


# --- крок 7 + керування -------------------------------------------------------------------------------------
def report(env, rep):
    """§5.3 крок 7: `migration_report` = JSON усіх лічильників."""
    env["ir.config_parameter"].sudo().set_param(REPORT_KEY, json.dumps(rep, ensure_ascii=False, sort_keys=True))
    return rep


def _previous_install_ts(env):
    raw = env["ir.config_parameter"].sudo().get_param(REPORT_KEY, "{}")
    try:
        value = json.loads(raw or "{}").get("install_ts")
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S") if value else None
    except (ValueError, AttributeError, TypeError):
        return None


def run_migration(env):
    """Кроки 0–7 (§5.3); ідемпотентна. Повертає звіт (`state`: `done` | `partial` | `skipped`)."""
    if not env.su and not env.user.has_group("td_factory3d.group_td_admin"):
        raise AccessError("Запускати міграцію може лише адміністратор «Завод 3D».")
    env = env(su=True)
    # Позначка «до установки»: перший запуск — зараз; повтор (кнопка) — той самий момент (записи модуля не стають demo).
    install_ts = _previous_install_ts(env) or fields.Datetime.now()
    rep = {name: 0 for name in COUNTERS}
    rep["timelog_created"] = 0
    state = "done"
    for step in (params, losses, sheets, machines, signals, stacks):
        res = step(env) or {}
        rep.update(res)
        _logger.info("machine_connect: крок %s: %s", step.__name__, res)
    try:
        with env.cr.savepoint():
            rep.update(demo_journal(env, install_ts))
    except Exception:
        _logger.exception("machine_connect: крок demo_journal не виконано")
        state = "partial"
    rep.update(
        ts=fields.Datetime.to_string(fields.Datetime.now()),
        install_ts=fields.Datetime.to_string(install_ts),
        state=state,
    )
    return report(env, rep)


def post_init_hook(env):
    run_migration(env)


def uninstall_hook(env):
    """§5.4: крони модуля неактивні, параметри `td.machine_connect.%` видалено; сигнали, джерела — лишаються."""
    env = env(su=True)
    cron_ids = env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "ir.cron")]).mapped("res_id")
    env["ir.cron"].with_context(active_test=False).browse(cron_ids).exists().write({"active": False})
    env["ir.config_parameter"].search([("key", "=like", P + "%")]).unlink()
