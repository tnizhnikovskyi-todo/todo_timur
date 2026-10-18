"""M-08 `td.energy.res.dashboard` — API екрана (W3-E). Каркас: `get_resources`, `_td_totals`, хуки — воркер E.

Хуки ядра (порожні; перекриває міст `td_energy_resources_bms`): `_td_heat_kpis(ctx)`, `_td_heat_list(ctx)`,
`_td_heat_chart_note(ctx)`, `_td_resource_extra(code, ctx)`.
"""

from odoo import models


class TdEnergyResDashboard(models.AbstractModel):
    _name = "td.energy.res.dashboard"
    _description = "Енергетика: дані екрана ресурсів"
