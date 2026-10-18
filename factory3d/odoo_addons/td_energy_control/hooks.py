"""post_init_hook / uninstall_hook (SPEC §1, §5.6, R-61, R-66).

Видалення модуля видаляє його дані як у будь-якого модуля Odoo: архівних таблиць немає (D-45).
"""

import csv
import io
import json
import logging

from odoo.tools import file_open

_logger = logging.getLogger(__name__)

MODULE = "td_energy_control"
PARAM = "td.energy_control."
FLAGS = ("write_enabled", "automation_enabled", "remote_switching_enabled")
SOURCES = ("MB-U73-SWB-CMD", "ENERGY-CTL")


def _rows(name):
    with file_open("%s/data/%s" % (MODULE, name), "rb") as f:
        return list(csv.DictReader(io.StringIO(f.read().decode("utf-8"), newline="")))


def _internal(env):
    return env(su=True, context=dict(env.context, td_energy_control_internal=True, tracking_disable=True))


# --- 5.6: джерела й сигнали ---------------------------------------------------------------------------------------
def _load_sources_signals(env):
    """Ідемпотентно: 2 джерела і 36 сигналів `energy_control`; наявні записи не змінюються."""
    env = _internal(env)
    collector = env.ref("td_telemetry.collector_main")
    Source = env["td.source"].with_context(active_test=False)
    Signal = env["td.signal"].with_context(active_test=False)
    by_code = {
        s.code: s for s in Source.search([("code", "in", [r["code"] for r in _rows("energy_control_sources.csv")])])
    }
    for row in _rows("energy_control_sources.csv"):
        if row["code"] in by_code:
            continue
        equipment = env["maintenance.equipment"].search_f3d(row["equipment"]) if row["equipment"] else None
        by_code[row["code"]] = Source.create(
            {
                "code": row["code"],
                "name": row["name"],
                "type": row["type"],
                "collector_id": collector.id,
                "params": json.loads(row["params"]) if row["params"] else {},
                "module": "energy_control",
                "equipment_id": equipment.id if equipment else False,
                "read_enabled": True,
                "write_enabled": False,
            }
        )
    rows = _rows("energy_control_signals.csv")
    have = set(Signal.search([("code", "in", [r["code"] for r in rows])]).mapped("code"))
    to_create = []
    for row in rows:
        if row["code"] in have:
            continue
        to_create.append(
            {
                "code": row["code"],
                "name": row["name"],
                "quantity": row["quantity"],
                "kind": row["kind"],
                "unit": row["unit"] or False,
                "source_id": by_code[row["source"]].id,
                "address": json.loads(row["address"]) if row["address"] else {},
                "period_s": int(row["period_s"]),
                "store_period_s": int(row["store_period_s"]),
                "decimals": int(row["decimals"]),
                "states": json.loads(row["states"]) if row["states"] else False,
                "viewer_visible": row["viewer_visible"] in ("1", "True", "true"),
                "module": "energy_control",
                "origin": "module",
                "write_enabled": False,
            }
        )
    if to_create:
        Signal.create(to_create)
    return len(rows)


# --- 5.2…5.5: початкові дані ----------------------------------------------------------------------------------------
def _seed_defaults(env):
    """Прив'язка сигналів до сценаріїв і пріоритетів, ручні слоти «Зарядна станція», перший план дня, стан."""
    env = _internal(env)
    env["td.energy.control.state"].get()
    Signal = env["td.signal"].with_context(active_test=False)
    for sc in env["td.energy.scenario"].search([]):
        if not sc.state_signal_id:
            sig = Signal.search([("code", "=", "energy_control/auto/%s/state" % sc.code)], limit=1)
            sc.state_signal_id = sig.id
    env["td.energy.shed.item"].search([("signal_id", "=", False)])._td_link_signal()
    Slot = env["td.energy.schedule.slot"]
    if not Slot.search_count([("resource", "=", "charging"), ("source", "=", "manual")]):
        Slot.create(
            [
                {"resource": "charging", "time_from": 0.0, "time_to": 6.0, "mode": "charge", "label": "заряд",
                 "source": "manual", "weekdays": "1111111"},
                {"resource": "charging", "time_from": 22.0, "time_to": 24.0, "mode": "charge", "label": "заряд",
                 "source": "manual", "weekdays": "1111111"},
            ]
        )  # fmt: skip
    try:
        with env.cr.savepoint():
            Slot._td_plan_all()
    except Exception:  # план не повинен ламати встановлення
        _logger.exception("td_energy_control: перший план дня")


def _bump_config(env):
    env = _internal(env)
    env["td.energy.control.state"].bump()


def post_init_hook(env):
    n = _load_sources_signals(env)
    _seed_defaults(env)
    _bump_config(env)
    _logger.info("td_energy_control: встановлено, сигналів %d, прапори запису вимкнені", n)


# --- R-61: стенд -------------------------------------------------------------------------------------------------
def _td_enable_stand(env):
    """Вмикає всі запобіжники й дозволи запису для стенда (вручну через `odoo-bin shell`, НЕ з post_init_hook)."""
    env = _internal(env)
    icp = env["ir.config_parameter"].sudo()
    changes = []

    def setp(key, value="True"):
        if icp.get_param(key) != value:
            icp.set_param(key, value)
            changes.append("%s=%s" % (key, value))

    setp("td.telemetry.write_enabled")
    for flag in FLAGS:  # у т.ч. D-46 remote_switching_enabled
        setp(PARAM + flag)
    Source = env["td.source"].with_context(active_test=False)
    Signal = env["td.signal"].with_context(active_test=False)
    for src in Source.search([("code", "in", list(SOURCES))]):
        if not src.write_enabled:
            src.write_enabled = True
            changes.append("source %s" % src.code)
    for sig in Signal.search([("module", "=", "energy_control")]):
        writable = bool((sig.address or {}).get("write")) or sig.code == "energy_control/intent"
        if writable and not sig.write_enabled:
            sig.write_enabled = True
            changes.append("signal %s" % sig.code)
    from .tools import config_builder

    bms = config_builder.bms_targets(env)
    codes = set()
    for group in bms.values():
        for items in group.values():
            for item in items:
                codes |= {item.get("mode_signal"), item.get("sp_night_signal"), item.get("scene_signal")}
    codes.discard(None)
    if codes:
        setp("td.bms.write_enabled")
        for sig in Signal.search([("code", "in", list(codes))]):
            if not sig.write_enabled:
                sig.write_enabled = True
                changes.append("signal %s" % sig.code)
            if sig.source_id and not sig.source_id.write_enabled:
                sig.source_id.write_enabled = True
                changes.append("source %s" % sig.source_id.code)
    return changes


# --- R-66: видалення (без архівних таблиць, D-45) --------------------------------------------------------------
def uninstall_hook(env):
    """Прибирає сигнали й джерела `energy_control`/`energy_ctl`, крони й параметри; скидає прапори. Дані моделей
    модуля видаляє сам Odoo разом із моделями. Збирач після видалення отримує 404 на `/td/energy/automation/*` і
    повертає пристрої в автоматичний режим сторожовими таймерами контролера (R-53 №7)."""
    env = env(su=True, context=dict(env.context, tracking_disable=True))
    icp = env["ir.config_parameter"].sudo()
    for flag in FLAGS:
        icp.set_param(PARAM + flag, "False")
    env["td.signal"].with_context(active_test=False).search([("module", "=", "energy_control")]).unlink()
    sources = (
        env["td.source"]
        .with_context(active_test=False)
        .search(["|", ("module", "=", "energy_control"), ("type", "=", "energy_ctl")])
    )
    sources.unlink()
    env["ir.cron"].with_context(active_test=False).search(
        [
            (
                "id",
                "in",
                env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "ir.cron")]).mapped("res_id"),
            )
        ]
    ).unlink()
    icp.search([("key", "=like", PARAM + "%")]).unlink()
