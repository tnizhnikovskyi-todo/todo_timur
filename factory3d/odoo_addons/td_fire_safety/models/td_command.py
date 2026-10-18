from odoo import api, models
from odoo.exceptions import ValidationError


class F3dCommand(models.Model):
    _inherit = "td.command"

    @api.model_create_multi
    def create(self, vals_list):
        Signal = self.env["td.signal"].sudo()
        for vals in vals_list:
            sig = Signal.browse(vals.get("signal_id") or 0).exists()
            if sig and (sig.module == "fire_safety" or sig.source_id.td_fire_readonly):
                raise ValidationError("Команди на пристрої пожежної безпеки заборонені (D-07).")
        return super().create(vals_list)
