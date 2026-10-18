"""Чисті функції й допоміжні модулі td_energy_control (імпортуються з моделей; без побічних ефектів)."""

PARAM = "td.energy_control."


def is_internal(env):
    """Внутрішні операції модуля (методи моделей, завантаження даних): прямий write/unlink з клієнта заборонений."""
    ctx = env.context
    return bool(ctx.get("td_energy_control_internal") or ctx.get("install_mode") or ctx.get("module"))


def cparam(env, name, default=None):
    val = env["ir.config_parameter"].sudo().get_param(PARAM + name)
    return default if val in (None, False, "") else val


def cparam_bool(env, name, default=False):
    val = cparam(env, name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def cparam_float(env, name, default=0.0):
    try:
        return float(cparam(env, name))
    except (TypeError, ValueError):
        return default


def cparam_int(env, name, default=0):
    return int(cparam_float(env, name, default))


def iso(dt):
    """naive UTC → `2026-10-18T11:20:03Z`."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def local_hhmm(dt, now=None):
    """naive UTC → «HH:MM» за Києвом; старше доби — «DD.MM HH:MM»."""
    if not dt:
        return ""
    from odoo.addons.td_energy.tools.tariff import to_local

    local = to_local(dt)
    if now is not None and (now - dt).total_seconds() > 86400:
        return local.strftime("%d.%m %H:%M")
    return local.strftime("%H:%M")
