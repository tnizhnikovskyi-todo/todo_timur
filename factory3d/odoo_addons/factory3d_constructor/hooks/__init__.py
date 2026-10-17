"""Хуки установки/видалення factory3d_constructor (SPEC §5.2, §5.3, R-24)."""
import logging

_logger = logging.getLogger('odoo.addons.factory3d_constructor.hooks')

PARAM_PREFIX = 'factory3d.constructor.'
PARAM_PUBLISH = PARAM_PREFIX + 'publish_enabled'


def _step_params(env):
    """Крок 1: publish_enabled за factory3d.base.environment (CB-10): True на test, False на prod."""
    params = env['ir.config_parameter'].sudo()
    if params.get_param(PARAM_PUBLISH) is False:
        environment = params.get_param('factory3d.base.environment') or 'test'
        params.set_param(PARAM_PUBLISH, 'True' if environment == 'test' else 'False')
        return environment
    return None


def post_init_hook(env):
    """Порядок: params → categories → seed → link → baseline → report (R-24). Кроки 2-6 — у наступних комітах."""
    _step_params(env)


def uninstall_hook(env):
    """§5.3: видаляє лише власні ir.config_parameter; записи Odoo й знімки версій лишаються."""
    env['ir.config_parameter'].sudo().search([('key', '=like', PARAM_PREFIX + '%')]).unlink()
