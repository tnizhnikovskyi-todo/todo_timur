import csv
import json
import logging

from odoo import fields
from odoo.tools import file_open

from .tools import params as P

_logger = logging.getLogger('odoo.addons.td_access.hooks')

KEY_ENV = 'td.base.environment'
CSV_PATH = 'td_access/data/scene_home_zones.csv'
EQUIPMENT_CODES = {'device_acr_in': 'TURNSTILES', 'device_acr_elec': 'ACCESS', 'device_acr_chg': 'ACCESS',
                   'device_acr_paint': 'ACCESS', 'device_acr_srv': 'ACCESS'}
XMLID = 'td_access.%s'


def _server(env):
    server = env.ref(XMLID % 'server_biostar_sim', raise_if_not_found=False)
    return server or env['td.access.server'].search([('active', '=', True)], limit=1)


def _attendance_snapshot(env):
    rows = env['hr.attendance'].sudo().search_read(
        [], ['employee_id', 'check_in', 'check_out', 'in_mode', 'out_mode'], order='id')
    return {r['id']: (r['employee_id'], r['check_in'], r['check_out'], r['in_mode'], r['out_mode']) for r in rows}


def _step_params(env):
    """Крок 1: read_enabled, якщо параметра немає: True для середовища test, інакше False."""
    icp = env['ir.config_parameter'].sudo()
    if icp.search_count([('key', '=', P.PREFIX + 'read_enabled')]):
        return {'read_enabled_set': 0}
    environment = icp.get_param(KEY_ENV, 'prod')
    P.set_param(env, 'read_enabled', 'True' if environment == 'test' else 'False')
    return {'read_enabled_set': 1}


def _step_server(env):
    """Крок 2: сервер-емулятор без перевірки TLS на тестовому середовищі."""
    server = env.ref(XMLID % 'server_biostar_sim', raise_if_not_found=False)
    if server and env['ir.config_parameter'].sudo().get_param(KEY_ENV) == 'test' and server.verify_ssl:
        server.sudo().write({'verify_ssl': False})
    return {'servers': env['td.access.server'].sudo().search_count([])}


def _step_equipment(env):
    """Крок 3: пристрої -> обладнання (лише порожнє equipment_id)."""
    bound = 0
    devices = env['td.access.device'].sudo()
    for xmlid, code in EQUIPMENT_CODES.items():
        device = env.ref(XMLID % xmlid, raise_if_not_found=False)
        if not device or device.equipment_id:
            continue
        equipment = env['maintenance.equipment'].sudo().search_f3d(code)
        if not equipment:
            _logger.warning("Обладнання %s для пристрою %s не знайдено", code, device.code)
            continue
        device.sudo().write({'equipment_id': equipment.id})
        bound += 1
    return {'devices': devices.search_count([]), 'doors': env['td.access.door'].sudo().search_count([]),
            'equipment_bound': bound}


def _step_links(env):
    """Крок 4: зв'язки «користувач BioStar ↔ працівник» за бейджем."""
    server = _server(env)
    if not server:
        return {'links': 0}
    Link = env['td.access.user.link'].sudo().with_context(active_test=False)
    taken_users = set(Link.search([('server_id', '=', server.id)]).mapped('biostar_user_id'))
    taken_emps = set(Link.search([('server_id', '=', server.id), ('employee_id', '!=', False)]).employee_id.ids)
    created = 0
    for emp in env['hr.employee'].sudo().search([('active', '=', True), ('barcode', '!=', False)], order='id'):
        barcode = emp.barcode
        if not P.BSID_RE.match(barcode) or barcode in taken_users or emp.id in taken_emps:
            continue
        Link.create({'server_id': server.id, 'biostar_user_id': barcode, 'employee_id': emp.id,
                     'match': 'barcode', 'synced': False})
        taken_users.add(barcode)
        taken_emps.add(emp.id)
        created += 1
    return {'links': created}


def _csv_zones():
    with file_open(CSV_PATH) as fh:
        return {row['code']: row['zone'] for row in csv.DictReader(fh)}


def _step_home_zones(env):
    """Крок 5: домашні зони (лише порожні)."""
    Workcenter = env['mrp.workcenter'].sudo()
    Zone = env['td.zone'].sudo()
    csv_zones = _csv_zones()
    res = {'home_zones': 0, 'from_workcenter': 0, 'from_csv': 0, 'home_zone_missing': 0}
    for emp in env['hr.employee'].sudo().search([('active', '=', True), ('td_home_zone_id', '=', False)], order='id'):
        zone = Zone.browse()
        code = emp.td_code or ''
        if code.startswith('OP-'):
            zone = Workcenter.search_f3d(code[3:]).td_zone_id
        if not zone and 'employee_ids' in Workcenter._fields:
            zone = Workcenter.search([('employee_ids', 'in', emp.id), ('td_zone_id', '!=', False)],
                                     order='id', limit=1).td_zone_id
        if zone:
            res['from_workcenter'] += 1
        elif code in csv_zones:
            zone = Zone.search_f3d(csv_zones[code])
            if zone:
                res['from_csv'] += 1
        if zone:
            emp.write({'td_home_zone_id': zone.id})
            res['home_zones'] += 1
        else:
            res['home_zone_missing'] += 1
    return res


def _step_presence(env):
    """Крок 6 (A-22): початкова присутність за відкритими відмітками; відмітки не змінюються."""
    seeded = 0
    open_atts = env['hr.attendance'].sudo().search([('check_out', '=', False)], order='check_in')
    for att in open_atts:
        emp = att.employee_id
        if emp.td_access_present or not emp.active:
            continue
        emp.write({'td_access_present': True, 'td_access_zone_id': emp.td_home_zone_id.id,
                   'td_access_zone_since': att.check_in, 'td_access_last_in': att.check_in})
        seeded += 1
    return {'presence_seeded': seeded}


def run_all(env):
    """Кроки 1–8 (SPEC §5.3); ідемпотентно; повертає звіт."""
    env = env(su=True)
    before = _attendance_snapshot(env)
    report = {}
    for name, step in (('параметри', _step_params), ('сервер', _step_server), ('обладнання', _step_equipment),
                       ('зв\'язки', _step_links), ('домашні зони', _step_home_zones),
                       ('початкова присутність', _step_presence)):
        result = step(env)
        report.update(result)
        _logger.info("СКУД, хук, крок «%s»: %s", name, result)
    after = _attendance_snapshot(env)
    touched = sum(1 for k, v in before.items() if after.get(k) != v) + len(set(after) - set(before))
    if touched or len(before) != len(after):
        raise ValueError("Хук СКУД змінив відмітки Відвідування: %d" % touched)
    report['attendances_touched'] = touched
    report['attendances_total'] = len(after)
    badges = env['hr.employee'].search_count([('active', '=', True), ('barcode', '!=', False)])
    if not badges:
        state = 'skipped'
    elif env['td.access.device'].search_count([('equipment_id', '!=', False)]) < 5 or report['home_zone_missing'] > 0:
        state = 'partial'
    else:
        state = 'done'
    report['migration_state'] = state
    P.set_param(env, 'migration_state', state)
    P.set_param(env, 'migration_report', json.dumps(dict(report, ts=fields.Datetime.to_string(fields.Datetime.now())),
                                                    ensure_ascii=False))
    _logger.info("СКУД, хук: підсумок %s", report)
    return report


def post_init_hook(env):
    run_all(env)


def uninstall_hook(env):
    """SPEC §5.4: параметри td.access.*; решту прибирає стандартна деінсталяція.

    Візити і картки — першими: ``visitor.server_id`` (required) і ``card.server_id`` (``ondelete='restrict'``, SPEC:
    сервер із картками користувач не видалить) блокують ``DELETE`` сервера, тож стандартна деінсталяція, що знищує
    сервер із демо-даних, падала б на FK (ERROR у лозі). Хук виконується до ``module_uninstall``, моделі ще в реєстрі.
    """
    env['td.access.visitor'].sudo().with_context(active_test=False, f3d_housekeeping=True).search([]).unlink()
    env['td.access.card'].sudo().with_context(active_test=False).search([]).unlink()
    env['ir.config_parameter'].sudo().search([('key', '=like', 'td.access.%')]).unlink()
