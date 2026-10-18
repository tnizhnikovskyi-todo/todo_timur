"""M-33 td.energy.action (журнал, потік prepare/confirm/confirm_second/undo). Каркас W2-0; реалізація — A."""

from odoo import models


class TdEnergyAction(models.Model):
    _name = "td.energy.action"
    _description = "Дія оператора, автоматики й конфігурації"
