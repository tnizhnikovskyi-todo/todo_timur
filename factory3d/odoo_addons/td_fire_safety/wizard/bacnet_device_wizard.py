from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class F3dFireBacnetDeviceWizard(models.TransientModel):
    _name = "td.fire.bacnet.device.wizard"
    _description = "Пожежна безпека: зміна BACnet device instance"

    panel_id = fields.Many2one("td.fire.panel", string="Прилад", required=True)
    source_id = fields.Many2one("td.source", related="panel_id.source_id", string="Джерело", readonly=True)
    old_instance = fields.Integer(string="Поточний device instance", readonly=True)
    new_instance = fields.Integer(string="Новий device instance", required=True)
    signal_count = fields.Integer(string="Сигналів на новому device", compute="_compute_counts")
    explicit_count = fields.Integer(string="З явною адресою device", compute="_compute_counts")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "old_instance" in fields_list and "old_instance" not in res:
            panel = self.env["td.fire.panel"].browse(res.get("panel_id") or 0).exists()
            if panel.source_id:
                res["old_instance"] = int((panel.source_id.params or {}).get("device") or 0)
        return res

    def _signals(self):
        self.ensure_one()
        if not self.source_id:
            return self.env["td.signal"]
        return (
            self.env["td.signal"].sudo().with_context(active_test=False).search([("source_id", "=", self.source_id.id)])
        )

    @api.depends("panel_id", "panel_id.source_id")
    def _compute_counts(self):
        for rec in self:
            signals = rec._signals()
            rec.signal_count = len(signals)
            rec.explicit_count = len(signals.filtered(lambda s: "device" in (s.address or {})))

    @api.constrains("new_instance")
    def _check_new_instance(self):
        for rec in self:
            if not 0 <= rec.new_instance <= 4194302:
                raise ValidationError("BACnet instance: 0…4194302")

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError("Змінювати BACnet device instance може лише адміністратор 3D Завод.")
        panel = self.panel_id
        source = panel.source_id.sudo()
        if not source:
            raise UserError("Прилад не має джерела BACnet.")
        old = int((source.params or {}).get("device") or self.old_instance or 0)
        new = self.new_instance
        if new == old:
            return self._notify("Без змін", "info")
        signals = self._signals()
        explicit = signals.filtered(lambda s: "device" in (s.address or {}))
        count_all, count_explicit = len(signals), len(explicit)
        code = source.code
        vals = {"params": dict(source.params or {}, device=new)}
        if code == "BAC-%d-FACP-1" % old:
            code = "BAC-%d-FACP-1" % new
            vals["code"] = code
        source.write(vals)
        for sig in explicit:
            sig.write({"address": dict(sig.address, device=new)})
        panel.message_post(
            body="BACnet device змінено: %d → %d (джерело %s), сигналів %d, з явною адресою %d"
            % (old, new, code, count_all, count_explicit)
        )
        return self._notify("BACnet device змінено: %d → %d" % (old, new), "success")

    @staticmethod
    def _notify(message, kind):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Пожежна безпека",
                "message": message,
                "type": kind,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
