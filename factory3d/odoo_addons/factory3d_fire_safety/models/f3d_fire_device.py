import logging
import math
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import geometry
from .f3d_fire_zone import BACK_TO_NORMAL, ENTER

_logger = logging.getLogger(__name__)

ADDRESS_RE = re.compile(r"^[0-4]\.[A-Z0-9-]{2,8}\.[0-9]{2}$")
TYPES = [
    ("smoke", "Димовий оптичний"), ("multi", "Оптико-тепловий"), ("heat", "Тепловий"), ("mcp", "Ручний"),
    ("sounder", "Оповіщувач"), ("flame", "Полум'я"), ("spark_detector", "Датчик іскор"),
    ("spark_nozzle", "Форсунка гасіння"), ("smoke_vent", "Люк димовидалення")]
TYPE_NAME = {
    "smoke": "Сповіщувач", "multi": "Сповіщувач", "heat": "Сповіщувач", "mcp": "Ручний сповіщувач",
    "sounder": "Оповіщувач", "flame": "Сповіщувач полум'я", "spark_detector": "Датчик іскор",
    "spark_nozzle": "Форсунка гасіння", "smoke_vent": "Люк димовидалення"}
DETECTORS = ("smoke", "multi", "heat")
CNET = ("smoke", "multi", "heat", "mcp", "sounder", "flame")
OFF_LOOP = ("spark_detector", "spark_nozzle", "smoke_vent")
FAULT_STATES = ["fault", "tamper", "abnormal", "emergency-power", "supervisory"]
DUST_ORDER = {"na": 0, "ok": 1, "warn": 2, "alarm": 3}


class F3dFireDevice(models.Model):
    _name = "f3d.fire.device"
    _description = "Пожежна сигналізація: пристрій"
    _order = "loop_id, zone_id, seq, address"
    _rec_name = "name"
    _rec_names_search = ["address", "name"]

    address = fields.Char(string="Адреса", size=16, required=True, index=True)
    name = fields.Char(compute="_compute_name", store=True)
    type = fields.Selection(TYPES, required=True, index=True)
    is_detector = fields.Boolean(compute="_compute_is_detector", store=True)
    panel_id = fields.Many2one("f3d.fire.panel", ondelete="cascade", index=True)
    loop_id = fields.Many2one("f3d.fire.loop", ondelete="restrict")
    zone_id = fields.Many2one("f3d.fire.zone", string="Зона виявлення", ondelete="restrict", index=True)
    plant_zone_id = fields.Many2one("f3d.zone", string="Зона цеху", compute="_compute_plant_zone", store=True)
    system_id = fields.Many2one("f3d.fire.system", ondelete="restrict")
    smoke_zone_id = fields.Many2one("f3d.fire.smoke.zone", ondelete="set null")
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання групи", ondelete="set null")
    model = fields.Char(related="equipment_id.f3d_model")
    lsp_instance = fields.Integer(string="BACnet LSP instance", index=True)
    seq = fields.Integer(string="№ у групі")
    x = fields.Float(digits=(8, 2), required=True)
    y = fields.Float(digits=(8, 2), required=True)
    z = fields.Float(digits=(8, 2), default=0.0)
    side = fields.Selection(
        [("W", "Захід"), ("E", "Схід"), ("S", "Південь"), ("N", "Північ"), ("P", "Стійка"), ("X", "Вісь X"),
         ("Y", "Вісь Y")])
    heading_deg = fields.Float(digits=(6, 1))
    state = fields.Selection(
        [("unknown", "Невідомо"), ("normal", "Норма"), ("prealarm", "Передтривога"), ("alarm", "Тривога"),
         ("fault", "Несправність"), ("disabled", "Вимкнено"), ("test", "Тест"), ("active", "Активний")],
        default="unknown", readonly=True, index=True)
    raw_state = fields.Char(size=32, readonly=True)
    reliability = fields.Char(size=32, readonly=True)
    state_ts = fields.Datetime(readonly=True)
    dust_pct = fields.Float(string="Запиленість, %", digits=(5, 1), readonly=True)
    dust_ts = fields.Datetime(readonly=True)
    dust_state = fields.Selection(
        [("na", "—"), ("ok", "Норма"), ("warn", "Попередження"), ("alarm", "Очистити")],
        compute="_compute_dust_state", store=True)
    monitor = fields.Boolean(string="Окремі сигнали", default=False, groups="factory3d_base.group_f3d_manager")
    state_signal_id = fields.Many2one("f3d.signal", string="Сигнал стану (LSP)", ondelete="set null")
    dust_signal_id = fields.Many2one("f3d.signal", string="Сигнал запиленості (PIV)", ondelete="set null")
    maintenance_request_id = fields.Many2one("maintenance.request", compute="_compute_request")
    event_count = fields.Integer(compute="_compute_event_count")
    note = fields.Text()
    active = fields.Boolean(default=True)

    _f3d_fire_device_address_uniq = models.Constraint("UNIQUE(address)", "Адреса пристрою має бути унікальною.")
    _f3d_fire_device_lsp_uniq = models.UniqueIndex(
        "(lsp_instance) WHERE lsp_instance > 0", "BACnet LSP instance має бути унікальним.")

    # --- compute ------------------------------------------------------------------------------------------
    @api.depends("type", "address")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s %s" % (TYPE_NAME.get(rec.type, ""), rec.address or "")

    @api.depends("type")
    def _compute_is_detector(self):
        for rec in self:
            rec.is_detector = rec.type in DETECTORS

    @api.depends("type", "zone_id.zone_id", "x", "y")
    def _compute_plant_zone(self):
        Zone = self.env["f3d.zone"]
        for rec in self:
            if rec.is_detector or rec.type in DETECTORS:
                rec.plant_zone_id = rec.zone_id.zone_id
            else:
                rec.plant_zone_id = Zone.zone_at(rec.x, rec.y)

    @api.depends("dust_pct", "dust_ts")
    def _compute_dust_state(self):
        panel = self.env["f3d.fire.panel"]
        warn_pct = panel._get_param("dust_warn_pct", 80.0)
        alarm_pct = panel._get_param("dust_alarm_pct", 90.0)
        for rec in self:
            if not rec.dust_ts:
                rec.dust_state = "na"
            elif rec.dust_pct >= alarm_pct:
                rec.dust_state = "alarm"
            elif rec.dust_pct >= warn_pct:
                rec.dust_state = "warn"
            else:
                rec.dust_state = "ok"

    def _compute_request(self):
        Request = self.env["maintenance.request"]
        has_device = "f3d_fire_device_id" in Request._fields
        has_signal = "f3d_signal_id" in Request._fields
        for rec in self:
            conds = []
            if has_device:
                conds.append([("f3d_fire_device_id", "=", rec.id)])
            signals = (rec.state_signal_id | rec.dust_signal_id).ids
            if has_signal and signals:
                conds.append([("f3d_signal_id", "in", signals)])
            request = Request.browse()
            if conds:
                dom = [("stage_id.done", "=", False)] + ["|"] * (len(conds) - 1) + [c for cd in conds for c in cd]
                request = Request.search(dom, limit=1, order="id")
            rec.maintenance_request_id = request

    def _compute_event_count(self):
        Event = self.env["f3d.fire.event"]
        for rec in self:
            rec.event_count = Event.search_count([("device_id", "=", rec.id)])

    # --- обмеження ----------------------------------------------------------------------------------------
    @api.constrains("address", "type", "loop_id")
    def _check_address(self):
        for rec in self:
            if not rec.address or not ADDRESS_RE.match(rec.address):
                raise ValidationError(
                    "Адреса пристрою: <шлейф>.<ЗОНА>.<nn>, напр. 2.FAC.07 (отримано %s)" % rec.address)
            if rec.type in CNET:
                expected = rec.loop_id.number if rec.loop_id else None
            else:
                expected = 0
            if expected is not None and int(rec.address[0]) != expected:
                raise ValidationError("Адреса %s не відповідає шлейфу %s." % (rec.address, expected))

    @api.constrains("type", "zone_id")
    def _check_zone(self):
        for rec in self:
            if (rec.type in DETECTORS) != bool(rec.zone_id):
                raise ValidationError("Сповіщувач зони має належати зоні виявлення; інші пристрої — ні")

    @api.constrains("type", "loop_id", "panel_id", "system_id", "smoke_zone_id")
    def _check_links(self):
        for rec in self:
            if rec.type in CNET and not (rec.loop_id and rec.panel_id):
                raise ValidationError("Пристрій %s на шлейфі приладу: вкажіть шлейф і прилад." % rec.address)
            if rec.type in OFF_LOOP and not rec.system_id:
                raise ValidationError("Пристрій %s належить системі: вкажіть систему." % rec.address)
            if rec.type == "smoke_vent" and not rec.smoke_zone_id:
                raise ValidationError("Люк %s має належати димовій зоні." % rec.address)

    @api.constrains("x", "y", "z")
    def _check_coords(self):
        x0, y0, x1, y1 = geometry.site_bounds(self.env)
        for rec in self:
            if not (x0 <= rec.x <= x1 and y0 <= rec.y <= y1 and 0 <= rec.z <= 12):
                raise ValidationError("Координати пристрою %s поза територією (CB-04/CB-12)." % rec.address)

    # --- R-23 ---------------------------------------------------------------------------------------------
    @api.model
    def lsp_id(self, loop, ordinal, nn):
        if not (1 <= loop <= 8 and 1 <= ordinal <= 99 and 1 <= nn <= 99):
            raise ValueError("LSP: шлейф 1…8, номер групи 1…99, номер 1…99")
        return loop * 10000 + ordinal * 100 + nn

    # --- стан ---------------------------------------------------------------------------------------------
    def _set_state(self, new_state, raw, ts, reliability=None):
        self.ensure_one()
        old = self.state
        vals = {"raw_state": raw, "state_ts": ts}
        if reliability is not None:
            vals["reliability"] = reliability
        if new_state != old:
            vals["state"] = new_state
        self.write(vals)
        if new_state == old:
            return
        entry = None
        if new_state == "normal":
            entry = BACK_TO_NORMAL.get(old)
        elif new_state in ("alarm", "prealarm", "fault", "disabled", "test"):
            entry = ENTER[new_state]
        if not entry:
            return
        etype, template = entry
        zone = self.zone_id
        z = "%s (%s)" % (zone.code, zone.name) if zone else self.address
        text = template.format(z=z, raw=raw or "", dd=", сповіщувач %s" % self.address)
        if etype in ("fault", "fault_ok", "disabled", "enabled") or not zone:
            text = "%s: %s" % (self.name, text)
        self.env["f3d.fire.event"]._log(
            etype, self.address, ts, text, device_id=self.id, zone_id=zone.id if zone else False,
            panel_id=self.panel_id.id if self.panel_id else False)

    def _set_dust(self, pct, ts, log=True):
        self.ensure_one()
        old = self.dust_state
        self.write({"dust_pct": pct, "dust_ts": ts})
        new = self.dust_state
        if not log or new == old:
            return
        etype = None
        if new == "warn" and old in ("na", "ok"):
            etype = "dust_warn"
        elif new == "alarm":
            etype = "dust_alarm"
        elif new == "ok" and old in ("warn", "alarm"):
            etype = "dust_ok"
        if not etype:
            return
        zone = self.zone_id
        zname = zone.name if zone else ""
        floor = math.floor(pct)
        if etype == "dust_warn":
            loc = ", %s" % self.note if self.note else ""
            text = "Попередження про запиленість: сповіщувач %s (%s%s) — %d %%" % (self.address, zname, loc, floor)
        elif etype == "dust_alarm":
            alarm_pct = int(self.env["f3d.fire.panel"]._get_param("dust_alarm_pct", 90.0))
            text = "Запиленість сповіщувача %s (%s) %d %% понад %d %%" % (self.address, zname, floor, alarm_pct)
        else:
            text = "Сповіщувач %s: запиленість %d %% — у нормі" % (self.address, floor)
        self.env["f3d.fire.event"]._log(
            etype, self.address, ts, text, device_id=self.id, zone_id=zone.id if zone else False,
            panel_id=self.panel_id.id if self.panel_id else False, signal_id=self.dust_signal_id.id)

    # --- сигнали (A-02) -----------------------------------------------------------------------------------
    def action_create_signals(self):
        Signal = self.env["f3d.signal"].with_context(active_test=False)
        panel_param = self.env["f3d.fire.panel"]
        warn_pct = panel_param._get_param("dust_warn_pct", 80.0)
        alarm_pct = panel_param._get_param("dust_alarm_pct", 90.0)
        created = 0
        for dev in self.filtered(lambda d: d.type in CNET and d.panel_id.source_id):
            source = dev.panel_id.source_id
            zone_name = dev.zone_id.name or dev.plant_zone_id.name or ""
            if not dev.state_signal_id:
                code = "fire/devices/%s/state" % dev.address
                sig = Signal.search([("code", "=", code)], limit=1)
                if sig:
                    sig.active = True
                else:
                    sig = Signal.create({
                        "code": code, "name": "%s: стан" % dev.name, "kind": "state", "unit": "",
                        "equipment_id": dev.equipment_id.id, "source_id": source.id,
                        "address": {"object": "LSP", "instance": dev.lsp_instance, "mode": "poll"},
                        "period_s": 10, "store_period_s": 3600, "viewer_visible": False,
                        "module": "fire_safety", "origin": "module", "write_enabled": False,
                        "alarm_states": FAULT_STATES,
                        "alarm_title": "Несправність пристрою %s (%s): стан {text}" % (dev.address, zone_name)})
                    created += 1
                dev.state_signal_id = sig
            if dev.is_detector and not dev.dust_signal_id:
                code = "fire/devices/%s/dust" % dev.address
                sig = Signal.search([("code", "=", code)], limit=1)
                if sig:
                    sig.active = True
                else:
                    sig = Signal.create({
                        "code": code, "name": "%s: запиленість" % dev.name, "kind": "gauge", "unit": "%",
                        "equipment_id": dev.equipment_id.id, "source_id": source.id,
                        "address": {"object": "PIV", "instance": dev.lsp_instance, "mode": "poll"},
                        "period_s": 600, "store_period_s": 3600, "decimals": 1, "hysteresis": 1.8,
                        "warn_high_on": True, "alarm_high_on": True,
                        "warn_high": warn_pct, "alarm_high": alarm_pct,
                        "viewer_visible": False, "module": "fire_safety", "origin": "module",
                        "write_enabled": False,
                        "alarm_title": ("Очистити сповіщувач %s (%s): запиленість {value} % при нормі до "
                                        "{threshold}" % (dev.address, zone_name))})
                    created += 1
                dev.dust_signal_id = sig
            dev.sudo().monitor = True
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": "Пожежна безпека", "message": "Створено сигналів: %d" % created,
                           "type": "success", "sticky": False}}

    def action_remove_signals(self):
        for dev in self:
            dev.sudo().monitor = False
            for sig in (dev.state_signal_id, dev.dust_signal_id):
                if not sig:
                    continue
                if sig == dev.zone_id.dust_signal_id:
                    continue  # сигнал запиленості 2.FAC.07 належить зоні
                sig.sudo().active = False
        return True

    def action_f3d_show(self):
        self.ensure_one()
        if self.equipment_id:
            return self.equipment_id.action_f3d_show()
        if self.plant_zone_id:
            return self.plant_zone_id.action_f3d_show()
        raise UserError("Пристрій не прив'язаний до об'єкта сцени.")
