"""Параметри td.yard.* (SPEC §5.1): умовчання й типізоване читання."""

import logging

_logger = logging.getLogger(__name__)

PREFIX = "td.yard."

# name: (type, default); умовчання збігаються з data/ir_config_parameter.xml
PARAMS = {
    "read_enabled": ("bool", "True"),
    "write_enabled": ("bool", "False"),
    "antipassback": ("bool", "True"),
    "walk_in_allowed": ("bool", "True"),
    "walk_in_limit_per_day": ("int", "5"),
    "lpr_min_confidence": ("float", "0.80"),
    "lpr_match_window_h": ("int", "4"),
    "lpr_store_images": ("bool", "True"),
    "lpr_image_max_kb": ("int", "1024"),
    "lpr_keep_days": ("int", "30"),
    "kpp_refresh_s": ("int", "10"),
    "slot_default_min": ("int", "60"),
    "dock_turnaround_min": ("int", "15"),
    "enforce_calendar": ("bool", "False"),
    "calendar_id": ("int", ""),
    "early_min": ("int", "60"),
    "late_min": ("int", "120"),
    "auto_call_next": ("bool", "False"),
    "queue_slot_window_min": ("int", "30"),
    "arrival_timeout_min": ("int", "30"),
    "no_show_min": ("int", "120"),
    "dock_shift_min": ("int", "480"),
    "open_timeout_s": ("int", "10"),
    "cmd_cooldown_s": ("int", "30"),
    "cmd_expire_s": ("int", "30"),
    "hold_max_min": ("int", "30"),
    "signal_max_age_s": ("int", "15"),
    "net_tolerance_pct": ("float", "2.0"),
    "net_tolerance_kg": ("float", "100"),
    "weigh_max_age_s": ("int", "15"),
    "scale_auto_capture": ("bool", "True"),
    "scale_dwell_s": ("int", "120"),
    "weighing_policy_west": ("str", "in_out"),
    "weighing_policy_east": ("str", "in_out"),
    "visit_pii_keep_days": ("int", "90"),
    "weighing_unassigned_keep_days": ("int", "7"),
    "seed_product_weights": ("bool", "True"),
    "migration_state": ("str", "pending"),
    "migration_report": ("str", "{}"),
}
_WARNED = set()


def _raw(env, name):
    typ, default = PARAMS[name]
    return env["ir.config_parameter"].sudo().get_param(PREFIX + name, default)


def _warn(name, raw):
    if name not in _WARNED:
        _WARNED.add(name)
        _logger.warning("Параметр %s%s=%r некоректний, взято умовчання", PREFIX, name, raw)


def get_str(env, name):
    return _raw(env, name)


def get_bool(env, name):
    return _raw(env, name) in ("True", "true", "1")


def get_int(env, name):
    raw = _raw(env, name)
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        _warn(name, raw)
        try:
            return int(float(PARAMS[name][1]))
        except ValueError:
            return 0


def get_float(env, name):
    raw = _raw(env, name)
    try:
        return float(raw)
    except (TypeError, ValueError):
        _warn(name, raw)
        return float(PARAMS[name][1] or 0)


def set_param(env, name, value):
    env["ir.config_parameter"].sudo().set_param(PREFIX + name, str(value))
