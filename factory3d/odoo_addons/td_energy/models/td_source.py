from odoo import api, fields, models


class F3dSource(models.Model):
    """M-16: локальний тип джерела `f3d_energy` (CT-12, A-08) — обчислені показники без колектора."""

    _inherit = "td.source"

    type = fields.Selection(
        selection_add=[("f3d_energy", "Енергетика (обчислені)")], ondelete={"f3d_energy": "cascade"}
    )

    @api.model
    def _f3d_local_types(self):
        return super()._f3d_local_types() + ["f3d_energy"]
