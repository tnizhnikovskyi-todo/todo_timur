"""M-12 `td.energy.analytics` — API екрана (AbstractModel; W4-A). Каркас: `get_dashboard` й API-02…API-09,
`_td_seed_demo` (API-14), `_td_check_access` — воркер A (замінює файл цілком).
Контракт відповіді: `contracts/api01_get_dashboard.json`."""

from odoo import models


class TdEnergyAnalytics(models.AbstractModel):
    _name = "td.energy.analytics"
    _description = "Енергетика: дані аналітики"
