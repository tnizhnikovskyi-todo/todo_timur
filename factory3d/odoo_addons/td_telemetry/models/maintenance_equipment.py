from datetime import timedelta
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools.titles import fmt_num

KYIV = ZoneInfo("Europe/Kyiv")


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    td_signal_ids = fields.One2many("td.signal", "equipment_id", string="Сигнали")
    td_signal_count = fields.Integer(compute="_compute_f3d_signal_counts", string="Сигналів")
    td_alarm_count = fields.Integer(compute="_compute_f3d_signal_counts", string="Тривог")
    td_stale_count = fields.Integer(compute="_compute_f3d_signal_counts", string="Без даних")
    td_meter_signal_id = fields.Many2one(
        "td.signal",
        string="Лічильник для ТО",
        ondelete="set null",
        tracking=True,
        domain="[('kind', '=', 'counter'), '|', ('equipment_id', '=', id), ('equipment_id', '=', False)]",
    )
    td_meter_unit = fields.Char(related="td_meter_signal_id.unit", string="Одиниця лічильника")
    td_meter_interval = fields.Float(
        string="Інтервал ТО", digits=(12, 1), help="У одиницях лічильника: мотогодини, цикли, м³"
    )
    td_meter_last_value = fields.Float(string="Останнє ТО при показнику", digits=(12, 1))
    td_meter_last_date = fields.Date(string="Дата останнього ТО")
    td_meter_lead_pct = fields.Float(
        string="Планувати за, % інтервалу",
        default=lambda self: float(
            self.env["ir.config_parameter"].sudo().get_param("td.telemetry.meter_lead_pct", "5") or 5
        ),
    )
    td_meter_next_value = fields.Float(
        string="Наступне ТО при показнику", compute="_compute_f3d_meter", store=True, digits=(12, 1)
    )
    td_meter_current = fields.Float(string="Показник зараз", compute="_compute_f3d_meter_current", digits=(12, 1))
    td_meter_remaining = fields.Float(string="Лишилось до ТО", compute="_compute_f3d_meter_current", digits=(12, 1))
    td_meter_request_id = fields.Many2one(
        "maintenance.request", string="Планова заявка", ondelete="set null", readonly=True
    )

    def _compute_f3d_signal_counts(self):
        counts = {}
        if self.ids:
            groups = self.env["td.signal"]._read_group(
                [("equipment_id", "in", self.ids)], ["equipment_id", "status"], ["__count"]
            )
            for eq, status, n in groups:
                c = counts.setdefault(eq.id, {"all": 0, "alarm": 0, "stale": 0})
                c["all"] += n
                c["alarm"] += n if status == "alarm" else 0
                c["stale"] += n if status == "stale" else 0
        for rec in self:
            c = counts.get(rec.id, {})
            rec.td_signal_count = c.get("all", 0)
            rec.td_alarm_count = c.get("alarm", 0)
            rec.td_stale_count = c.get("stale", 0)

    @api.depends("td_meter_last_value", "td_meter_interval")
    def _compute_f3d_meter(self):
        for rec in self:
            if rec.td_meter_interval:
                rec.td_meter_next_value = rec.td_meter_last_value + rec.td_meter_interval
            else:
                rec.td_meter_next_value = 0.0

    @api.depends("td_meter_signal_id.last_value", "td_meter_next_value")
    def _compute_f3d_meter_current(self):
        for rec in self:
            rec.td_meter_current = rec.td_meter_signal_id.last_value or 0.0
            rec.td_meter_remaining = rec.td_meter_next_value - rec.td_meter_current

    @api.constrains("td_meter_signal_id", "td_meter_interval")
    def _check_f3d_meter(self):
        for rec in self:
            sig = rec.td_meter_signal_id
            if not sig:
                continue
            if rec.td_meter_interval <= 0:
                raise ValidationError(_("Задайте інтервал ТО за лічильником (> 0)."))
            if sig.equipment_id and sig.equipment_id != rec:
                raise ValidationError(_("Лічильник належить іншому обладнанню."))

    # --- R-11 ----------------------------------------------------------------------------------------
    def _td_default_team(self):
        self.ensure_one()
        if self.maintenance_team_id:
            return self.maintenance_team_id
        param = self.env["ir.config_parameter"].sudo().get_param("td.telemetry.default_team_id") or ""
        return self.env["maintenance.team"].browse(int(param)) if param.isdigit() else self.env["maintenance.team"]

    def _td_meter_rate(self, signal, now):
        """Приріст лічильника за годину за останні 7 діб (з годинних агрегатів); 0 — невідомо."""
        rows = (
            self.env["td.reading.hour"]
            .sudo()
            ._read_group([("signal_id", "=", signal.id), ("hour", ">=", now - timedelta(days=7))], [], ["delta:sum"])
        )
        total = rows[0][0] if rows else 0.0
        return (total or 0.0) / 168.0

    def _td_meter_check(self):
        """R-11: заявка ТО, коли лічильник наблизився до порога `next − lead`."""
        now = fields.Datetime.now()
        Request = self.env["maintenance.request"].sudo()
        for rec in self.sudo():
            sig = rec.td_meter_signal_id
            if not sig or rec.td_meter_interval <= 0 or not sig.last_ts or sig.status == "unknown":
                continue
            if rec.td_meter_request_id and not rec.td_meter_request_id.stage_id.done:
                continue
            current = sig.last_value
            nxt = rec.td_meter_last_value + rec.td_meter_interval
            lead = rec.td_meter_interval * rec.td_meter_lead_pct / 100.0
            if current < nxt - lead:
                continue
            rate = rec._td_meter_rate(sig, now)
            wait_h = max(0.0, (nxt - current) / rate) if rate > 0 else 0.0
            team = rec._td_default_team()
            name = _(
                "ТО за лічильником: %(code)s — %(next)s %(unit)s (зараз %(cur)s)",
                code=rec.td_code or rec.name,
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
                    "td_signal_id": sig.id,
                    "td_origin": "meter",
                    "td_value": current,
                    "td_threshold": nxt,
                }
            )
            rec.with_context(mail_notrack=True).td_meter_request_id = request.id
            rec.message_post(
                body=_("Створено заявку ТО за лічильником: %s", request.name), subtype_xmlid="mail.mt_note"
            )

    def _td_meter_closed(self, request):
        """R-11 п. 5: ТО виконано — зафіксувати показник і дату, перерахувати наступне."""
        today = fields.Datetime.now().replace(tzinfo=ZoneInfo("UTC")).astimezone(KYIV).date()
        for rec in self.sudo():
            sig = rec.td_meter_signal_id
            if not sig:
                continue
            vals = {"td_meter_last_value": sig.last_value, "td_meter_last_date": today}
            if rec.td_meter_request_id == request or not rec.td_meter_request_id:
                vals["td_meter_request_id"] = False
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
            "res_model": "td.signal",
            "view_mode": "list,form,graph,pivot",
            "domain": [("equipment_id", "=", self.id)],
            "context": {"default_equipment_id": self.id, "search_default_active": 1},
        }

    def action_f3d_view_readings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Показання"),
            "res_model": "td.reading",
            "view_mode": "graph,list",
            "domain": [("equipment_id", "=", self.id)],
            "context": {"search_default_last_48h": 1},
        }
