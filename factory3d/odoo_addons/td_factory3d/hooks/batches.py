"""Кроки 8–9 post_init_hook: міграція x_dock/x_truck/x_vehicle у пакети (R-11…R-13)."""

import logging
import re

from .codes import is_valid_code
from .x_fields import read_manual_field

_logger = logging.getLogger("odoo.addons.td_factory3d.hooks")

SNAPSHOT_KEY = "f3d_moves_snapshot"


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _read_x(env):
    return (
        read_manual_field(env, "stock.picking", "x_dock"),
        read_manual_field(env, "stock.picking", "x_truck"),
        read_manual_field(env, "stock.picking", "x_vehicle"),
    )


def _snapshot(env, picking_ids):
    env.cr.execute(
        "SELECT id, location_id, location_dest_id, state FROM stock_move WHERE picking_id = ANY(%s) ORDER BY id",
        (list(picking_ids),),
    )
    return env.cr.fetchall()


def _find_truck_batch(env, truck, picking):
    Batch = env["stock.picking.batch"]
    data = env["ir.model.data"].search(
        [("module", "=", "factory3d"), ("model", "=", "stock.picking.batch"), ("name", "=", "batch_" + _slug(truck))],
        limit=1,
    )
    batch = Batch.browse(data.res_id).exists() if data else Batch
    if not batch:
        batch = Batch.search([("description", "=like", truck + " %")], limit=1)
    return batch or picking.batch_id


def migrate(env):
    """Крок 8: згрупувати документи з x_* у пакети; повертає лічильники або {'skipped': True}."""
    x_dock, x_truck, x_vehicle = _read_x(env)
    ids = sorted(set(x_dock) | set(x_truck) | set(x_vehicle))
    if not ids:
        _logger.info("Крок 8 batches: полів x_* немає або вони порожні — skipped")
        return {"skipped": True}
    env.cr.cache[SNAPSHOT_KEY] = _snapshot(env, ids)
    Picking, Batch = env["stock.picking"], env["stock.picking.batch"]
    Loc, Equipment = env["stock.location"], env["maintenance.equipment"]
    truck_cat = env.ref("factory3d.vehcat_truck", raise_if_not_found=False)
    res = {"batches_updated": 0, "batches_created": 0, "pickings_attached": 0, "pickings_total_in_batches": 0}
    cache = {}  # x_truck -> batch
    attach, created, updated = [], set(), set()
    for picking in Picking.browse(ids):
        dock_code, truck, vehicle = x_dock.get(picking.id), x_truck.get(picking.id), x_vehicle.get(picking.id)
        batch = None
        if truck:
            batch = cache.get(truck) or _find_truck_batch(env, truck, picking)
            if batch:
                vals = {}
                if batch.td_truck != truck:
                    vals["td_truck"] = truck
                if not batch.td_code and is_valid_code(truck):
                    vals["td_code"] = truck
                if vehicle and not batch.td_vehicle_id:
                    equipment = Equipment.search_f3d(vehicle)
                    if equipment:
                        vals["td_vehicle_id"] = equipment.id
                if vals:
                    batch.write(vals)
                    if batch.id not in created:
                        updated.add(batch.id)
        elif picking.batch_id:
            batch = picking.batch_id
        if not batch:
            batch = Batch.create(_batch_vals(env, picking, dock_code, truck, vehicle, truck_cat, Loc, Equipment))
            created.add(batch.id)
        if truck:
            cache[truck] = batch
        if not picking.batch_id:
            attach.append((batch.id, picking.id))
    for bid, pid in attach:
        env.cr.execute("UPDATE stock_picking SET batch_id = %s WHERE id = %s AND batch_id IS NULL", (bid, pid))
        res["pickings_attached"] += env.cr.rowcount
    Picking.invalidate_model(["batch_id"])
    Batch.invalidate_model(["picking_ids", "state", "scheduled_date"])
    for batch in Batch.browse(created):
        if all(p.state in ("done", "cancel") for p in batch.picking_ids):
            batch._compute_state()
        elif any(p.state == "draft" for p in batch.picking_ids):
            batch.state = "in_progress"
        else:
            batch.action_confirm()
    res["batches_created"] = len(created)
    res["batches_updated"] = len(updated)
    res["pickings_total_in_batches"] = len(Picking.browse(ids).filtered("batch_id"))
    _logger.info("Крок 8 batches: %s", res)
    return res


def _batch_vals(env, picking, dock_code, truck, vehicle, truck_cat, Loc, Equipment):
    vals = {
        "picking_type_id": picking.picking_type_id.id,
        "scheduled_date": picking.scheduled_date,
        "user_id": picking.user_id.id,
        "description": " · ".join(filter(None, [truck, dock_code, vehicle])),
    }
    if truck:
        vals["td_truck"] = truck
        if is_valid_code(truck):
            vals["td_code"] = truck
    if dock_code:
        dock = Loc.search_f3d(dock_code)
        if dock:
            vals["dock_id"] = dock.id
        if truck_cat and "vehicle_category_id" in env["stock.picking.batch"]._fields:
            vals["vehicle_category_id"] = truck_cat.id
    if vehicle:
        equipment = Equipment.search_f3d(vehicle)
        if equipment:
            vals["td_vehicle_id"] = equipment.id
    return vals


def verify(env):
    """Крок 9 (R-13): {'mismatches': [...], 'moves_changed': n}."""
    x_dock, x_truck, x_vehicle = _read_x(env)
    ids = sorted(set(x_dock) | set(x_truck) | set(x_vehicle))
    mismatches = []
    for picking in env["stock.picking"].browse(ids):
        batch = picking.batch_id
        if picking.id in x_dock and batch.dock_id.td_code != x_dock[picking.id]:
            mismatches.append(
                "%s: x_dock=%s, batch.dock=%s" % (picking.name, x_dock[picking.id], batch.dock_id.td_code or None)
            )
        if picking.id in x_truck and batch.td_code != x_truck[picking.id]:
            mismatches.append(
                "%s: x_truck=%s, batch.code=%s" % (picking.name, x_truck[picking.id], batch.td_code or None)
            )
        if picking.id in x_vehicle and batch.td_vehicle_id.td_code != x_vehicle[picking.id]:
            mismatches.append(
                "%s: x_vehicle=%s, batch.vehicle=%s"
                % (picking.name, x_vehicle[picking.id], batch.td_vehicle_id.td_code or None)
            )
    moves_changed = 0
    before = env.cr.cache.get(SNAPSHOT_KEY)
    if before is not None:
        after = _snapshot(env, ids)
        old = {row[0]: row for row in before}
        new = {row[0]: row for row in after}
        moves_changed = sum(1 for mid in old.keys() | new.keys() if old.get(mid) != new.get(mid))
        if moves_changed:
            mismatches.append("рухи документів змінено: %d" % moves_changed)
    res = {"mismatches": mismatches, "moves_changed": moves_changed}
    _logger.info("Крок 9 verify: %s", res)
    return res
