from odoo import api, fields, models


class F3dSource(models.Model):
    """M-12 (CT-12, A-01): локальний тип джерела `f3d_bms` — обчислені перевірки модуля без колектора."""

    _inherit = "td.source"

    type = fields.Selection(
        selection_add=[("f3d_bms", "Будівля (обчислені)")],
        ondelete={"f3d_bms": "cascade"},
    )

    @api.model
    def _td_local_types(self):
        return super()._td_local_types() + ["f3d_bms"]
