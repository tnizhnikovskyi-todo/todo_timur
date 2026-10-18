from odoo import api, fields, models
from odoo.exceptions import ValidationError


class F3dFireLoop(models.Model):
    _name = "td.fire.loop"
    _description = "Пожежна сигналізація: шлейф"
    _order = "panel_id, number"
    _rec_name = "name"

    panel_id = fields.Many2one("td.fire.panel", required=True, ondelete="cascade", index=True)
    number = fields.Integer(string="Номер", required=True)
    name = fields.Char(compute="_compute_name", store=True)
    from_x_m = fields.Float(string="X від, м", digits=(8, 1))
    to_x_m = fields.Float(string="X до, м", digits=(8, 1))
    detectors_count = fields.Integer(compute="_compute_device_counts", store=True)
    mcp_count = fields.Integer(compute="_compute_device_counts", store=True)
    sounders_count = fields.Integer(compute="_compute_device_counts", store=True)
    flame_count = fields.Integer(compute="_compute_device_counts", store=True)
    modules_count = fields.Integer(string="Модулі вводу")
    device_count = fields.Integer(compute="_compute_device_counts", store=True)
    signal_id = fields.Many2one("td.signal", string="Сигнал несправності (BV)", ondelete="set null")
    state = fields.Selection(
        [("unknown", "Невідомо"), ("ok", "Норма"), ("fault", "Несправність")], default="unknown", readonly=True)
    fault_since = fields.Datetime(readonly=True)
    request_id = fields.Many2one("maintenance.request", related="signal_id.maintenance_request_id", readonly=True)
    device_ids = fields.One2many("td.fire.device", "loop_id")

    _f3d_fire_loop_number_uniq = models.Constraint(
        "UNIQUE(panel_id, number)", "Номер шлейфу має бути унікальним у межах приладу")

    @api.constrains("number")
    def _check_number(self):
        for rec in self:
            if not 1 <= rec.number <= 8:
                raise ValidationError("Номер шлейфу: 1…8")

    @api.depends("number")
    def _compute_name(self):
        for rec in self:
            rec.name = "Шлейф %d" % rec.number

    @api.depends("device_ids.type", "device_ids.active")
    def _compute_device_counts(self):
        for rec in self:
            devices = rec.device_ids.filtered("active")
            rec.device_count = len(devices)
            rec.detectors_count = len(devices.filtered(lambda d: d.type in ("smoke", "multi", "heat")))
            rec.mcp_count = len(devices.filtered(lambda d: d.type == "mcp"))
            rec.sounders_count = len(devices.filtered(lambda d: d.type == "sounder"))
            rec.flame_count = len(devices.filtered(lambda d: d.type == "flame"))

    def _set_state(self, new, ts):
        for rec in self:
            if new == rec.state:
                continue
            vals = {"state": new}
            if new == "fault":
                vals["fault_since"] = ts
            old = rec.state
            rec.write(vals)
            Event = self.env["td.fire.event"]
            if new == "fault":
                Event._log("loop_fault", "%s/L%d" % (rec.panel_id.code, rec.number), ts,
                           "Несправність шлейфу %d приладу %s" % (rec.number, rec.panel_id.code),
                           loop_id=rec.id, panel_id=rec.panel_id.id, signal_id=rec.signal_id.id)
            elif old == "fault":
                Event._log("loop_ok", "%s/L%d" % (rec.panel_id.code, rec.number), ts,
                           "Шлейф %d: несправність усунено" % rec.number,
                           loop_id=rec.id, panel_id=rec.panel_id.id, signal_id=rec.signal_id.id)

    @api.model
    def loop_of(self, x):
        """Шлейф, для якого from_x_m ≤ x < to_x_m, інакше порожньо."""
        return self.search([("from_x_m", "<=", x), ("to_x_m", ">", x)], limit=1)
