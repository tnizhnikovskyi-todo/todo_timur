"""Хуки модуля: деінсталяція вимикає свої крони й не чіпає бізнес-дані (замовлення, МО, простої лишаються)."""

MODULE = "td_live_production"


def uninstall_hook(env):
    env = env(su=True)
    cron_ids = env["ir.model.data"].search([("module", "=", MODULE), ("model", "=", "ir.cron")]).mapped("res_id")
    env["ir.cron"].with_context(active_test=False).browse(cron_ids).exists().write({"active": False})
    env["ir.config_parameter"].search([("key", "=like", "td.live_production.%")]).unlink()
