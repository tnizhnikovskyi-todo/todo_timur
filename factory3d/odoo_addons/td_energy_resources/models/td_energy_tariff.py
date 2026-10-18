"""M-05 `td.energy.tariff` — розширення: доплата за реактивну енергію (FR-21, Q-03)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COST_GROUP = "td_energy.group_td_energy_cost"


class TdEnergyTariff(models.Model):
    _inherit = "td.energy.tariff"

    tg_phi_limit = fields.Float(
        string="Допустимий tg φ (0 — доплати немає)", digits=(4, 2), default=0.0, groups=COST_GROUP
    )
    react_rate = fields.Float(
        string="Ставка за реактивну енергію понад ліміт, ₴/квар·год", digits=(10, 4), default=0.0, groups=COST_GROUP
    )

    @api.constrains("tg_phi_limit", "react_rate")
    def _check_react(self):
        for rec in self.sudo():
            if rec.tg_phi_limit < 0 or rec.react_rate < 0:
                raise ValidationError(_("Ліміт tg φ і ставка не можуть бути від'ємними."))
            if rec.react_rate > 0 and rec.tg_phi_limit == 0:
                raise ValidationError(_("Ставка без ліміту tg φ не має сенсу."))

    def _td_react_penalty(self, excess_kvarh):
        """Доплата за реактивну енергію понад ліміт: `excess × react_rate` (0, якщо ліміт не заданий)."""
        self.ensure_one()
        tariff = self.sudo()
        if not tariff.tg_phi_limit or excess_kvarh <= 0:
            return 0.0
        return round(excess_kvarh * tariff.react_rate, 2)
