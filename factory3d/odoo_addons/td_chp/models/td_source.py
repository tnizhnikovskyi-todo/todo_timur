"""M-05: модуль-власник `chp` для джерел."""

from odoo import fields, models


class TdSource(models.Model):
    _inherit = "td.source"

    module = fields.Selection(selection_add=[("chp", "Когенерація")], ondelete={"chp": "set default"})
