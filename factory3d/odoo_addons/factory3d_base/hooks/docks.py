"""Крок 1 post_init_hook: ворота зі scene_docks.csv (SPEC §5.3, R-10, Додаток D)."""
import logging

from odoo import Command

from .codes import read_rows

_logger = logging.getLogger('odoo.addons.factory3d_base.hooks')

DOCK_WIDTH_M = 3.4
DOCK_HEIGHT_M = 4.5


def _categories(env, names):
    Categ = env['product.category']
    ids = []
    for name in names:
        found = Categ.search([('name', '=', name)])
        if not found:
            _logger.warning("Категорію товарів «%s» для воріт не знайдено", name)
        ids += found.ids
    return ids


def register(env):
    """Прив'язати ворота до локацій за barcode, зареєструвати як доки; повертає лічильники."""
    Loc = env['stock.location']
    res = {'docks': 0, 'in_type.dock_ids': 0, 'out_type.dock_ids': 0}
    rows = read_rows('scene_docks.csv')
    docks = Loc
    missing = []
    for row in rows:
        loc = Loc.search([('barcode', '=', row['barcode'])], limit=1)
        if not loc:
            missing.append(row['barcode'])
            continue
        vals = {
            'f3d_code': row['code'],
            'f3d_alias': row.get('alias') or False,
            'f3d_kind': 'dock',
            'f3d_side': row['side'],
            'f3d_dock_no': int(row['no']),
            'f3d_x': float(row['x']),
            'f3d_y': float(row['y']),
            'f3d_dock_width_m': DOCK_WIDTH_M,
            'f3d_dock_height_m': DOCK_HEIGHT_M,
            'f3d_accepts': [Command.set(_categories(env, [n for n in (row.get('accepts') or '').split(';') if n]))],
        }
        loc.write(vals)
        loc.f3d_register_dock()
        docks |= loc
        res['docks'] += 1
    if missing and docks:
        _logger.warning("Локацій воріт не знайдено за barcode: %s", ', '.join(missing))
    elif missing:
        _logger.info("Локацій воріт у базі немає (чиста база): воріт 0")
    for wh in docks.mapped('warehouse_id'):
        west = docks.filtered(lambda d: d.warehouse_id == wh and d.f3d_side == 'west')
        east = docks.filtered(lambda d: d.warehouse_id == wh and d.f3d_side == 'east')
        if west and wh.in_type_id:
            wh.in_type_id.sudo().dock_ids = [Command.set(west.ids)]
            res['in_type.dock_ids'] += len(west)
        if east and wh.out_type_id:
            wh.out_type_id.sudo().dock_ids = [Command.set(east.ids)]
            res['out_type.dock_ids'] += len(east)
    _logger.info("Крок 1 docks: %s", res)
    return res
