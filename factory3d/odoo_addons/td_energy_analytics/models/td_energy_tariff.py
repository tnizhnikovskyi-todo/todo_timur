"""M-18 `td.energy.tariff` — розширення (`_inherit`): плата за потужність для сценаріїв «Що якщо» (R-23)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

COST = "td_energy.group_td_energy_cost"


class TdEnergyTariff(models.Model):
    _inherit = "td.energy.tariff"

    capacity_price = fields.Float(
        string="Плата за потужність, грн/кВт·міс", digits=(10, 2), default=0.0, groups=COST,
        help="Нараховується за піком 15-хв потужності з мережі за місяць; 0 — договір плати за потужність не містить.",
    )  # fmt: skip

    @api.constrains("capacity_price")
    def _check_capacity_price(self):
        if any(rec.capacity_price < 0 for rec in self):
            raise ValidationError(_("Плата за потужність не може бути від'ємною."))
