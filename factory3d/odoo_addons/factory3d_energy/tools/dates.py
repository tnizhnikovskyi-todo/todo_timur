"""R-20: час і часові пояси. Зберігання — UTC naive; доба, година, зміна — за Києвом. Чисті функції."""

from datetime import datetime, time, timedelta, timezone

from .tariff import KYIV, to_local  # noqa: F401  (to_local, KYIV — спільні з тарифом)

SLOT = timedelta(minutes=15)


def to_utc(local_dt):
    """Aware (або місцевий naive за Києвом) → naive UTC."""
    if local_dt.tzinfo is None:
        local_dt = local_dt.replace(tzinfo=KYIV)
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


def floor15(dt):
    return dt.replace(minute=dt.minute - dt.minute % 15, second=0, microsecond=0)


def ceil15(dt):
    base = floor15(dt)
    return base if base == dt else base + SLOT


def floor_minute(dt):
    return dt.replace(second=0, microsecond=0)


def local_day_bounds(day):
    """Місцева дата (`date`) → (початок, кінець) доби в UTC naive; у добу переходу 23/25 год — фактична довжина."""
    start = to_utc(datetime.combine(day, time(0, 0)))
    end = to_utc(datetime.combine(day + timedelta(days=1), time(0, 0)))
    return start, end


def local_day(dt_utc):
    return to_local(dt_utc).date()


def shift_start(now_utc, hours_by_weekday):
    """R-11: початок поточної зміни (UTC naive). `hours_by_weekday` — {weekday: мінімальний hour_from атендансів}.
    `now_local` раніше початку зміни дня або день без атендансів — попередній день з атендансами (≤ 7 діб);
    немає жодного — місцева північ."""
    now_local = to_local(now_utc)
    for back in range(0, 8):
        day = now_local.date() - timedelta(days=back)
        hour = hours_by_weekday.get(day.weekday())
        if hour is None:
            continue
        start = datetime.combine(day, time(0, 0)).replace(tzinfo=KYIV) + timedelta(hours=hour)
        if start <= now_local:
            return start.astimezone(timezone.utc).replace(tzinfo=None)
    return local_day_bounds(now_local.date())[0]


def param_bool(env, name, default=False):
    val = env["ir.config_parameter"].sudo().get_param("factory3d.energy." + name)
    if val is None or val is False or val == "":
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def param_float(env, name, default=0.0):
    val = env["ir.config_parameter"].sudo().get_param("factory3d.energy." + name)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def now_utc(env):
    """«Зараз» (UTC naive); у тестах підміняється ключем контексту `f3d_now`."""
    from odoo import fields

    return env.context.get("f3d_now") or fields.Datetime.now()
