from odoo import api, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        energy = records.filtered(lambda r: r.td_signal_id.module == "energy")
        if energy:
            group = self.env.ref("td_energy.group_td_energy_manager")
            partners = group.sudo().all_user_ids.partner_id.filtered(lambda p: p.active)
            if partners:
                energy.message_subscribe(partner_ids=partners.ids)
        return records
