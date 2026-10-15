from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import params as P
from ..tools import tz
from .f3d_yard_visit import GRP_DISP, _f3d_yard_require


def _hhmm(hours):
    return "%02d:%02d" % (int(hours), int(round((hours - int(hours)) * 60)))


class F3dYardBooking(models.Model):
    _name = "f3d.yard.booking"
    _description = "Двір: бронювання воріт"
    _inherit = ["mail.thread"]
    _order = "slot_start, dock_id"
    _check_company_auto = True

    name = fields.Char(string="Назва", compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, index=True, default=lambda s: s.env.company
    )
    visit_id = fields.Many2one(
        "f3d.yard.visit", string="Рейс", index=True, ondelete="cascade", check_company=True, tracking=True
    )
    dock_id = fields.Many2one(
        "stock.location",
        string="Ворота",
        required=True,
        index=True,
        check_company=True,
        domain="[('f3d_kind','=','dock')]",
        tracking=True,
        ondelete="restrict",
    )
    dock_code = fields.Char(string="Код воріт", related="dock_id.f3d_code")
    side = fields.Selection(related="dock_id.f3d_side", store=True)
    slot_start = fields.Datetime(string="Початок", required=True, index=True, tracking=True)
    slot_end = fields.Datetime(string="Кінець", required=True, index=True, tracking=True)
    duration_min = fields.Integer(string="Тривалість, хв", compute="_compute_duration_min")
    day = fields.Date(string="День", compute="_compute_day", store=True, index=True)
    source = fields.Selection(
        [
            ("dispatcher", "Диспетчер"),
            ("supplier", "Постачальник"),
            ("walk_in", "Без броні (КПП)"),
            ("migration", "Міграція"),
        ],
        string="Джерело",
        required=True,
        default="dispatcher",
    )
    state = fields.Selection(
        [("requested", "Запит"), ("confirmed", "Підтверджено"), ("cancelled", "Скасовано")],
        string="Стан",
        required=True,
        default="requested",
        index=True,
        tracking=True,
        copy=False,
    )
    batch_id = fields.Many2one(related="visit_id.batch_id")
    partner_id = fields.Many2one(related="visit_id.partner_id")
    plate = fields.Char(related="visit_id.plate")
    visit_type = fields.Selection(related="visit_id.visit_type", store=True)
    visit_state = fields.Selection(related="visit_id.state")
    side_hint = fields.Selection(
        [("west", "Захід"), ("east", "Схід")], string="Сторона рейсу", compute="_compute_side_hint"
    )
    color = fields.Integer(string="Колір", compute="_compute_color", store=True)
    warning = fields.Char(string="Попередження", compute="_compute_warning")
    note = fields.Text(string="Примітка")

    _f3d_yard_booking_slot = models.Constraint(
        "CHECK(slot_end > slot_start)", "Кінець слоту має бути пізніше за початок."
    )

    # ------------------------------------------------------------------ computes
    @api.depends("dock_id.f3d_code", "dock_id.name", "slot_start", "slot_end")
    def _compute_name(self):
        for rec in self:
            if rec.dock_id and rec.slot_start and rec.slot_end:
                start, end = tz.to_local(rec.slot_start), tz.to_local(rec.slot_end)
                rec.name = "%s · %s–%s" % (
                    rec.dock_id.f3d_code or rec.dock_id.name,
                    start.strftime("%d.%m %H:%M"),
                    end.strftime("%H:%M"),
                )
            else:
                rec.name = False

    @api.depends("slot_start", "slot_end")
    def _compute_duration_min(self):
        for rec in self:
            rec.duration_min = (
                int((rec.slot_end - rec.slot_start).total_seconds() // 60) if rec.slot_start and rec.slot_end else 0
            )

    @api.depends("slot_start")
    def _compute_day(self):
        for rec in self:
            rec.day = tz.local_day(rec.slot_start) if rec.slot_start else False

    @api.depends("visit_id.side")
    def _compute_side_hint(self):
        for rec in self:
            rec.side_hint = rec.visit_id.side or False

    @api.depends("visit_id.visit_type", "source")
    def _compute_color(self):
        for rec in self:
            if rec.visit_id.visit_type == "incoming":
                rec.color = 4
            elif rec.visit_id.visit_type == "outgoing":
                rec.color = 2
            elif rec.source == "walk_in":
                rec.color = 3
            else:
                rec.color = 0

    def _f3d_yard_expected_side(self):
        self.ensure_one()
        return "east" if self.visit_id.visit_type == "outgoing" else "west"

    def _f3d_yard_others(self, state):
        self.ensure_one()
        return self.search(
            [
                ("dock_id", "=", self.dock_id.id),
                ("state", "=", state),
                ("id", "not in", (self._origin.id or self.id or 0,)),
            ]
        )

    def _f3d_yard_calendar_issues(self):
        """R-03 п. 6: повідомлення про слот поза зміною (порожній список — усе гаразд)."""
        self.ensure_one()
        calendar_id = P.get_int(self.env, "calendar_id")
        calendar = self.env["resource.calendar"].browse(calendar_id).exists() if calendar_id else None
        if not calendar or not self.slot_start or not self.slot_end:
            return []
        start, end = tz.to_local(self.slot_start), tz.to_local(self.slot_end)
        atts = calendar.attendance_ids.filtered(
            lambda a: a.dayofweek == str(start.weekday()) and not getattr(a, "display_type", False)
        )
        if not atts:
            return ["День без зміни «%s»." % calendar.name]
        low, high = min(atts.mapped("hour_from")), max(atts.mapped("hour_to"))
        start_h = start.hour + start.minute / 60.0
        end_h = end.hour + end.minute / 60.0
        if end.date() != start.date() or start_h < low or end_h > high:
            return ["Слот поза зміною «%s» (%s–%s)." % (calendar.name, _hhmm(low), _hhmm(high))]
        return []

    @api.depends("dock_id", "slot_start", "slot_end", "state", "visit_id.batch_id", "visit_id.visit_type")
    def _compute_warning(self):
        turnaround = P.get_int(self.env, "dock_turnaround_min")
        for rec in self:
            lines = []
            if rec.dock_id and rec.slot_start and rec.slot_end and rec.state != "cancelled":
                for other in rec._f3d_yard_others("requested"):
                    if other.slot_start < rec.slot_end and rec.slot_start < other.slot_end:
                        lines.append("Перетин із запитом %s" % other.name)
                for other in rec._f3d_yard_others("confirmed"):
                    if other.slot_end <= rec.slot_start:
                        gap = (rec.slot_start - other.slot_end).total_seconds() / 60
                    elif other.slot_start >= rec.slot_end:
                        gap = (other.slot_start - rec.slot_end).total_seconds() / 60
                    else:
                        continue
                    if 0 <= gap < turnaround:
                        lines.append("Між слотами %s хв (буфер %s хв): %s" % (int(gap), turnaround, other.name))
                lines += rec._f3d_yard_calendar_issues()
                if rec.visit_id:
                    text = rec.visit_id._f3d_yard_category_warning(rec.dock_id)
                    if text:
                        lines.append(text)
            rec.warning = "\n".join(lines) or False

    # ------------------------------------------------------------------ constraints
    @api.constrains("dock_id", "slot_start", "slot_end", "state")
    def _check_overlap(self):
        for rec in self.filtered(lambda r: r.state == "confirmed"):
            clash = self._f3d_yard_overlaps(rec.dock_id, rec.slot_start, rec.slot_end, exclude_ids=rec.ids)[:1]
            if clash:
                raise ValidationError(
                    "Ворота %s уже заброньовані: %s (%s–%s)."
                    % (
                        rec.dock_id.f3d_code or rec.dock_id.name,
                        clash.name,
                        tz.local_hm(clash.slot_start),
                        tz.local_hm(clash.slot_end),
                    )
                )

    @api.constrains("dock_id", "visit_id")
    def _check_dock_side(self):
        labels = dict(self.env["stock.location"]._fields["f3d_side"].selection)
        for rec in self.filtered("visit_id"):
            expected = rec._f3d_yard_expected_side()
            if rec.dock_id.f3d_side != expected:
                raise ValidationError(
                    "Ворота %s на стороні «%s», а рейс — «%s»."
                    % (
                        rec.dock_id.f3d_code or rec.dock_id.name,
                        labels.get(rec.dock_id.f3d_side, "—"),
                        labels[expected],
                    )
                )
            ptype = rec.visit_id.batch_id.picking_type_id
            if ptype.dock_ids and rec.dock_id not in ptype.dock_ids:
                raise ValidationError(
                    "Ворота %s не належать типу операцій %s."
                    % (rec.dock_id.f3d_code or rec.dock_id.name, ptype.display_name)
                )

    @api.constrains("slot_start", "slot_end")
    def _check_duration(self):
        for rec in self:
            if rec.slot_start and rec.slot_end and rec.slot_end - rec.slot_start > timedelta(hours=24):
                raise ValidationError("Слот довший за 24 год.")

    @api.constrains("dock_id", "slot_start", "slot_end", "state")
    def _check_calendar(self):
        if not P.get_bool(self.env, "enforce_calendar"):
            return
        for rec in self.filtered(lambda r: r.state == "confirmed"):
            issues = rec._f3d_yard_calendar_issues()
            if issues:
                raise ValidationError("\n".join(issues))

    @api.onchange("slot_start")
    def _onchange_slot_start(self):
        if self.slot_start and (not self.slot_end or self.slot_end <= self.slot_start):
            self.slot_end = self.slot_start + timedelta(minutes=P.get_int(self.env, "slot_default_min"))

    # ------------------------------------------------------------------ CRUD
    def write(self, vals):
        res = super().write(vals)
        if {"dock_id", "slot_start", "slot_end"} & set(vals) and not self.env.context.get("f3d_yard_sync"):
            self.filtered(lambda r: r.state == "confirmed")._sync_batch()
        self.visit_id._f3d_yard_notify()
        return res

    # ------------------------------------------------------------------ actions
    def action_confirm(self):
        _f3d_yard_require(self.env, GRP_DISP)
        for rec in self.filtered(lambda r: r.state == "requested"):
            self.env.cr.execute("SELECT id FROM stock_location WHERE id = %s FOR UPDATE", [rec.dock_id.id])
            rec.state = "confirmed"
            rec._sync_batch()
            visit = rec.visit_id.sudo()
            if visit:
                if visit.state == "draft":
                    visit._set_state("planned")
                visit.message_post(body="Заброньовано %s" % rec.name)
        return True

    def action_cancel(self):
        _f3d_yard_require(self.env, GRP_DISP)
        for rec in self.filtered(lambda r: r.state in ("requested", "confirmed")):
            rec.state = "cancelled"
            visit = rec.visit_id.sudo()
            if visit.state == "planned" and not visit.booking_ids.filtered(lambda b: b.state == "confirmed"):
                visit._set_state("draft")
        return True

    def action_reset(self):
        _f3d_yard_require(self.env, GRP_DISP)
        if self.filtered(lambda r: r.state != "cancelled"):
            raise UserError("Повернути в запит можна лише скасоване бронювання.")
        self.state = "requested"
        return True

    def _sync_batch(self):
        """R-02 п. 1: бронювання → пакет (пишуться лише змінені поля)."""
        for rec in self:
            batch = rec.visit_id.batch_id
            if not batch or batch.state in ("done", "cancel"):
                continue
            vals = {}
            if batch.dock_id != rec.dock_id:
                vals["dock_id"] = rec.dock_id.id
            if batch.scheduled_date != rec.slot_start:
                vals["scheduled_date"] = rec.slot_start
            if batch.end_date != rec.slot_end:
                vals["end_date"] = rec.slot_end
            if vals:
                batch.sudo().with_context(f3d_yard_sync=True).write(vals)

    @api.model
    def _f3d_yard_overlaps(self, dock, start, end, exclude_ids=()):
        return self.search(
            [
                ("dock_id", "=", dock.id),
                ("state", "=", "confirmed"),
                ("slot_start", "<", end),
                ("slot_end", ">", start),
                ("id", "not in", list(exclude_ids)),
            ]
        )
