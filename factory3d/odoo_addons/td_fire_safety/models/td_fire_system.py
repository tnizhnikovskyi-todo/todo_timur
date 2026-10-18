import math

from odoo import api, fields, models
from odoo.exceptions import ValidationError

SYS_LABEL = {"spark": "Іскрогасіння", "smoke": "Димовидалення", "sprinkler": "Спринклери"}

# R-13 п. 8: короткий підпис (systems_text)
SHORT_LABEL = {
    ("spark", "ok"): "норма", ("spark", "active"): "спрацювання", ("spark", "fault"): "несправність",
    ("spark", "unknown"): "немає даних",
    ("smoke", "ok"): "норма", ("smoke", "active"): "спрацювання", ("smoke", "fault"): "несправність",
    ("smoke", "battery"): "від АКБ", ("smoke", "unknown"): "немає даних",
    ("sprinkler", "ok"): "очікування", ("sprinkler", "low_pressure"): "низький тиск",
    ("sprinkler", "unknown"): "немає даних",
}


class F3dFireSystem(models.Model):
    _name = "f3d.fire.system"
    _inherit = ["mail.thread"]
    _description = "Пожежна безпека: система"
    _order = "sequence, code"
    _rec_name = "name"

    code = fields.Char(string="Код сцени", size=32, required=True, index=True)
    name = fields.Char(size=128, required=True)
    sequence = fields.Integer(default=10)
    system_type = fields.Selection(
        [("spark", "Іскрогасіння"), ("smoke", "Димовидалення"), ("sprinkler", "Спринклери")], required=True)
    panel_id = fields.Many2one("f3d.fire.panel", required=True, ondelete="cascade")
    equipment_id = fields.Many2one("maintenance.equipment", ondelete="set null")
    vents_equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання люків", ondelete="set null")
    source_id = fields.Many2one("f3d.source", ondelete="set null")
    signal_state_id = fields.Many2one("f3d.signal", string="Сигнал: стан", ondelete="set null")
    signal_active_id = fields.Many2one("f3d.signal", string="Сигнал: гасіння", ondelete="set null")
    signal_fault_id = fields.Many2one("f3d.signal", string="Сигнал: несправність", ondelete="set null")
    signal_water_id = fields.Many2one("f3d.signal", string="Сигнал: тиск води гасіння", ondelete="set null")
    signal_battery_id = fields.Many2one("f3d.signal", string="Сигнал: живлення від АКБ", ondelete="set null")
    signal_count_id = fields.Many2one("f3d.signal", string="Сигнал: іскор за добу", ondelete="set null")
    pressure_signal_id = fields.Many2one("f3d.signal", string="Сигнал: тиск", ondelete="set null")
    pressure_bar = fields.Float(related="pressure_signal_id.last_value", string="Тиск, бар")
    pressure_min_bar = fields.Float(related="pressure_signal_id.alarm_low", string="Мінімум, бар")
    state = fields.Selection(
        [("unknown", "Невідомо"), ("ok", "Норма"), ("active", "Спрацювання"), ("fault", "Несправність"),
         ("battery", "Від акумуляторів"), ("low_pressure", "Низький тиск")],
        default="unknown", readonly=True, index=True, tracking=True)
    state_text = fields.Char(compute="_compute_state_text")
    state_ts = fields.Datetime(readonly=True)
    stale = fields.Boolean(readonly=True)
    count_today = fields.Integer(string="Іскор за добу", readonly=True)
    count_ts = fields.Datetime(readonly=True)
    device_ids = fields.One2many("f3d.fire.device", "system_id")
    detector_count = fields.Integer(compute="_compute_counts", store=True)
    nozzle_count = fields.Integer(compute="_compute_counts", store=True)
    vent_count = fields.Integer(compute="_compute_counts", store=True)
    smoke_zone_ids = fields.One2many("f3d.fire.smoke.zone", "system_id")
    drive_current_a = fields.Float(string="Струм приводу, А", default=7.5)
    panel_current_a = fields.Float(string="Струм щита, А", default=80.0)
    panels_needed = fields.Integer(compute="_compute_panels")
    vent_area_m2 = fields.Float(compute="_compute_panels", digits=(8, 1))
    last_test_date = fields.Date(string="Остання перевірка")
    note = fields.Text()
    active = fields.Boolean(default=True)

    _f3d_fire_system_code_uniq = models.Constraint("UNIQUE(code)", "Код системи має бути унікальним.")

    @api.constrains("system_type", "pressure_signal_id")
    def _check_pressure(self):
        for rec in self:
            if rec.system_type in ("spark", "smoke") and rec.pressure_signal_id:
                raise ValidationError("Сигнал тиску — лише для спринклерів.")

    @api.depends("device_ids.type", "device_ids.active")
    def _compute_counts(self):
        for rec in self:
            devices = rec.device_ids.filtered("active")
            rec.detector_count = len(devices.filtered(lambda d: d.type == "spark_detector"))
            rec.nozzle_count = len(devices.filtered(lambda d: d.type == "spark_nozzle"))
            rec.vent_count = len(devices.filtered(lambda d: d.type == "smoke_vent"))

    @api.depends("vent_count", "drive_current_a", "panel_current_a")
    def _compute_panels(self):
        aa = self.env["f3d.fire.norm"].get("smoke_vent_aa", 0.0)
        for rec in self:
            rec.panels_needed = (
                math.ceil(rec.vent_count * rec.drive_current_a / rec.panel_current_a - 1e-9)
                if rec.panel_current_a else 0)
            rec.vent_area_m2 = rec.vent_count * aa

    @api.depends("state", "system_type", "count_today", "pressure_bar", "pressure_min_bar", "signal_water_id.last_text")
    def _compute_state_text(self):
        for rec in self:
            t, s = rec.system_type, rec.state
            if s == "unknown":
                text = "Спринклерна система: немає даних тиску" if t == "sprinkler" else "Немає даних"
            elif t == "spark":
                if s == "ok":
                    text = "Норма, іскор за добу — %d" % rec.count_today
                elif s == "active":
                    text = "Спрацювання: іскру гасять"
                else:
                    text = "Несправність"
                    if rec.signal_water_id.last_text == "low":
                        text += " — немає тиску води"
            elif t == "smoke":
                text = {"ok": "Клапани закриті, живлення від мережі", "active": "Клапани відкриті",
                        "fault": "Несправність щита D+H",
                        "battery": "Живлення від акумуляторів (резерв 72 год)"}.get(s, "Немає даних")
            else:
                if s == "low_pressure":
                    text = "Спринклерна система: тиск %s бар нижче норми %s бар" % (
                        _fmt(rec.pressure_bar), _fmt(rec.pressure_min_bar))
                else:
                    text = "Спринклерна система в режимі очікування"
            rec.state_text = text

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()  # f3d.signal._f3d_fire_extra_codes (M-15)
        return records

    def write(self, vals):
        res = super().write(vals)
        if "pressure_signal_id" in vals or "active" in vals:
            self.env.registry.clear_cache()
        return res

    def _set_state(self, new, ts, etype=None, text=None):
        self.ensure_one()
        vals = {"state_ts": ts}
        if new != self.state:
            vals["state"] = new
        self.write(vals)
        if etype:
            self.env["f3d.fire.event"]._log(
                etype, self.code, ts, text or self.state_text, system_id=self.id, panel_id=self.panel_id.id)
        from .f3d_fire_panel import fire_notify
        fire_notify(self.env, "f3d.fire.panel", [self.panel_id.code], "state")

    def action_f3d_show(self):
        self.ensure_one()
        if not self.equipment_id:
            from odoo.exceptions import UserError
            raise UserError("Система не прив'язана до обладнання зі сцени.")
        return self.equipment_id.action_f3d_show()

    def action_view_devices(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Пристрої системи", "res_model": "f3d.fire.device",
                "view_mode": "list,form", "domain": [("system_id", "=", self.id)]}

    def action_view_events(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Події системи", "res_model": "f3d.fire.event",
                "view_mode": "list,form,graph", "domain": [("system_id", "=", self.id)]}


def _fmt(value):
    return ("%g" % round(value, 2)).replace(".", ",")
