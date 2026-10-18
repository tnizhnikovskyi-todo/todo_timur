"""Шина переглядача: створення/видалення версії планування → подія `td.layout.version` (клієнти беруть дельту)."""
from odoo import api, models


class F3dLayoutVersion(models.Model):
    _inherit = "td.layout.version"

    def _f3d_notify_viewer(self):
        if "td.viewer.event" not in self.env:
            return
        codes = {v.site_id.code or str(v.site_id.id) for v in self.sudo()}
        self.env["td.viewer.event"]._notify("td.layout.version", codes, "state")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._f3d_notify_viewer()
        return records

    def unlink(self):
        self._f3d_notify_viewer()
        return super().unlink()
