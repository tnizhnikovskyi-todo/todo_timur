import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class F3dSource(models.Model):
    _inherit = "f3d.source"

    type = fields.Selection(
        selection_add=[("f3d_machine", "Верстати: обчислені стани")], ondelete={"f3d_machine": "cascade"}
    )

    @api.model
    def _f3d_local_types(self):
        return super()._f3d_local_types() + ["f3d_machine"]
