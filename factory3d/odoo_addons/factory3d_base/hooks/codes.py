"""Кроки 2–5 post_init_hook: коди сцени з даних Odoo і data-файлів (SPEC §5.3, R-05…R-07, R-21)."""
import csv
import logging
import os
import re

_logger = logging.getLogger('odoo.addons.factory3d_base.hooks')

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
CODE_RE = re.compile(r'^[A-Z0-9]+(-[A-Z0-9]+)*$')  # R-01


def read_csv_rows(name):
    """Рядки data/<name> як список словників."""
    with open(os.path.join(DATA_DIR, name), encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def read_rows(name):
    """Рядки data-файлу; тести підміняють hooks.read_data_file (common.with_data_file)."""
    from odoo.addons.factory3d_base import hooks
    reader = getattr(hooks, 'read_data_file', None) or read_csv_rows
    return reader(name)


def is_valid_code(code):
    return bool(code) and len(code) <= 32 and bool(CODE_RE.match(code))


def employee_table(env):
    """barcode -> код сцени за scene_employee_codes.csv (для hr.employee._f3d_code_from_barcode)."""
    return {r['barcode']: r['f3d_code'] for r in read_rows('scene_employee_codes.csv')}


def _assign(rec, code, what):
    """Записати код, якщо він валідний і вільний у моделі; True — записано."""
    if not is_valid_code(code):
        _logger.debug("%s %s: код %r невалідний — пропуск", what, rec.display_name, code)
        return False
    if rec.search_f3d(code):
        _logger.warning("%s %s: код %s уже зайнятий — пропуск", what, rec.display_name, code)
        return False
    rec.write({'f3d_code': code})
    return True


def locations(env):
    """R-05 (а) код із штрихкоду; R-21 (б) вид і місткість із scene_locations.csv."""
    Loc = env['stock.location']
    res = {'locations': 0, 'kinds': 0, 'capacities': 0}
    for wh in env['stock.warehouse'].search([]):
        candidates = Loc.search([
            ('barcode', '!=', False), ('usage', '=', 'internal'), ('f3d_code', '=', False),
            ('id', 'child_of', wh.view_location_id.id), ('id', '!=', wh.lot_stock_id.id)])
        for loc in candidates:
            if _assign(loc, loc.barcode, "Локація"):
                res['locations'] += 1
    if 'f3d_loc_kind' not in Loc._fields:
        _logger.warning("stock.location.f3d_loc_kind відсутнє — вид і місткість місць пропущено")
        return res
    for row in read_rows('scene_locations.csv'):
        loc = Loc.search_f3d(row['code'])
        if not loc:
            continue
        capacity = int(float(row['capacity'])) if row.get('capacity') else 0
        vals = {'f3d_loc_kind': row['kind'], 'f3d_capacity': capacity}
        if loc.f3d_loc_kind != vals['f3d_loc_kind'] or loc.f3d_capacity != capacity:
            loc.write(vals)
        res['kinds'] += 1
        if capacity > 0:
            res['capacities'] += 1
    return res


def workcenters(env):
    res = {'workcenters': 0}
    for wc in env['mrp.workcenter'].search([('f3d_code', '=', False), ('code', '!=', False)]):
        if _assign(wc, wc.code, "Робочий центр"):
            res['workcenters'] += 1
    return res


def employees(env):
    """R-06: код за таблицею, РЦ або шаблоном OPW<n>; лише для порожніх кодів."""
    WC = env['mrp.workcenter']
    has_link = 'employee_ids' in WC._fields  # у CE поля немає (mrp_workorder)
    res = {'employees': 0}
    for emp in env['hr.employee'].with_context(active_test=False).search(
            [('barcode', '!=', False), ('f3d_code', '=', False)]):
        wc = WC.search([('employee_ids', 'in', emp.id)], order='id', limit=1) if has_link else WC
        code = emp._f3d_code_from_barcode(emp.barcode, wc)
        if code and _assign(emp, code, "Працівник"):
            res['employees'] += 1
    return res


def equipment(env):
    """R-07: serial_no ∈ code → xml-id демо → legacy_serial; пишеться лише порожнім."""
    rows = read_rows('scene_equipment_codes.csv')
    codes = {r['code'] for r in rows}
    by_xmlid = {r['xmlid']: r['code'] for r in rows if r.get('xmlid')}
    by_legacy = {r['legacy_serial']: r['code'] for r in rows if r.get('legacy_serial')}
    Eq = env['maintenance.equipment'].with_context(active_test=False)
    xmlid_of = {d['res_id']: d['name'] for d in env['ir.model.data'].search_read(
        [('module', '=', 'factory3d'), ('model', '=', 'maintenance.equipment'),
         ('name', 'in', list(by_xmlid))], ['name', 'res_id'])}
    res = {'equipment': 0, 'by_serial': 0, 'by_xmlid_or_legacy': 0, 'unmatched': 0}
    for eq in Eq.search([('f3d_code', '=', False)]):
        if eq.serial_no in codes:
            code, how = eq.serial_no, 'by_serial'
        elif eq.id in xmlid_of:
            code, how = by_xmlid[xmlid_of[eq.id]], 'by_xmlid_or_legacy'
        elif eq.serial_no in by_legacy:
            code, how = by_legacy[eq.serial_no], 'by_xmlid_or_legacy'
        else:
            _logger.warning("Обладнання %s (serial_no=%s): код сцени не знайдено",
                            eq.display_name, eq.serial_no)
            res['unmatched'] += 1
            continue
        if _assign(eq, code, "Обладнання"):
            res['equipment'] += 1
            res[how] += 1
    return res
