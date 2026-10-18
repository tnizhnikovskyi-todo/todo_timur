"""Каркас: пакет імпортується, тип джерела й push_mode зафіксовані (SPEC 8.1)."""

from td_collector_energy import EnergyCtlPlugin


def test_plugin_declaration():
    assert EnergyCtlPlugin.type == "energy_ctl"
    assert EnergyCtlPlugin.push_mode is True
