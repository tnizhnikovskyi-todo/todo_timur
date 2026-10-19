import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .td_machine_event import CATEGORIES

_logger = logging.getLogger(__name__)

MESSAGE_RE = re.compile(r"^[A-Z0-9]{1,15}\*?$")


class F3dMachineMessage(models.Model):
    _name = "td.machine.message"
    _description = "Верстати: повідомлення верстата"
    _order = "sequence, message_id"

    message_id = fields.Char(
        string="Код", size=16, required=True, index=True, help="Точний (E0421) або префікс із * у кінці (E04*)"
    )
    name = fields.Char(string="Текст", size=128, required=True)
    category = fields.Selection(CATEGORIES, string="Категорія")
    loss_id = fields.Many2one(
        "mrp.workcenter.productivity.loss",
        string="Причина",
        required=True,
        ondelete="restrict",
        domain="[('loss_type', 'in', ('availability', 'quality'))]",
    )
    auto_apply = fields.Boolean(string="Ставити причиною автоматично", default=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _f3d_message_uniq = models.Constraint("UNIQUE(message_id)", "Код повідомлення повторюється.")

    @api.constrains("message_id")
    def _check_message_id(self):
        for rec in self:
            if not MESSAGE_RE.match(rec.message_id or ""):
                raise ValidationError(_("Код повідомлення: латиниця й цифри, ≤ 15, необов'язкова * у кінці."))

    @api.model
    def _td_match(self, message_id):
        """Точний збіг активного запису, інакше найдовший префікс із `*`; порожньо — запису немає."""
        if not message_id:
            return self.browse()
        exact = self.search([("message_id", "=", message_id)], limit=1)
        if exact:
            return exact
        best = self.browse()
        for rec in self.search([("message_id", "=like", "%*")]):
            prefix = rec.message_id[:-1]
            if message_id.startswith(prefix) and (not best or len(prefix) > len(best.message_id) - 1):
                best = rec
        return best
