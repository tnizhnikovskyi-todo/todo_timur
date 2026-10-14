"""Хуки установки/видалення factory3d_base (SPEC §5.3, §5.4)."""
import json
import logging

from odoo import fields

from . import batches, codes, docks, passports, x_fields, zones

_logger = logging.getLogger('odoo.addons.factory3d_base.hooks')

PARAM_STATE = 'factory3d.base.migration_state'
PARAM_REPORT = 'factory3d.base.migration_report'


def _step(report, name, func, env, *args):
    result = func(env, *args)
    report[name] = result
    _logger.info("Крок %s: %s", name, result)
    return result


def write_report(env, report):
    """Крок 11: migration_state (skipped/partial/done) і migration_report (JSON з ts)."""
    migrate = report.get('batches.migrate') or {}
    drop = report.get('x_fields.drop_demo') or {}
    verify = report.get('batches.verify') or {}
    keep = env['ir.config_parameter'].sudo().get_param('factory3d.base.keep_x_fields') == 'True'
    if migrate.get('skipped'):
        state = 'skipped'
    elif verify.get('mismatches') or drop.get('blocked_views') or keep:
        state = 'partial'
    else:
        state = 'done'
    report['migration_state'] = state
    report['ts'] = fields.Datetime.to_string(fields.Datetime.now())
    params = env['ir.config_parameter'].sudo()
    params.set_param(PARAM_STATE, state)
    params.set_param(PARAM_REPORT, json.dumps(report, ensure_ascii=False, default=str))
    _logger.info("Крок 11: migration_state=%s", state)
    return state


def run_all(env):
    """Виконати кроки 1–11 і записати звіт; повертає словник звіту."""
    report = {}
    _step(report, 'docks.register', docks.register, env)
    _step(report, 'codes.locations', codes.locations, env)
    _step(report, 'codes.workcenters', codes.workcenters, env)
    _step(report, 'codes.employees', codes.employees, env)
    _step(report, 'codes.equipment', codes.equipment, env)
    _step(report, 'passports.link', passports.link, env)
    _step(report, 'zones.bind', zones.bind, env)
    _step(report, 'batches.migrate', batches.migrate, env)
    verify = {'mismatches': [], 'moves_changed': 0}
    if not report['batches.migrate'].get('skipped'):
        verify = _step(report, 'batches.verify', batches.verify, env)
    _step(report, 'x_fields.drop_demo', x_fields.drop_demo, env, verify['mismatches'])
    write_report(env, report)
    return report


def post_init_hook(env):
    run_all(env)


def uninstall_hook(env):
    """§5.4: відновити x_* (якщо дозволено параметром), потім прибрати параметри factory3d.base.*."""
    res = x_fields.restore_on_uninstall(env)
    _logger.info("uninstall: %s", res)
    env['ir.config_parameter'].sudo().search([('key', '=like', 'factory3d.base.%')]).unlink()
