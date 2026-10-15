"""post_init_hook / uninstall_hook пожежної безпеки (SPEC §5.4, §5.5). W0: скелет без логіки."""

import logging
from types import SimpleNamespace

_logger = logging.getLogger("odoo.addons.factory3d_fire_safety.hooks")


def params(env):
    """Крок 1 (§5.4): read_enabled за CB-10, team_id."""
    return {}


def _link(env):
    """Крок 2: зв'язок приладу, зон, пристроїв, систем, виходів, джерел і сигналів з обладнанням (R-24)."""
    return {}


def _dust(env):
    """Крок 3: сигнал запиленості 2.FAC.07."""
    return {}


def _requests_link(env):
    """Крок 4: зв'язок заявок із зонами (R-22)."""
    return {}


def _events_demo(env):
    """Крок 5: 4 демо-події."""
    return {}


def _drills_demo(env):
    """Крок 6: демо-навчання."""
    return {}


def _sync_first(env):
    """Крок 7: перший sync (R-19)."""
    return {}


def compliance(env):
    """Крок 8: перерахунок відповідності (R-01…R-09)."""
    return {}


def _report_write(env, report):
    """Крок 9: запис migration_report."""
    return report


# Тести (FireCase) викликають hooks.equipment.link(env) — простір імен, як підмодулі зі SPEC §5.4
equipment = SimpleNamespace(link=_link)
signals = SimpleNamespace(dust=_dust)
requests = SimpleNamespace(link=_requests_link)
events = SimpleNamespace(demo=_events_demo)
drills = SimpleNamespace(demo=_drills_demo)
sync = SimpleNamespace(first=_sync_first)
report = SimpleNamespace(write=_report_write)


def run_all(env):
    """Виконує кроки 1–9; повертає звіт (лічильники кроків)."""
    return {}


def post_init_hook(env):
    run_all(env)


def uninstall_hook(env):
    """§5.5: видалення параметрів, відв'язування сигналу запиленості."""
