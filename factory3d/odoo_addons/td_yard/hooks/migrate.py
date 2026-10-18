"""Міграція демо-бази й початкове налаштування двору (SPEC §5.3, §5.4, R-24).

Кожен крок — функція ``step(env, ...) -> dict`` лічильників; ідемпотентна, чіпає лише порожні поля або
записи без дублікатів. Журнали не містять персональних даних.
"""

import csv
import io
import json
import logging
import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tools import file_open

from ..tools import params as P

_logger = logging.getLogger("odoo.addons.factory3d_yard.hooks")

KEY_ENV = "factory3d.base.environment"
CSV_PATH = "factory3d_yard/data/f3d_yard_signals.csv"
CALENDAR_NAME = "Зміна 1 (07:00–15:30)"
BATCH_DESC_RE = re.compile(r"^(TRUCK-[A-Z0-9-]+) · (DOCK-[EW]\d)$")
OUT_PLATE = "АА4512КТ"
OUT_CODE = "TRUCK-OUT-1"
OUT_PICKING = "WH/OUT/00413"
OUT_WEIGHT = 21380.0

# (xml-id воріт/ваг, код обладнання, зона, зона камери ставиться окремо)
GATE_LINKS = (("gate_w", "GATE-W", "Z-GATE-W"), ("gate_e", "GATE-E", "Z-GATE-E"))
SCALE_LINK = ("scale_truck", "TRUCK-SCALE", "Z-GATE-E")
CAMERA_EQUIPMENT = "CCTV"

SOURCES = (
    {
        "code": "MB-U86-IO7",
        "name": "ADAM-6060 IO-7 (шлагбауми двору)",
        "type": "modbus_tcp",
        "params": {"host": "iot-sim", "port": 502, "unit": 86, "timeout_s": 2, "retries": 1, "max_block": 32},
        "equipment": "GATE-W",
    },
    {
        "code": "SICS-TRUCK-SCALE",
        "name": "Автоваги АКСІС (SICS)",
        "type": "sics",
        "params": {
            "host": "iot-sim",
            "port": 4001,
            "mode": "stream",
            "period_s": 1,
            "timeout_s": 5,
            "unit": "kg",
            "dialect": "mt_sics",
            "reset_on_connect": True,
        },
        "equipment": "TRUCK-SCALE",
    },
)
HTTP_PUSH_XMLID = "factory3d_telemetry.source_http_push"
COLLECTOR_XMLID = "factory3d_telemetry.collector_main"

PRODUCT_WEIGHTS = (
    ("DSP16-SON", 56.0),
    ("DSP16-WHT", 56.0),
    ("DSP16-ANT", 56.0),
    ("DSP16-WNG", 56.0),
    ("DSP18-CON", 63.0),  # ПРИПУЩЕННЯ: 56 × 18/16 (Q-09)
    ("MDF18-RAW", 70.0),
    ("HDF3-WHT", 12.0),
)


def _ref(env, xmlid):
    return env.ref(xmlid, raise_if_not_found=False)


# ---------------------------------------------------------------- 0
def params(env):
    """Крок 0: read_enabled за середовищем і календар — лише при migration_state == 'pending'."""
    if P.get_str(env, "migration_state") != "pending":
        return {"skipped": 1}
    environment = env["ir.config_parameter"].sudo().get_param(KEY_ENV, "prod")
    P.set_param(env, "read_enabled", "True" if environment == "test" else "False")
    done = {"read_enabled": 1}
    if not int(P.get_str(env, "calendar_id") or 0):
        calendar = env["resource.calendar"].search([("name", "=", CALENDAR_NAME)], limit=1)
        calendar = calendar or env.company.resource_calendar_id
        if calendar:
            P.set_param(env, "calendar_id", calendar.id)
            done["calendar"] = 1
    return done


# ---------------------------------------------------------------- 1
def gates_and_scale(env):
    """Крок 1: обладнання, зони, камери воріт і ваг (лише порожні поля)."""
    Equipment, Zone = env["maintenance.equipment"], env["f3d.zone"]
    res = {"gates": 0, "scales": 0, "linked_equipment": 0, "cameras": 0, "zones": 0}
    camera = Equipment.search_f3d(CAMERA_EQUIPMENT)
    if not camera:
        _logger.warning("Обладнання %s для камер воріт не знайдено", CAMERA_EQUIPMENT)
    items = [(x, "gates") for x in GATE_LINKS] + [(SCALE_LINK, "scales")]
    for (xmlid, eq_code, zone_code), kind in items:
        rec = _ref(env, "factory3d_yard.%s" % xmlid)
        if not rec:
            continue
        res[kind] += 1
        vals = {}
        if not rec.equipment_id:
            eq = Equipment.search_f3d(eq_code)
            if eq:
                vals["equipment_id"] = eq.id
                res["linked_equipment"] += 1
            else:
                _logger.warning("Обладнання %s не знайдено", eq_code)
        if not rec.zone_id:
            zone = Zone.search_f3d(zone_code)
            if zone:
                vals["zone_id"] = zone.id
                res["zones"] += 1
            else:
                _logger.warning("Зону %s не знайдено", zone_code)
        if kind == "gates" and camera and not rec.camera_equipment_id:
            vals["camera_equipment_id"] = camera.id
            res["cameras"] += 1
        if vals:
            rec.write(vals)
    return res


# ---------------------------------------------------------------- 2
def _collector(env):
    collector = _ref(env, COLLECTOR_XMLID)
    return collector or env["f3d.collector"].search([("active", "=", True)], limit=1)


def _csv_rows():
    with file_open(CSV_PATH, "rb") as fh:
        return list(csv.DictReader(io.StringIO(fh.read().decode("utf-8"))))


def _flag(value):
    return str(value).strip() in ("1", "True", "true")


def signals_and_sources(env):
    """Крок 2: джерела й сигнали за кодом (без ir.model.data), прив'язка до воріт і ваг."""
    Source, Signal, Equipment = env["f3d.source"], env["f3d.signal"], env["maintenance.equipment"]
    res = {"sources_created": 0, "sources_updated": 0, "http_push_reused": 0, "signals_created": 0}
    res.update(signals_updated=0, linked=0)
    collector = _collector(env)
    if not collector:
        _logger.warning("Немає жодного колектора: крок signals_and_sources пропущено")
        return {"skipped": 1, **res}
    sources = {}
    for spec in SOURCES:
        eq = Equipment.search_f3d(spec["equipment"])
        vals = {
            "name": spec["name"],
            "type": spec["type"],
            "params": spec["params"],
            "module": "yard",
            "collector_id": collector.id,
            "read_enabled": True,
            "write_enabled": False,
            "period_s_default": 1,
        }
        if eq:
            vals["equipment_id"] = eq.id
        src = Source.with_context(active_test=False).search([("code", "=", spec["code"])], limit=1)
        if src:
            src.write(vals)
            res["sources_updated"] += 1
        else:
            src = Source.create(dict(vals, code=spec["code"]))
            res["sources_created"] += 1
        sources[spec["code"]] = src
    push = _ref(env, HTTP_PUSH_XMLID)
    if push and "lpr" in ((push.params or {}).get("routes") or []):
        sources["HTTP-PUSH"] = push
        res["http_push_reused"] = 1
    else:
        _logger.warning("Джерело HTTP-PUSH з маршрутом lpr не знайдено: сигнали LPR без джерела")
    owners = {}
    for row in _csv_rows():
        eq = Equipment.search_f3d(row["equipment"])
        src = sources.get(row["source"])
        warn = row["warn_high"].strip()
        vals = {
            "name": row["name"],
            "kind": row["kind"],
            "unit": row["unit"] or False,
            "equipment_id": eq.id if eq else False,
            "source_id": src.id if src else False,
            "address": json.loads(row["address"]),
            "period_s": int(row["period_s"]),
            "store_period_s": int(row["store_period_s"]),
            "write_enabled": _flag(row["write_enabled"]),
            "warn_high_on": bool(warn),
            "warn_high": float(warn) if warn else 0.0,
            "min_duration_s": int(row["min_duration_s"] or 0),
            "create_request": _flag(row["create_request"]),
            "viewer_visible": _flag(row["viewer_visible"]),
            "module": "yard",
            "scale": 1.0,
            "decimals": 0,
        }
        sig = Signal.with_context(active_test=False).search([("code", "=", row["code"])], limit=1)
        if sig:
            sig.write(vals)
            res["signals_updated"] += 1
        else:
            sig = Signal.create(dict(vals, code=row["code"], origin="catalog"))
            res["signals_created"] += 1
        if row["owner"]:
            owners.setdefault(row["owner"], {})[row["role"] + "_signal_id"] = sig.id
            if src:
                owners[row["owner"]]["source_id"] = src.id
    for xmlid, vals in owners.items():
        rec = _ref(env, "factory3d_yard.%s" % xmlid)
        if rec:
            rec.write(vals)
            res["linked"] += sum(1 for k in vals if k.endswith("_signal_id"))
    return res


# ---------------------------------------------------------------- 3
def product_weights(env):
    """Крок 3: маси еталонних товарів iot_sim (лише нульові)."""
    if not P.get_bool(env, "seed_product_weights"):
        return {"products_weighted": 0}
    n = 0
    for code, weight in PRODUCT_WEIGHTS:
        products = env["product.product"].search([("default_code", "=", code), ("weight", "=", 0)])
        if products:
            products.write({"weight": weight})
            n += len(products)
    return {"products_weighted": n}


# ---------------------------------------------------------------- 4
def carrier_partners(env):
    """Крок 4: перевізники доставки → партнери (лише порожній f3d_partner_id)."""
    res = {"carriers_linked": 0, "unmatched": 0}
    for carrier in env["delivery.carrier"].search([("f3d_partner_id", "=", False)]):
        if carrier.name == "Власний транспорт":
            partner = env.company.partner_id
        else:
            found = env["res.partner"].search([("name", "=", carrier.name), ("is_company", "=", True)])
            partner = found if len(found) == 1 else env["res.partner"]
        if not partner:
            res["unmatched"] += 1
            continue
        carrier.f3d_partner_id = partner
        partner.f3d_is_carrier = True
        res["carriers_linked"] += 1
    return res


# ---------------------------------------------------------------- 5
def _candidate_batches(env):
    """Пакети рейсів: за f3d_code TRUCK-%, інакше — за описом `TRUCK-… · DOCK-…`."""
    Batch = env["stock.picking.batch"]
    batches = Batch.search([("f3d_code", "=like", "TRUCK-%")], order="id")
    if batches:
        return batches, False
    by_desc = Batch
    for batch in Batch.search([("description", "!=", False)], order="id"):
        if BATCH_DESC_RE.match((batch.description or "").strip()):
            by_desc |= batch
    return by_desc, True


def _batch_code(batch):
    if batch.f3d_code:
        return batch.f3d_code
    match = BATCH_DESC_RE.match((batch.description or "").strip())
    return match.group(1) if match else False


def visits_from_batches(env):
    """Крок 5: рейс у стані «Операція» для кожного пакета без рейсів."""
    res = {"visits": 0, "incoming": 0, "outgoing": 0, "with_plate": 0, "by_description": 0}
    batches, by_desc = _candidate_batches(env)
    if not batches:
        return dict(res, skipped=1)
    gate_w = _ref(env, "factory3d_yard.gate_w")
    Visit = env["f3d.yard.visit"]
    for batch in batches:
        if batch.f3d_visit_ids:
            continue
        picks = batch.picking_ids.sorted("name")
        visit_type = batch.picking_type_code if batch.picking_type_code in ("incoming", "outgoing") else "other"
        partner = picks[:1].partner_id.commercial_partner_id
        dcarrier = picks.carrier_id[:1]
        carrier = partner if visit_type == "incoming" else dcarrier.f3d_partner_id
        start = batch.scheduled_date or fields.Datetime.now()
        code = _batch_code(batch)
        vals = {
            "visit_type": visit_type,
            "partner_id": partner.id or False,
            "delivery_carrier_id": dcarrier.id or False,
            "carrier_id": carrier.id or False,
            "batch_id": batch.id,
            "state": "handling",
            "arrived_at": start - timedelta(minutes=20),
            "admitted_at": start - timedelta(minutes=15),
            "at_dock_at": start,
            "handling_start_at": start,
        }
        if gate_w:
            vals["gate_in_id"] = gate_w.id
        if code == OUT_CODE:
            vals["plate"] = OUT_PLATE
            res["with_plate"] += 1
        Visit.create(vals)
        res["visits"] += 1
        res[visit_type] = res.get(visit_type, 0) + 1
        if by_desc:
            res["by_description"] += 1
    return res


# ---------------------------------------------------------------- 6
def bookings_from_batches(env):
    """Крок 6: бронювання за воротами й вікном пакета (рейси без бронювань)."""
    res = {"bookings": 0, "conflicts": 0}
    batches, _by_desc = _candidate_batches(env)
    Booking = env["f3d.yard.booking"].with_context(f3d_yard_sync=True)
    slot_min = P.get_int(env, "slot_default_min")
    for batch in batches:
        dock = batch.dock_id
        if not dock or not batch.scheduled_date:
            continue
        for visit in batch.f3d_visit_ids:
            if visit.booking_ids:
                continue
            vals = {
                "visit_id": visit.id,
                "dock_id": dock.id,
                "slot_start": batch.scheduled_date,
                "slot_end": batch.end_date or batch.scheduled_date + timedelta(minutes=slot_min),
                "source": "migration",
                "state": "confirmed",
            }
            try:
                with env.cr.savepoint():
                    Booking.create(vals)
            except ValidationError:
                Booking.create(dict(vals, state="requested"))
                res["conflicts"] += 1
            res["bookings"] += 1
    return res


# ---------------------------------------------------------------- 7
def weighing_from_card(env):
    """Крок 7: зважування з картки ваг макета (рейс пакета TRUCK-OUT-1)."""
    res = {"weighings": 0}
    scale = _ref(env, "factory3d_yard.scale_truck")
    batch = env["stock.picking.batch"].search([("f3d_code", "=", OUT_CODE)], limit=1)
    visit = batch.f3d_visit_ids[:1]
    if not (scale and visit):
        return res
    if env["f3d.yard.weighing"].search_count([("visit_id", "=", visit.id), ("source", "=", "migration")]):
        return res
    picking = env["stock.picking"].search([("name", "=", OUT_PICKING)], limit=1)
    env["f3d.yard.weighing"].create(
        {
            "scale_id": scale.id,
            "kind": "check",
            "weight_kg": OUT_WEIGHT,
            "source": "migration",
            "visit_id": visit.id,
            "picking_id": picking.id or False,
            "ts": batch.scheduled_date or fields.Datetime.now(),
            "plate": OUT_PLATE,
        }
    )
    res["weighings"] = 1
    return res


# ---------------------------------------------------------------- 8
def report(env, rep):
    """Крок 8: стан і звіт міграції."""
    conflicts = (rep.get("bookings_from_batches") or {}).get("conflicts", 0)
    if (rep.get("visits_from_batches") or {}).get("skipped"):
        state = "skipped"
    elif rep.get("errors") or conflicts:
        state = "partial"
    else:
        state = "done"
    rep["ts"] = fields.Datetime.to_string(fields.Datetime.now())
    P.set_param(env, "migration_state", state)
    P.set_param(env, "migration_report", json.dumps(rep, ensure_ascii=False, default=str))
    return {"state": state}
