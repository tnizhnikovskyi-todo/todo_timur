from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape


_LINK_KINDS = ("fault", "dust", "spark", "smoke", "sprinkler", "loop")


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    f3d_fire_event_id = fields.Many2one(
        "f3d.fire.event", string="Подія пожежної безпеки", ondelete="set null")
    f3d_fire_zone_id = fields.Many2one(
        "f3d.fire.zone", string="Зона сигналізації", ondelete="set null", index=True)
    f3d_fire_device_id = fields.Many2one("f3d.fire.device", string="Пристрій", ondelete="set null")
    f3d_origin = fields.Selection(
        selection_add=[("fire_comm", "Немає зв'язку з пожежним приладом")], ondelete={"fire_comm": "set null"})

    @api.model_create_multi
    def create(self, vals_list):
        team_id = self.env["ir.config_parameter"].sudo().get_param("factory3d.fire_safety.team_id") or ""
        if team_id.isdigit():
            Signal = self.env["f3d.signal"].sudo()
            pressure = Signal._f3d_fire_extra_codes()
            for vals in vals_list:
                if not vals.get("f3d_signal_id"):
                    continue
                origin = vals.get("f3d_origin")
                # заявку telemetry (threshold/stale) команда модуля переозначує; явну команду інших викликачів — ні
                if origin not in ("threshold", "stale") and (origin or vals.get("maintenance_team_id")):
                    continue
                sig = Signal.browse(vals["f3d_signal_id"])
                if sig.module == "fire_safety" or sig.code in pressure:
                    vals["maintenance_team_id"] = int(team_id)
        records = super().create(vals_list)
        records._f3d_fire_link()
        return records

    def _f3d_fire_link(self):
        """R-22 п. 1: зв'язок заявки сигналу модуля з зоною, пристроєм і подією журналу."""
        Device = self.env["f3d.fire.device"].sudo().with_context(active_test=False)
        Zone = self.env["f3d.fire.zone"].sudo()
        for rec in self.sudo():
            sig = rec.f3d_signal_id
            if not sig or rec.f3d_fire_zone_id or rec.f3d_fire_device_id:
                continue
            device = Device.search(
                ["|", ("dust_signal_id", "=", sig.id), ("state_signal_id", "=", sig.id)], limit=1)
            zone = device.zone_id or Zone.search(
                ["|", ("signal_id", "=", sig.id), ("dust_signal_id", "=", sig.id)], limit=1)
            if not (device or zone) and sig.module != "fire_safety":
                continue
            vals = {}
            if device:
                vals["f3d_fire_device_id"] = device.id
            if zone:
                vals["f3d_fire_zone_id"] = zone.id
            line = "Пожежна безпека: зона %s" % ("%s (%s)" % (zone.code, zone.name) if zone else "—")
            if device:
                line += ", пристрій %s%s, BACnet LSP %s" % (
                    device.address, (" " + device.note) if device.note else "", device.lsp_instance)
            line += "."
            vals["description"] = "%s<p>%s</p>" % (rec.description or "", html_escape(line))
            rec.write(vals)
        self._f3d_fire_link_events()

    def _f3d_fire_link_events(self):
        """R-22 п. 1: остання подія (≤ 10 хв) сигналу, пристрою чи зони; події — `request_id`."""
        Event = self.env["f3d.fire.event"].sudo()
        since = fields.Datetime.now() - timedelta(minutes=10)
        for rec in self.sudo():
            if rec.f3d_fire_event_id or not rec.f3d_signal_id:
                continue
            if not (rec.f3d_fire_device_id or rec.f3d_fire_zone_id or rec.f3d_signal_id.module == "fire_safety"):
                continue
            dom = [("signal_id", "=", rec.f3d_signal_id.id)]
            if rec.f3d_fire_device_id or rec.f3d_fire_zone_id:
                dom = ["|"] + dom + ["&", ("kind", "in", _LINK_KINDS),
                                     ("device_id", "=", rec.f3d_fire_device_id.id)
                                     if rec.f3d_fire_device_id else ("zone_id", "=", rec.f3d_fire_zone_id.id)]
            event = Event.search(dom + [("ts", ">=", since)], order="ts desc, id desc", limit=1)
            if event:
                rec.f3d_fire_event_id = event
                if not event.request_id:
                    event.request_id = rec.id

    def action_f3d_fire_open_zone(self):
        self.ensure_one()
        if not self.f3d_fire_zone_id:
            raise UserError(_("Заявка не пов'язана із зоною сигналізації."))
        return {"type": "ir.actions.act_window", "res_model": "f3d.fire.zone", "view_mode": "form",
                "res_id": self.f3d_fire_zone_id.id}
