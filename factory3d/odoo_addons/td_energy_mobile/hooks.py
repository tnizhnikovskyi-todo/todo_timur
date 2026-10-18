"""post_init_hook / uninstall_hook (W4_SPEC H.5.3, H.5.4)."""

import logging

from odoo import tools

_logger = logging.getLogger(__name__)

MODULE = "td_energy_mobile"
TEMPLATE_CODE = "TP-GRSH"


def _internal(env):
    return env(su=True, context=dict(env.context, tracking_disable=True))


def _seed_template(env):
    """H.5.3: шаблон `TP-GRSH` завантажує XML `noupdate`; тут лише перевірка (ідемпотентно): якщо шаблона немає
    (видалений до `-i`), XML завантажується знову. Обходи не створюються — їх відкриває крон."""
    env = _internal(env)
    Template = env["td.energy.round.template"].with_context(active_test=False)
    if Template.search_count([("code", "=", TEMPLATE_CODE)]):
        return False
    tools.convert_file(env, MODULE, "data/round_template_data.xml", None, mode="init", noupdate=True)
    return True


def post_init_hook(env):
    """H.5.3: `_seed_template(env)` (ідемпотентно)."""
    _seed_template(env)


def uninstall_hook(env):
    """H.5.4: події `round` → `manual`; видаляє власні крон-записи й параметри `td.energy_mobile.*`."""
    env = _internal(env)
    env.cr.execute("UPDATE td_energy_event SET kind = 'manual' WHERE kind = 'round'")
    env.cr.execute("DELETE FROM ir_config_parameter WHERE key LIKE %s", ("td.energy\\_mobile.%",))
    cron_ids = env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "ir.cron")]).mapped("res_id")
    env["ir.cron"].browse(cron_ids).exists().unlink()
