"""Крок 1 post_init_hook: ворота зі scene_docks.csv (SPEC §5.3, R-10, Додаток D)."""
import logging

from odoo import Command

from .codes import read_rows

_logger = logging.getLogger('odoo.addons.td_factory3d.hooks')

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
            'td_code': row['code'],
            'td_alias': row.get('alias') or False,
            'td_kind': 'dock',
            'td_side': row['side'],
            'td_dock_no': int(row['no']),
            'td_x': float(row['x']),
            'td_y': float(row['y']),
            'td_dock_width_m': DOCK_WIDTH_M,
            'td_dock_height_m': DOCK_HEIGHT_M,
            'td_accepts': [Command.set(_categories(env, [n for n in (row.get('accepts') or '').split(';') if n]))],
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
        wh_docks = docks.filtered(lambda d, wh=wh: d.warehouse_id == wh)
        west = wh_docks.filtered(lambda d: d.td_side == 'west')
        east = wh_docks.filtered(lambda d: d.td_side == 'east')
        if west and wh.in_type_id:
            wh.in_type_id.sudo().dock_ids = [Command.set(west.ids)]
            res['in_type.dock_ids'] += len(west)
        if east and wh.out_type_id:
            wh.out_type_id.sudo().dock_ids = [Command.set(east.ids)]
            res['out_type.dock_ids'] += len(east)
    _logger.info("Крок 1 docks: %s", res)
    return res
