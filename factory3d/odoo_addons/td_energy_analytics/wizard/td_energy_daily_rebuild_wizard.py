"""M-16 `td.energy.daily.rebuild.wizard` — перерахунок фактів (Transient; W4-B). Каркас: `action_rebuild` — воркер B
(замінює файл цілком); діапазон ≤ 400 діб, `group_td_energy_manager`."""

from odoo import fields, models


class TdEnergyDailyRebuildWizard(models.TransientModel):
    _name = "td.energy.daily.rebuild.wizard"
    _description = "Енергетика: майстер перерахунку добових фактів"

    date_from = fields.Date(string="З", required=True)
    date_to = fields.Date(string="По", required=True)

    def action_rebuild(self):
        raise NotImplementedError("W4-B: M-16")
