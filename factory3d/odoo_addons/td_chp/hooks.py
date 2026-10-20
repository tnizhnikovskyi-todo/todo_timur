"""Хуки модуля: `post_init` (R-14 — карта сигналів `chp/…`), `uninstall_hook` (лише крони й параметри)."""

import logging

from .tools import signals

_logger = logging.getLogger(__name__)
CRON_XMLIDS = ("cron_td_chp_expire", "cron_td_chp_stale", "cron_td_chp_maintenance", "cron_td_chp_gc")


def post_init(env):
    """R-14, ідемпотентно: немає сигналу за `code` → створити (`origin='module'`, `source_id`, `equipment_id`);
    є → адресу, тип, множник, одиницю, період і пороги не чіпати (правки інженера зберігаються)."""
    unit = env.ref("td_chp.unit_chp", raise_if_not_found=False)
    if not unit:
        return
    if not unit.equipment_id:
        eq = env["maintenance.equipment"].sudo().search([("td_code", "=", unit.code)], limit=1)
        if eq:
            unit.equipment_id = eq
    res = signals.sync_map(env, unit)
    _logger.info("td_chp: карта сигналів %s", res)
    return res


def uninstall_hook(env):
    """Прибирає лише крони й параметри модуля; журнал, команди й сигнали не чіпає."""
    for name in CRON_XMLIDS:
        cron = env.ref("td_chp." + name, raise_if_not_found=False)
        if cron:
            cron.unlink()
    env["ir.config_parameter"].sudo().search([("key", "=like", "td.chp.%")]).unlink()
