"""Параметри factory3d.access.* і регулярні вирази R-01 (SPEC §5.1)."""
import logging
import re

_logger = logging.getLogger(__name__)

PREFIX = "factory3d.access."

CODE_RE = re.compile(r'^[A-Z0-9]+(-[A-Z0-9]+)*$')
BSID_RE = re.compile(r'^[0-9A-Za-z_\-]{1,64}$')
URL_RE = re.compile(r'^https?://[A-Za-z0-9.\-]+(:[0-9]{1,5})?/?$')
CARD_RE = re.compile(r'^[0-9]{1,32}$')


def get_str(env, key, default=''):
    return env['ir.config_parameter'].sudo().get_param(PREFIX + key, default)


def get_flag(env, key):
    return get_str(env, key, 'False') in ('True', 'true', '1')


def get_int(env, key, default, lo=None, hi=None):
    raw = get_str(env, key, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = None
    if value is None or (lo is not None and value < lo) or (hi is not None and value > hi):
        _logger.warning("Параметр factory3d.access.%s=%r поза межами, взято %s", key, raw, default)
        return default
    return value


def set_param(env, key, value):
    env['ir.config_parameter'].sudo().set_param(PREFIX + key, value)
