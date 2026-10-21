"""`td.energy.command.kind` (розширення): виконавець `chp` і підписи шаблонів видів КГУ (D-15)."""

from odoo import fields, models

from ..tools import energy_route as route


class TdEnergyCommandKind(models.Model):
    _inherit = "td.energy.command.kind"

    executor = fields.Selection(
        selection_add=[("chp", "КГУ (td_chp)")],
        ondelete={"chp": "cascade"},
    )

    def _td_text_values(self, params, base=None):
        vals = super()._td_text_values(params, base)
        kind = route.chp_kind(self.code)
        if kind and self.executor == route.EXECUTOR:
            vals.update(route.text_values(kind, params))
        return vals
