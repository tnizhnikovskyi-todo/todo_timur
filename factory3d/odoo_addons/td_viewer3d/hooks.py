import logging
import secrets


_logger = logging.getLogger(__name__)

PREFIX = "factory3d.viewer."
DEMO_COMPANY = "Меблева фабрика (демо)"
DEMO_CLOCK = "2026-10-12 10:30"


def is_demo_db(env):
    """Ознака демо/тестової бази: встановлений factory3d_iot_sim або компанія демо."""
    iot = env["ir.module.module"].sudo().search_count(
        [("name", "=", "factory3d_iot_sim"), ("state", "=", "installed")])
    return bool(iot) or bool(env["res.company"].sudo().search_count([("name", "=", DEMO_COMPANY)]))


def post_init(env):
    params = env["ir.config_parameter"].sudo()
    # 1. токен кіоска
    if not params.get_param(PREFIX + "kiosk_token"):
        params.set_param(PREFIX + "kiosk_token", secrets.token_hex(16))
    # 2. демо-ознака
    demo = is_demo_db(env)
    if params.get_param(PREFIX + "demo_enabled") is False:
        params.set_param(PREFIX + "demo_enabled", str(demo))
    if demo and not params.get_param(PREFIX + "demo_clock"):
        params.set_param(PREFIX + "demo_clock", DEMO_CLOCK)
    for key in ("kiosk_enabled", "bus_enabled"):
        if params.get_param(PREFIX + key) is False:
            params.set_param(PREFIX + key, "True")
    # 3. перевірка кодів сцени (резолвер R-16 — tools/payload, якщо вже є)
    try:
        from .tools import payload  # noqa: F401
        check = getattr(payload, "log_scene_codes", None)
        if check:
            check(env)
    except ImportError:
        pass
    # 4. перший знімок install (модель f3d.viewer.snapshot — окремий воркер)
    snapshot = env.get("f3d.viewer.snapshot")
    if snapshot is not None and hasattr(snapshot, "_take"):
        snapshot.sudo()._take(kind="install")
    # 5. крон сигналів — лише якщо є x_f3d_signal
    cron = env.ref("factory3d_viewer.cron_f3d_signal_bus", raise_if_not_found=False)
    if cron and "x_f3d_signal" in env:
        cron.sudo().active = True


def uninstall(env):
    params = env["ir.config_parameter"].sudo()
    params.search([("key", "=like", PREFIX + "%")]).unlink()
    data = env["ir.model.data"].sudo().search(
        [("module", "=", "factory3d_viewer"), ("name", "=", "user_kiosk"), ("model", "=", "res.users")])
    user = env["res.users"].sudo().browse(data.mapped("res_id")).exists()
    # без xmlid модульна деінсталяція не видалить користувача (він лише архівується)
    data.unlink()
    user.write({"active": False})
