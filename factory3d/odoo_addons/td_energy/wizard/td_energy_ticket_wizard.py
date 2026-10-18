"""W1-A: M-28 `td.energy.ticket.wizard` — заявка ТО з картки вузла (W1_SPEC M-28, API-14). Каркас: наповнює W1-A."""

from odoo import models


class TdEnergyTicketWizard(models.TransientModel):
    _name = "td.energy.ticket.wizard"
    _description = "Енергетика: заявка ТО з картки вузла"
