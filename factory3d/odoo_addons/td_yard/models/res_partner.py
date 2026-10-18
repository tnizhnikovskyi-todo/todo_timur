from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import plate as plate_tools

GRP_SEC = "factory3d_yard.group_f3d_yard_security"


class ResPartner(models.Model):
    _inherit = "res.partner"

    f3d_is_carrier = fields.Boolean(string="Перевізник", default=False)
    f3d_is_driver = fields.Boolean(string="Водій", default=False)
    f3d_carrier_id = fields.Many2one(
        "res.partner", string="Перевізник водія", domain="[('f3d_is_carrier','=',True)]", ondelete="set null"
    )
    f3d_driver_doc = fields.Char(string="Документ водія", size=32, groups=GRP_SEC)
    f3d_default_plate = fields.Char(string="Типовий держномер", size=16)
    f3d_visit_count = fields.Integer(string="Рейси", compute="_compute_f3d_visit_count")

    @api.constrains("f3d_default_plate")
    def _check_f3d_default_plate(self):
        for partner in self:
            value = (partner.f3d_default_plate or "").strip().upper()
            if value and not (
                plate_tools.is_valid_plate_input(value)
                and plate_tools.is_valid_norm(plate_tools.normalize_plate(value))
            ):
                raise ValidationError(
                    "Держномер «%s»: лише літери, цифри, пробіл і дефіс, 2–16 символів." % partner.f3d_default_plate
                )

    def _f3d_visit_domain(self):
        self.ensure_one()
        return ["|", "|", ("partner_id", "=", self.id), ("carrier_id", "=", self.id), ("driver_id", "=", self.id)]

    def _compute_f3d_visit_count(self):
        Visit = self.env["f3d.yard.visit"].sudo()
        for partner in self:
            partner.f3d_visit_count = Visit.search_count(partner._f3d_visit_domain()) if partner.id else 0

    def action_f3d_view_visits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Рейси",
            "res_model": "f3d.yard.visit",
            "view_mode": "list,form",
            "domain": self._f3d_visit_domain(),
        }
