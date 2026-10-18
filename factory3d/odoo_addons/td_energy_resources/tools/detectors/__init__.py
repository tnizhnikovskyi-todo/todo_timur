"""Реєстр детекторів резервів (R-14, A-08): рядок на детектор. Змінює лише менеджер.

Міст `td_energy_resources_bms` додає свої (`preheat_early`, `ahu_recuperation`, `dock_gates`) методами
`_td_detect_<code>` у `td.energy.opportunity.rule` (`_inherit`), а не записами цього реєстру.
"""

from . import air_leaks, air_pressure, common, idle_machines, pv_export, react_section, vent_offshift  # noqa: F401

DETECTORS = {
    "vent_offshift": vent_offshift.detect,
    "idle_machines": idle_machines.detect,
    "air_leaks": air_leaks.detect,
    "air_pressure": air_pressure.detect,
    "react_section": react_section.detect,
    "pv_export": pv_export.detect,
}
