from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from ..tools import params as P
from .td_yard_visit import FINAL_STATES, GRP_DISP, _f3d_yard_require


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    td_visit_ids = fields.One2many("td.yard.visit", "batch_id", string="Рейси")
    td_visit_id = fields.Many2one(
        "td.yard.visit", string="Активний рейс", compute="_compute_f3d_visit", store=True, index=True
    )
    td_visit_state = fields.Selection(related="td_visit_id.state", string="Стан рейсу")
    td_plate = fields.Char(
        related="td_visit_id.plate",
        string="Держномер (рейс)",
        help="Держномер активного рейсу двору (td.yard.visit.plate). Код фури в 3D — td_code; "
        "td_truck — опис/назва фури з макета, не номер.",
    )
    td_visit_count = fields.Integer(string="Рейсів", compute="_compute_f3d_visit_count")

    @api.depends("td_visit_ids.state")
    def _compute_f3d_visit(self):
        for batch in self:
            visits = batch.td_visit_ids
            active = visits.filtered(lambda v: v.state not in FINAL_STATES)
            if active:
                batch.td_visit_id = max(active, key=lambda v: v.id)
                continue
            left = visits.filtered(lambda v: v.state == "left")
            batch.td_visit_id = max(left, key=lambda v: (v.left_at or fields.Datetime.now(), v.id)) if left else False

    @api.depends("td_visit_ids")
    def _compute_f3d_visit_count(self):
        for batch in self:
            batch.td_visit_count = len(batch.td_visit_ids)

    def _f3d_visit_form_action(self, visit):
        return {
            "type": "ir.actions.act_window",
            "name": "Рейс",
            "res_model": "td.yard.visit",
            "res_id": visit.id,
            "view_mode": "form",
        }

    def action_f3d_create_visit(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_DISP)
        if self.td_visit_id and self.td_visit_id.state not in FINAL_STATES:
            return self._f3d_visit_form_action(self.td_visit_id)
        if self.picking_type_code not in ("incoming", "outgoing"):
            raise UserError("Рейс створюється лише для пакетів приймання або відвантаження.")
        carrier = self.picking_ids.carrier_id[:1]
        visit = self.env["td.yard.visit"].create(
            {
                "visit_type": self.picking_type_code,
                "batch_id": self.id,
                "partner_id": self.picking_ids[:1].partner_id.commercial_partner_id.id or False,
                "delivery_carrier_id": carrier.id or False,
                "carrier_id": carrier.td_partner_id.id or False,
                "company_id": self.company_id.id or self.env.company.id,
            }
        )
        if self.dock_id and self.scheduled_date:
            self.env["td.yard.booking"].create(
                {
                    "visit_id": visit.id,
                    "dock_id": self.dock_id.id,
                    "slot_start": self.scheduled_date,
                    "slot_end": self.end_date
                    or self.scheduled_date + timedelta(minutes=P.get_int(self.env, "slot_default_min")),
                    "company_id": visit.company_id.id,
                }
            )
        return self._f3d_visit_form_action(visit)

    def action_f3d_open_visits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Рейси",
            "res_model": "td.yard.visit",
            "view_mode": "list,form",
            "domain": [("batch_id", "=", self.id)],
        }

    def write(self, vals):
        res = super().write(vals)
        if {"dock_id", "scheduled_date", "end_date"} & set(vals) and not self.env.context.get("f3d_yard_sync"):
            for batch in self:
                booking = batch.td_visit_id.booking_id
                if booking.state == "confirmed" and batch.dock_id and batch.scheduled_date:
                    slot_min = timedelta(minutes=P.get_int(self.env, "slot_default_min"))
                    booking.with_context(f3d_yard_sync=True).sudo().write(
                        {
                            "dock_id": batch.dock_id.id,
                            "slot_start": batch.scheduled_date,
                            "slot_end": batch.end_date or batch.scheduled_date + slot_min,
                        }
                    )
        return res
