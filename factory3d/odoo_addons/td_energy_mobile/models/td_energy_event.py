"""M-H6 `td.energy.event` — розширення: вид `round` (W4-C): `selection_add`; при видаленні модуля події `round`
переводяться в `manual` (`uninstall_hook` дублює це як страховку)."""

from odoo import fields, models


class TdEnergyEvent(models.Model):
    _inherit = "td.energy.event"

    kind = fields.Selection(
        selection_add=[("round", "Обхід")], ondelete={"round": lambda recs: recs.write({"kind": "manual"})}
    )
