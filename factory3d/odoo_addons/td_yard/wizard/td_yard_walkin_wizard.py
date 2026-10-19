"""M-16 td.yard.walkin.wizard: рейс без броні (R-06)."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.td_yard_visit import GRP_DISP, GRP_SEC, _td_yard_require
from ..tools import params as P
from ..tools import tz


class F3dYardWalkinWizard(models.TransientModel):
    _name = "td.yard.walkin.wizard"
    _description = "Двір: рейс без бронювання"

    event_id = fields.Many2one("td.yard.lpr.event", readonly=True)
    gate_id = fields.Many2one("td.yard.gate", required=True, default=lambda self: self._default_gate())
    plate = fields.Char(string="Номер", size=16, required=True, default=lambda self: self._default_plate())
    visit_type = fields.Selection(
        lambda self: self.env["td.yard.visit"]._fields["visit_type"].selection,
        string="Тип рейсу",
        required=True,
        default="incoming",
    )
    partner_id = fields.Many2one("res.partner", string="Постачальник / клієнт")
    carrier_id = fields.Many2one("res.partner", string="Перевізник", domain="[('is_company','=',True)]")
    driver_id = fields.Many2one("res.partner", string="Водій")
    driver_phone = fields.Char(size=32, groups=GRP_SEC)
    driver_doc = fields.Char(size=32, groups=GRP_SEC)
    batch_id = fields.Many2one(
        "stock.picking.batch",
        string="Пакет (якщо відомий)",
        domain="[('state','in',('draft','in_progress')),('td_visit_id','=',False),('picking_type_code','=',visit_type)]",
    )
    walk_in_left = fields.Integer(string="Залишок рейсів без броні", compute="_compute_walk_in_left")
    note = fields.Text()

    def _event(self):
        event_id = self.env.context.get("default_event_id")
        return self.env["td.yard.lpr.event"].browse(event_id) if event_id else self.env["td.yard.lpr.event"]

    def _default_gate(self):
        event = self._event()
        if event.gate_id:
            return event.gate_id
        return self.env["td.yard.gate"].search([("direction", "in", ("in", "both"))], limit=1)

    def _default_plate(self):
        event = self._event()
        return (event.plate_unicode or event.plate_raw or "")[:16]

    @api.model
    def _walk_in_today(self):
        start, end = tz.day_bounds_utc(tz.local_day(fields.Datetime.now()))
        return (
            self.env["td.yard.visit"]
            .sudo()
            .search_count(
                [
                    ("is_walk_in", "=", True),
                    ("state", "!=", "rejected"),
                    ("arrived_at", ">=", start),
                    ("arrived_at", "<", end),
                ]
            )
        )

    @api.depends("event_id")
    def _compute_walk_in_left(self):
        left = max(P.get_int(self.env, "walk_in_limit_per_day") - self._walk_in_today(), 0)
        for wiz in self:
            wiz.walk_in_left = left

    def action_create(self):
        self.ensure_one()
        _td_yard_require(self.env, GRP_SEC)
        if not (self.env.su or self.env.user.has_group(GRP_DISP)):
            if not P.get_bool(self.env, "walk_in_allowed"):
                raise UserError("Рейси без броні створює лише диспетчер.")
            limit = P.get_int(self.env, "walk_in_limit_per_day")
            if self._walk_in_today() >= limit:
                raise UserError("Ліміт рейсів без броні на сьогодні (%s) вичерпано — зверніться до диспетчера." % limit)
        event = self.event_id
        ts = (event.ts if event else None) or fields.Datetime.now()
        visit = (
            self.env["td.yard.visit"]
            .sudo()
            .create(
                {
                    "visit_type": self.visit_type,
                    "plate": self.plate,
                    "partner_id": self.partner_id.id,
                    "carrier_id": self.carrier_id.id,
                    "driver_id": self.driver_id.id,
                    "driver_phone": self.driver_phone,
                    "driver_doc": self.driver_doc,
                    "batch_id": self.batch_id.id,
                    "note": self.note,
                    "is_walk_in": True,
                    "gate_in_id": self.gate_id.id,
                }
            )
        )
        visit._set_state("arrived", ts=ts, gate=self.gate_id)
        if event:
            event.write(
                {
                    "visit_id": visit.id,
                    "match_state": "handled",
                    "kpp_alert": False,
                    "handled_by": self.env.uid,
                    "handled_at": fields.Datetime.now(),
                }
            )
        if self.env.context.get("kpp"):
            return {"type": "ir.actions.act_window_close"}
        return {
            "type": "ir.actions.act_window",
            "res_model": "td.yard.visit",
            "res_id": visit.id,
            "view_mode": "form",
            "target": "current",
        }
