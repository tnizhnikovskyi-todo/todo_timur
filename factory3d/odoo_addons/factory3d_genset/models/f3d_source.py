from odoo import api, fields, models


class F3dSource(models.Model):
    _inherit = "f3d.source"

    type = fields.Selection(
        selection_add=[("td_genset", "td_genset (ретранслятор SmartGen)")], ondelete={"td_genset": "cascade"})

    @api.model
    def _f3d_local_types(self):
        # CT-12, R-26 factory3d_telemetry: джерело типу td_genset — локальне, без колектора (X-01, D-17)
        return super()._f3d_local_types() + ["td_genset"]
