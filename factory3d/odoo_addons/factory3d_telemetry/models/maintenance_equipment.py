from datetime import timedelta
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools.titles import fmt_num

KYIV = ZoneInfo("Europe/Kyiv")


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    f3d_signal_ids = fields.One2many("f3d.signal", "equipment_id", string="Сигнали")
    f3d_signal_count = fields.Integer(compute="_compute_f3d_signal_counts", string="Сигналів")
    f3d_alarm_count = fields.Integer(compute="_compute_f3d_signal_counts", string="Тривог")
    f3d_stale_count = fields.Integer(compute="_compute_f3d_signal_counts", string="Без даних")
    f3d_meter_signal_id = fields.Many2one(
        "f3d.signal",
        string="Лічильник для ТО",
        ondelete="set null",
        tracking=True,
        domain="[('kind', '=', 'counter'), '|', ('equipment_id', '=', id), ('equipment_id', '=', False)]",
    )
    f3d_meter_unit = fields.Char(related="f3d_meter_signal_id.unit", string="Одиниця лічильника")
    f3d_meter_interval = fields.Float(
        string="Інтервал ТО", digits=(12, 1), help="У одиницях лічильника: мотогодини, цикли, м³"
    )
    f3d_meter_last_value = fields.Float(string="Останнє ТО при показнику", digits=(12, 1))
    f3d_meter_last_date = fields.Date(string="Дата останнього ТО")
    f3d_meter_lead_pct = fields.Float(
        string="Планувати за, % інтервалу",
        default=lambda self: float(
            self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.meter_lead_pct", "5") or 5
        ),
    )
    f3d_meter_next_value = fields.Float(
        string="Наступне ТО при показнику", compute="_compute_f3d_meter", store=True, digits=(12, 1)
    )
    f3d_meter_current = fields.Float(string="Показник зараз", compute="_compute_f3d_meter_current", digits=(12, 1))
    f3d_meter_remaining = fields.Float(string="Лишилось до ТО", compute="_compute_f3d_meter_current", digits=(12, 1))
    f3d_meter_request_id = fields.Many2one(
        "maintenance.request", string="Планова заявка", ondelete="set null", readonly=True
    )

    def _compute_f3d_signal_counts(self):
        counts = {}
        if self.ids:
            groups = self.env["f3d.signal"]._read_group(
                [("equipment_id", "in", self.ids)], ["equipment_id", "status"], ["__count"]
            )
            for eq, status, n in groups:
                c = counts.setdefault(eq.id, {"all": 0, "alarm": 0, "stale": 0})
                c["all"] += n
                c["alarm"] += n if status == "alarm" else 0
                c["stale"] += n if status == "stale" else 0
        for rec in self:
            c = counts.get(rec.id, {})
            rec.f3d_signal_count = c.get("all", 0)
            rec.f3d_alarm_count = c.get("alarm", 0)
            rec.f3d_stale_count = c.get("stale", 0)

    @api.depends("f3d_meter_last_value", "f3d_meter_interval")
    def _compute_f3d_meter(self):
        for rec in self:
            if rec.f3d_meter_interval:
                rec.f3d_meter_next_value = rec.f3d_meter_last_value + rec.f3d_meter_interval
            else:
                rec.f3d_meter_next_value = 0.0

    @api.depends("f3d_meter_signal_id.last_value", "f3d_meter_next_value")
    def _compute_f3d_meter_current(self):
        for rec in self:
            rec.f3d_meter_current = rec.f3d_meter_signal_id.last_value or 0.0
            rec.f3d_meter_remaining = rec.f3d_meter_next_value - rec.f3d_meter_current

    @api.constrains("f3d_meter_signal_id", "f3d_meter_interval")
    def _check_f3d_meter(self):
        for rec in self:
            sig = rec.f3d_meter_signal_id
            if not sig:
                continue
            if rec.f3d_meter_interval <= 0:
                raise ValidationError(_("Задайте інтервал ТО за лічильником (> 0)."))
            if sig.equipment_id and sig.equipment_id != rec:
                raise ValidationError(_("Лічильник належить іншому обладнанню."))

    # --- R-11 ----------------------------------------------------------------------------------------
    def _f3d_default_team(self):
        self.ensure_one()
        if self.maintenance_team_id:
            return self.maintenance_team_id
        param = self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.default_team_id") or ""
        return self.env["maintenance.team"].browse(int(param)) if param.isdigit() else self.env["maintenance.team"]

    def _f3d_meter_rate(self, signal, now):
        """Приріст лічильника за годину за останні 7 діб (з годинних агрегатів); 0 — невідомо."""
        rows = (
            self.env["f3d.reading.hour"]
            .sudo()
            ._read_group([("signal_id", "=", signal.id), ("hour", ">=", now - timedelta(days=7))], [], ["delta:sum"])
        )
        total = rows[0][0] if rows else 0.0
        return (total or 0.0) / 168.0

    def _f3d_meter_check(self):
        """R-11: заявка ТО, коли лічильник наблизився до порога `next − lead`."""
        now = fields.Datetime.now()
        Request = self.env["maintenance.request"].sudo()
        for rec in self.sudo():
            sig = rec.f3d_meter_signal_id
            if not sig or rec.f3d_meter_interval <= 0 or not sig.last_ts or sig.status == "unknown":
                continue
            if rec.f3d_meter_request_id and not rec.f3d_meter_request_id.stage_id.done:
                continue
            current = sig.last_value
            nxt = rec.f3d_meter_last_value + rec.f3d_meter_interval
            lead = rec.f3d_meter_interval * rec.f3d_meter_lead_pct / 100.0
            if current < nxt - lead:
                continue
            rate = rec._f3d_meter_rate(sig, now)
            wait_h = max(0.0, (nxt - current) / rate) if rate > 0 else 0.0
            team = rec._f3d_default_team()
            name = _(
                "ТО за лічильником: %(code)s — %(next)s %(unit)s (зараз %(cur)s)",
                code=rec.f3d_code or rec.name,
                next=fmt_num(nxt, 0),
                unit=sig.unit or "",
                cur=fmt_num(current, 0),
            )
            request = Request.create(
                {
                    "name": name,
                    "equipment_id": rec.id,
                    "maintenance_type": "preventive",
                    "maintenance_team_id": team.id or False,
                    "priority": "3" if current >= nxt else "1",
                    "request_date": fields.Date.today(),
                    "schedule_date": now + timedelta(hours=wait_h),
                    "recurring_maintenance": False,
                    "f3d_signal_id": sig.id,
                    "f3d_origin": "meter",
                    "f3d_value": current,
                    "f3d_threshold": nxt,
                }
            )
            rec.with_context(mail_notrack=True).f3d_meter_request_id = request.id
            rec.message_post(
                body=_("Створено заявку ТО за лічильником: %s", request.name), subtype_xmlid="mail.mt_note"
            )

    def _f3d_meter_closed(self, request):
        """R-11 п. 5: ТО виконано — зафіксувати показник і дату, перерахувати наступне."""
        today = fields.Datetime.now().replace(tzinfo=ZoneInfo("UTC")).astimezone(KYIV).date()
        for rec in self.sudo():
            sig = rec.f3d_meter_signal_id
            if not sig:
                continue
            vals = {"f3d_meter_last_value": sig.last_value, "f3d_meter_last_date": today}
            if rec.f3d_meter_request_id == request or not rec.f3d_meter_request_id:
                vals["f3d_meter_request_id"] = False
            rec.with_context(mail_notrack=True).write(vals)
            rec.message_post(
                body=_("ТО за лічильником виконано при %s", fmt_num(sig.last_value, 0)), subtype_xmlid="mail.mt_note"
            )

    # --- дії -----------------------------------------------------------------------------------------
    def action_f3d_view_signals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Сигнали"),
            "res_model": "f3d.signal",
            "view_mode": "list,form,graph,pivot",
            "domain": [("equipment_id", "=", self.id)],
            "context": {"default_equipment_id": self.id, "search_default_active": 1},
        }

    def action_f3d_view_readings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Показання"),
            "res_model": "f3d.reading",
            "view_mode": "graph,list",
            "domain": [("equipment_id", "=", self.id)],
            "context": {"search_default_last_48h": 1},
        }
