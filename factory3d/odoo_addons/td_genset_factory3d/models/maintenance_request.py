from odoo import _, fields, models


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    td_genset_event_key = fields.Char(string="Ключ події генератора", size=80, index=True, readonly=True, copy=False)

    def write(self, vals):
        if "stage_id" not in vals:
            return super().write(vals)
        was_done = {rec.id: rec.stage_id.done for rec in self}
        res = super().write(vals)
        for rec in self.filtered(lambda r: r.td_genset_event_key and r.stage_id.done and not was_done.get(r.id)):
            rec._td_genset_on_closed()
        return res

    def _td_genset_on_closed(self):
        """R-08 крок 4: запис у чаттер зв'язки. Статус сигналу перераховує telemetry (_on_request_closed)."""
        self.ensure_one()
        link = self.env["td.genset3d.link"].sudo().search([("equipment_id", "=", self.equipment_id.id)], limit=1)
        if link:
            link.message_post(body=_("Заявку %s закрито", self.name))
