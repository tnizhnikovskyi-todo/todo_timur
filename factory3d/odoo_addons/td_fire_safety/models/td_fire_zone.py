import math
import re
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import geometry
from .td_fire_panel import STATES, fire_notify

CODE_RE = re.compile(r"^FA-[A-Z0-9-]{2,10}$")
KINDS = [("smoke", "Димові оптичні"), ("multi", "Оптико-теплові (пил деревини)"), ("heat", "Теплові")]
COLORS = {"normal": 10, "warn": 3, "fault": 2, "disabled": 2, "alarm": 1, "prealarm": 1, "test": 4, "unknown": 0}
# перехід у стан → (etype, текст-шаблон); {z} — «код (назва)», {dd} — «, сповіщувач адреса», {raw} — сирий стан
ENTER = {
    "alarm": ("alarm", "ТРИВОГА: зона {z}{dd}"),
    "prealarm": ("prealarm", "Передтривога: зона {z}{dd}"),
    "fault": ("fault", "Несправність зони {z}: стан {raw}"),
    "disabled": ("disabled", "Зону {z} вимкнено на приладі"),
    "test": ("test", "Тест: зона {z}{dd}"),
}
BACK_TO_NORMAL = {
    "fault": ("fault_ok", "Зона {z}: несправність усунено"),
    "disabled": ("enabled", "Зону {z} увімкнено"),
    "test": ("test_end", "Тест завершено: зона {z}"),
    "alarm": ("reset", "Зона {z}: тривогу скинуто"),
    "prealarm": ("reset", "Зона {z}: тривогу скинуто"),
}


class F3dFireZone(models.Model):
    _name = "td.fire.zone"
    _description = "Пожежна сигналізація: зона виявлення"
    _order = "lsz_instance"
    _rec_name = "display"
    _rec_names_search = ["code", "name", "zone_id.name"]

    code = fields.Char(string="Код групи", size=16, required=True, index=True)
    name = fields.Char(string="Назва", size=128, required=True)
    display = fields.Char(compute="_compute_display", store=True)
    panel_id = fields.Many2one("td.fire.panel", required=True, ondelete="cascade", index=True)
    loop_id = fields.Many2one("td.fire.loop", string="Шлейф", required=True, ondelete="restrict")
    zone_id = fields.Many2one("td.zone", string="Зона цеху", required=True, ondelete="restrict", index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання (група сповіщувачів)", ondelete="set null"
    )
    lsz_instance = fields.Integer(string="BACnet LSZ instance", required=True)
    ordinal = fields.Integer(related="lsz_instance")
    kind = fields.Selection(KINDS, required=True)
    kind_name = fields.Char(compute="_compute_kind_name")
    spacing_m = fields.Float(string="Крок, м", digits=(6, 1))
    wall_m = fields.Float(string="До стіни, м", digits=(6, 1))
    x0 = fields.Float(string="Контур виявлення, м", digits=(8, 2))
    y0 = fields.Float(digits=(8, 2))
    x1 = fields.Float(digits=(8, 2))
    y1 = fields.Float(digits=(8, 2))
    area_m2 = fields.Float(compute="_compute_area", store=True, digits=(12, 0))
    z_m = fields.Float(string="Висота встановлення, м", digits=(6, 2))
    device_ids = fields.One2many("td.fire.device", "zone_id")
    detector_count = fields.Integer(compute="_compute_detector_count", store=True)
    n_required = fields.Integer(string="Потрібно за ДБН", readonly=True)
    n_ok = fields.Boolean(readonly=True)
    cover_max_gap_m = fields.Float(string="Найбільший розрив покриття, м", digits=(6, 2), readonly=True)
    cover_point = fields.Char(size=32, readonly=True)
    cover_ok = fields.Boolean(readonly=True)
    compliance = fields.Selection(
        [("na", "Не перевірено"), ("ok", "Відповідає"), ("warn", "Зауваження"), ("fail", "Не відповідає")],
        default="na",
        readonly=True,
        index=True,
    )
    compliance_note = fields.Text(readonly=True)
    signal_id = fields.Many2one("td.signal", string="Сигнал стану (LSZ)", ondelete="set null")
    dust_signal_id = fields.Many2one("td.signal", string="Сигнал запиленості зони", ondelete="set null")
    state = fields.Selection(STATES, default="unknown", readonly=True, index=True)
    raw_state = fields.Char(size=32, readonly=True)
    state_ts = fields.Datetime(readonly=True)
    stale = fields.Boolean(readonly=True, default=False)
    warn = fields.Boolean(compute="_compute_warn", store=True)
    warning = fields.Text(compute="_compute_warn", store=True)
    dust_max_pct = fields.Float(compute="_compute_warn", store=True)
    maintenance_request_id = fields.Many2one("maintenance.request", compute="_compute_request")
    maintenance_request_name = fields.Char(compute="_compute_request")
    color = fields.Integer(compute="_compute_color")
    event_count = fields.Integer(compute="_compute_event_count")
    active = fields.Boolean(default=True)

    _f3d_fire_zone_code_uniq = models.Constraint("UNIQUE(code)", "Код групи має бути унікальним.")
    _f3d_fire_zone_lsz_uniq = models.Constraint(
        "UNIQUE(panel_id, lsz_instance)", "BACnet LSZ instance має бути унікальним у межах приладу."
    )

    # --- обмеження ----------------------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not CODE_RE.match(rec.code):
                raise ValidationError("Код групи: FA-<зона>")

    @api.constrains("x0", "y0", "x1", "y1")
    def _check_rect(self):
        sx0, sy0, sx1, sy1 = geometry.site_bounds(self.env)
        for rec in self:
            if not (
                rec.x0 < rec.x1
                and rec.y0 < rec.y1
                and sx0 <= rec.x0
                and rec.x1 <= sx1
                and sy0 <= rec.y0
                and rec.y1 <= sy1
            ):
                raise ValidationError("Контур виявлення %s: некоректний прямокутник" % rec.code)

    @api.constrains("spacing_m", "wall_m")
    def _check_spacing(self):
        for rec in self:
            if rec.spacing_m <= 0 or rec.wall_m <= 0:
                raise ValidationError("Крок і відстань до стіни мають бути більшими за нуль (%s)." % rec.code)

    # --- compute ------------------------------------------------------------------------------------------
    @api.depends("code", "name")
    def _compute_display(self):
        for rec in self:
            rec.display = "%s · %s" % (rec.code, rec.name)

    def _compute_kind_name(self):
        names = dict(KINDS)
        for rec in self:
            rec.kind_name = names.get(rec.kind, "")

    def _all_detectors(self):
        """Детектори зони, включно з архівними."""
        self.ensure_one()
        return (
            self.env["td.fire.device"]
            .with_context(active_test=False)
            .search([("zone_id", "=", self.id), ("is_detector", "=", True)])
        )

    def _floors(self):
        """Висоти поверхів зони — різні `z` сповіщувачів, включно з архівними (мінімум один поверх)."""
        z_values = sorted({round(d.z, 2) for d in self._all_detectors()})
        return z_values or [round(self.z_m, 2)]

    @api.depends("x0", "y0", "x1", "y1", "device_ids.z", "device_ids.active")
    def _compute_area(self):
        for rec in self:
            floors = len(rec._floors()) if rec.id else 1
            rec.area_m2 = round((rec.x1 - rec.x0) * (rec.y1 - rec.y0) * floors)

    @api.depends("device_ids.type", "device_ids.active")
    def _compute_detector_count(self):
        for rec in self:
            rec.detector_count = len(
                rec.device_ids.filtered(lambda d: d.active and d.type in ("smoke", "multi", "heat"))
            )

    @api.depends(
        "device_ids.dust_state",
        "device_ids.dust_pct",
        "device_ids.state",
        "device_ids.reliability",
        "device_ids.raw_state",
        "device_ids.note",
        "device_ids.active",
    )
    def _compute_warn(self):
        Norm = self.env["td.fire.norm"]
        alarm_pct = self.env["td.fire.panel"]._get_param("dust_alarm_pct", 90.0)
        for rec in self:
            devices = rec.device_ids.filtered("active")
            rec.dust_max_pct = max(devices.mapped("dust_pct") or [0.0])
            worst, rank = None, 0
            for dev in devices.sorted("address"):
                if dev.dust_state == "alarm":
                    r = 5
                elif dev.dust_state == "warn":
                    r = 4
                elif dev.state == "fault":
                    r = 3
                elif dev.state == "disabled":
                    r = 2
                elif dev.reliability and dev.reliability != "no-fault-detected":
                    r = 1
                else:
                    r = 0
                if r > rank:
                    worst, rank = dev, r
            rec.warn = bool(worst)
            if not worst:
                rec.warning = False
                continue
            loc = (" " + worst.note) if worst.note else ""
            pct = math.floor(worst.dust_pct)
            if rank == 4:
                rec.warning = (
                    "Сповіщувач %s%s: запиленість камери %d %% — очистити до кінця зміни, інакше "
                    "прилад переведе його в несправність." % (worst.address, loc, pct)
                )
            elif rank == 5:
                rec.warning = (
                    "Сповіщувач %s%s: запиленість камери %d %% понад %d %% — потрібне очищення "
                    "(заявка ТО)." % (worst.address, loc, pct, alarm_pct)
                )
            elif rank == 3:
                rec.warning = "Пристрій %s%s: несправність (%s)." % (
                    worst.address,
                    loc,
                    worst.raw_state or worst.reliability,
                )
            elif rank == 2:
                rec.warning = "Пристрій %s%s: вимкнено на приладі." % (worst.address, loc)
            else:
                rec.warning = "Пристрій %s%s: несправність (%s)." % (worst.address, loc, worst.reliability)

    def _compute_request(self):
        Request = self.env["maintenance.request"]
        has_zone = "td_fire_zone_id" in Request._fields
        has_signal = "td_signal_id" in Request._fields
        for rec in self:
            domain = [("stage_id.done", "=", False)]
            conds = []
            if has_zone:
                conds.append([("td_fire_zone_id", "=", rec.id)])
            signals = (
                rec.signal_id | rec.dust_signal_id | rec.device_ids.state_signal_id | rec.device_ids.dust_signal_id
            ).ids
            if has_signal and signals:
                conds.append([("td_signal_id", "in", signals)])
            request = Request.browse()
            if conds:
                dom = domain + (["|"] * (len(conds) - 1)) + [c for cond in conds for c in cond]
                request = Request.search(dom, limit=1, order="id")
            rec.maintenance_request_id = request
            rec.maintenance_request_name = request.name if request else False

    @api.depends("state", "warn")
    def _compute_color(self):
        for rec in self:
            rec.color = COLORS["warn"] if rec.state == "normal" and rec.warn else COLORS.get(rec.state, 0)

    def _compute_event_count(self):
        since = fields.Datetime.now() - timedelta(days=30)
        for rec in self:
            rec.event_count = self.env["td.fire.event"].search_count([("zone_id", "=", rec.id), ("ts", ">=", since)])

    # --- відповідність (R-01, R-02) -----------------------------------------------------------------------
    def _step(self):
        """R-01 п. 1: крок сітки s або (None, ключ відсутньої норми)."""
        self.ensure_one()
        Norm = self.env["td.fire.norm"]
        prefix = "heat" if self.kind == "heat" else "smoke"
        spacing_key = "heat_spacing" if prefix == "heat" else "smoke_spacing_6_12m"
        wall_key = "heat_wall" if prefix == "heat" else "smoke_wall_6_12m"
        area_key = "heat_area" if prefix == "heat" else "smoke_area_6_12m"
        spacing, wall = Norm.get(spacing_key), Norm.get(wall_key)
        if spacing is None:
            return None, spacing_key
        if wall is None:
            return None, wall_key
        s = min(spacing, 2 * wall)
        area = Norm.get(area_key)
        if area is not None and area > 0:
            s = min(s, math.sqrt(area))
        return s, None

    def _compute_required(self):
        for rec in self:
            s, missing = rec._step()
            if s is None:
                rec.write(
                    {
                        "n_required": 0,
                        "n_ok": False,
                        "compliance": "na",
                        "compliance_note": "Норма %s не задана" % missing,
                    }
                )
                continue
            nx = max(1, math.ceil((rec.x1 - rec.x0) / s - 1e-9))
            ny = max(1, math.ceil((rec.y1 - rec.y0) / s - 1e-9))
            n = nx * ny * len(rec._floors())
            rec.write({"n_required": n, "n_ok": rec.detector_count >= n})

    def _compute_coverage(self):
        panel = self.env["td.fire.panel"]
        tol = panel._get_param("cover_tol_m", 0.5)
        for rec in self:
            s, missing = rec._step()
            if s is None:
                continue  # compliance='na' уже виставлено _compute_required
            r = s / math.sqrt(2)
            detectors = rec._all_detectors()
            by_floor = []
            for z in rec._floors():
                by_floor.append([(d.x, d.y) for d in detectors if d.active and round(d.z, 2) == z] if detectors else [])
            gap, pt = geometry.coverage_gap(by_floor, rec.x0, rec.y0, rec.x1, rec.y1)
            infinite = gap == math.inf
            gap_v = geometry.INF_GAP if infinite else round(gap, 2)
            cover_ok = (not infinite) and gap <= r + tol
            if not rec.n_ok or infinite or gap > r + 2 * tol:
                compliance = "fail"
            elif not cover_ok:
                compliance = "warn"
            else:
                compliance = "ok"
            nx = max(1, math.ceil((rec.x1 - rec.x0) / s - 1e-9))
            ny = max(1, math.ceil((rec.y1 - rec.y0) / s - 1e-9))
            gap_text = "—" if infinite else gap_v
            note = (
                "Потрібно %d (%d×%d при кроці %s м), є %d. Покриття: найбільший розрив %s м у точці %s "
                "при радіусі %s м + допуск %s м."
                % (
                    rec.n_required,
                    nx,
                    ny,
                    round(s, 2),
                    rec.detector_count,
                    gap_text,
                    geometry.fmt_point(*pt),
                    round(r, 2),
                    tol,
                )
            )
            rec.write(
                {
                    "cover_max_gap_m": gap_v,
                    "cover_point": "" if infinite else geometry.fmt_point(*pt),
                    "cover_ok": cover_ok,
                    "compliance": compliance,
                    "compliance_note": note,
                }
            )

    def action_recompute(self):
        self._compute_required()
        self._compute_coverage()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "Пожежна безпека", "message": "Зону перераховано.", "type": "success"},
        }

    # --- стан ---------------------------------------------------------------------------------------------
    def _set_state(self, new_state, raw, ts, device=None):
        self.ensure_one()
        old = self.state
        if new_state == old:
            if raw != self.raw_state:
                self.write({"raw_state": raw})
            return
        self.write({"state": new_state, "raw_state": raw, "state_ts": ts})
        entry = None
        if new_state == "normal":
            entry = BACK_TO_NORMAL.get(old)
        elif new_state in ENTER:
            entry = ENTER[new_state]
        if entry:
            etype, template = entry
            text = template.format(
                z="%s (%s)" % (self.code, self.name),
                raw=raw or "",
                dd=(", сповіщувач %s" % device.address) if device else "",
            )
            self.env["td.fire.event"]._log(
                etype,
                self.code,
                ts,
                text,
                zone_id=self.id,
                device_id=device.id if device else False,
                panel_id=self.panel_id.id,
            )
        if new_state in ("alarm", "prealarm"):
            self.panel_id._notify_alarm(self, device)
        if (
            new_state in ("test", "alarm")
            and "td.fire.drill" in self.env
            and hasattr(self.env["td.fire.drill"], "_match_test_alarm")
        ):
            self.env["td.fire.drill"]._match_test_alarm(self, device, ts, real=(new_state == "alarm"))
        fire_notify(self.env, "td.fire.zone", [self.code], "state")
        if self.zone_id.td_code:
            fire_notify(self.env, "td.zone", [self.zone_id.td_code], "state")

    # --- дії ----------------------------------------------------------------------------------------------
    def action_f3d_show(self):
        self.ensure_one()
        if self.equipment_id:
            return self.equipment_id.action_f3d_show()
        return self.zone_id.action_f3d_show()

    def _act_window(self, model, name, domain):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_view_devices(self):
        self.ensure_one()
        return self._act_window("td.fire.device", "Сповіщувачі зони", [("zone_id", "=", self.id)])

    def action_view_events(self):
        self.ensure_one()
        return self._act_window("td.fire.event", "Події зони", [("zone_id", "=", self.id)])

    def action_view_requests(self):
        self.ensure_one()
        if not self.maintenance_request_id:
            raise UserError("Для зони немає відкритих заявок ТО.")
        return {
            "type": "ir.actions.act_window",
            "res_model": "maintenance.request",
            "view_mode": "form",
            "res_id": self.maintenance_request_id.id,
        }

    def action_create_device_signals(self):
        return self.device_ids.action_create_signals()

    def point_inside(self, x, y):
        self.ensure_one()
        return geometry.point_in_rect(x, y, self.x0, self.y0, self.x1, self.y1)
