"""М'який виклик адаптера ADP-12 моста `td_genset_factory3d` (SPEC 8.3, R-67). Без моста — `available=False`."""

import importlib

from odoo import _
from odoo.exceptions import UserError

ADAPTER = "odoo.addons.td_genset_factory3d.adapters.td_genset"
NOT_INSTALLED = "Не встановлено міст td_genset_factory3d"


def adapter(env):
    """Модуль адаптера або None (міст не встановлений / не імпортується)."""
    installed = (
        env["ir.module.module"].sudo().search_count([("name", "=", "td_genset_factory3d"), ("state", "=", "installed")])
    )
    if not installed:
        return None
    try:
        return importlib.import_module(ADAPTER)
    except ImportError:  # pragma: no cover
        return None


def availability(env):
    """(доступно, причина)."""
    return (True, "") if adapter(env) else (False, NOT_INSTALLED)


def generator(env):
    mod = adapter(env)
    if mod is None:
        return None, None
    gens = mod.generators(env)
    return mod, (gens[:1] or None)


def facts(env):
    """`test_facts` першого генератора для перевірок діалогу; без моста/генератора — {}."""
    mod, gen = generator(env)
    if mod is None or not gen:
        return {}
    try:
        return mod.test_facts(gen) or {}
    except Exception:  # pragma: no cover - перевірки не повинні ламати діалог
        return {}


def start_test(env, user):
    """ADP-12: `start_test(gen, 'idle', user)`. Немає моста/генератора → `UserError`; помилки td_genset — як є."""
    mod, gen = generator(env)
    if mod is None:
        raise UserError(_("Не встановлено міст td_genset_factory3d."))
    if not gen:
        raise UserError(_("Генератор не налаштовано."))
    return mod.start_test(gen, "idle", user)
