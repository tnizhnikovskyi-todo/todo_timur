"""EnergyCtlPlugin: validate/connect/subscribe/call/health/disconnect (SPEC 8.1.3). Каркас W2-0; реалізація — C."""

from __future__ import annotations

import json
from importlib import resources
from typing import ClassVar

from collector.plugins.base import SourcePlugin


def _load(name: str) -> dict:
    return json.loads(resources.files("td_collector_energy").joinpath("schemas", name).read_text("utf-8"))


class EnergyCtlPlugin(SourcePlugin):
    type: ClassVar[str] = "energy_ctl"
    version: ClassVar[str] = "0.1.0"
    address_schema: ClassVar[dict] = _load("address.energy_ctl.json")
    params_schema: ClassVar[dict] = _load("params.energy_ctl.json")
    push_mode: ClassVar[bool] = True
