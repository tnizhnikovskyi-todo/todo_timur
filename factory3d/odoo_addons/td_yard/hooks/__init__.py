"""post_init_hook / uninstall_hook двору (SPEC §5.4, §5.5)."""

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import SUPERUSER_ID, api

from . import migrate

_logger = logging.getLogger("odoo.addons.td_yard.hooks")

STEPS = (
    migrate.params,
    migrate.gates_and_scale,
    migrate.signals_and_sources,
    migrate.product_weights,
    migrate.carrier_partners,
    migrate.visits_from_batches,
    migrate.bookings_from_batches,
    migrate.weighing_from_card,
)
CTX = {"f3d_yard_no_auto": True, "tracking_disable": True, "mail_create_nolog": True}
KYIV = ZoneInfo("Europe/Kyiv")
CRONS = (("cron_td_yard_gc", time(3, 0)), ("cron_td_yard_day_reset", time(0, 5)))


def run_all(env):
    """Виконує кроки 0–8; виняток кроку не зупиняє наступні. Повертає звіт."""
    env = env(user=SUPERUSER_ID, context=dict(env.context, **CTX))
    rep = {"errors": []}
    for step in STEPS:
        try:
            with env.cr.savepoint():
                rep[step.__name__] = step(env)
            _logger.info("f3d_yard: %s %s", step.__name__, rep[step.__name__])
        except Exception as exc:
            _logger.exception("f3d_yard: крок %s", step.__name__)
            rep["errors"].append("%s: %s" % (step.__name__, exc))
    try:
        with env.cr.savepoint():
            rep["report"] = migrate.report(env, rep)
    except Exception:
        _logger.exception("f3d_yard: крок report")
    return rep


def _next_local(at, now=None):
    """Найближчий момент `at` за Києвом, як наївний UTC (формат Odoo)."""
    now = (now or datetime.now(KYIV)).astimezone(KYIV)
    cand = datetime.combine(now.date(), at, tzinfo=KYIV)
    if cand <= now:
        cand = datetime.combine(now.date() + timedelta(days=1), at, tzinfo=KYIV)
    return cand.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def set_cron_times(env):
    for xmlid, at in CRONS:
        cron = env.ref("td_yard.%s" % xmlid, raise_if_not_found=False)
        if cron:
            cron.sudo().nextcall = _next_local(at)


def post_init_hook(env):
    rep = run_all(env)
    set_cron_times(env)
    return rep


def uninstall_hook(env):
    """Параметри й вкладення знімків; джерела/сигнали двору (без xml-id) лишаються."""
    env["ir.config_parameter"].sudo().search([("key", "=like", "td.yard.%")]).unlink()
    env["ir.attachment"].sudo().search([("res_model", "=", "td.yard.lpr.event")]).unlink()
