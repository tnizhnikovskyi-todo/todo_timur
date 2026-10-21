"""`td.chp.command` (розширення): верифікація й строки дій моста в `td.energy.action` (R-09: показання й крон)."""

from odoo import api, models

from odoo.addons.td_chp.tools.signals import cparam_bool


class TdChpCommand(models.Model):
    _inherit = "td.chp.command"

    @api.model
    def _td_on_ingest(self, before, readings):
        super()._td_on_ingest(before, readings)
        self.env["td.energy.action"]._td_chp_verify(readings)

    @api.model
    def _cron_expire(self):
        n = super()._cron_expire() or 0
        if cparam_bool(self.env, "read_enabled"):
            n += self.env["td.energy.action"]._td_chp_expire()
        return n
