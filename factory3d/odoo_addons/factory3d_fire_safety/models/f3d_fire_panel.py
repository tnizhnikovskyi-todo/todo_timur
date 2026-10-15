import logging
import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import geometry
from .f3d_fire_system import SHORT_LABEL, SYS_LABEL

_logger = logging.getLogger(__name__)

STATES = [
    ("unknown", "Невідомо"), ("normal", "Норма"), ("prealarm", "Передтривога"), ("alarm", "ТРИВОГА"),
    ("fault", "Несправність"), ("disabled", "Вимкнення"), ("test", "Тест")]
PRIORITY = {"alarm": 6, "prealarm": 5, "fault": 4, "disabled": 3, "test": 2, "normal": 1, "unknown": 0}
PARAM_PREFIX = "factory3d.fire_safety."


def fire_notify(env, model, codes, kind="state"):
    """Подія шини переглядача (CF-04); без factory3d_viewer — нічого."""
    if "f3d.viewer.event" in env:
        try:
            env["f3d.viewer.event"]._notify(model, list(codes), kind)
        except Exception:  # шина не повинна ламати зміну стану
            _logger.exception("f3d.viewer.event._notify(%s, %s) не вдалося", model, codes)


def _plural_warnings(n):
    if n % 10 in (1, 2, 3, 4) and n % 100 not in (11, 12, 13, 14):
        return "%d попередження" % n
    return "%d попереджень" % n


def _names(zones):
    names = [z.name for z in zones[:3]]
    text = ", ".join(names)
    if len(zones) > 3:
        text += " та ще %d" % (len(zones) - 3)
    return text


class F3dFirePanel(models.Model):
    _name = "f3d.fire.panel"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Пожежна сигналізація: прилад"
    _order = "name"

    name = fields.Char(string="Назва", size=128, required=True, default="Приймально-контрольний прилад")
    code = fields.Char(string="Код сцени", size=32, required=True, index=True, default="FACP-1")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання", ondelete="set null", domain=[("f3d_code", "!=", False)])
    manufacturer = fields.Char(related="equipment_id.f3d_manufacturer", readonly=True)
    model = fields.Char(related="equipment_id.f3d_model", readonly=True)
    zone_id = fields.Many2one("f3d.zone", string="Зона розміщення", ondelete="set null")
    x = fields.Float(string="X, м", digits=(8, 2))
    y = fields.Float(string="Y, м", digits=(8, 2))
    source_id = fields.Many2one(
        "f3d.source", string="Джерело BACnet", domain=[("type", "=", "bacnet_ip")], ondelete="set null")
    io_source_id = fields.Many2one(
        "f3d.source", string="Джерело вводів (ADAM)", domain=[("type", "=", "modbus_tcp")], ondelete="set null")
    signal_state_id = fields.Many2one("f3d.signal", string="Сигнал: стан приладу (LSZ:0)", ondelete="set null")
    signal_system_id = fields.Many2one("f3d.signal", string="Сигнал: системний стан (MSV:1)", ondelete="set null")
    signal_alarms_id = fields.Many2one("f3d.signal", string="Сигнал: тривоги (PIV:1)", ondelete="set null")
    signal_faults_id = fields.Many2one("f3d.signal", string="Сигнал: несправності (PIV:2)", ondelete="set null")
    signal_disabled_id = fields.Many2one("f3d.signal", string="Сигнал: вимкнення (PIV:3)", ondelete="set null")
    signal_sounders_id = fields.Many2one("f3d.signal", string="Сигнал: оповіщувачі (BV:10)", ondelete="set null")
    signal_brigade_id = fields.Many2one("f3d.signal", string="Сигнал: передача на пульт (BV:11)", ondelete="set null")
    state = fields.Selection(STATES, default="unknown", readonly=True, index=True, tracking=True)
    raw_state = fields.Char(string="Стан LSZ:0", size=32, readonly=True)
    system_state = fields.Integer(string="MSV:1", readonly=True)
    state_text = fields.Char(compute="_compute_state_text")
    state_ts = fields.Datetime(string="Стан з")
    comm = fields.Selection(
        [("online", "Онлайн"), ("stale", "Дані застарілі"), ("lost", "Зв'язок втрачено"),
         ("off", "Обробка вимкнена")], default="lost", readonly=True, tracking=True)
    last_seen = fields.Datetime(string="Останнє показання", readonly=True)
    comm_since = fields.Datetime(string="Стан зв'язку з")
    comm_request_id = fields.Many2one("maintenance.request", string="Заявка про зв'язок", ondelete="set null")
    alarm_activity_id = fields.Many2one("mail.activity", ondelete="set null")
    alarms_count = fields.Integer(readonly=True)
    faults_count = fields.Integer(readonly=True)
    disabled_count = fields.Integer(readonly=True)
    sounders_active = fields.Boolean(readonly=True)
    brigade_transmitted = fields.Boolean(readonly=True)
    loop_ids = fields.One2many("f3d.fire.loop", "panel_id")
    zone_ids = fields.One2many("f3d.fire.zone", "panel_id")
    zone_count = fields.Integer(compute="_compute_counts")
    device_count = fields.Integer(compute="_compute_counts")
    event_count = fields.Integer(compute="_compute_counts")
    warn_count = fields.Integer(compute="_compute_counts")
    alarm_zone_count = fields.Integer(compute="_compute_counts")
    alarm_zone_ids = fields.Many2many("f3d.fire.zone", compute="_compute_counts")
    compliance_mcp_max_m = fields.Float(
        string="Найбільша відстань до ручного сповіщувача, м", digits=(8, 1), readonly=True)
    compliance_mcp_point = fields.Char(size=32, readonly=True)
    compliance_mcp_ok = fields.Boolean(readonly=True)
    compliance_sounder_max_m = fields.Float(
        string="Найбільша відстань до оповіщувача, м", digits=(8, 1), readonly=True)
    compliance_zones_ok = fields.Integer(readonly=True)
    compliance_zones_total = fields.Integer(readonly=True)
    compliance_missing_zones = fields.Char(string="Зони цеху без сигналізації", readonly=True)
    compliance_ts = fields.Datetime(string="Перераховано", readonly=True)
    compliance_routes_ok = fields.Integer(readonly=True)
    compliance_routes_total = fields.Integer(readonly=True)
    compliance_exits_ok = fields.Boolean(readonly=True)
    compliance_exit_pair_m = fields.Float(
        string="Найбільша відстань між виходами, м", digits=(8, 1), readonly=True)
    compliance_exit_l_m = fields.Float(string="Потрібна розосередженість L, м", digits=(8, 1), readonly=True)
    compliance_smoke_ok = fields.Integer(readonly=True)
    compliance_smoke_total = fields.Integer(readonly=True)
    evac_max_distance_m = fields.Float(string="Найдовший шлях до виходу (макет), м", digits=(8, 1))
    evac_worst_x = fields.Float(digits=(8, 2))
    evac_worst_y = fields.Float(digits=(8, 2))
    system_ids = fields.One2many("f3d.fire.system", "panel_id")
    systems_text = fields.Char(compute="_compute_systems_text")
    compliance_dirty = fields.Boolean(default=True)
    first_sync = fields.Boolean(default=True)
    read_enabled = fields.Boolean(compute="_compute_read_enabled")
    viewer_available = fields.Boolean(compute="_compute_availability")
    sim_available = fields.Boolean(compute="_compute_availability")

    _f3d_fire_panel_code_uniq = models.Constraint("UNIQUE(code)", "Код приладу має бути унікальним.")

    # --- параметри ----------------------------------------------------------------------------------------
    @api.model
    def _get_param(self, key, default=None):
        value = self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + key)
        if value is None or value == "":
            return default
        if isinstance(default, bool):
            return value in ("True", "true", "1")
        try:
            if isinstance(default, int):
                return int(float(value))
            if isinstance(default, float):
                return float(value)
        except ValueError:
            return default
        return value

    # --- compute ------------------------------------------------------------------------------------------
    @api.depends("state", "comm", "zone_ids.state", "zone_ids.warn", "zone_ids.name")
    def _compute_state_text(self):
        for rec in self:
            zones = rec.zone_ids
            alarm = zones.filtered(lambda z: z.state == "alarm")
            prealarm = zones.filtered(lambda z: z.state == "prealarm")
            fault = zones.filtered(lambda z: z.state == "fault")
            disabled = zones.filtered(lambda z: z.state == "disabled")
            warn_count = len(zones.filtered("warn"))
            if rec.comm == "off":
                rec.state_text = "Обробка вимкнена"
                continue
            if rec.comm == "lost":
                rec.state_text = "Зв'язок із приладом втрачено"
                continue
            state = rec.state
            if state == "normal":
                text = "Норма"
            elif state == "alarm":
                text = "ТРИВОГА: %s" % _names(alarm) if alarm else "ТРИВОГА"
            elif state == "prealarm":
                text = "Передтривога: %s" % _names(prealarm) if prealarm else "Передтривога"
            elif state == "fault":
                text = "Несправність: %s" % _names(fault) if fault else "Несправність"
            elif state == "disabled":
                text = "Вимкнення: %d зон" % len(disabled)
            elif state == "test":
                text = "Тест"
            else:
                text = "Немає даних"
            if state in ("normal", "test") and warn_count:
                text += ", " + _plural_warnings(warn_count)
            if rec.comm == "stale":
                text += " (дані застарілі)"
            rec.state_text = text

    def _compute_counts(self):
        Zone, Device, Event = self.env["f3d.fire.zone"], self.env["f3d.fire.device"], self.env["f3d.fire.event"]
        since = fields.Datetime.now() - timedelta(days=7)
        for rec in self:
            zones = Zone.search([("panel_id", "=", rec.id)])
            rec.zone_count = len(zones)
            rec.device_count = Device.search_count([("panel_id", "=", rec.id)])
            rec.event_count = Event.search_count([("panel_id", "=", rec.id), ("ts", ">=", since)])
            rec.warn_count = len(zones.filtered("warn"))
            alarm = zones.filtered(lambda z: z.state in ("alarm", "prealarm"))
            rec.alarm_zone_ids = alarm
            rec.alarm_zone_count = len(zones.filtered(lambda z: z.state == "alarm"))

    @api.depends("system_ids.state", "system_ids.code", "system_ids.system_type")
    def _compute_systems_text(self):
        for rec in self:
            parts = []
            for system in rec.system_ids.sorted("code"):
                label = SHORT_LABEL.get((system.system_type, system.state), "немає даних")
                parts.append("%s: %s" % (SYS_LABEL[system.system_type], label))
            rec.systems_text = " · ".join(parts)

    def _compute_read_enabled(self):
        value = self._get_param("read_enabled", True)
        for rec in self:
            rec.read_enabled = value

    def _compute_availability(self):
        viewer = "f3d.viewer.provider" in self.env
        sim = "f3d.sim.panel" in self.env
        for rec in self:
            rec.viewer_available = viewer
            rec.sim_available = sim

    # --- стан ---------------------------------------------------------------------------------------------
    def _set_state(self, new_state, raw, ts, source="signal"):
        self.ensure_one()
        old = self.state
        if new_state == old:
            if raw != self.raw_state:
                self.write({"raw_state": raw})
            return
        self.write({"state": new_state, "raw_state": raw, "state_ts": ts})
        Event = self.env["f3d.fire.event"]
        zones = self.zone_ids
        if new_state == "fault" and not zones.filtered(lambda z: z.state == "fault"):
            Event._log("fault", self.code, ts, "Несправність приладу %s: стан %s" % (self.code, raw),
                       source=source, panel_id=self.id)
        elif new_state == "normal" and old != "unknown":
            Event._log("reset", self.code, ts, "Прилад %s: стан «Норма»" % self.code,
                       source=source, panel_id=self.id)
        if new_state in ("alarm", "prealarm") and not zones.filtered(
                lambda z: z.state in ("alarm", "prealarm")):
            self._notify_alarm()
        if old == "alarm" and new_state in ("normal",):
            self._close_alarm_activity()
        fire_notify(self.env, "f3d.fire.panel", [self.code], "state")

    def _set_comm(self, comm, ts):
        """R-12 п. 4–6: зміна зв'язку, події, активність."""
        self.ensure_one()
        old = self.comm
        if comm == old:
            return
        vals = {"comm": comm, "comm_since": ts}
        Event = self.env["f3d.fire.event"]
        first = self.first_sync
        if comm == "online":
            vals["first_sync"] = False
        self.write(vals)
        self.zone_ids.write({"stale": comm in ("stale", "lost")})
        if comm == "off":
            return
        if comm == "online":
            Event._log("comm_restored", self.code, ts, "Зв'язок із приладом %s відновлено" % self.code,
                       panel_id=self.id)
            self._close_comm_activity()
        elif comm == "stale" and old == "online":
            age = int((ts - self.last_seen).total_seconds()) if self.last_seen else 0
            Event._log("comm_stale", self.code, ts,
                       "Дані приладу %s застарілі: немає показань %d с" % (self.code, age), panel_id=self.id)
        elif comm == "lost" and not (first and old == "lost") and old in ("online", "stale"):
            minutes = int((ts - self.last_seen).total_seconds() // 60) if self.last_seen else 0
            since = self.last_seen.strftime("%H:%M") if self.last_seen else "—"
            from ..tools.dates import local
            if self.last_seen:
                since = local(self.last_seen)[-5:]
            ev = Event._log(
                "comm_lost", self.code, ts,
                "Зв'язок із приладом %s втрачено: немає даних з %s (%d хв)" % (self.code, since, minutes),
                panel_id=self.id)
            self._schedule_activity(
                "Втрата зв'язку з приладом %s" % self.code, ev.text if ev else "")
            if hasattr(self, "_f3d_fire_comm_request"):
                self._f3d_fire_comm_request(ts)
        fire_notify(self.env, "f3d.fire.panel", [self.code], "state")

    # --- синхронізація з сигналами (R-19, R-22 п. 3) -------------------------------------------------------
    @api.model
    def _f3d_fire_sync(self, codes=None, full=False):
        from ..tools.sync import FireSync
        return FireSync(self.env).run(codes=codes, full=full)

    @api.model
    def _cron_sync(self):
        """Крон «звірка станів і зв'язку» (A-22): наздоганяє push, виставляє зв'язок."""
        return self._f3d_fire_sync(full=True)

    def _f3d_fire_comm_request(self, ts):
        """Заявка ТО про втрату зв'язку (R-22 п. 3): одна відкрита на прилад."""
        self.ensure_one()
        request = self.comm_request_id
        if request.exists() and not request.stage_id.done:
            return request
        equipment = self.equipment_id
        if not equipment:
            _logger.warning("Прилад %s без обладнання: заявку про втрату зв'язку не створено", self.code)
            return False
        from ..tools.dates import local
        icp = self.env["ir.config_parameter"].sudo()
        team = self.env["maintenance.team"]
        for param_team in (self._get_param("team_id", 0), equipment.maintenance_team_id.id,
                           int(icp.get_param("factory3d.telemetry.default_team_id") or 0)):
            if param_team:
                team = team.browse(param_team).exists()
                if team:
                    break
        since = local(self.last_seen)[-5:] if self.last_seen else "—"
        minutes = int((ts - self.last_seen).total_seconds() // 60) if self.last_seen else 0
        request = self.env["maintenance.request"].sudo().create({
            "name": "Втрата зв'язку з приладом %s: немає даних з %s (%d хв)" % (self.code, since, minutes),
            "equipment_id": equipment.id,
            "maintenance_type": "corrective",
            "maintenance_team_id": team.id or False,
            "priority": "3",
            "f3d_origin": "fire_comm",
            "request_date": fields.Date.today(),
            "schedule_date": fields.Datetime.now(),
            "description": "Автоматично: немає показань приладу %s (джерело %s) з %s; поріг %d с." % (
                self.code, self.source_id.code or "—", local(self.last_seen) if self.last_seen else "—",
                self._get_param("comm_lost_after_s", 180)),
        })
        self.sudo().write({"comm_request_id": request.id})
        event = self.env["f3d.fire.event"].search(
            [("etype", "=", "comm_lost"), ("panel_id", "=", self.id)], order="ts desc, id desc", limit=1)
        if event and not event.request_id:
            event.request_id = request.id
        return request

    # --- сповіщення ---------------------------------------------------------------------------------------
    def _alert_users(self):
        xmlid = self._get_param("alert_group_xmlid", "factory3d_base.group_f3d_user")
        group = self.env.ref(xmlid, raise_if_not_found=False)
        if not group:
            return self.env["res.users"]
        users = self.env["res.users"].sudo().search([("group_ids", "in", group.id), ("share", "=", False)])
        return users.filtered("active")

    def _schedule_activity(self, summary, note):
        """Активність «Пожежна тривога» кожному користувачу охорони; повертає створені."""
        self.ensure_one()
        act_xmlid = "factory3d_fire_safety.mail_act_fire_alarm"
        created = self.env["mail.activity"]
        for user in self._alert_users():
            try:
                with self.env.cr.savepoint():
                    created |= self.sudo().activity_schedule(
                        act_xmlid, user_id=user.id, summary=summary, note=note or summary)
            except Exception:
                _logger.warning("Не вдалося створити активність для користувача %s", user.login, exc_info=True)
        return created

    def _notify_alarm(self, zone=None, device=None):
        self.ensure_one()
        if self.alarm_activity_id and self.alarm_activity_id.exists():
            return
        zone_text = zone.display if zone else self.code
        dev_text = device.address if device else "—"
        summary = "Пожежна тривога: %s, сповіщувач %s" % (zone_text, dev_text)
        event = self.env["f3d.fire.event"].search(
            [("etype", "in", ("alarm", "prealarm")), ("panel_id", "=", self.id)], limit=1)
        created = self._schedule_activity(summary, event.text if event else summary)
        if created:
            self.sudo().write({"alarm_activity_id": created[0].id})
        fire_notify(self.env, "f3d.fire.panel", [self.code], "state")

    def _close_comm_activity(self):
        for rec in self:
            acts = rec.sudo().activity_ids.filtered(
                lambda a: a.activity_type_id == self.env.ref("factory3d_fire_safety.mail_act_fire_alarm")
                and (a.summary or "").startswith("Втрата зв'язку"))
            acts.action_feedback(feedback="Зв'язок відновлено")

    def _close_alarm_activity(self):
        act_type = self.env.ref("factory3d_fire_safety.mail_act_fire_alarm")
        for rec in self:
            acts = rec.sudo().activity_ids.filtered(
                lambda a: a.activity_type_id == act_type and not (a.summary or "").startswith("Втрата зв'язку"))
            if acts:
                acts.action_feedback(feedback="Прилад скинуто")
            rec.sudo().alarm_activity_id = False

    # --- відповідність нормам (R-01…R-09) -----------------------------------------------------------------
    @api.model
    def _schedule_compliance(self):
        self.sudo().search([]).write({"compliance_dirty": True})

    @api.model
    def _cron_compliance(self):
        self.search([("compliance_dirty", "=", True)]).action_recompute_compliance()

    def _plant_size(self):
        icp = self.env["ir.config_parameter"].sudo()
        return (float(icp.get_param("factory3d.base.plant_length_m", 150)),
                float(icp.get_param("factory3d.base.plant_width_m", 72)))

    def _recompute_exits(self, panel):
        """R-06 п. 1–3, 5 + R-07: підсумок рахує `f3d.fire.exit._dispersal_summary` (M-09)."""
        Exit = self.env["f3d.fire.exit"]
        Exit.search([])._recompute()
        res = Exit._dispersal_summary()
        return {"compliance_exit_l_m": res["l_m"], "compliance_exit_pair_m": res["pair_m"],
                "compliance_exits_ok": res["ok"]}

    def action_recompute_compliance(self):
        note = ""
        for panel in self.sudo():
            zones = panel.zone_ids
            for zone in zones:
                zone._compute_required()
                zone._compute_coverage()
            vals = {
                "compliance_zones_total": len(zones),
                "compliance_zones_ok": len(zones.filtered(lambda z: z.compliance == "ok")),
            }
            Device = self.env["f3d.fire.device"]
            length, width = self._plant_size()
            mcps = Device.search([("type", "=", "mcp"), ("panel_id", "=", panel.id)])
            gap, pt = geometry.plant_grid_gap([(d.x, d.y) for d in mcps], length, width)
            if gap == math.inf:
                gap, pt_text = geometry.INF_GAP, ""
            else:
                pt_text = geometry.fmt_point(*pt)
            vals.update({
                "compliance_mcp_max_m": round(gap, 1), "compliance_mcp_point": pt_text,
                "compliance_mcp_ok": gap <= self.env["f3d.fire.norm"].get("mcp_spacing", 30.0)})
            snd = Device.search([("type", "=", "sounder"), ("panel_id", "=", panel.id)])
            gap_s, _pt = geometry.plant_grid_gap([(d.x, d.y) for d in snd], length, width)
            vals["compliance_sounder_max_m"] = geometry.INF_GAP if gap_s == math.inf else round(gap_s, 1)
            # R-08
            fire_zone_ids = set(self.env["f3d.fire.zone"].search([("panel_id", "!=", False)]).mapped("zone_id").ids)
            missing = self.env["f3d.zone"].search([("zone_type", "!=", "outdoor")]).filtered(
                lambda z: z.id not in fire_zone_ids)
            vals["compliance_missing_zones"] = ", ".join(sorted(missing.mapped("f3d_code"))) or False
            # R-05…R-09 (моделі W3 — за наявності)
            routes_ok = routes_total = smoke_ok = smoke_total = 0
            if "f3d.fire.exit" in self.env:
                vals.update(self._recompute_exits(panel))
            if "f3d.fire.route" in self.env:
                routes = self.env["f3d.fire.route"].search([])
                routes._recompute()
                routes_total, routes_ok = len(routes), len(routes.filtered(lambda r: r.compliance == "ok"))
            if "f3d.fire.smoke.zone" in self.env:
                smoke = self.env["f3d.fire.smoke.zone"].search([])
                smoke._recompute()
                smoke_total, smoke_ok = len(smoke), len(smoke.filtered(lambda r: r.compliance == "ok"))
            vals.update({
                "compliance_routes_ok": routes_ok, "compliance_routes_total": routes_total,
                "compliance_smoke_ok": smoke_ok, "compliance_smoke_total": smoke_total,
                "compliance_ts": fields.Datetime.now(), "compliance_dirty": False})
            panel.write(vals)
            note = "Перераховано: зони %d/%d, ручні max %s м, маршрути %d/%d, димові зони %d/%d" % (
                vals["compliance_zones_ok"], vals["compliance_zones_total"],
                ("%.1f" % vals["compliance_mcp_max_m"]).replace(".", ","),
                routes_ok, routes_total, smoke_ok, smoke_total)
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": "Пожежна безпека", "message": note, "type": "success", "sticky": False}}

    # --- дії ----------------------------------------------------------------------------------------------
    def action_f3d_show(self):
        self.ensure_one()
        if not self.equipment_id:
            raise UserError("Прилад не прив'язаний до обладнання зі сцени.")
        return self.equipment_id.action_f3d_show()

    def action_view_3d_alarm(self):
        self.ensure_one()
        zone = self.alarm_zone_ids[:1]
        if zone and zone.equipment_id:
            return zone.equipment_id.action_f3d_show()
        return self.action_f3d_show()

    def _act_window(self, model, name, domain, view_mode="list,form", context=None):
        return {"type": "ir.actions.act_window", "name": name, "res_model": model, "view_mode": view_mode,
                "domain": domain, "context": context or {}}

    def action_view_zones(self):
        self.ensure_one()
        return self._act_window("f3d.fire.zone", "Зони сигналізації", [("panel_id", "=", self.id)],
                                "kanban,list,form")

    def action_view_devices(self):
        self.ensure_one()
        return self._act_window("f3d.fire.device", "Пристрої", [("panel_id", "=", self.id)])

    def action_view_events(self):
        self.ensure_one()
        since = fields.Datetime.now() - timedelta(days=7)
        return self._act_window("f3d.fire.event", "Події за 7 діб",
                                [("panel_id", "=", self.id), ("ts", ">=", since)], "list,form,graph")

    def action_view_requests(self):
        self.ensure_one()
        equipment = (self.equipment_id | self.zone_ids.equipment_id).ids
        return self._act_window(
            "maintenance.request", "Заявки ТО",
            [("equipment_id", "in", equipment), ("stage_id.done", "=", False)])

    def action_set_bacnet_device(self):
        self.ensure_one()
        if not self.source_id:
            raise UserError("Прилад не має джерела BACnet.")
        old = (self.source_id.params or {}).get("device")
        return {
            "type": "ir.actions.act_window", "name": "Змінити BACnet device",
            "res_model": "f3d.fire.bacnet.device.wizard", "view_mode": "form", "target": "new",
            "context": {"default_panel_id": self.id, "default_old_instance": old or 0}}

    def action_add_comment(self):
        self.ensure_one()
        view = self.env.ref("factory3d_fire_safety.view_f3d_fire_event_form_manual", raise_if_not_found=False)
        return {
            "type": "ir.actions.act_window", "name": "Коментар у журнал", "res_model": "f3d.fire.event",
            "view_mode": "form", "view_id": view.id if view else False, "target": "new",
            "context": {"default_etype": "manual", "default_level": "info", "default_source": "manual",
                        "default_object_code": self.code, "default_panel_id": self.id}}

    def _f3d_print_evac_report(self):
        self.ensure_one()
        if self.compliance_dirty:
            self.action_recompute_compliance()
        report = self.env.ref("factory3d_fire_safety.report_f3d_fire_evac_compliance", raise_if_not_found=False)
        if not report:
            raise UserError("Звіт перевірки евакуації не встановлено.")
        return report.report_action(self)
