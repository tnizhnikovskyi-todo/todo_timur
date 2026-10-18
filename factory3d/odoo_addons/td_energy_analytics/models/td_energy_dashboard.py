"""M-14 `td.energy.dashboard` — розширення (W4-A): хук `_td_report_action` для кнопки «Звіт за зміну» Пульту (C-02).

Хук оголошено в `td_energy` (повертає `None`); тут — значення модуля аналітики. Серверну дію з цим xml-id створює
воркер B (V-13, `report/report_shift.xml`).
"""

from odoo import api, models


class TdEnergyDashboard(models.AbstractModel):
    _inherit = "td.energy.dashboard"

    @api.model
    def _td_report_action(self):
        return "td_energy_analytics.action_td_energy_shift_report"
