from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import plate as plate_tools

GRP_SEC = "td_yard.group_td_yard_security"


class ResPartner(models.Model):
    _inherit = "res.partner"

    td_is_carrier = fields.Boolean(string="Перевізник", default=False)
    td_is_driver = fields.Boolean(string="Водій", default=False)
    td_carrier_id = fields.Many2one(
        "res.partner", string="Перевізник водія", domain="[('td_is_carrier','=',True)]", ondelete="set null"
    )
    td_driver_doc = fields.Char(string="Документ водія", size=32, groups=GRP_SEC)
    td_default_plate = fields.Char(string="Типовий держномер", size=16)
    td_visit_count = fields.Integer(string="Рейси", compute="_compute_f3d_visit_count")

    @api.constrains("td_default_plate")
    def _check_f3d_default_plate(self):
        for partner in self:
            value = (partner.td_default_plate or "").strip().upper()
            if value and not (
                plate_tools.is_valid_plate_input(value)
                and plate_tools.is_valid_norm(plate_tools.normalize_plate(value))
            ):
                raise ValidationError(
                    "Держномер «%s»: лише літери, цифри, пробіл і дефіс, 2–16 символів." % partner.td_default_plate
                )

    def _f3d_visit_domain(self):
        self.ensure_one()
        return ["|", "|", ("partner_id", "=", self.id), ("carrier_id", "=", self.id), ("driver_id", "=", self.id)]

    def _compute_f3d_visit_count(self):
        Visit = self.env["td.yard.visit"].sudo()
        for partner in self:
            partner.td_visit_count = Visit.search_count(partner._f3d_visit_domain()) if partner.id else 0

    def action_f3d_view_visits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Рейси",
            "res_model": "td.yard.visit",
            "view_mode": "list,form",
            "domain": self._f3d_visit_domain(),
        }
