"""Утиліти міграції manual-полів x_* (CB-11, R-14…R-16) і відновлення при деінсталяції (SPEC §5.4)."""

import logging
import re

_logger = logging.getLogger("odoo.addons.td_factory3d.hooks")

X_NAME_RE = re.compile(r"^x_[a-z0-9_]+$")
STOCK_PICKING_X_FIELDS = [("x_dock", "Ворота (док)"), ("x_truck", "Фура"), ("x_vehicle", "Техніка")]
DEMO_VIEWS = ("factory3d.view_picking_form_dock", "factory3d.view_picking_list_dock")


def _field_exists(env, model, name):
    return bool(env["ir.model.fields"].search_count([("model", "=", model), ("name", "=", name)]))


def read_manual_field(env, model, name):
    """R-14: {record_id: значення} для manual-поля x_*; {} якщо поля немає."""
    if not X_NAME_RE.match(name):
        raise ValueError("Некоректне ім'я manual-поля: %r" % name)
    if not _field_exists(env, model, name):
        return {}
    table = env[model]._table
    env.cr.execute('SELECT id, "%s" FROM %s WHERE "%s" IS NOT NULL AND "%s" <> \'\'' % (name, table, name, name))
    return dict(env.cr.fetchall())


def drop_manual_fields(env, model, names):
    """R-15: видалити manual-поля (Odoo сам прибирає колонки); повертає кількість."""
    fields = env["ir.model.fields"].search(
        [("model", "=", model), ("name", "in", list(names)), ("state", "=", "manual")]
    )
    count = len(fields)
    fields.unlink()
    return count


def restore_manual_fields(env, model, spec):
    """R-16: створити відсутні manual-поля char; spec = [(name, label)]; повертає кількість створених."""
    Fields = env["ir.model.fields"]
    model_id = env["ir.model"]._get_id(model)
    created = 0
    for name, label in spec:
        if not X_NAME_RE.match(name):
            raise ValueError("Некоректне ім'я manual-поля: %r" % name)
        if _field_exists(env, model, name):
            continue
        Fields.create(
            {"model_id": model_id, "name": name, "field_description": label, "ttype": "char", "state": "manual"}
        )
        created += 1
    return created


def drop_demo(env, mismatches=None):
    """Крок 10: прибрати демо-представлення й поля x_*, лише коли звірка чиста й keep_x_fields=False."""
    res = {"views_dropped": 0, "fields_dropped": 0}
    keep = env["ir.config_parameter"].sudo().get_param("td.base.keep_x_fields") == "True"
    if mismatches or keep:
        return res
    for xmlid in DEMO_VIEWS:
        view = env.ref(xmlid, raise_if_not_found=False)
        if view:
            view.unlink()
            res["views_dropped"] += 1
    names = [n for n, _label in STOCK_PICKING_X_FIELDS]
    blocked = []
    for name in names:
        views = env["ir.ui.view"].with_context(active_test=False).search([("arch_db", "ilike", name)])
        blocked += views.mapped("name")
    if blocked:
        _logger.warning("Поля x_* не видалено: на них посилаються представлення %s", sorted(set(blocked)))
        res["blocked_views"] = sorted(set(blocked))
        return res
    res["fields_dropped"] = drop_manual_fields(env, "stock.picking", names)
    return res


def restore_on_uninstall(env):
    """§5.4 кроки 1–3: відновити x_dock/x_truck/x_vehicle і значення з пакетів; повертає лічильники."""
    res = {"fields_restored": 0, "x_dock": 0, "x_truck": 0, "x_vehicle": 0}
    param = env["ir.config_parameter"].sudo().get_param("td.base.uninstall_restore_x_fields")
    if param != "True":
        return res
    res["fields_restored"] = restore_manual_fields(env, "stock.picking", STOCK_PICKING_X_FIELDS)
    cr = env.cr
    cr.execute(
        "UPDATE stock_picking p SET x_dock = l.td_code FROM stock_picking_batch b "
        "JOIN stock_location l ON l.id = b.dock_id WHERE p.batch_id = b.id"
    )
    res["x_dock"] = cr.rowcount
    cr.execute(
        "UPDATE stock_picking p SET x_truck = COALESCE(b.td_code, b.td_truck) "
        "FROM stock_picking_batch b WHERE p.batch_id = b.id "
        "AND (b.td_code IS NOT NULL OR b.td_truck IS NOT NULL)"
    )
    res["x_truck"] = cr.rowcount
    cr.execute(
        "UPDATE stock_picking p SET x_vehicle = e.td_code FROM stock_picking_batch b "
        "JOIN maintenance_equipment e ON e.id = b.td_vehicle_id WHERE p.batch_id = b.id"
    )
    res["x_vehicle"] = cr.rowcount
    return res
