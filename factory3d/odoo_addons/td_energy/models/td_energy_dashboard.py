"""W1-A: M-27 `td.energy.dashboard` — API Пульту, картки, мобільного, генерації (W1_SPEC M-27). Каркас."""

from odoo import models


class TdEnergyDashboard(models.AbstractModel):
    _name = "td.energy.dashboard"
    _description = "Енергетика: дані Пульту"

    def _td_genset_summary(self):
        return None

    def _td_generation_cards(self):
        return []

    def _td_node_facts_extra(self, node):
        return []

    def _td_node_card_extra(self, node):
        return {}
